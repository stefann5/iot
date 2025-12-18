import time
import random

# 4x4 Membrane Switch keypad layout
KEYPAD = [
    ['1', '2', '3', 'A'],
    ['4', '5', '6', 'B'],
    ['7', '8', '9', 'C'],
    ['*', '0', '#', 'D']
]

def run_membrane_switch_simulator(callback, stop_event):
    """
    Simulates membrane switch (4x4 keypad) behavior.
    Randomly simulates key presses.
    """
    all_keys = [key for row in KEYPAD for key in row]
    
    while not stop_event.is_set():
        # Random delay between key presses (3-10 seconds)
        delay = random.uniform(3, 10)
        time.sleep(delay)
        
        if stop_event.is_set():
            break
        
        # 50% chance of a key press
        if random.random() > 0.5:
            key = random.choice(all_keys)
            callback(key)
