import time
import math

try:
    import smbus2 as smbus
except ImportError:
    try:
        import smbus
    except ImportError:
        smbus = None


class Gyroscope:
    """
    MPU6050 Gyroscope/Accelerometer sensor driver.
    Communicates via I2C.
    """
    MPU6050_ADDR = 0x68
    PWR_MGMT_1 = 0x6B
    ACCEL_XOUT_H = 0x3B

    def __init__(self, bus_num=1, address=0x68):
        self.address = address
        if smbus is None:
            raise RuntimeError("smbus library not available")
        self.bus = smbus.SMBus(bus_num)
        # Wake up the MPU6050
        self.bus.write_byte_data(self.address, self.PWR_MGMT_1, 0)
        time.sleep(0.1)

    def _read_raw(self, reg):
        high = self.bus.read_byte_data(self.address, reg)
        low = self.bus.read_byte_data(self.address, reg + 1)
        value = (high << 8) | low
        if value >= 0x8000:
            value = -((65535 - value) + 1)
        return value

    def get_accel(self):
        """Returns (x, y, z) acceleration in m/s^2."""
        x = self._read_raw(self.ACCEL_XOUT_H) / 16384.0 * 9.81
        y = self._read_raw(self.ACCEL_XOUT_H + 2) / 16384.0 * 9.81
        z = self._read_raw(self.ACCEL_XOUT_H + 4) / 16384.0 * 9.81
        return round(x, 2), round(y, 2), round(z, 2)

    def is_significant_movement(self, threshold=5.0):
        """Check if movement exceeds threshold (deviation from gravity)."""
        x, y, z = self.get_accel()
        magnitude = math.sqrt(x**2 + y**2 + z**2)
        deviation = abs(magnitude - 9.81)
        return deviation > threshold, x, y, z


def run_gyroscope_loop(gyro, delay, callback, stop_event):
    """
    Continuously read gyroscope and call callback with (x, y, z, significant).
    """
    while not stop_event.is_set():
        time.sleep(delay)
        if stop_event.is_set():
            break
        try:
            significant, x, y, z = gyro.is_significant_movement()
            callback(x, y, z, significant)
        except Exception as e:
            print(f"[GSG] Read error: {e}")
