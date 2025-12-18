from simulators.ultrasonic import run_ultrasonic_simulator
import threading
import time

def ultrasonic_callback(distance, name):
    t = time.localtime()
    print("="*20)
    print(f"[{name}] Timestamp: {time.strftime('%H:%M:%S', t)}")
    print(f"[{name}] Distance: {distance:.2f} cm")


def run_ultrasonic(settings, threads, stop_event, name="DUS1"):
    if settings['simulated']:
        print(f"Starting {name} (Ultrasonic Sensor) simulator")
        ultrasonic_thread = threading.Thread(target=run_ultrasonic_simulator, args=(2, lambda dist: ultrasonic_callback(dist, name), stop_event))
        ultrasonic_thread.start()
        threads.append(ultrasonic_thread)
        print(f"{name} (Ultrasonic Sensor) simulator started")
    else:
        from sensors.ultrasonic import run_ultrasonic_loop, UltrasonicSensor
        print(f"Starting {name} (Ultrasonic Sensor)")
        ultrasonic = UltrasonicSensor(settings['trig_pin'], settings['echo_pin'])
        ultrasonic_thread = threading.Thread(target=run_ultrasonic_loop, args=(ultrasonic, 2, lambda dist: ultrasonic_callback(dist, name), stop_event))
        ultrasonic_thread.start()
        threads.append(ultrasonic_thread)
        print(f"{name} (Ultrasonic Sensor) started")
