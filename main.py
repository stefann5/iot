import threading
import time
import json
import math
from collections import deque
from settings import load_settings
from mqtt_publisher import init_publisher, shutdown_publisher, publish_sensor_data
import paho.mqtt.client as mqtt

try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
except:
    pass


# ==================== KITCHEN TIMER (Feature 8) ====================
class KitchenTimer:
    """Kitchen countdown timer displayed on 4SD, controllable via web and BTN."""

    def __init__(self):
        self.remaining_seconds = 0
        self.running = False
        self.blinking = False
        self.lock = threading.Lock()
        self.btn_add_seconds = 10  # N seconds added per BTN press (configurable via web)
        self._timer_thread = None
        self._stop_event = threading.Event()
        self._on_tick_callback = None
        self._on_finished_callback = None
        self._on_blink_stopped_callback = None

    def set_time(self, seconds):
        """Set timer duration (from web app)."""
        with self.lock:
            self.remaining_seconds = max(0, seconds)
            self.blinking = False
            print(f"[TIMER] Time set to {self.remaining_seconds}s ({self._format_time()})")
            if self._on_tick_callback:
                self._on_tick_callback(self.remaining_seconds, self._format_time(), self.blinking)

    def start(self):
        """Start the countdown."""
        with self.lock:
            if self.remaining_seconds <= 0:
                return False
            if self.running:
                return False
            self.running = True
            self.blinking = False
            self._stop_event.clear()

        self._timer_thread = threading.Thread(target=self._countdown, daemon=True)
        self._timer_thread.start()
        print(f"[TIMER] Started: {self._format_time()}")
        return True

    def stop(self):
        """Stop the countdown."""
        with self.lock:
            self.running = False
            self._stop_event.set()
            print("[TIMER] Stopped")

    def add_seconds(self, n=None):
        """Add N seconds to timer (BTN press). If blinking, stop blink instead."""
        with self.lock:
            if self.blinking:
                self.blinking = False
                self.running = False
                print("[TIMER] Blinking stopped by BTN press")
                if self._on_blink_stopped_callback:
                    self._on_blink_stopped_callback()
                if self._on_tick_callback:
                    self._on_tick_callback(0, "00:00", False)
                return
            seconds = n if n is not None else self.btn_add_seconds
            self.remaining_seconds += seconds
            print(f"[TIMER] Added {seconds}s -> {self._format_time()}")
            if self._on_tick_callback:
                self._on_tick_callback(self.remaining_seconds, self._format_time(), self.blinking)

    def set_btn_seconds(self, n):
        """Configure how many seconds BTN adds (from web app)."""
        with self.lock:
            self.btn_add_seconds = max(1, n)
            print(f"[TIMER] BTN add seconds set to {self.btn_add_seconds}")

    def get_state(self):
        """Return current timer state."""
        with self.lock:
            return {
                "remaining": self.remaining_seconds,
                "display": self._format_time(),
                "running": self.running,
                "blinking": self.blinking,
                "btn_seconds": self.btn_add_seconds,
            }

    def _format_time(self):
        """Format remaining seconds as MM:SS."""
        mins = self.remaining_seconds // 60
        secs = self.remaining_seconds % 60
        return f"{mins:02d}:{secs:02d}"

    def _countdown(self):
        """Countdown thread loop."""
        while not self._stop_event.is_set():
            time.sleep(1)
            if self._stop_event.is_set():
                break

            with self.lock:
                if not self.running:
                    break
                self.remaining_seconds = max(0, self.remaining_seconds - 1)
                display = self._format_time()
                remaining = self.remaining_seconds

                if self._on_tick_callback:
                    self._on_tick_callback(remaining, display, self.blinking)

                if remaining <= 0:
                    self.running = False
                    self.blinking = True
                    print("[TIMER] TIME'S UP! 4SD blinking 00:00")
                    if self._on_finished_callback:
                        self._on_finished_callback()
                    if self._on_tick_callback:
                        self._on_tick_callback(0, "00:00", True)
                    break


