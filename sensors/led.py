import RPi.GPIO as GPIO
import time

class LED:
    """
    LED class for door light control.
    """
    def __init__(self, pin, callback=None):
        self.pin = pin
        self.callback = callback
        self.state = False
        GPIO.setup(self.pin, GPIO.OUT)
        GPIO.output(self.pin, GPIO.LOW)
    
    def turn_on(self):
        """Turn LED on"""
        GPIO.output(self.pin, GPIO.HIGH)
        self.state = True
        if self.callback:
            self.callback(self.state)
    
    def turn_off(self):
        """Turn LED off"""
        GPIO.output(self.pin, GPIO.LOW)
        self.state = False
        if self.callback:
            self.callback(self.state)
    
    def toggle(self):
        """Toggle LED state"""
        if self.state:
            self.turn_off()
        else:
            self.turn_on()
    
    def get_state(self):
        """Returns current state"""
        return self.state
    
    def blink(self, times=3, on_time=0.5, off_time=0.5):
        """Blink LED specified number of times"""
        for _ in range(times):
            self.turn_on()
            time.sleep(on_time)
            self.turn_off()
            time.sleep(off_time)
