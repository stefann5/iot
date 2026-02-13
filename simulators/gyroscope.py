import time
import random
import math


def run_gyroscope_simulator(delay, callback, stop_event):
    """
    Simulates GSG gyroscope sensor behavior.
    Outputs acceleration/rotation values on X, Y, Z axes.
    Occasionally simulates significant movement (e.g., someone touching the icon).
    """
    # Base values (at rest)
    base_x, base_y, base_z = 0.0, 0.0, 9.8  # gravity on Z axis

    while not stop_event.is_set():
        time.sleep(delay)

        if stop_event.is_set():
            break

        # 10% chance of significant movement
        if random.random() < 0.10:
            # Significant movement - simulate shaking/tilting
            x = base_x + random.uniform(-15, 15)
            y = base_y + random.uniform(-15, 15)
            z = base_z + random.uniform(-10, 10)
            significant = True
        else:
            # Normal slight vibration/noise
            x = base_x + random.uniform(-0.5, 0.5)
            y = base_y + random.uniform(-0.5, 0.5)
            z = base_z + random.uniform(-0.3, 0.3)
            significant = False

        callback(x, y, z, significant)
