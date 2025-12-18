import RPi.GPIO as GPIO
import time

# 4x4 Membrane Switch keypad layout
KEYPAD = [
    ['1', '2', '3', 'A'],
    ['4', '5', '6', 'B'],
    ['7', '8', '9', 'C'],
    ['*', '0', '#', 'D']
]

class MembraneSwitch:
    """
    4x4 Membrane Switch (Keypad) class.
    Uses row-column scanning method.
    """
    def __init__(self, row_pins, col_pins):
        """
        Initialize membrane switch.
        row_pins: list of 4 GPIO pins for rows [R1, R2, R3, R4]
        col_pins: list of 4 GPIO pins for columns [C1, C2, C3, C4]
        """
        self.row_pins = row_pins
        self.col_pins = col_pins
        
        # Setup row pins as outputs
        for pin in self.row_pins:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.HIGH)
        
        # Setup column pins as inputs with pull-up resistors
        for pin in self.col_pins:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
    def scan_key(self):
        """
        Scan the keypad and return the pressed key.
        Returns None if no key is pressed.
        """
        for row_idx, row_pin in enumerate(self.row_pins):
            # Set current row LOW
            GPIO.output(row_pin, GPIO.LOW)
            
            # Check each column
            for col_idx, col_pin in enumerate(self.col_pins):
                if GPIO.input(col_pin) == GPIO.LOW:
                    # Key pressed at (row_idx, col_idx)
                    # Reset row pin
                    GPIO.output(row_pin, GPIO.HIGH)
                    # Wait for key release (debouncing)
                    while GPIO.input(col_pin) == GPIO.LOW:
                        time.sleep(0.01)
                    return KEYPAD[row_idx][col_idx]
            
            # Reset row pin
            GPIO.output(row_pin, GPIO.HIGH)
        
        return None


def run_membrane_switch_loop(membrane, callback, stop_event, scan_delay=0.1):
    """
    Runs the membrane switch scanning loop.
    """
    while not stop_event.is_set():
        key = membrane.scan_key()
        if key is not None:
            callback(key)
        
        if stop_event.is_set():
            break
        time.sleep(scan_delay)
