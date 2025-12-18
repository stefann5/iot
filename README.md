# PI1 - Smart Home Door Control System

A Raspberry Pi-based door control system with support for hardware simulation.

## Components

- **DS1** - Door Sensor (Button)
- **DL** - Door Light (LED)
- **DUS1** - Door Ultrasonic Sensor
- **DB** - Door Buzzer
- **DPIR1** - PIR Motion Sensor
- **DMS** - Membrane Switch Keypad

## Usage

```bash
python main.py
```

## Configuration

Edit `settings.json` to configure components. Set `"simulated": true` to run without hardware.
