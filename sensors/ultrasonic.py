import RPi.GPIO as GPIO
import time

class UltrasonicSensor:
    """
    HC-SR04 Ultrasonic Distance Sensor class.
    """
    def __init__(self, trig_pin, echo_pin):
        self.trig_pin = trig_pin
        self.echo_pin = echo_pin
        
        GPIO.setup(self.trig_pin, GPIO.OUT)
        GPIO.setup(self.echo_pin, GPIO.IN)
        GPIO.output(self.trig_pin, GPIO.LOW)
        time.sleep(0.1)  # Let sensor settle
    
    def get_distance(self):
        """
        Measure distance in centimeters.
        Returns -1 if measurement fails.
        """
        # Send trigger pulse
        GPIO.output(self.trig_pin, GPIO.HIGH)
        time.sleep(0.00001)  # 10 microseconds
        GPIO.output(self.trig_pin, GPIO.LOW)
        
        # Wait for echo start
        timeout = time.time() + 0.1
        pulse_start = time.time()
        while GPIO.input(self.echo_pin) == GPIO.LOW:
            pulse_start = time.time()
            if pulse_start > timeout:
                return -1
        
        # Wait for echo end
        timeout = time.time() + 0.1
        pulse_end = time.time()
        while GPIO.input(self.echo_pin) == GPIO.HIGH:
            pulse_end = time.time()
            if pulse_end > timeout:
                return -1
        
        # Calculate distance
        pulse_duration = pulse_end - pulse_start
        # Speed of sound = 34300 cm/s, divide by 2 for round trip
        distance = pulse_duration * 17150
        
        # Sensor range is typically 2-400 cm
        if distance < 2 or distance > 400:
            return -1
        
        return round(distance, 2)


def run_ultrasonic_loop(ultrasonic, delay, callback, stop_event):
    """
    Runs the ultrasonic sensor monitoring loop.
    """
    while not stop_event.is_set():
        distance = ultrasonic.get_distance()
        if distance != -1:
            callback(distance)
        if stop_event.is_set():
            break
        time.sleep(delay)
