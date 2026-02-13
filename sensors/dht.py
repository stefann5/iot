import time

try:
    import adafruit_dht
    import board
except ImportError:
    adafruit_dht = None
    board = None


class DHTSensor:
    """
    DHT11/DHT22 Temperature and Humidity sensor driver.
    """

    def __init__(self, pin, dht_type="DHT11"):
        if adafruit_dht is None:
            raise RuntimeError("adafruit_dht library not available")
        board_pin = getattr(board, f"D{pin}")
        if dht_type == "DHT22":
            self.device = adafruit_dht.DHT22(board_pin)
        else:
            self.device = adafruit_dht.DHT11(board_pin)

    def read(self):
        """Returns (temperature_c, humidity_percent) or (None, None) on failure."""
        try:
            temperature = self.device.temperature
            humidity = self.device.humidity
            return temperature, humidity
        except RuntimeError:
            return None, None


def run_dht_loop(dht, delay, callback, stop_event):
    """
    Continuously read DHT sensor and call callback with (temperature, humidity).
    """
    while not stop_event.is_set():
        time.sleep(delay)
        if stop_event.is_set():
            break
        try:
            temp, hum = dht.read()
            if temp is not None and hum is not None:
                callback(round(temp, 1), round(hum, 1))
        except Exception as e:
            print(f"[DHT] Read error: {e}")
