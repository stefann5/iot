import threading
from settings import load_settings
from components.button import run_button
from components.led import run_led
from components.ultrasonic import run_ultrasonic
from components.buzzer import run_buzzer
from components.pir import run_pir
from components.membrane_switch import run_membrane_switch
from mqtt_publisher import init_publisher, shutdown_publisher
import time

try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
except:
    pass


def print_menu(device_info):
    print("\n" + "="*40)
    print(f"{device_info.get('pi_id', 'PI1')} - {device_info.get('device_name', 'Door Control System')}")
    print(f"Location: {device_info.get('location', 'unknown')}")
    print("="*40)
    print("Commands:")
    print("  led on     - Turn door light ON")
    print("  led off    - Turn door light OFF")
    print("  buzz on    - Turn buzzer ON")
    print("  buzz off   - Turn buzzer OFF")
    print("  buzz beep  - Beep buzzer (short)")
    print("  exit       - Exit application")
    print("="*40)


if __name__ == "__main__":
    print('Starting PI1 Smart Home App')
    settings = load_settings()

    # Extract device info for display
    device_info = settings.get('device_info', {
        'pi_id': 'PI1',
        'device_name': 'DoorController',
        'location': 'unknown'
    })

    print(f"Device: {device_info.get('pi_id')} - {device_info.get('device_name')}")
    print(f"Location: {device_info.get('location')}")

    threads = []
    stop_event = threading.Event()

    # Initialize MQTT Publisher with batch daemon
    print("\nInitializing MQTT Publisher...")
    mqtt_publisher = init_publisher(settings)

    actuator_controllers = {}

    try:
        # Initialize Door Sensor (Button) - DS1
        if 'DS1' in settings:
            ds1_settings = settings['DS1']
            run_button(ds1_settings, threads, stop_event, "DS1")

        # Initialize Door Light (LED) - DL
        if 'DL' in settings:
            dl_settings = settings['DL']
            led_controller = run_led(dl_settings, threads, stop_event, "DL")
            actuator_controllers['led'] = led_controller

        # Initialize Door Ultrasonic Sensor - DUS1
        if 'DUS1' in settings:
            dus1_settings = settings['DUS1']
            run_ultrasonic(dus1_settings, threads, stop_event, "DUS1")

        # Initialize Door Buzzer - DB
        if 'DB' in settings:
            db_settings = settings['DB']
            buzzer_controller = run_buzzer(db_settings, threads, stop_event, "DB")
            actuator_controllers['buzzer'] = buzzer_controller

        # Initialize Door PIR Motion Sensor - DPIR1
        if 'DPIR1' in settings:
            dpir1_settings = settings['DPIR1']
            run_pir(dpir1_settings, threads, stop_event, "DPIR1")

        # Initialize Door Membrane Switch - DMS
        if 'DMS' in settings:
            dms_settings = settings['DMS']
            run_membrane_switch(dms_settings, threads, stop_event, "DMS")

        # Console control loop
        time.sleep(1)
        print_menu(device_info)

        while True:
            try:
                command = input("\nEnter command: ").strip().lower()

                if command == "exit":
                    break
                elif command == "led on":
                    if 'led' in actuator_controllers and actuator_controllers['led']:
                        actuator_controllers['led'].turn_on()
                    else:
                        print("LED controller not available")
                elif command == "led off":
                    if 'led' in actuator_controllers and actuator_controllers['led']:
                        actuator_controllers['led'].turn_off()
                    else:
                        print("LED controller not available")
                elif command == "buzz on":
                    if 'buzzer' in actuator_controllers and actuator_controllers['buzzer']:
                        actuator_controllers['buzzer'].turn_on()
                    else:
                        print("Buzzer controller not available")
                elif command == "buzz off":
                    if 'buzzer' in actuator_controllers and actuator_controllers['buzzer']:
                        actuator_controllers['buzzer'].turn_off()
                    else:
                        print("Buzzer controller not available")
                elif command == "buzz beep":
                    if 'buzzer' in actuator_controllers and actuator_controllers['buzzer']:
                        actuator_controllers['buzzer'].beep()
                    else:
                        print("Buzzer controller not available")
                elif command == "menu":
                    print_menu(device_info)
                else:
                    print("Unknown command. Type 'menu' for available commands.")

            except EOFError:
                break

    except KeyboardInterrupt:
        print('\nStopping app')
    finally:
        print("\nShutting down...")
        stop_event.set()

        # Stop MQTT publisher
        print("Stopping MQTT publisher...")
        shutdown_publisher()

        # Wait for threads to finish
        for t in threads:
            t.join(timeout=2)

        try:
            GPIO.cleanup()
        except:
            pass
        print("Application stopped.")
