import time


class LCDSimulator:
    """
    Simulates a 16x2 LCD display.
    """

    def __init__(self, callback=None):
        self.line1 = ""
        self.line2 = ""
        self._callback = callback

    def write(self, line1, line2=""):
        self.line1 = line1
        self.line2 = line2
        print(f"[LCD] Line1: {line1}")
        if line2:
            print(f"[LCD] Line2: {line2}")
        if self._callback:
            self._callback(line1, line2)

    def clear(self):
        self.line1 = ""
        self.line2 = ""
        if self._callback:
            self._callback("", "")

    def get_display(self):
        return self.line1, self.line2
