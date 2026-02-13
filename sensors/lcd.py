import time

try:
    import smbus2 as smbus
except ImportError:
    try:
        import smbus
    except ImportError:
        smbus = None


class LCD:
    """
    16x2 LCD display driver via I2C (PCF8574 backpack).
    """
    LCD_BACKLIGHT = 0x08
    ENABLE = 0b00000100
    LCD_CMD = 0
    LCD_CHR = 1
    LCD_LINE_1 = 0x80
    LCD_LINE_2 = 0xC0

    def __init__(self, bus_num=1, address=0x27, callback=None):
        self.address = address
        self._callback = callback
        self.line1 = ""
        self.line2 = ""
        if smbus is None:
            raise RuntimeError("smbus library not available")
        self.bus = smbus.SMBus(bus_num)
        self._init_display()

    def _init_display(self):
        self._write_byte(0x33, self.LCD_CMD)
        self._write_byte(0x32, self.LCD_CMD)
        self._write_byte(0x06, self.LCD_CMD)
        self._write_byte(0x0C, self.LCD_CMD)
        self._write_byte(0x28, self.LCD_CMD)
        self._write_byte(0x01, self.LCD_CMD)
        time.sleep(0.005)

    def _write_byte(self, bits, mode):
        high = mode | (bits & 0xF0) | self.LCD_BACKLIGHT
        low = mode | ((bits << 4) & 0xF0) | self.LCD_BACKLIGHT
        self.bus.write_byte(self.address, high)
        self._toggle_enable(high)
        self.bus.write_byte(self.address, low)
        self._toggle_enable(low)

    def _toggle_enable(self, bits):
        time.sleep(0.0005)
        self.bus.write_byte(self.address, bits | self.ENABLE)
        time.sleep(0.0005)
        self.bus.write_byte(self.address, bits & ~self.ENABLE)
        time.sleep(0.0005)

    def write(self, line1, line2=""):
        self.line1 = line1
        self.line2 = line2
        self._write_byte(self.LCD_LINE_1, self.LCD_CMD)
        for char in line1.ljust(16)[:16]:
            self._write_byte(ord(char), self.LCD_CHR)
        self._write_byte(self.LCD_LINE_2, self.LCD_CMD)
        for char in line2.ljust(16)[:16]:
            self._write_byte(ord(char), self.LCD_CHR)
        if self._callback:
            self._callback(line1, line2)

    def clear(self):
        self._write_byte(0x01, self.LCD_CMD)
        time.sleep(0.005)
        self.line1 = ""
        self.line2 = ""
        if self._callback:
            self._callback("", "")

    def get_display(self):
        return self.line1, self.line2
