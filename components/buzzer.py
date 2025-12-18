from simulators.buzzer import BuzzerSimulator
import threading
import time

def buzzer_callback(state, name):
    t = time.localtime()
    print("="*20)
    print(f"[{name}] Timestamp: {time.strftime('%H:%M:%S', t)}")
    if state:
        print(f"[{name}] Buzzer: ON (BEEPING)")
    else:
        print(f"[{name}] Buzzer: OFF")


def run_buzzer(settings, threads, stop_event, name="DB"):
    if settings['simulated']:
        print(f"Starting {name} (Door Buzzer) simulator")
        buzzer = BuzzerSimulator(lambda state: buzzer_callback(state, name))
        print(f"{name} (Door Buzzer) simulator started")
        return buzzer
    else:
        from sensors.buzzer import Buzzer
        print(f"Starting {name} (Door Buzzer)")
        buzzer = Buzzer(settings['pin'], lambda state: buzzer_callback(state, name))
        print(f"{name} (Door Buzzer) started")
        return buzzer
