from simulators.button import run_button_simulator
import threading
import time
from mqtt_publisher import publish_sensor_data


def button_callback(state, name, simulated):
    t = time.localtime()
    print("="*20)
    print(f"[{name}] Timestamp: {time.strftime('%H:%M:%S', t)}")
    if state:
        print(f"[{name}] Door: CLOSED (Button pressed)")
    else:
        print(f"[{name}] Door: OPEN (Button released)")

    # Queue data for MQTT publishing with simulated tag
    publish_sensor_data(
        sensor_id=name,
        sensor_type="button",
        value=1 if state else 0,
        simulated=simulated,
        unit="state"
    )


def run_button(settings, threads, stop_event, name="DS1"):
    simulated = settings['simulated']

    if simulated:
        print(f"Starting {name} (Door Sensor) simulator")
        button_thread = threading.Thread(target=run_button_simulator, args=(lambda state: button_callback(state, name, True), stop_event))
        button_thread.start()
        threads.append(button_thread)
        print(f"{name} (Door Sensor) simulator started")
    else:
        from sensors.button import run_button_loop, Button
        print(f"Starting {name} (Door Sensor)")
        button = Button(settings['pin'])
        button_thread = threading.Thread(target=run_button_loop, args=(button, lambda state: button_callback(state, name, False), stop_event))
        button_thread.start()
        threads.append(button_thread)
        print(f"{name} (Door Sensor) started")
