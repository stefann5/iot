# PI1 - Smart Home Door Control System

A Raspberry Pi-based smart home security system with motion detection, people counting, door monitoring, and alarm management. Supports hardware simulation, MQTT messaging, InfluxDB storage, Grafana visualization, and a real-time Angular web dashboard.

## Implemented Features

### Feature 1: Motion-activated Door Light
When **DPIR1** detects motion, **DL** (door light) turns on for 10 seconds. Timer resets on repeated motion.

### Feature 2: Enter/Exit Detection + People Counting
When **DPIR1** detects motion, **DUS1** ultrasonic distance trend is analyzed to determine if a person is entering or exiting. Same logic applies to **DPIR2** + **DUS2**. People count is tracked (minimum 0).

### Feature 3: Unlocked Door Alarm
If **DS1** or **DS2** stays open for longer than 5 seconds, **ALARM** triggers regardless of armed/disarmed state. Simulates an unlocked/unattended door. Alarm clears with PIN entry.

### Feature 4: DMS Security Alarm with Delayed Arming
- Pressing `A` on **DMS** starts a 10-second arming countdown (**ARMING** state), then transitions to **ARMED**.
- While **ARMED**, door opening on **DS1**/**DS2** starts a grace period for PIN entry on **DMS**.
- If correct PIN not entered in time, **ALARM** triggers.
- PIN (`1234#`) deactivates from any state (ARMING, ARMED, ALARM).

### Feature 5: Intruder Detection (Empty Facility)
When people count is 0 and any of **RPIR1-3** (room PIR sensors) detects motion, **ALARM** triggers immediately. Protects against intruders when facility is empty.

### Alarm System
- States: `DISARMED` → `ARMING` (10s delay) → `ARMED` → `ALARM`
- During ALARM: **DB** (buzzer) ON + **DL** (LED) ON
- Events stored in InfluxDB, displayed in Grafana, notified via web app
- Deactivated by PIN on **DMS** or via web application

## Components

| Code  | Name                    | Function                          |
|-------|-------------------------|-----------------------------------|
| DS1   | Door Sensor 1 (Button)  | Door open/close monitoring        |
| DS2   | Door Sensor 2 (Button)  | Second door monitoring            |
| DL    | Door Light (LED)        | Motion-activated + alarm indicator|
| DUS1  | Ultrasonic Sensor 1     | Distance for enter/exit detection |
| DUS2  | Ultrasonic Sensor 2     | Second door distance detection    |
| DB    | Door Buzzer             | Alarm audio indicator             |
| DPIR1 | Door PIR Sensor 1       | Motion at door 1                  |
| DPIR2 | Door PIR Sensor 2       | Motion at door 2                  |
| DMS   | Membrane Switch (4x4)   | PIN entry, alarm control          |
| RPIR1 | Bedroom PIR Sensor      | Intruder detection                |
| RPIR2 | Master Bedroom PIR      | Intruder detection                |
| RPIR3 | Living Room PIR         | Intruder detection                |

## Prerequisites

- Python 3.8+
- Docker and Docker Compose
- pip

## Quick Start

### 1. Start All Services

```bash
docker-compose up -d --build
```

This starts:
- **Mosquitto MQTT Broker** - localhost:1883
- **InfluxDB** - localhost:8086
- **Grafana** - localhost:3000 (admin/admin)
- **FastAPI Server** - localhost:8000
- **Angular Frontend** - localhost:4200

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the PI1 Device Script

```bash
python main.py
```

### 4. Access the Web Dashboard

Open http://localhost:4200

### 5. Access Grafana

Open http://localhost:3000 (login: admin/admin)

## Console Commands

| Command      | Description                      |
|--------------|----------------------------------|
| `arm`        | Arm alarm system (immediate)     |
| `disarm`     | Disarm (enter PIN when prompted) |
| `led on/off` | Control door light               |
| `buzz on/off/beep` | Control buzzer              |
| `status`     | Show system status               |
| `exit`       | Exit application                 |

## DMS Keypad Controls

| Key   | Action                             |
|-------|------------------------------------|
| `0-9` | Add digit to PIN buffer            |
| `#`   | Submit PIN (deactivate alarm)      |
| `*`   | Clear PIN buffer                   |
| `A`   | Arm system (10-second delay)       |

Default PIN: **1234**

## Configuration

Edit `settings.json` to configure sensors. Set `"simulated": false` for real hardware:

```json
{
    "alarm_pin": "1234",
    "DS1": {
        "simulated": true,
        "pin": 17,
        "name": "Door Sensor 1",
        "type": "button"
    }
}
```

## Architecture

```
┌─────────────────┐     MQTT      ┌─────────────────┐
│   PI1 Device    │──────────────>│    Mosquitto    │
│   (main.py)     │<──────────────│   MQTT Broker   │
└─────────────────┘   commands    └────────┬────────┘
                                           │
                                           v
                                  ┌─────────────────┐
                                  │  FastAPI Server  │──> InfluxDB
                                  │   (app.py)       │
                                  └────────┬────────┘
                                           │ WebSocket
                                           v
                                  ┌─────────────────┐
                                  │ Angular Frontend │──> Grafana (iframe)
                                  │   (PrimeNG)      │
                                  └─────────────────┘
```

## MQTT Topics

| Topic                          | Description                        |
|--------------------------------|------------------------------------|
| `pi1/sensors/button`           | DS1, DS2 door state                |
| `pi1/sensors/ultrasonic`       | DUS1, DUS2 distance readings       |
| `pi1/sensors/pir`              | DPIR1, DPIR2, RPIR1-3 motion      |
| `pi1/sensors/membrane_switch`  | DMS key presses                    |
| `pi1/actuators/led`            | LED state changes                  |
| `pi1/actuators/buzzer`         | Buzzer state changes               |
| `pi1/alarm/state`              | Alarm state (0-3)                  |
| `pi1/alarm/event`              | Alarm events                       |
| `pi1/alarm/reason`             | Alarm trigger reason               |
| `pi1/people/count`             | People count                       |
| `pi1/people/event`             | Enter/exit direction               |
| `pi1/commands/#`               | Web app commands                   |

## Stopping Services

```bash
# Stop the PI1 device
# Press Ctrl+C or type 'exit'

# Stop Docker services
docker-compose down
```
