import time
import random


def run_dht_simulator(delay, callback, stop_event):
    """
    Simulates DHT temperature and humidity sensor.
    Produces realistic temperature (18-28C) and humidity (30-70%) values.
    """
    temperature = random.uniform(20, 24)
    humidity = random.uniform(40, 55)

    while not stop_event.is_set():
        time.sleep(delay)

        if stop_event.is_set():
            break

        # Gradual random walk
        temperature += random.uniform(-0.3, 0.3)
        temperature = max(18, min(28, temperature))

        humidity += random.uniform(-1, 1)
        humidity = max(30, min(70, humidity))

        callback(round(temperature, 1), round(humidity, 1))
