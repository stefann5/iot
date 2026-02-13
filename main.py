import threading
import time
import json
from collections import deque
from settings import load_settings
from mqtt_publisher import init_publisher, shutdown_publisher, publish_sensor_data
import paho.mqtt.client as mqtt

try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
except:
    pass


# ==================== ALARM SYSTEM ====================
class AlarmSystem:
    DISARMED = "DISARMED"
    ARMED = "ARMED"
    ALARM = "ALARM"

    def __init__(self, pin="1234"):
        self.state = self.DISARMED
        self.pin = pin
        self.pin_buffer = ""
        self.lock = threading.Lock()

    def arm(self):
        with self.lock:
            if self.state == self.DISARMED:
                self.state = self.ARMED
                print(f"[ALARM] System ARMED")
                return True
            return False

    def trigger_alarm(self):
        with self.lock:
            if self.state == self.ARMED:
                self.state = self.ALARM
                print(f"[ALARM] *** ALARM TRIGGERED ***")
                return True
            return False

    def deactivate(self, pin):
        with self.lock:
            if pin == self.pin and self.state in (self.ARMED, self.ALARM):
                prev = self.state
                self.state = self.DISARMED
                self.pin_buffer = ""
                print(f"[ALARM] System DISARMED (was {prev})")
                return True
            if pin != self.pin:
                print(f"[ALARM] Wrong PIN entered")
            self.pin_buffer = ""
            return False

    def process_key(self, key):
        """Process membrane switch key press. Returns (action, success)."""
        if key == '#':
            pin = self.pin_buffer
            self.pin_buffer = ""
            if self.deactivate(pin):
                return "deactivated", True
            return "wrong_pin", False
        elif key == '*':
            self.pin_buffer = ""
            print("[ALARM] PIN buffer cleared")
            return "cleared", False
        elif key == 'A':
            self.pin_buffer = ""
            if self.arm():
                return "armed", True
            return "already_armed", False
        else:
            self.pin_buffer += key
            print(f"[ALARM] PIN buffer: {'*' * len(self.pin_buffer)}")
            return "key_added", False


# ==================== PEOPLE COUNTER ====================
class PeopleCounter:
    def __init__(self):
        self.count = 0
        self.lock = threading.Lock()
        self.distance_buffer = deque(maxlen=50)
        self.last_detection_time = 0

    def add_distance(self, distance, timestamp):
        self.distance_buffer.append((distance, timestamp))

    def detect_direction(self):
        """Analyze ultrasonic distance trend to determine enter/exit."""
        if len(self.distance_buffer) < 5:
            return None

        now = time.time()
        if now - self.last_detection_time < 3:
            return None

        recent = [(d, t) for d, t in self.distance_buffer if now - t < 5]
        if len(recent) < 4:
            return None

        mid = len(recent) // 2
        first_half_avg = sum(d for d, _ in recent[:mid]) / mid
        second_half_avg = sum(d for d, _ in recent[mid:]) / (len(recent) - mid)

        diff = second_half_avg - first_half_avg

        if diff < -10:
            self.last_detection_time = now
            return "ENTERING"
        elif diff > 10:
            self.last_detection_time = now
            return "EXITING"
        return None

    def person_entered(self):
        with self.lock:
            self.count += 1
            return self.count

    def person_exited(self):
        with self.lock:
            self.count = max(0, self.count - 1)
            return self.count

    def get_count(self):
        with self.lock:
            return self.count


