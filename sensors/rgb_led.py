try:
    import RPi.GPIO as GPIO
except ImportError:
    GPIO = None


class RGBLED:
    """
    Real BRGB LED control using PWM on 3 GPIO pins (R, G, B).
    """

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

    def __init__(self, r_pin, g_pin, b_pin, callback=None):
        self.r_pin = r_pin
        self.g_pin = g_pin
        self.b_pin = b_pin
        self.callback = callback
        self.on = False
        self.r = 255
        self.g = 255
        self.b = 255
        self.brightness = 100

        if GPIO:
            GPIO.setup(r_pin, GPIO.OUT)
            GPIO.setup(g_pin, GPIO.OUT)
            GPIO.setup(b_pin, GPIO.OUT)
            self.pwm_r = GPIO.PWM(r_pin, 1000)
            self.pwm_g = GPIO.PWM(g_pin, 1000)
            self.pwm_b = GPIO.PWM(b_pin, 1000)
            self.pwm_r.start(0)
            self.pwm_g.start(0)
            self.pwm_b.start(0)

    def _update_pwm(self):
        if not GPIO:
            return
        if self.on:
            factor = self.brightness / 100.0
            self.pwm_r.ChangeDutyCycle(self.r / 255.0 * 100 * factor)
            self.pwm_g.ChangeDutyCycle(self.g / 255.0 * 100 * factor)
            self.pwm_b.ChangeDutyCycle(self.b / 255.0 * 100 * factor)
        else:
            self.pwm_r.ChangeDutyCycle(0)
            self.pwm_g.ChangeDutyCycle(0)
            self.pwm_b.ChangeDutyCycle(0)

    def turn_on(self):
        self.on = True
        self._update_pwm()
        self._notify()

    def turn_off(self):
        self.on = False
        self._update_pwm()
        self._notify()

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
        self._update_pwm()
        self._notify()

    def set_color_name(self, name):
        color = self.COLORS.get(name.lower())
        if color:
            self.set_color(*color)

    def set_brightness(self, brightness):
        self.brightness = max(0, min(100, brightness))
        self._update_pwm()
        self._notify()

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
