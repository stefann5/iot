from simulators.membrane_switch import run_membrane_switch_simulator
import threading
import time
from mqtt_publisher import publish_sensor_data


def membrane_switch_callback(key, name, simulated):
    t = time.localtime()
    print("="*20)
    print(f"[{name}] Timestamp: {time.strftime('%H:%M:%S', t)}")
    print(f"[{name}] Key Pressed: {key}")

    # Queue data for MQTT publishing with simulated tag
    publish_sensor_data(
        sensor_id=name,
        sensor_type="membrane_switch",
        value=key,
        simulated=simulated,
        unit="key"
    )


def run_membrane_switch(settings, threads, stop_event, name="DMS"):
    simulated = settings['simulated']

    if simulated:
        print(f"Starting {name} (Membrane Switch) simulator")
        membrane_thread = threading.Thread(target=run_membrane_switch_simulator, args=(lambda key: membrane_switch_callback(key, name, True), stop_event))
        membrane_thread.start()
        threads.append(membrane_thread)
        print(f"{name} (Membrane Switch) simulator started")
    else:
        from sensors.membrane_switch import run_membrane_switch_loop, MembraneSwitch
        print(f"Starting {name} (Membrane Switch)")
        row_pins = [settings['R1'], settings['R2'], settings['R3'], settings['R4']]
        col_pins = [settings['C1'], settings['C2'], settings['C3'], settings['C4']]
        membrane = MembraneSwitch(row_pins, col_pins)
        membrane_thread = threading.Thread(target=run_membrane_switch_loop, args=(membrane, lambda key: membrane_switch_callback(key, name, False), stop_event))
        membrane_thread.start()
        threads.append(membrane_thread)
        print(f"{name} (Membrane Switch) started")
