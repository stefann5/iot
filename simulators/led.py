import time

class LEDSimulator:
    """
    Simulates LED (Door Light) behavior.
    Provides turn_on, turn_off, and toggle methods.
    """
    def __init__(self, callback=None):
        self.state = False
        self.callback = callback
    
    def turn_on(self):
        self.state = True
        if self.callback:
            self.callback(self.state)
        print("[LED Simulator] LED turned ON")
    
    def turn_off(self):
        self.state = False
        if self.callback:
            self.callback(self.state)
        print("[LED Simulator] LED turned OFF")
    
    def toggle(self):
        if self.state:
            self.turn_off()
        else:
            self.turn_on()
    
    def get_state(self):
        return self.state
