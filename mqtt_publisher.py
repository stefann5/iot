import json
import threading
import time
from collections import deque
import paho.mqtt.client as mqtt


class MQTTPublisher:
    """
    MQTT Publisher with batch sending via daemon thread.
    Thread-safe implementation with minimal mutex-protected sections.
    """

    def __init__(self, broker_host, broker_port, device_info, topics, batch_interval=5):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.device_info = device_info
        self.topics = topics
        self.batch_interval = batch_interval

        # Thread-safe queue for sensor data
        # Using deque with maxlen to prevent unbounded growth
        self._data_queue = deque(maxlen=1000)
        self._queue_lock = threading.Lock()

        # MQTT client
        self.client = mqtt.Client(client_id=f"{device_info['pi_id']}_{device_info['device_name']}")
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self._connected = False

        # Daemon thread control
        self._stop_event = threading.Event()
        self._daemon_thread = None

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"[MQTT] Connected to broker at {self.broker_host}:{self.broker_port}")
            self._connected = True
        else:
            print(f"[MQTT] Connection failed with code {rc}")

    def _on_disconnect(self, client, userdata, rc):
        print(f"[MQTT] Disconnected from broker (rc={rc})")
        self._connected = False

    def connect(self):
        """Connect to the MQTT broker."""
        try:
            self.client.connect(self.broker_host, self.broker_port, keepalive=60)
            self.client.loop_start()
            # Wait briefly for connection
            time.sleep(0.5)
            return True
        except Exception as e:
            print(f"[MQTT] Failed to connect: {e}")
            return False

    def disconnect(self):
        """Disconnect from the MQTT broker."""
        self.client.loop_stop()
        self.client.disconnect()

    def queue_data(self, sensor_id, sensor_type, value, simulated, unit=""):
        """
        Queue sensor data for batch publishing.
        This method is thread-safe and designed to be called from sensor callbacks.

        Args:
            sensor_id: Unique identifier of the sensor (e.g., "DS1", "DUS1")
            sensor_type: Type of sensor (e.g., "button", "ultrasonic")
            value: The measured/simulated value
            simulated: Boolean indicating if the value is simulated
            unit: Optional unit of measurement
        """
        data = {
            "measurement": sensor_type,
            "sensor_id": sensor_id,
            "pi_id": self.device_info["pi_id"],
            "device_name": self.device_info["device_name"],
            "value": value,
            "simulated": simulated,
            "unit": unit,
            "timestamp": time.time()
        }

        # Minimal critical section - just append to queue
        with self._queue_lock:
            self._data_queue.append(data)

    def _publish_batch(self):
        """
        Publish all queued data in batches grouped by sensor type.
        Called periodically by the daemon thread.
        """
        # Quickly extract all data from queue (minimal lock time)
        with self._queue_lock:
            if not self._data_queue:
                return
            batch_data = list(self._data_queue)
            self._data_queue.clear()

        # Group data by sensor type for batch publishing
        grouped_data = {}
        for data in batch_data:
            sensor_type = data["measurement"]
            if sensor_type not in grouped_data:
                grouped_data[sensor_type] = []
            grouped_data[sensor_type].append(data)

        # Publish each batch to its respective topic
        for sensor_type, readings in grouped_data.items():
            topic = self.topics.get(sensor_type, f"pi1/sensors/{sensor_type}")
            payload = {
                "pi_id": self.device_info["pi_id"],
                "device_name": self.device_info["device_name"],
                "batch_timestamp": time.time(),
                "readings": readings
            }

            try:
                result = self.client.publish(topic, json.dumps(payload), qos=1)
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    print(f"[MQTT] Published batch of {len(readings)} {sensor_type} readings to {topic}")
                else:
                    print(f"[MQTT] Failed to publish to {topic}: rc={result.rc}")
            except Exception as e:
                print(f"[MQTT] Error publishing to {topic}: {e}")

    def _daemon_loop(self):
        """
        Daemon thread loop that periodically publishes batched data.
        """
        print(f"[MQTT] Batch publisher daemon started (interval: {self.batch_interval}s)")

        while not self._stop_event.is_set():
            # Wait for the batch interval or stop event
            if self._stop_event.wait(timeout=self.batch_interval):
                break  # Stop event was set

            if self._connected:
                self._publish_batch()

        # Final flush before stopping
        if self._connected:
            self._publish_batch()

        print("[MQTT] Batch publisher daemon stopped")

    def start_batch_daemon(self):
        """Start the batch publishing daemon thread."""
        if self._daemon_thread is not None and self._daemon_thread.is_alive():
            print("[MQTT] Daemon already running")
            return

        self._stop_event.clear()
        self._daemon_thread = threading.Thread(target=self._daemon_loop, daemon=True)
        self._daemon_thread.start()

    def stop_batch_daemon(self):
        """Stop the batch publishing daemon thread."""
        self._stop_event.set()
        if self._daemon_thread is not None:
            self._daemon_thread.join(timeout=self.batch_interval + 1)
            self._daemon_thread = None


# Global publisher instance (initialized in main.py)
_publisher = None


def init_publisher(settings):
    """
    Initialize the global MQTT publisher from settings.

    Args:
        settings: Dictionary containing mqtt and device_info configuration
    """
    global _publisher

    mqtt_config = settings.get('mqtt', {})
    device_info = settings.get('device_info', {
        'pi_id': 'PI1',
        'device_name': 'Unknown'
    })

    _publisher = MQTTPublisher(
        broker_host=mqtt_config.get('broker_host', 'localhost'),
        broker_port=mqtt_config.get('broker_port', 1883),
        device_info=device_info,
        topics=mqtt_config.get('topics', {}),
        batch_interval=mqtt_config.get('batch_interval', 5)
    )

    if _publisher.connect():
        _publisher.start_batch_daemon()
        return _publisher
    else:
        print("[MQTT] Warning: Running without MQTT connection")
        return _publisher


def get_publisher():
    """Get the global MQTT publisher instance."""
    return _publisher


def publish_sensor_data(sensor_id, sensor_type, value, simulated, unit=""):
    """
    Convenience function to queue sensor data for publishing.

    Args:
        sensor_id: Unique identifier of the sensor
        sensor_type: Type of sensor (matches topic configuration)
        value: The measured/simulated value
        simulated: Boolean indicating if the value is simulated
        unit: Optional unit of measurement
    """
    if _publisher is not None:
        _publisher.queue_data(sensor_id, sensor_type, value, simulated, unit)


def shutdown_publisher():
    """Shutdown the global MQTT publisher."""
    global _publisher
    if _publisher is not None:
        _publisher.stop_batch_daemon()
        _publisher.disconnect()
        _publisher = None
