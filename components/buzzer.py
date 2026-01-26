from simulators.buzzer import BuzzerSimulator
import threading
import time
from mqtt_publisher import publish_sensor_data


def buzzer_callback(state, name, simulated):
    t = time.localtime()
    print("="*20)
    print(f"[{name}] Timestamp: {time.strftime('%H:%M:%S', t)}")
    if state:
        print(f"[{name}] Buzzer: ON (BEEPING)")
    else:
        print(f"[{name}] Buzzer: OFF")

    # Queue data for MQTT publishing with simulated tag
    publish_sensor_data(
        sensor_id=name,
        sensor_type="buzzer",
        value=1 if state else 0,
        simulated=simulated,
        unit="state"
    )


def run_buzzer(settings, threads, stop_event, name="DB"):
    simulated = settings['simulated']

    if simulated:
        print(f"Starting {name} (Door Buzzer) simulator")
        buzzer = BuzzerSimulator(lambda state: buzzer_callback(state, name, True))
        print(f"{name} (Door Buzzer) simulator started")
        return buzzer
    else:
        from sensors.buzzer import Buzzer
        print(f"Starting {name} (Door Buzzer)")
        buzzer = Buzzer(settings['pin'], lambda state: buzzer_callback(state, name, False))
        print(f"{name} (Door Buzzer) started")
        return buzzer
