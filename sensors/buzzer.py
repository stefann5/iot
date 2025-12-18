import RPi.GPIO as GPIO
import time
import threading

class Buzzer:
    """
    Active Buzzer class for door buzzer control.
    """
    def __init__(self, pin, callback=None):
        self.pin = pin
        self.callback = callback
        self.state = False
        GPIO.setup(self.pin, GPIO.OUT)
        GPIO.output(self.pin, GPIO.LOW)
    
    def turn_on(self):
        """Turn buzzer on"""
        GPIO.output(self.pin, GPIO.HIGH)
        self.state = True
        if self.callback:
            self.callback(self.state)
    
    def turn_off(self):
        """Turn buzzer off"""
        GPIO.output(self.pin, GPIO.LOW)
        self.state = False
        if self.callback:
            self.callback(self.state)
    
    def beep(self, duration=0.5):
        """Short beep for specified duration"""
        def _beep():
            self.turn_on()
            time.sleep(duration)
            self.turn_off()
        
        beep_thread = threading.Thread(target=_beep)
        beep_thread.start()
    
    def beep_pattern(self, pattern):
        """
        Play a beep pattern.
        Pattern is a list of tuples: (on_time, off_time)
        """
        def _pattern():
            for on_time, off_time in pattern:
                self.turn_on()
                time.sleep(on_time)
                self.turn_off()
                time.sleep(off_time)
        
        pattern_thread = threading.Thread(target=_pattern)
        pattern_thread.start()
    
    def get_state(self):
        """Returns current state"""
        return self.state
