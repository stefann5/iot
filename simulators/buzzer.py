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
        return self.state
