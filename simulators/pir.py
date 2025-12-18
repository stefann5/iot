import time
import random

def run_pir_simulator(delay, callback, stop_event):
    """
    Simulates PIR motion sensor behavior.
    Randomly detects motion.
    """
    while not stop_event.is_set():
        time.sleep(delay)
        
        if stop_event.is_set():
            break
        
        # 30% chance of detecting motion
        motion_detected = random.random() < 0.3
        callback(motion_detected)
