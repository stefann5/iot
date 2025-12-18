from simulators.membrane_switch import run_membrane_switch_simulator
import threading
import time

def membrane_switch_callback(key, name):
    t = time.localtime()
    print("="*20)
    print(f"[{name}] Timestamp: {time.strftime('%H:%M:%S', t)}")
    print(f"[{name}] Key Pressed: {key}")


def run_membrane_switch(settings, threads, stop_event, name="DMS"):
    if settings['simulated']:
        print(f"Starting {name} (Membrane Switch) simulator")
        membrane_thread = threading.Thread(target=run_membrane_switch_simulator, args=(lambda key: membrane_switch_callback(key, name), stop_event))
        membrane_thread.start()
        threads.append(membrane_thread)
        print(f"{name} (Membrane Switch) simulator started")
    else:
        from sensors.membrane_switch import run_membrane_switch_loop, MembraneSwitch
        print(f"Starting {name} (Membrane Switch)")
        row_pins = [settings['R1'], settings['R2'], settings['R3'], settings['R4']]
        col_pins = [settings['C1'], settings['C2'], settings['C3'], settings['C4']]
        membrane = MembraneSwitch(row_pins, col_pins)
        membrane_thread = threading.Thread(target=run_membrane_switch_loop, args=(membrane, lambda key: membrane_switch_callback(key, name), stop_event))
        membrane_thread.start()
        threads.append(membrane_thread)
        print(f"{name} (Membrane Switch) started")