# ==================== ALARM SYSTEM ====================
class AlarmSystem:
    DISARMED = "DISARMED"
    ARMED = "ARMED"
    ALARM = "ALARM"
    ARMING = "ARMING"  # 10-second arming delay

    def __init__(self, pin="1234"):
        self.state = self.DISARMED
        self.pin = pin
        self.pin_buffer = ""
        self.lock = threading.Lock()
        self.alarm_reason = ""
        self._arming_timer = None
        self._door_open_timers = {}  # DS sensor -> timer for feature 3
        self._ds_grace_timers = {}   # DS sensor -> grace timer for feature 4
        self._on_armed_callback = None
        self._on_alarm_callback = None
        self._on_deactivated_callback = None
        self._on_arming_callback = None

    def arm(self, delayed=False):
        """Arm the system. If delayed=True, arm after 10 seconds (feature 4)."""
        with self.lock:
            if self.state != self.DISARMED:
                return False
            if delayed:
                self.state = self.ARMING
                print(f"[ALARM] System ARMING in 10 seconds...")
                if self._on_arming_callback:
                    self._on_arming_callback()
                self._arming_timer = threading.Timer(10, self._complete_arming)
                self._arming_timer.daemon = True
                self._arming_timer.start()
                return True
            else:
                self.state = self.ARMED
                print(f"[ALARM] System ARMED")
                if self._on_armed_callback:
                    self._on_armed_callback()
                return True

    def _complete_arming(self):
        with self.lock:
            if self.state == self.ARMING:
                self.state = self.ARMED
                print(f"[ALARM] System ARMED (after delay)")
                if self._on_armed_callback:
                    self._on_armed_callback()

    def trigger_alarm(self, reason=""):
        """Trigger alarm. Works from ARMED state, or directly for door-open-5s (feature 3)."""
        with self.lock:
            if self.state == self.ALARM:
                return False  # Already in alarm
            if self.state in (self.ARMED, self.DISARMED):
                self.state = self.ALARM
                self.alarm_reason = reason
                print(f"[ALARM] *** ALARM TRIGGERED *** Reason: {reason}")
                if self._on_alarm_callback:
                    self._on_alarm_callback(reason)
                return True
            return False

    def trigger_alarm_from_armed(self, reason=""):
        """Trigger alarm only if system is ARMED."""
        with self.lock:
            if self.state == self.ARMED:
                self.state = self.ALARM
                self.alarm_reason = reason
                print(f"[ALARM] *** ALARM TRIGGERED *** Reason: {reason}")
                if self._on_alarm_callback:
                    self._on_alarm_callback(reason)
                return True
            return False

    def deactivate(self, pin):
        with self.lock:
            if pin == self.pin and self.state in (self.ARMED, self.ALARM, self.ARMING):
                prev = self.state
                self.state = self.DISARMED
                self.pin_buffer = ""
                self.alarm_reason = ""
                # Cancel any arming timer
                if self._arming_timer:
                    self._arming_timer.cancel()
                    self._arming_timer = None
                # Cancel any door grace timers
                for timer in self._ds_grace_timers.values():
                    timer.cancel()
                self._ds_grace_timers.clear()
                print(f"[ALARM] System DISARMED (was {prev})")
                if self._on_deactivated_callback:
                    self._on_deactivated_callback()
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
            # Feature 4: arm with 10-second delay via DMS
            if self.arm(delayed=True):
                return "arming", True
            return "already_armed", False
        else:
            self.pin_buffer += key
            print(f"[ALARM] PIN buffer: {'*' * len(self.pin_buffer)}")
            return "key_added", False

    def start_door_open_timer(self, sensor_id, on_timeout):
        """Feature 3: Start 5-second timer when door opens. If still open, trigger ALARM."""
        self.cancel_door_open_timer(sensor_id)
        timer = threading.Timer(5.0, on_timeout, args=[sensor_id])
        timer.daemon = True
        timer.start()
        self._door_open_timers[sensor_id] = timer
        print(f"[ALARM] Door {sensor_id} open - 5s timer started")

    def cancel_door_open_timer(self, sensor_id):
        """Feature 3: Cancel door open timer (door was closed)."""
        if sensor_id in self._door_open_timers:
            self._door_open_timers[sensor_id].cancel()
            del self._door_open_timers[sensor_id]

    def start_ds_grace_timer(self, sensor_id, on_timeout):
        """Feature 4: When armed and DS triggers, give grace period for PIN entry."""
        if sensor_id in self._ds_grace_timers:
            return  # Already waiting
        timer = threading.Timer(10.0, on_timeout, args=[sensor_id])
        timer.daemon = True
        timer.start()
        self._ds_grace_timers[sensor_id] = timer
        print(f"[ALARM] Door {sensor_id} opened while ARMED - 10s grace for PIN entry")

    def cancel_ds_grace_timer(self, sensor_id):
        if sensor_id in self._ds_grace_timers:
            self._ds_grace_timers[sensor_id].cancel()
            del self._ds_grace_timers[sensor_id]


