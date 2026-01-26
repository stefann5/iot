from simulators.pir import run_pir_simulator
import threading
import time
from mqtt_publisher import publish_sensor_data


def pir_callback(motion_detected, name, simulated):
    t = time.localtime()
    print("="*20)
    print(f"[{name}] Timestamp: {time.strftime('%H:%M:%S', t)}")
    if motion_detected:
        print(f"[{name}] Motion: DETECTED!")
    else:
        print(f"[{name}] Motion: No motion")

    # Queue data for MQTT publishing with simulated tag
    publish_sensor_data(
        sensor_id=name,
        sensor_type="pir",
        value=1 if motion_detected else 0,
        simulated=simulated,
        unit="motion"
    )


def run_pir(settings, threads, stop_event, name="DPIR1"):
    simulated = settings['simulated']

    if simulated:
        print(f"Starting {name} (PIR Motion Sensor) simulator")
        pir_thread = threading.Thread(target=run_pir_simulator, args=(2, lambda motion: pir_callback(motion, name, True), stop_event))
        pir_thread.start()
        threads.append(pir_thread)
        print(f"{name} (PIR Motion Sensor) simulator started")
    else:
        from sensors.pir import run_pir_loop, PIRSensor
        print(f"Starting {name} (PIR Motion Sensor)")
        pir = PIRSensor(settings['pin'])
        pir_thread = threading.Thread(target=run_pir_loop, args=(pir, 2, lambda motion: pir_callback(motion, name, False), stop_event))
        pir_thread.start()
        threads.append(pir_thread)
        print(f"{name} (PIR Motion Sensor) started")
