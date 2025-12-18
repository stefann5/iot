from simulators.led import LEDSimulator
import threading
import time

def led_callback(state, name):
    t = time.localtime()
    print("="*20)
    print(f"[{name}] Timestamp: {time.strftime('%H:%M:%S', t)}")
    if state:
        print(f"[{name}] Door Light: ON")
    else:
        print(f"[{name}] Door Light: OFF")


def run_led(settings, threads, stop_event, name="DL"):
    if settings['simulated']:
        print(f"Starting {name} (Door Light) simulator")
        led = LEDSimulator(lambda state: led_callback(state, name))
        print(f"{name} (Door Light) simulator started")
        return led
    else:
        from sensors.led import LED
        print(f"Starting {name} (Door Light)")
        led = LED(settings['pin'], lambda state: led_callback(state, name))
        print(f"{name} (Door Light) started")
        return led
