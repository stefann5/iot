import time


class SegmentDisplaySimulator:
    """
    Simulates a 4-digit 7-segment display (4SD).
    Displays time in MM:SS format.
    """

    def __init__(self, callback=None):
        self.display_value = "00:00"
        self.blinking = False
        self._callback = callback

    def set_value(self, value):
        """Set the display value (e.g., '05:30')."""
        self.display_value = value
        print(f"[4SD] Display: {value}")
        if self._callback:
            self._callback(value, self.blinking)

    def set_blinking(self, blinking):
        """Enable or disable blinking."""
        self.blinking = blinking
        print(f"[4SD] Blinking: {blinking}")
        if self._callback:
            self._callback(self.display_value, self.blinking)

    def get_display(self):
        return self.display_value, self.blinking

    def clear(self):
        self.display_value = "00:00"
        self.blinking = False
        if self._callback:
            self._callback("00:00", False)
