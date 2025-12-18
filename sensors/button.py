import RPi.GPIO as GPIO
import time

class Button:
    """
    Button class for door sensor.
    Uses pull-up resistor configuration.
    """
    def __init__(self, pin):
        self.pin = pin
        GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        self.last_state = GPIO.input(self.pin)
    
    def is_pressed(self):
        """Returns True if button is pressed (LOW due to pull-up)"""
        return GPIO.input(self.pin) == GPIO.LOW
    
    def get_state(self):
        """Returns current state"""
        return GPIO.input(self.pin)
    
    def state_changed(self):
        """Returns True if state changed since last check"""
        current_state = GPIO.input(self.pin)
        if current_state != self.last_state:
            self.last_state = current_state
            return True
        return False


def run_button_loop(button, callback, stop_event, debounce_time=0.2):
    """
    Runs the button monitoring loop.
    Uses interrupt-based detection with debouncing.
    """
    last_callback_time = 0
    
    while not stop_event.is_set():
        if button.state_changed():
            current_time = time.time()
            if current_time - last_callback_time > debounce_time:
                callback(button.is_pressed())
                last_callback_time = current_time
        time.sleep(0.05)  # Small delay to prevent CPU overload
