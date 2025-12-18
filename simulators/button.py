import time
import random

def run_button_simulator(callback, stop_event):
    """
    Simulates door sensor (button) behavior.
    Randomly changes between pressed (door closed) and released (door open).
    """
    current_state = False  # Start with door open
    
    while not stop_event.is_set():
        # Random delay between state changes (5-15 seconds)
        delay = random.uniform(5, 15)
        time.sleep(delay)
        
        if stop_event.is_set():
            break
        
        # Toggle state randomly (simulating door opening/closing)
        if random.random() > 0.5:
            current_state = not current_state
            callback(current_state)
