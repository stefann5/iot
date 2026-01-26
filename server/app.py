import json
import threading
from datetime import datetime
from flask import Flask, jsonify
import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from config import (
    MQTT_BROKER, MQTT_PORT,
    INFLUXDB_URL, INFLUXDB_TOKEN, INFLUXDB_ORG, INFLUXDB_BUCKET,
    FLASK_HOST, FLASK_PORT, FLASK_DEBUG
)

app = Flask(__name__)

# MQTT Topics to subscribe
MQTT_TOPICS = [
    ("pi1/sensors/#", 0),
    ("pi1/actuators/#", 0)
]

# InfluxDB client
influx_client = None
write_api = None


def init_influxdb():
    """Initialize InfluxDB client and create bucket if needed."""
    global influx_client, write_api

    try:
        influx_client = InfluxDBClient(
            url=INFLUXDB_URL,
            token=INFLUXDB_TOKEN,
            org=INFLUXDB_ORG
        )
        write_api = influx_client.write_api(write_options=SYNCHRONOUS)
        print(f"[InfluxDB] Connected to {INFLUXDB_URL}")
        return True
    except Exception as e:
        print(f"[InfluxDB] Failed to connect: {e}")
        return False


def write_to_influxdb(measurement, tags, fields, timestamp=None):
    """
    Write a data point to InfluxDB.

    Args:
        measurement: The measurement name (e.g., "ultrasonic", "pir")
        tags: Dictionary of tags (e.g., {"sensor_id": "DUS1", "simulated": "true"})
        fields: Dictionary of field values (e.g., {"value": 45.5})
        timestamp: Optional timestamp (uses current time if not provided)
    """
    if write_api is None:
        print("[InfluxDB] Write API not initialized")
        return False

    try:
        point = Point(measurement)

        for tag_key, tag_value in tags.items():
            point = point.tag(tag_key, str(tag_value))

        for field_key, field_value in fields.items():
            point = point.field(field_key, field_value)

        if timestamp:
            point = point.time(datetime.fromtimestamp(timestamp))

        write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=point)
        return True
    except Exception as e:
        print(f"[InfluxDB] Error writing data: {e}")
        return False


def process_mqtt_message(topic, payload):
    """
    Process an MQTT message and store it in InfluxDB.

    Args:
        topic: MQTT topic string
        payload: JSON payload from MQTT message
    """
    try:
        data = json.loads(payload)

        # Extract batch information
        pi_id = data.get("pi_id", "unknown")
        device_name = data.get("device_name", "unknown")
        readings = data.get("readings", [])

        # Determine measurement type from topic
        topic_parts = topic.split("/")
        measurement_type = topic_parts[-1] if len(topic_parts) > 2 else "unknown"

        print(f"[MQTT] Received {len(readings)} {measurement_type} readings from {pi_id}")

        for reading in readings:
            sensor_id = reading.get("sensor_id", "unknown")
            value = reading.get("value")
            simulated = reading.get("simulated", False)
            unit = reading.get("unit", "")
            timestamp = reading.get("timestamp")

            # Prepare tags
            tags = {
                "pi_id": pi_id,
                "device_name": device_name,
                "sensor_id": sensor_id,
                "simulated": str(simulated).lower(),
                "unit": unit
            }

            # Prepare fields based on value type
            if isinstance(value, (int, float)):
                fields = {"value": float(value)}
            else:
                # For string values (like membrane switch keys)
                fields = {"value_str": str(value), "value": 1.0}

            # Write to InfluxDB
            write_to_influxdb(measurement_type, tags, fields, timestamp)

        print(f"[InfluxDB] Stored {len(readings)} {measurement_type} readings")

    except json.JSONDecodeError as e:
        print(f"[MQTT] Invalid JSON payload: {e}")
    except Exception as e:
        print(f"[MQTT] Error processing message: {e}")


# MQTT callbacks
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[MQTT] Connected to broker at {MQTT_BROKER}:{MQTT_PORT}")
        # Subscribe to all topics
        client.subscribe(MQTT_TOPICS)
        print(f"[MQTT] Subscribed to topics: {[t[0] for t in MQTT_TOPICS]}")
    else:
        print(f"[MQTT] Connection failed with code {rc}")


def on_disconnect(client, userdata, rc):
    print(f"[MQTT] Disconnected from broker (rc={rc})")


def on_message(client, userdata, msg):
    """Handle incoming MQTT messages."""
    process_mqtt_message(msg.topic, msg.payload.decode('utf-8'))


# Initialize MQTT client
mqtt_client = mqtt.Client(client_id="pi1_server")
mqtt_client.on_connect = on_connect
mqtt_client.on_disconnect = on_disconnect
mqtt_client.on_message = on_message


def start_mqtt_client():
    """Start the MQTT client in a background thread."""
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        mqtt_client.loop_start()
        return True
    except Exception as e:
        print(f"[MQTT] Failed to connect: {e}")
        return False


# Flask routes
@app.route('/')
def index():
    return jsonify({
        "service": "PI1 Data Server",
        "status": "running",
        "endpoints": {
            "/": "This help message",
            "/health": "Health check endpoint",
            "/status": "Service status"
        }
    })


@app.route('/health')
def health():
    mqtt_connected = mqtt_client.is_connected()
    influx_connected = influx_client is not None

    status = "healthy" if mqtt_connected and influx_connected else "degraded"

    return jsonify({
        "status": status,
        "mqtt": "connected" if mqtt_connected else "disconnected",
        "influxdb": "connected" if influx_connected else "disconnected"
    })


@app.route('/status')
def status():
    return jsonify({
        "mqtt": {
            "broker": MQTT_BROKER,
            "port": MQTT_PORT,
            "topics": [t[0] for t in MQTT_TOPICS],
            "connected": mqtt_client.is_connected()
        },
        "influxdb": {
            "url": INFLUXDB_URL,
            "org": INFLUXDB_ORG,
            "bucket": INFLUXDB_BUCKET,
            "connected": influx_client is not None
        }
    })


def initialize_services():
    """Initialize all external services."""
    print("=" * 50)
    print("PI1 Data Server - Starting")
    print("=" * 50)

    # Initialize InfluxDB
    print("\nInitializing InfluxDB connection...")
    init_influxdb()

    # Start MQTT client
    print("\nStarting MQTT client...")
    start_mqtt_client()

    print("\n" + "=" * 50)
    print("Server ready to receive data")
    print("=" * 50)


if __name__ == '__main__':
    initialize_services()
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
