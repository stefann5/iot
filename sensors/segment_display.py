import time

try:
    import RPi.GPIO as GPIO
except ImportError:
    GPIO = None


class SegmentDisplay:
    """
    4-Digit 7-Segment Display driver (common cathode, direct GPIO).
    Displays time in MM:SS format using multiplexing.
    """

    SEGMENTS = {
        '0': [1, 1, 1, 1, 1, 1, 0],
        '1': [0, 1, 1, 0, 0, 0, 0],
        '2': [1, 1, 0, 1, 1, 0, 1],
        '3': [1, 1, 1, 1, 0, 0, 1],
        '4': [0, 1, 1, 0, 0, 1, 1],
        '5': [1, 0, 1, 1, 0, 1, 1],
        '6': [1, 0, 1, 1, 1, 1, 1],
        '7': [1, 1, 1, 0, 0, 0, 0],
        '8': [1, 1, 1, 1, 1, 1, 1],
        '9': [1, 1, 1, 1, 0, 1, 1],
        ' ': [0, 0, 0, 0, 0, 0, 0],
    }

    def __init__(self, segment_pins, digit_pins, callback=None):
        """
        segment_pins: list of 7 GPIO pins [a, b, c, d, e, f, g]
        digit_pins: list of 4 GPIO pins [d1, d2, d3, d4]
        """
        self.segment_pins = segment_pins
        self.digit_pins = digit_pins
        self._callback = callback
        self.display_value = "00:00"
        self.blinking = False

        if GPIO:
            for pin in segment_pins + digit_pins:
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.LOW)

    def _display_digit(self, digit_idx, char):
        if GPIO is None:
            return
        for pin in self.digit_pins:
            GPIO.output(pin, GPIO.LOW)
        segments = self.SEGMENTS.get(char, self.SEGMENTS[' '])
        for i, seg in enumerate(segments):
            GPIO.output(self.segment_pins[i], GPIO.HIGH if seg else GPIO.LOW)
        GPIO.output(self.digit_pins[digit_idx], GPIO.HIGH)
        time.sleep(0.005)
        GPIO.output(self.digit_pins[digit_idx], GPIO.LOW)

    def set_value(self, value):
        self.display_value = value
        if self._callback:
            self._callback(value, self.blinking)

    def set_blinking(self, blinking):
        self.blinking = blinking
        if self._callback:
            self._callback(self.display_value, self.blinking)

    def get_display(self):
        return self.display_value, self.blinking

    def clear(self):
        self.display_value = "00:00"
        self.blinking = False
        if self._callback:
            self._callback("00:00", False)


def run_segment_display_loop(display, stop_event):
    """Multiplex the display continuously."""
    while not stop_event.is_set():
        value = display.display_value.replace(":", "")
        if display.blinking:
            # Blink: show for 0.5s, blank for 0.5s
            for _ in range(50):
                if stop_event.is_set():
                    break
                for i, ch in enumerate(value[:4]):
                    display._display_digit(i, ch)
            for _ in range(50):
                if stop_event.is_set():
                    break
                time.sleep(0.01)
        else:
            for i, ch in enumerate(value[:4]):
                display._display_digit(i, ch)
