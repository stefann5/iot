import time
import threading

class BuzzerSimulator:
    """
    Simulates Buzzer behavior.
    Provides turn_on, turn_off, and beep methods.
    """
    def __init__(self, callback=None):
        self.state = False
        self.callback = callback
    
    def turn_on(self):
        self.state = True
        if self.callback:
            self.callback(self.state)
        print("[Buzzer Simulator] Buzzer turned ON")
    
    def turn_off(self):
        self.state = False
        if self.callback:
            self.callback(self.state)
        print("[Buzzer Simulator] Buzzer turned OFF")
    
    def beep(self, duration=0.5):
        """Short beep for specified duration"""
        def _beep():
            self.turn_on()
            time.sleep(duration)
            self.turn_off()
        
        beep_thread = threading.Thread(target=_beep)
        beep_thread.start()
    
    
    def get_state(self):
        return self.state
