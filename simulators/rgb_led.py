class RGBLEDSimulator:
    """
    Simulates BRGB (Bedroom RGB LED bulb) behavior.
    Supports on/off, color setting, and brightness control.
    """

    # Predefined color map
    COLORS = {
        "red": (255, 0, 0),
        "green": (0, 255, 0),
        "blue": (0, 0, 255),
        "yellow": (255, 255, 0),
        "cyan": (0, 255, 255),
        "magenta": (255, 0, 255),
        "white": (255, 255, 255),
        "orange": (255, 165, 0),
        "purple": (128, 0, 128),
        "off": (0, 0, 0),
    }

    def __init__(self, callback=None):
        self.on = False
        self.r = 255
        self.g = 255
        self.b = 255
        self.brightness = 100  # 0-100
        self.callback = callback

    def turn_on(self):
        self.on = True
        self._notify()
        print(f"[BRGB Simulator] ON - RGB({self.r},{self.g},{self.b}) @ {self.brightness}%")

    def turn_off(self):
        self.on = False
        self._notify()
        print("[BRGB Simulator] OFF")

    def toggle(self):
        if self.on:
            self.turn_off()
        else:
            self.turn_on()

    def set_color(self, r, g, b):
        self.r = max(0, min(255, r))
        self.g = max(0, min(255, g))
        self.b = max(0, min(255, b))
        if not self.on:
            self.on = True
        self._notify()
        print(f"[BRGB Simulator] Color set to RGB({self.r},{self.g},{self.b})")

    def set_color_name(self, name):
        """Set color by predefined name."""
        color = self.COLORS.get(name.lower())
        if color:
            self.set_color(*color)
        else:
            print(f"[BRGB Simulator] Unknown color: {name}")

    def set_brightness(self, brightness):
        self.brightness = max(0, min(100, brightness))
        self._notify()
        print(f"[BRGB Simulator] Brightness: {self.brightness}%")

    def brightness_up(self, step=10):
        self.set_brightness(self.brightness + step)

    def brightness_down(self, step=10):
        self.set_brightness(self.brightness - step)

    def get_state(self):
        return {
            "on": self.on,
            "r": self.r,
            "g": self.g,
            "b": self.b,
            "brightness": self.brightness,
        }

    def _notify(self):
        if self.callback:
            self.callback(self.get_state())