# ==================== PEOPLE COUNTER ====================
class PeopleCounter:
    def __init__(self):
        self.count = 0
        self.lock = threading.Lock()
        self._distance_buffers = {}  # sensor_id -> deque
        self.last_detection_time = {}

    def add_distance(self, sensor_id, distance, timestamp):
        if sensor_id not in self._distance_buffers:
            self._distance_buffers[sensor_id] = deque(maxlen=50)
        self._distance_buffers[sensor_id].append((distance, timestamp))

    def detect_direction(self, sensor_id="DUS1"):
        """Analyze ultrasonic distance trend to determine enter/exit."""
        buf = self._distance_buffers.get(sensor_id)
        if not buf or len(buf) < 5:
            return None

        now = time.time()
        last_time = self.last_detection_time.get(sensor_id, 0)
        if now - last_time < 3:
            return None

        recent = [(d, t) for d, t in buf if now - t < 5]
        if len(recent) < 4:
            return None

        mid = len(recent) // 2
        first_half_avg = sum(d for d, _ in recent[:mid]) / mid
        second_half_avg = sum(d for d, _ in recent[mid:]) / (len(recent) - mid)

        diff = second_half_avg - first_half_avg

        if diff < -10:
            self.last_detection_time[sensor_id] = now
            return "ENTERING"
        elif diff > 10:
            self.last_detection_time[sensor_id] = now
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

    def activate_alarm_hardware(reason=""):
        if buzzer:
            buzzer.turn_on()
        if led:
            led.turn_on()
        publish_sensor_data("ALARM", "alarm", 1, True, "state")
        publish_sensor_data("ALARM", "alarm_event", "alarm_activated", True, "event")
        publish_sensor_data("ALARM", "alarm_reason", reason, True, "reason")
        print(f"[ALARM] Hardware activated: Buzzer ON, LED ON. Reason: {reason}")

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
        state_map = {
            AlarmSystem.ALARM: 1,
            AlarmSystem.ARMED: 2,
            AlarmSystem.ARMING: 3,
            AlarmSystem.DISARMED: 0,
        }
        publish_sensor_data("ALARM", "alarm",
                          state_map.get(alarm.state, 0),
                          True, "state")

    # ---- Alarm callbacks ----
    def on_alarm_armed():
        publish_alarm_state()
        publish_sensor_data("ALARM", "alarm_event", "armed", True, "event")

    def on_alarm_arming():
        publish_alarm_state()
        publish_sensor_data("ALARM", "alarm_event", "arming", True, "event")

    def on_alarm_triggered(reason):
        activate_alarm_hardware(reason)

    def on_alarm_deactivated():
        deactivate_alarm_hardware()

    alarm._on_armed_callback = on_alarm_armed
    alarm._on_arming_callback = on_alarm_arming
    alarm._on_alarm_callback = on_alarm_triggered
    alarm._on_deactivated_callback = on_alarm_deactivated

    # ---- Feature 3: Door open >5s alarm handler ----
    def on_door_open_timeout(sensor_id):
        """Called when a door has been open for more than 5 seconds."""
        print(f"[ALARM] Door {sensor_id} open for >5 seconds! Triggering ALARM.")
        alarm.trigger_alarm(reason=f"Door {sensor_id} open >5s (unlocked door)")

    # ---- Feature 4: DS grace period expired handler ----
    def on_ds_grace_expired(sensor_id):
        """Called when PIN was not entered in time after door opened while armed."""
        if alarm.state == AlarmSystem.ARMED:
            print(f"[ALARM] Grace period expired for {sensor_id} - no PIN entered!")
            alarm.trigger_alarm_from_armed(reason=f"Door {sensor_id} opened - no PIN entered")

    # ---- Feature 5: Room PIR alarm when facility empty ----
    def on_room_pir_motion(sensor_id):
        """Room PIR detected motion. If people count is 0, trigger ALARM."""
        count = people.get_count()
        if count == 0:
            print(f"[ALARM] {sensor_id} detected motion with 0 people inside!")
            alarm.trigger_alarm(reason=f"{sensor_id} motion detected - facility empty")

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
        def on_ultrasonic_dus1(distance):
            publish_sensor_data("DUS1", "ultrasonic", round(distance, 2), dus1_simulated, "cm")
            people.add_distance("DUS1", distance, time.time())

        if dus1_simulated:
            from simulators.ultrasonic import run_ultrasonic_simulator
            t = threading.Thread(target=run_ultrasonic_simulator,
                               args=(0.5, on_ultrasonic_dus1, stop_event), daemon=True)
            t.start()
            threads.append(t)
            print("[DUS1] Ultrasonic Sensor simulator started")
        else:
            from sensors.ultrasonic import run_ultrasonic_loop, UltrasonicSensor
            us = UltrasonicSensor(dus1_settings['trig_pin'], dus1_settings['echo_pin'])
            t = threading.Thread(target=run_ultrasonic_loop,
                               args=(us, 0.5, on_ultrasonic_dus1, stop_event), daemon=True)
            t.start()
            threads.append(t)
            print("[DUS1] Ultrasonic Sensor started")

    # ---- Ultrasonic Sensor (DUS2) ----
    dus2_settings = settings.get('DUS2', {})
    if dus2_settings:
        dus2_simulated = dus2_settings.get('simulated', True)
        def on_ultrasonic_dus2(distance):
            publish_sensor_data("DUS2", "ultrasonic", round(distance, 2), dus2_simulated, "cm")
            people.add_distance("DUS2", distance, time.time())

        if dus2_simulated:
            from simulators.ultrasonic import run_ultrasonic_simulator
            t = threading.Thread(target=run_ultrasonic_simulator,
                               args=(0.5, on_ultrasonic_dus2, stop_event), daemon=True)
            t.start()
            threads.append(t)
            print("[DUS2] Ultrasonic Sensor simulator started")
        else:
            from sensors.ultrasonic import run_ultrasonic_loop, UltrasonicSensor
            us2 = UltrasonicSensor(dus2_settings['trig_pin'], dus2_settings['echo_pin'])
            t = threading.Thread(target=run_ultrasonic_loop,
                               args=(us2, 0.5, on_ultrasonic_dus2, stop_event), daemon=True)
            t.start()
            threads.append(t)
            print("[DUS2] Ultrasonic Sensor started")

    # ---- PIR Motion Sensor (DPIR1) ----
    dpir1_settings = settings.get('DPIR1', {})
    if dpir1_settings:
        dpir1_simulated = dpir1_settings.get('simulated', True)
        last_pir1_motion = [False]

        def on_pir1(motion_detected):
            if motion_detected == last_pir1_motion[0]:
                return
            last_pir1_motion[0] = motion_detected

            publish_sensor_data("DPIR1", "pir", 1 if motion_detected else 0, dpir1_simulated, "motion")

            if motion_detected:
                print("[DPIR1] Motion DETECTED!")

                # 1. Turn on DL for 10 seconds
                turn_on_led_timed(10)

                # 2. Detect enter/exit using ultrasonic data
                direction = people.detect_direction("DUS1")
                if direction == "ENTERING":
                    count = people.person_entered()
                    publish_people_event("ENTERING", count)
                elif direction == "EXITING":
                    count = people.person_exited()
                    publish_people_event("EXITING", count)

                # Feature 4: Check alarm - trigger if system is armed
                if alarm.state == AlarmSystem.ARMED:
                    if alarm.trigger_alarm_from_armed(reason="DPIR1 motion while armed"):
                        pass  # callback handles hardware

        if dpir1_simulated:
            from simulators.pir import run_pir_simulator
            t = threading.Thread(target=run_pir_simulator,
                               args=(2, on_pir1, stop_event), daemon=True)
            t.start()
            threads.append(t)
            print("[DPIR1] PIR Motion Sensor simulator started")
        else:
            from sensors.pir import run_pir_loop, PIRSensor
            pir = PIRSensor(dpir1_settings['pin'])
            t = threading.Thread(target=run_pir_loop,
                               args=(pir, 0.5, on_pir1, stop_event), daemon=True)
            t.start()
            threads.append(t)
            print("[DPIR1] PIR Motion Sensor started")

    # ---- PIR Motion Sensor (DPIR2) ----
    dpir2_settings = settings.get('DPIR2', {})
    if dpir2_settings:
        dpir2_simulated = dpir2_settings.get('simulated', True)
        last_pir2_motion = [False]

        def on_pir2(motion_detected):
            if motion_detected == last_pir2_motion[0]:
                return
            last_pir2_motion[0] = motion_detected

            publish_sensor_data("DPIR2", "pir", 1 if motion_detected else 0, dpir2_simulated, "motion")

            if motion_detected:
                print("[DPIR2] Motion DETECTED!")

                # 2a. Same logic as DPIR1 but using DUS2
                direction = people.detect_direction("DUS2")
                if direction == "ENTERING":
                    count = people.person_entered()
                    publish_people_event("ENTERING", count)
                elif direction == "EXITING":
                    count = people.person_exited()
                    publish_people_event("EXITING", count)

                # Feature 4: Check alarm
                if alarm.state == AlarmSystem.ARMED:
                    if alarm.trigger_alarm_from_armed(reason="DPIR2 motion while armed"):
                        pass

        if dpir2_simulated:
            from simulators.pir import run_pir_simulator
            t = threading.Thread(target=run_pir_simulator,
                               args=(2, on_pir2, stop_event), daemon=True)
            t.start()
            threads.append(t)
            print("[DPIR2] PIR Motion Sensor simulator started")
        else:
            from sensors.pir import run_pir_loop, PIRSensor
            pir2 = PIRSensor(dpir2_settings['pin'])
            t = threading.Thread(target=run_pir_loop,
                               args=(pir2, 0.5, on_pir2, stop_event), daemon=True)
            t.start()
            threads.append(t)
            print("[DPIR2] PIR Motion Sensor started")

    # ---- Door Sensor / Button (DS1) ----
    ds1_settings = settings.get('DS1', {})
    if ds1_settings:
        ds1_simulated = ds1_settings.get('simulated', True)

        def on_button_ds1(state):
            publish_sensor_data("DS1", "button", 1 if state else 0, ds1_simulated, "state")
            if state:
                print("[DS1] Door: CLOSED")
                alarm.cancel_door_open_timer("DS1")
            else:
                print("[DS1] Door: OPEN")
                # Feature 3: Start 5-second timer for door open
                alarm.start_door_open_timer("DS1", on_door_open_timeout)
                # Feature 4: If armed, start grace period for PIN
                if alarm.state == AlarmSystem.ARMED:
                    alarm.start_ds_grace_timer("DS1", on_ds_grace_expired)

        if ds1_simulated:
            from simulators.button import run_button_simulator
            t = threading.Thread(target=run_button_simulator,
                               args=(on_button_ds1, stop_event), daemon=True)
            t.start()
            threads.append(t)
            print("[DS1] Door Sensor simulator started")
        else:
            from sensors.button import run_button_loop, Button
            btn = Button(ds1_settings['pin'])
            t = threading.Thread(target=run_button_loop,
                               args=(btn, on_button_ds1, stop_event), daemon=True)
            t.start()
            threads.append(t)
            print("[DS1] Door Sensor started")

    # ---- Door Sensor / Button (DS2) ----
    ds2_settings = settings.get('DS2', {})
    if ds2_settings:
        ds2_simulated = ds2_settings.get('simulated', True)

        def on_button_ds2(state):
            publish_sensor_data("DS2", "button", 1 if state else 0, ds2_simulated, "state")
            if state:
                print("[DS2] Door: CLOSED")
                alarm.cancel_door_open_timer("DS2")
            else:
                print("[DS2] Door: OPEN")
                # Feature 3: Start 5-second timer for door open
                alarm.start_door_open_timer("DS2", on_door_open_timeout)
                # Feature 4: If armed, start grace period for PIN
                if alarm.state == AlarmSystem.ARMED:
                    alarm.start_ds_grace_timer("DS2", on_ds_grace_expired)

        if ds2_simulated:
            from simulators.button import run_button_simulator
            t = threading.Thread(target=run_button_simulator,
                               args=(on_button_ds2, stop_event), daemon=True)
            t.start()
            threads.append(t)
            print("[DS2] Door Sensor simulator started")
        else:
            from sensors.button import run_button_loop, Button
            btn2 = Button(ds2_settings['pin'])
            t = threading.Thread(target=run_button_loop,
                               args=(btn2, on_button_ds2, stop_event), daemon=True)
            t.start()
            threads.append(t)
            print("[DS2] Door Sensor started")

    # ---- Membrane Switch (DMS) ----
    dms_settings = settings.get('DMS', {})
    if dms_settings:
        dms_simulated = dms_settings.get('simulated', True)

        def on_membrane_key(key):
            publish_sensor_data("DMS", "membrane_switch", key, dms_simulated, "key")
            print(f"[DMS] Key pressed: {key}")

            action, success = alarm.process_key(key)
            if action == "arming":
                # Feature 4: arming with 10s delay handled by AlarmSystem
                pass
            elif action == "armed":
                publish_alarm_state()
                publish_sensor_data("ALARM", "alarm_event", "armed", True, "event")
            elif action == "deactivated":
                # Handled by callback
                pass

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

    # ---- Room PIR Sensors (RPIR1, RPIR2, RPIR3) - Feature 5 ----
    for rpir_id in ["RPIR1", "RPIR2", "RPIR3"]:
        rpir_settings = settings.get(rpir_id, {})
        if not rpir_settings:
            continue
        rpir_simulated = rpir_settings.get('simulated', True)
        last_state = [False]
        sid = rpir_id  # capture for closure

        def make_rpir_callback(sensor_id, simulated, last_st):
            def on_rpir(motion_detected):
                if motion_detected == last_st[0]:
                    return
                last_st[0] = motion_detected

                publish_sensor_data(sensor_id, "pir", 1 if motion_detected else 0, simulated, "motion")

                if motion_detected:
                    print(f"[{sensor_id}] Motion DETECTED!")
                    # Feature 5: trigger alarm if no people inside
                    on_room_pir_motion(sensor_id)
            return on_rpir

        rpir_callback = make_rpir_callback(sid, rpir_simulated, last_state)

        if rpir_simulated:
            from simulators.pir import run_pir_simulator
            t = threading.Thread(target=run_pir_simulator,
                               args=(2, rpir_callback, stop_event), daemon=True)
            t.start()
            threads.append(t)
            print(f"[{rpir_id}] Room PIR Sensor simulator started")
        else:
            from sensors.pir import run_pir_loop, PIRSensor
            rpir_sensor = PIRSensor(rpir_settings['pin'])
            t = threading.Thread(target=run_pir_loop,
                               args=(rpir_sensor, 0.5, rpir_callback, stop_event), daemon=True)
            t.start()
            threads.append(t)
            print(f"[{rpir_id}] Room PIR Sensor started")

    # ==================== FEATURE 6: GSG Gyroscope Alarm ====================
    gsg_settings = settings.get('GSG', {})
    if gsg_settings:
        gsg_simulated = gsg_settings.get('simulated', True)
        gsg_threshold = gsg_settings.get('threshold', 5.0)

        def on_gyroscope(x, y, z, significant):
            publish_sensor_data("GSG", "gyroscope",
                              json.dumps({"x": round(x, 2), "y": round(y, 2), "z": round(z, 2),
                                         "significant": significant}),
                              gsg_simulated, "m/s2")

            if significant:
                print(f"[GSG] SIGNIFICANT movement detected! x={x:.2f} y={y:.2f} z={z:.2f}")
                alarm.trigger_alarm(reason="GSG gyroscope - significant movement on patron saint icon")

        if gsg_simulated:
            from simulators.gyroscope import run_gyroscope_simulator
            t = threading.Thread(target=run_gyroscope_simulator,
                               args=(1, on_gyroscope, stop_event), daemon=True)
            t.start()
            threads.append(t)
            print("[GSG] Gyroscope simulator started")
        else:
            from sensors.gyroscope import run_gyroscope_loop, Gyroscope
            gyro = Gyroscope(bus_num=gsg_settings.get('bus', 1),
                           address=int(gsg_settings.get('address', '0x68'), 16))
            t = threading.Thread(target=run_gyroscope_loop,
                               args=(gyro, 1, on_gyroscope, stop_event), daemon=True)
            t.start()
            threads.append(t)
            print("[GSG] Gyroscope started")

    # ==================== FEATURE 7: DHT1-3 on LCD ====================
    lcd = None
    lcd_settings = settings.get('LCD', {})
    if lcd_settings:
        lcd_simulated = lcd_settings.get('simulated', True)
        def on_lcd_change(line1, line2):
            publish_sensor_data("LCD", "lcd",
                              json.dumps({"line1": line1, "line2": line2}),
                              lcd_simulated, "display")

        if lcd_simulated:
            from simulators.lcd import LCDSimulator
            lcd = LCDSimulator(callback=on_lcd_change)
            print("[LCD] LCD Display simulator initialized")
        else:
            from sensors.lcd import LCD as LCDDriver
            lcd = LCDDriver(bus_num=lcd_settings.get('bus', 1),
                          address=int(lcd_settings.get('address', '0x27'), 16),
                          callback=on_lcd_change)
            print("[LCD] LCD Display initialized")

    # DHT sensors storage for LCD rotation
    dht_readings = {}
    dht_readings_lock = threading.Lock()

    for dht_id in ["DHT1", "DHT2", "DHT3"]:
        dht_settings = settings.get(dht_id, {})
        if not dht_settings:
            continue
        dht_simulated = dht_settings.get('simulated', True)
        sid = dht_id

        def make_dht_callback(sensor_id, simulated):
            def on_dht(temperature, humidity):
                publish_sensor_data(sensor_id, "dht",
                                  json.dumps({"temperature": temperature, "humidity": humidity}),
                                  simulated, "C/%")
                with dht_readings_lock:
                    dht_readings[sensor_id] = {
                        "temperature": temperature,
                        "humidity": humidity,
                        "timestamp": time.time()
                    }
            return on_dht

        dht_callback = make_dht_callback(sid, dht_simulated)

        if dht_simulated:
            from simulators.dht import run_dht_simulator
            t = threading.Thread(target=run_dht_simulator,
                               args=(2, dht_callback, stop_event), daemon=True)
            t.start()
            threads.append(t)
            print(f"[{dht_id}] DHT Sensor simulator started")
        else:
            from sensors.dht import run_dht_loop, DHTSensor
            dht_sensor = DHTSensor(dht_settings['pin'])
            t = threading.Thread(target=run_dht_loop,
                               args=(dht_sensor, 2, dht_callback, stop_event), daemon=True)
            t.start()
            threads.append(t)
            print(f"[{dht_id}] DHT Sensor started")

    # LCD rotation thread - alternates DHT readings every 5 seconds
    def lcd_rotation_loop():
        dht_order = ["DHT1", "DHT2", "DHT3"]
        dht_names = {"DHT1": "Bedroom", "DHT2": "Master Bed", "DHT3": "Kitchen"}
        idx = 0
        while not stop_event.is_set():
            time.sleep(5)
            if stop_event.is_set():
                break
            if not lcd:
                continue

            with dht_readings_lock:
                if not dht_readings:
                    continue
                # Cycle through available DHTs
                for _ in range(len(dht_order)):
                    sensor_id = dht_order[idx % len(dht_order)]
                    idx += 1
                    if sensor_id in dht_readings:
                        reading = dht_readings[sensor_id]
                        name = dht_names.get(sensor_id, sensor_id)
                        line1 = f"{name}: {reading['temperature']}C"
                        line2 = f"Humidity: {reading['humidity']}%"
                        lcd.write(line1, line2)
                        break

    lcd_thread = threading.Thread(target=lcd_rotation_loop, daemon=True)
    lcd_thread.start()
    threads.append(lcd_thread)
    print("[LCD] DHT rotation display started")

    # ==================== FEATURE 8: Kitchen Timer ====================
    kitchen_timer = KitchenTimer()
    kitchen_timer.btn_add_seconds = settings.get('timer_btn_seconds', 10)

    # 4SD Display
    segment_display = None
    sd_settings = settings.get('4SD', {})
    if sd_settings:
        sd_simulated = sd_settings.get('simulated', True)
        def on_display_change(value, blinking):
            publish_sensor_data("4SD", "segment_display",
                              json.dumps({"display": value, "blinking": blinking}),
                              sd_simulated, "display")

        if sd_simulated:
            from simulators.segment_display import SegmentDisplaySimulator
            segment_display = SegmentDisplaySimulator(callback=on_display_change)
            print("[4SD] Segment Display simulator initialized")
        else:
            from sensors.segment_display import SegmentDisplay
            segment_display = SegmentDisplay(
                segment_pins=sd_settings['segment_pins'],
                digit_pins=sd_settings['digit_pins'],
                callback=on_display_change)
            print("[4SD] Segment Display initialized")

    # Kitchen Button (BTN)
    btn_settings = settings.get('BTN', {})
    if btn_settings:
        btn_simulated = btn_settings.get('simulated', True)
        last_btn_state = [False]

        def on_kitchen_btn(state):
            if state == last_btn_state[0]:
                return
            last_btn_state[0] = state
            publish_sensor_data("BTN", "button", 1 if state else 0, btn_simulated, "state")

            if state:
                print("[BTN] Kitchen button PRESSED")
                kitchen_timer.add_seconds()

        if btn_simulated:
            from simulators.button import run_button_simulator
            t = threading.Thread(target=run_button_simulator,
                               args=(on_kitchen_btn, stop_event), daemon=True)
            t.start()
            threads.append(t)
            print("[BTN] Kitchen Button simulator started")
        else:
            from sensors.button import run_button_loop, Button
            kitchen_btn = Button(btn_settings['pin'])
            t = threading.Thread(target=run_button_loop,
                               args=(kitchen_btn, on_kitchen_btn, stop_event), daemon=True)
            t.start()
            threads.append(t)
            print("[BTN] Kitchen Button started")

    # Timer callbacks -> update 4SD display
    def on_timer_tick(remaining, display, blinking):
        if segment_display:
            segment_display.set_value(display)
            segment_display.set_blinking(blinking)
        publish_sensor_data("TIMER", "timer_state",
                          json.dumps({"remaining": remaining, "display": display,
                                     "running": kitchen_timer.running, "blinking": blinking}),
                          True, "state")

    def on_timer_finished():
        publish_sensor_data("TIMER", "timer_event", "finished", True, "event")
        print("[TIMER] Published timer finished event")

    def on_blink_stopped():
        if segment_display:
            segment_display.set_blinking(False)
        publish_sensor_data("TIMER", "timer_event", "blink_stopped", True, "event")

    kitchen_timer._on_tick_callback = on_timer_tick
    kitchen_timer._on_finished_callback = on_timer_finished
    kitchen_timer._on_blink_stopped_callback = on_blink_stopped

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
                    alarm.arm(delayed=False)  # Web app arm is immediate
                elif action == "deactivate":
                    pin = payload.get("pin", "")
                    if not alarm.deactivate(pin):
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

            elif topic == "pi1/commands/timer":
                action = payload.get("action")
                if action == "set_time":
                    seconds = int(payload.get("seconds", 0))
                    kitchen_timer.set_time(seconds)
                elif action == "start":
                    kitchen_timer.start()
                elif action == "stop":
                    kitchen_timer.stop()
                elif action == "add_seconds":
                    n = int(payload.get("seconds", kitchen_timer.btn_add_seconds))
                    kitchen_timer.add_seconds(n)
                elif action == "set_btn_seconds":
                    n = int(payload.get("seconds", 10))
                    kitchen_timer.set_btn_seconds(n)

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
            # Publish timer state
            ts = kitchen_timer.get_state()
            publish_sensor_data("TIMER", "timer_state",
                              json.dumps(ts), True, "state")
            time.sleep(10)

    state_thread = threading.Thread(target=state_publisher, daemon=True)
    state_thread.start()
    threads.append(state_thread)

    # ---- Console Interface ----
    time.sleep(1)
    print("\n" + "=" * 50)
    print("System ready. Commands:")
    print("  arm        - Arm alarm system (immediate)")
    print("  disarm     - Disarm (enter PIN when prompted)")
    print("  led on/off - Control door light")
    print("  buzz on/off/beep - Control buzzer")
    print("  timer set N  - Set timer to N seconds")
    print("  timer start  - Start timer")
    print("  timer stop   - Stop timer")
    print("  timer add N  - Add N seconds")
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
                    if alarm.arm(delayed=False):
                        pass  # callback handles publishing
                    else:
                        print(f"Cannot arm: currently {alarm.state}")
                elif cmd == "disarm":
                    pin = input("Enter PIN: ").strip()
                    if not alarm.deactivate(pin):
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
                elif cmd.startswith("timer "):
                    parts = cmd.split()
                    if len(parts) >= 2:
                        tcmd = parts[1]
                        if tcmd == "set" and len(parts) >= 3:
                            kitchen_timer.set_time(int(parts[2]))
                        elif tcmd == "start":
                            kitchen_timer.start()
                        elif tcmd == "stop":
                            kitchen_timer.stop()
                        elif tcmd == "add" and len(parts) >= 3:
                            kitchen_timer.add_seconds(int(parts[2]))
                        else:
                            print("Timer commands: timer set N, timer start, timer stop, timer add N")
                elif cmd == "status":
                    print(f"\n  Alarm: {alarm.state}")
                    if alarm.alarm_reason:
                        print(f"  Alarm Reason: {alarm.alarm_reason}")
                    print(f"  People inside: {people.get_count()}")
                    print(f"  LED: {'ON' if led and led.get_state() else 'OFF'}")
                    print(f"  Buzzer: {'ON' if buzzer and buzzer.get_state() else 'OFF'}")
                    ts = kitchen_timer.get_state()
                    print(f"  Timer: {ts['display']} ({'running' if ts['running'] else 'stopped'})")
                    if ts['blinking']:
                        print("  Timer: BLINKING (press BTN to stop)")
                elif cmd == "menu":
                    print("Commands: arm, disarm, led on/off, buzz on/off/beep, timer ..., status, exit")
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