# ==================== MAIN APPLICATION ====================
def main():
    settings = load_settings()
    device_info = settings.get('device_info', {})
    mqtt_config = settings.get('mqtt', {})
    alarm_pin = settings.get('alarm_pin', '1234')

    print("=" * 50)
    print(f"PI1 Smart Home - {device_info.get('device_name', 'DoorController')}")
    print(f"Location: {device_info.get('location', 'front_door')}")
    print("=" * 50)

    # Initialize core systems
    alarm = AlarmSystem(pin=alarm_pin)
    people = PeopleCounter()

    threads = []
    stop_event = threading.Event()

    # Initialize MQTT Publisher
    print("\nInitializing MQTT Publisher...")
    publisher = init_publisher(settings)

    # ---- Actuator references ----
    led = None
    buzzer = None
    led_timer = None
    led_timer_lock = threading.Lock()

    # ---- Helper functions ----
    def turn_on_led_timed(seconds):
        nonlocal led_timer
        if led is None:
            return
        with led_timer_lock:
            if led_timer is not None:
                led_timer.cancel()
            led.turn_on()
            led_timer = threading.Timer(seconds, lambda: led.turn_off())
            led_timer.daemon = True
            led_timer.start()

    def activate_alarm_hardware():
        if buzzer:
            buzzer.turn_on()
        if led:
            led.turn_on()
        publish_sensor_data("ALARM", "alarm", 1, True, "state")
        publish_sensor_data("ALARM", "alarm_event", "alarm_activated", True, "event")
        print("[ALARM] Hardware activated: Buzzer ON, LED ON")

    def deactivate_alarm_hardware():
        if buzzer:
            buzzer.turn_off()
        if led:
            led.turn_off()
        alarm.state = AlarmSystem.DISARMED
        publish_sensor_data("ALARM", "alarm", 0, True, "state")
        publish_sensor_data("ALARM", "alarm_event", "alarm_deactivated", True, "event")
        print("[ALARM] Hardware deactivated: Buzzer OFF, LED OFF")

    def publish_people_event(direction, count):
        publish_sensor_data("PEOPLE", "people_count", count, True, "count")
        publish_sensor_data("PEOPLE", "people_event", direction, True, "direction")
        print(f"[PEOPLE] {direction} - Count: {count}")

    def publish_alarm_state():
        publish_sensor_data("ALARM", "alarm",
                          1 if alarm.state == AlarmSystem.ALARM else 0,
                          True, "state")

    # ---- LED Initialization ----
    dl_settings = settings.get('DL', {})
    if dl_settings:
        dl_simulated = dl_settings.get('simulated', True)
        def on_led_change(state):
            publish_sensor_data("DL", "led", 1 if state else 0, dl_simulated, "state")

        if dl_simulated:
            from simulators.led import LEDSimulator
            led = LEDSimulator(callback=on_led_change)
            print("[DL] Door Light simulator initialized")
        else:
            from sensors.led import LED
            led = LED(dl_settings['pin'], callback=on_led_change)
            print("[DL] Door Light initialized")

    # ---- Buzzer Initialization ----
    db_settings = settings.get('DB', {})
    if db_settings:
        db_simulated = db_settings.get('simulated', True)
        def on_buzzer_change(state):
            publish_sensor_data("DB", "buzzer", 1 if state else 0, db_simulated, "state")

        if db_simulated:
            from simulators.buzzer import BuzzerSimulator
            buzzer = BuzzerSimulator(callback=on_buzzer_change)
            print("[DB] Door Buzzer simulator initialized")
        else:
            from sensors.buzzer import Buzzer
            buzzer = Buzzer(db_settings['pin'], callback=on_buzzer_change)
            print("[DB] Door Buzzer initialized")

    # ---- Ultrasonic Sensor (DUS1) ----
    dus1_settings = settings.get('DUS1', {})
    if dus1_settings:
        dus1_simulated = dus1_settings.get('simulated', True)
        def on_ultrasonic(distance):
            publish_sensor_data("DUS1", "ultrasonic", round(distance, 2), dus1_simulated, "cm")
            people.add_distance(distance, time.time())

        if dus1_simulated:
            from simulators.ultrasonic import run_ultrasonic_simulator
            t = threading.Thread(target=run_ultrasonic_simulator,
                               args=(0.5, on_ultrasonic, stop_event), daemon=True)
            t.start()
            threads.append(t)
            print("[DUS1] Ultrasonic Sensor simulator started")
        else:
            from sensors.ultrasonic import run_ultrasonic_loop, UltrasonicSensor
            us = UltrasonicSensor(dus1_settings['trig_pin'], dus1_settings['echo_pin'])
            t = threading.Thread(target=run_ultrasonic_loop,
                               args=(us, 0.5, on_ultrasonic, stop_event), daemon=True)
            t.start()
            threads.append(t)
            print("[DUS1] Ultrasonic Sensor started")

    # ---- PIR Motion Sensor (DPIR1) ----
    dpir1_settings = settings.get('DPIR1', {})
    if dpir1_settings:
        dpir1_simulated = dpir1_settings.get('simulated', True)
        last_pir_motion = [False]

        def on_pir(motion_detected):
            if motion_detected == last_pir_motion[0]:
                return
            last_pir_motion[0] = motion_detected

            publish_sensor_data("DPIR1", "pir", 1 if motion_detected else 0, dpir1_simulated, "motion")

            if motion_detected:
                print("[DPIR1] Motion DETECTED!")

                # 1. Turn on DL for 10 seconds
                turn_on_led_timed(10)

                # 2. Detect enter/exit using ultrasonic data
                direction = people.detect_direction()
                if direction == "ENTERING":
                    count = people.person_entered()
                    publish_people_event("ENTERING", count)
                elif direction == "EXITING":
                    count = people.person_exited()
                    publish_people_event("EXITING", count)

                # 3. Check alarm - trigger if system is armed
                if alarm.state == AlarmSystem.ARMED:
                    if alarm.trigger_alarm():
                        activate_alarm_hardware()

        if dpir1_simulated:
            from simulators.pir import run_pir_simulator
            t = threading.Thread(target=run_pir_simulator,
                               args=(2, on_pir, stop_event), daemon=True)
            t.start()
            threads.append(t)
            print("[DPIR1] PIR Motion Sensor simulator started")
        else:
            from sensors.pir import run_pir_loop, PIRSensor
            pir = PIRSensor(dpir1_settings['pin'])
            t = threading.Thread(target=run_pir_loop,
                               args=(pir, 0.5, on_pir, stop_event), daemon=True)
            t.start()
            threads.append(t)
            print("[DPIR1] PIR Motion Sensor started")

    # ---- Door Sensor / Button (DS1) ----
    ds1_settings = settings.get('DS1', {})
    if ds1_settings:
        ds1_simulated = ds1_settings.get('simulated', True)

        def on_button(state):
            publish_sensor_data("DS1", "button", 1 if state else 0, ds1_simulated, "state")
            if state:
                print("[DS1] Door: CLOSED")
            else:
                print("[DS1] Door: OPEN")
                # Door opened while alarm is armed -> trigger alarm
                if alarm.state == AlarmSystem.ARMED:
                    if alarm.trigger_alarm():
                        activate_alarm_hardware()

        if ds1_simulated:
            from simulators.button import run_button_simulator
            t = threading.Thread(target=run_button_simulator,
                               args=(on_button, stop_event), daemon=True)
            t.start()
            threads.append(t)
            print("[DS1] Door Sensor simulator started")
        else:
            from sensors.button import run_button_loop, Button
            btn = Button(ds1_settings['pin'])
            t = threading.Thread(target=run_button_loop,
                               args=(btn, on_button, stop_event), daemon=True)
            t.start()
            threads.append(t)
            print("[DS1] Door Sensor started")

    # ---- Membrane Switch (DMS) ----
    dms_settings = settings.get('DMS', {})
    if dms_settings:
        dms_simulated = dms_settings.get('simulated', True)

        def on_membrane_key(key):
            publish_sensor_data("DMS", "membrane_switch", key, dms_simulated, "key")
            print(f"[DMS] Key pressed: {key}")

            action, success = alarm.process_key(key)
            if action == "armed":
                publish_alarm_state()
                publish_sensor_data("ALARM", "alarm_event", "armed", True, "event")
            elif action == "deactivated":
                deactivate_alarm_hardware()

        if dms_simulated:
            from simulators.membrane_switch import run_membrane_switch_simulator
            t = threading.Thread(target=run_membrane_switch_simulator,
                               args=(on_membrane_key, stop_event), daemon=True)
            t.start()
            threads.append(t)
            print("[DMS] Membrane Switch simulator started")
        else:
            from sensors.membrane_switch import run_membrane_switch_loop, MembraneSwitch
            row_pins = [dms_settings['R1'], dms_settings['R2'],
                       dms_settings['R3'], dms_settings['R4']]
            col_pins = [dms_settings['C1'], dms_settings['C2'],
                       dms_settings['C3'], dms_settings['C4']]
            ms = MembraneSwitch(row_pins, col_pins)
            t = threading.Thread(target=run_membrane_switch_loop,
                               args=(ms, on_membrane_key, stop_event), daemon=True)
            t.start()
            threads.append(t)
            print("[DMS] Membrane Switch started")

    # ---- MQTT Command Subscriber (for web app commands) ----
    command_client = mqtt.Client(client_id="pi1_command_listener")

    def on_command_connect(client, userdata, flags, rc):
        if rc == 0:
            client.subscribe("pi1/commands/#")
            print("[MQTT-CMD] Subscribed to pi1/commands/#")

    def on_command_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            topic = msg.topic

            if topic == "pi1/commands/alarm":
                action = payload.get("action")
                if action == "arm":
                    if alarm.arm():
                        publish_alarm_state()
                        publish_sensor_data("ALARM", "alarm_event", "armed", True, "event")
                elif action == "deactivate":
                    pin = payload.get("pin", "")
                    if alarm.deactivate(pin):
                        deactivate_alarm_hardware()
                    else:
                        publish_sensor_data("ALARM", "alarm_event", "wrong_pin", True, "event")

            elif topic == "pi1/commands/led":
                action = payload.get("action")
                if action == "on" and led:
                    led.turn_on()
                elif action == "off" and led:
                    led.turn_off()

            elif topic == "pi1/commands/buzzer":
                action = payload.get("action")
                if action == "on" and buzzer:
                    buzzer.turn_on()
                elif action == "off" and buzzer:
                    buzzer.turn_off()
                elif action == "beep" and buzzer:
                    buzzer.beep()

        except Exception as e:
            print(f"[MQTT-CMD] Error processing command: {e}")

    command_client.on_connect = on_command_connect
    command_client.on_message = on_command_message

    try:
        broker_host = mqtt_config.get('broker_host', 'localhost')
        broker_port = mqtt_config.get('broker_port', 1883)
        command_client.connect(broker_host, broker_port, keepalive=60)
        command_client.loop_start()
        print(f"[MQTT-CMD] Connected to {broker_host}:{broker_port}")
    except Exception as e:
        print(f"[MQTT-CMD] Failed to connect: {e}")

    # ---- Periodic state publisher ----
    def state_publisher():
        """Periodically publish system state for the web app."""
        while not stop_event.is_set():
            publish_alarm_state()
            publish_sensor_data("PEOPLE", "people_count", people.get_count(), True, "count")
            time.sleep(10)

    state_thread = threading.Thread(target=state_publisher, daemon=True)
    state_thread.start()
    threads.append(state_thread)

    # ---- Console Interface ----
    time.sleep(1)
    print("\n" + "=" * 50)
    print("System ready. Commands:")
    print("  arm        - Arm alarm system")
    print("  disarm     - Disarm (enter PIN when prompted)")
    print("  led on/off - Control door light")
    print("  buzz on/off/beep - Control buzzer")
    print("  status     - Show system status")
    print("  exit       - Exit application")
    print("=" * 50)

    try:
        while True:
            try:
                cmd = input("\n> ").strip().lower()
                if cmd == "exit":
                    break
                elif cmd == "arm":
                    if alarm.arm():
                        publish_alarm_state()
                        publish_sensor_data("ALARM", "alarm_event", "armed", True, "event")
                    else:
                        print(f"Cannot arm: currently {alarm.state}")
                elif cmd == "disarm":
                    pin = input("Enter PIN: ").strip()
                    if alarm.deactivate(pin):
                        deactivate_alarm_hardware()
                    else:
                        print("Wrong PIN or system not armed/alarmed")
                elif cmd == "led on" and led:
                    led.turn_on()
                elif cmd == "led off" and led:
                    led.turn_off()
                elif cmd == "buzz on" and buzzer:
                    buzzer.turn_on()
                elif cmd == "buzz off" and buzzer:
                    buzzer.turn_off()
                elif cmd == "buzz beep" and buzzer:
                    buzzer.beep()
                elif cmd == "status":
                    print(f"\n  Alarm: {alarm.state}")
                    print(f"  People inside: {people.get_count()}")
                    print(f"  LED: {'ON' if led and led.get_state() else 'OFF'}")
                    print(f"  Buzzer: {'ON' if buzzer and buzzer.get_state() else 'OFF'}")
                elif cmd == "menu":
                    print("Commands: arm, disarm, led on/off, buzz on/off/beep, status, exit")
                else:
                    print("Unknown command. Type 'menu' for help.")
            except EOFError:
                break
    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        print("\nShutting down...")
        stop_event.set()

        if buzzer:
            buzzer.turn_off()
        if led:
            led.turn_off()

        command_client.loop_stop()
        command_client.disconnect()
        shutdown_publisher()

        for t in threads:
            t.join(timeout=2)

        try:
            GPIO.cleanup()
        except:
            pass
        print("Application stopped.")


if __name__ == "__main__":
    main()
