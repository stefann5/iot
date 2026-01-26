# PI1 - Smart Home Door Control System

A Raspberry Pi-based door control system with support for hardware simulation, MQTT data publishing, and Grafana visualization.

## Components

- **DS1** - Door Sensor (Button)
- **DL** - Door Light (LED)
- **DUS1** - Door Ultrasonic Sensor
- **DB** - Door Buzzer
- **DPIR1** - PIR Motion Sensor
- **DMS** - Membrane Switch Keypad

## Prerequisites

- Python 3.8+
- Docker and Docker Compose
- pip

## Quick Start

### 1. Start Infrastructure Services

Start Mosquitto (MQTT broker), InfluxDB, and Grafana using Docker Compose:

```bash
docker-compose up -d
```

This starts:
- **Mosquitto MQTT Broker** - localhost:1883
- **InfluxDB** - localhost:8086
- **Grafana** - localhost:3000

### 2. Install Python Dependencies

For the PI1 device script:
```bash
pip install -r requirements.txt
```

For the server (if running locally without Docker):
```bash
pip install -r server/requirements.txt
```

### 3. Run the PI1 Device Script

```bash
python main.py
```

The script will:
- Initialize all sensors/actuators (simulated or real based on config)
- Connect to MQTT broker
- Start a daemon thread that publishes sensor data in batches every 5 seconds
- Provide a console interface for controlling actuators

### 4. Run the Data Server

**Option A: Using Docker (recommended)**
The server is included in docker-compose and starts automatically.

**Option B: Run locally**
```bash
cd server
python app.py
```

### 5. Access Grafana Dashboard

1. Open http://localhost:3000
2. Login with `admin` / `admin`
3. Navigate to Dashboards > "PI1 - Door Control System Sensors"

## Console Commands

When running `main.py`, use these commands:

| Command     | Description              |
|-------------|--------------------------|
| `led on`    | Turn door light ON       |
| `led off`   | Turn door light OFF      |
| `buzz on`   | Turn buzzer ON           |
| `buzz off`  | Turn buzzer OFF          |
| `buzz beep` | Short beep               |
| `menu`      | Show available commands  |
| `exit`      | Exit application         |

## Configuration

Edit `settings.json` to configure the system:

```json
{
    "device_info": {
        "pi_id": "PI1",
        "device_name": "DoorController",
        "location": "front_door"
    },
    "mqtt": {
        "broker_host": "localhost",
        "broker_port": 1883,
        "batch_interval": 5
    },
    "DS1": {
        "simulated": true,
        "pin": 17
    }
    ...
}
```

### Key Settings

- `device_info.pi_id` - Unique identifier for this PI device
- `device_info.device_name` - Human-readable device name
- `mqtt.broker_host` - MQTT broker address
- `mqtt.batch_interval` - How often to send batched data (seconds)
- `[SENSOR].simulated` - Set to `true` to simulate, `false` for real hardware

## Architecture

```
┌─────────────────┐     MQTT      ┌─────────────────┐
│   PI1 Device    │──────────────>│    Mosquitto    │
│   (main.py)     │               │   MQTT Broker   │
└─────────────────┘               └────────┬────────┘
                                           │
                                           v
                                  ┌─────────────────┐
                                  │  Flask Server   │
                                  │   (app.py)      │
                                  └────────┬────────┘
                                           │
                                           v
                                  ┌─────────────────┐
                                  │    InfluxDB     │
                                  │   (time-series) │
                                  └────────┬────────┘
                                           │
                                           v
                                  ┌─────────────────┐
                                  │     Grafana     │
                                  │  (visualization)│
                                  └─────────────────┘
```

## MQTT Topics

| Topic                       | Description                |
|-----------------------------|----------------------------|
| `pi1/sensors/button`        | Door sensor state          |
| `pi1/sensors/ultrasonic`    | Distance measurements      |
| `pi1/sensors/pir`           | Motion detection           |
| `pi1/sensors/membrane_switch` | Keypad key presses       |
| `pi1/actuators/led`         | LED state changes          |
| `pi1/actuators/buzzer`      | Buzzer state changes       |

## Stopping Services

```bash
# Stop the PI1 device
# Press Ctrl+C or type 'exit'

# Stop Docker services
docker-compose down
```
