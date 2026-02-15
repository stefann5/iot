import time

try:
    import RPi.GPIO as GPIO
except ImportError:
    GPIO = None


# NEC protocol IR codes mapped to button names
IR_CODES = {
    0xFF6897: "0",
    0xFF30CF: "1",
    0xFF18E7: "2",
    0xFF7A85: "3",
    0xFF10EF: "4",
    0xFF38C7: "5",
    0xFF5AA5: "6",
    0xFF42BD: "7",
    0xFF4AB5: "8",
    0xFF52AD: "9",
    0xFFA25D: "POWER",
    0xFFE21D: "FUNC",
    0xFF22DD: "PREV",
    0xFF02FD: "NEXT",
    0xFFC23D: "PLAY",
    0xFFE01F: "VOL_DOWN",
    0xFFA857: "VOL_UP",
    0xFF906F: "UP",
    0xFF9867: "EQ",
    0xFFB04F: "DOWN",
}

# Map remote buttons to RGB actions
BUTTON_ACTIONS = {
    "POWER": "toggle",
    "1": "red",
    "2": "green",
    "3": "blue",
    "4": "yellow",
    "5": "cyan",
    "6": "magenta",
    "7": "white",
    "8": "orange",
    "9": "purple",
    "0": "off",
    "VOL_UP": "brightness_up",
    "VOL_DOWN": "brightness_down",
}


class IRReceiver:
    """IR Receiver using GPIO pin (NEC protocol)."""

    def __init__(self, pin):
        self.pin = pin
        if GPIO:
            GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    def _read_nec(self):
        """Read NEC IR code from GPIO pin."""
        if not GPIO:
            return None

        # Wait for falling edge (start of transmission)
        GPIO.wait_for_edge(self.pin, GPIO.FALLING, timeout=1000)
        if GPIO.input(self.pin) == 1:
            return None

        # Read 32-bit NEC code
        code = 0
        for i in range(32):
            while GPIO.input(self.pin) == 0:
                pass
            start = time.time()
            while GPIO.input(self.pin) == 1:
                pass
            duration = time.time() - start
            if duration > 0.001:
                code |= (1 << i)

        return code


def run_ir_loop(ir_receiver, delay, callback, stop_event):
    """Run IR receiver loop on real hardware."""
    while not stop_event.is_set():
        code = ir_receiver._read_nec()
        if code is not None and code in IR_CODES:
            button = IR_CODES[code]
            action = BUTTON_ACTIONS.get(button, "unknown")
            callback(button, action)
        time.sleep(delay)
