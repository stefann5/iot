import RPi.GPIO as GPIO
import time

class PIRSensor:
    """
    PIR (Passive Infrared) Motion Sensor class.
    """
    def __init__(self, pin):
        self.pin = pin
        GPIO.setup(self.pin, GPIO.IN)
        self.last_state = GPIO.LOW
        time.sleep(2)  # Allow sensor to stabilize
    
    def motion_detected(self):
        """Returns True if motion is currently detected"""
        return GPIO.input(self.pin) == GPIO.HIGH
    
    def get_state(self):
        """Returns current state"""
        return GPIO.input(self.pin)


def run_pir_loop(pir, delay, callback, stop_event):
    """
    Runs the PIR sensor monitoring loop.
    Reports only when motion state changes to avoid spam.
    """
    last_motion = False
    
    while not stop_event.is_set():
        current_motion = pir.motion_detected()
        
        # Report on state change or periodically when motion detected
        if current_motion != last_motion or current_motion:
            callback(current_motion)
            last_motion = current_motion
        
        if stop_event.is_set():
            break
        time.sleep(delay)
