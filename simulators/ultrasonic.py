import time
import random

def generate_distance(initial_distance=100):
    """
    Generates simulated distance readings.
    Simulates object approaching and moving away.
    """
    distance = initial_distance
    direction = -1  # -1 = approaching, 1 = moving away
    
    while True:
        # Change distance
        change = random.uniform(0, 10) * direction
        distance += change
        
        # Bound distance (2cm to 400cm typical for HC-SR04)
        if distance < 2:
            distance = 2
            direction = 1
        elif distance > 400:
            distance = 400
            direction = -1
        
        # Randomly change direction occasionally
        if random.random() > 0.9:
            direction *= -1
        
        yield distance


def run_ultrasonic_simulator(delay, callback, stop_event):
    """
    Runs the ultrasonic sensor simulator loop.
    """
    for distance in generate_distance():
        time.sleep(delay)
        callback(distance)
        if stop_event.is_set():
            break
