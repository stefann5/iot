from simulators.led import LEDSimulator
import threading
import time
from mqtt_publisher import publish_sensor_data


def led_callback(state, name, simulated):
    t = time.localtime()
    print("="*20)
    print(f"[{name}] Timestamp: {time.strftime('%H:%M:%S', t)}")
    if state:
        print(f"[{name}] Door Light: ON")
    else:
        print(f"[{name}] Door Light: OFF")

    # Queue data for MQTT publishing with simulated tag
    publish_sensor_data(
        sensor_id=name,
        sensor_type="led",
        value=1 if state else 0,
        simulated=simulated,
        unit="state"
    )


def run_led(settings, threads, stop_event, name="DL"):
    simulated = settings['simulated']

    if simulated:
        print(f"Starting {name} (Door Light) simulator")
        led = LEDSimulator(lambda state: led_callback(state, name, True))
        print(f"{name} (Door Light) simulator started")
        return led
    else:
        from sensors.led import LED
        print(f"Starting {name} (Door Light)")
        led = LED(settings['pin'], lambda state: led_callback(state, name, False))
        print(f"{name} (Door Light) started")
        return led
