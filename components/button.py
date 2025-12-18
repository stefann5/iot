from simulators.button import run_button_simulator
import threading
import time

def button_callback(state, name):
    t = time.localtime()
    print("="*20)
    print(f"[{name}] Timestamp: {time.strftime('%H:%M:%S', t)}")
    if state:
        print(f"[{name}] Door: CLOSED (Button pressed)")
    else:
        print(f"[{name}] Door: OPEN (Button released)")


def run_button(settings, threads, stop_event, name="DS1"):
    if settings['simulated']:
        print(f"Starting {name} (Door Sensor) simulator")
        button_thread = threading.Thread(target=run_button_simulator, args=(lambda state: button_callback(state, name), stop_event))
        button_thread.start()
        threads.append(button_thread)
        print(f"{name} (Door Sensor) simulator started")
    else:
        from sensors.button import run_button_loop, Button
        print(f"Starting {name} (Door Sensor)")
        button = Button(settings['pin'])
        button_thread = threading.Thread(target=run_button_loop, args=(button, lambda state: button_callback(state, name), stop_event))
        button_thread.start()
        threads.append(button_thread)
        print(f"{name} (Door Sensor) started")
