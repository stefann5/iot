import json
import asyncio
import threading
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from config import (
    MQTT_BROKER, MQTT_PORT,
    INFLUXDB_URL, INFLUXDB_TOKEN, INFLUXDB_ORG, INFLUXDB_BUCKET,
)


# ==================== WebSocket Manager ====================
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, data: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(data)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()
event_loop = None

# ==================== In-memory State ====================
sensor_states = {
    "DS1": {"value": 0, "name": "Door Sensor 1", "type": "button", "timestamp": None},
    "DS2": {"value": 0, "name": "Door Sensor 2", "type": "button", "timestamp": None},
    "DL": {"value": 0, "name": "Door Light", "type": "led", "timestamp": None},
    "DUS1": {"value": 0, "name": "Ultrasonic Sensor 1", "type": "ultrasonic", "timestamp": None},
    "DUS2": {"value": 0, "name": "Ultrasonic Sensor 2", "type": "ultrasonic", "timestamp": None},
    "DB": {"value": 0, "name": "Door Buzzer", "type": "buzzer", "timestamp": None},
    "DPIR1": {"value": 0, "name": "Door PIR Sensor 1", "type": "pir", "timestamp": None},
    "DPIR2": {"value": 0, "name": "Door PIR Sensor 2", "type": "pir", "timestamp": None},
    "DMS": {"value": "", "name": "Membrane Switch", "type": "membrane_switch", "timestamp": None},
    "RPIR1": {"value": 0, "name": "Bedroom PIR", "type": "pir", "timestamp": None},
    "RPIR2": {"value": 0, "name": "Master Bedroom PIR", "type": "pir", "timestamp": None},
    "RPIR3": {"value": 0, "name": "Living Room PIR", "type": "pir", "timestamp": None},
    # Feature 6-8 sensors
    "GSG": {"value": {"x": 0, "y": 0, "z": 9.8, "significant": False}, "name": "Gyroscope (Patron Saint)", "type": "gyroscope", "timestamp": None},
    "DHT1": {"value": {"temperature": 0, "humidity": 0}, "name": "Bedroom DHT", "type": "dht", "timestamp": None},
    "DHT2": {"value": {"temperature": 0, "humidity": 0}, "name": "Master Bedroom DHT", "type": "dht", "timestamp": None},
    "DHT3": {"value": {"temperature": 0, "humidity": 0}, "name": "Kitchen DHT", "type": "dht", "timestamp": None},
    "LCD": {"value": {"line1": "", "line2": ""}, "name": "Living Room LCD", "type": "lcd", "timestamp": None},
    "4SD": {"value": {"display": "00:00", "blinking": False}, "name": "Kitchen 4-Digit Display", "type": "segment_display", "timestamp": None},
    "BTN": {"value": 0, "name": "Kitchen Button", "type": "button", "timestamp": None},
}

alarm_state = {"state": "DISARMED", "reason": "", "timestamp": None}
people_state = {"count": 0, "last_direction": None, "timestamp": None}
timer_state = {"remaining": 0, "display": "00:00", "running": False, "blinking": False, "btn_seconds": 10, "timestamp": None}

# ==================== InfluxDB ====================
influx_client = None
write_api = None
query_api = None


def init_influxdb():
    global influx_client, write_api, query_api
    try:
        influx_client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
        write_api = influx_client.write_api(write_options=SYNCHRONOUS)
        query_api = influx_client.query_api()
        print(f"[InfluxDB] Connected to {INFLUXDB_URL}")
    except Exception as e:
        print(f"[InfluxDB] Failed to connect: {e}")


def write_to_influxdb(measurement, tags, fields, timestamp=None):
    if write_api is None:
        return
    try:
        point = Point(measurement)
        for k, v in tags.items():
            point = point.tag(k, str(v))
        for k, v in fields.items():
            point = point.field(k, v)
        if timestamp:
            point = point.time(datetime.fromtimestamp(timestamp))
        write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=point)
    except Exception as e:
        print(f"[InfluxDB] Write error: {e}")


# ==================== MQTT ====================
mqtt_client = mqtt.Client(client_id="pi1_fastapi_server")

MQTT_TOPICS = [
    ("pi1/sensors/#", 0),
    ("pi1/actuators/#", 0),
    ("pi1/alarm/#", 0),
    ("pi1/people/#", 0),
    ("pi1/timer/#", 0),
]


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[MQTT] Connected to {MQTT_BROKER}:{MQTT_PORT}")
        client.subscribe(MQTT_TOPICS)
    else:
        print(f"[MQTT] Connection failed: rc={rc}")


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
        topic = msg.topic
        topic_parts = topic.split("/")
        measurement_type = topic_parts[-1] if len(topic_parts) > 2 else "unknown"

        readings = payload.get("readings", [])
        pi_id = payload.get("pi_id", "PI1")
        device_name = payload.get("device_name", "unknown")

        for reading in readings:
            sensor_id = reading.get("sensor_id", "unknown")
            value = reading.get("value")
            simulated = reading.get("simulated", False)
            unit = reading.get("unit", "")
            timestamp = reading.get("timestamp")

            # Update in-memory state
            if sensor_id in sensor_states:
                sensor_states[sensor_id]["value"] = value
                sensor_states[sensor_id]["timestamp"] = timestamp

            # Handle alarm state (numeric: 0=disarmed, 1=alarm, 2=armed, 3=arming)
            if measurement_type == "state" and "alarm" in topic:
                state_map = {0: "DISARMED", 1: "ALARM", 2: "ARMED", 3: "ARMING"}
                if isinstance(value, (int, float)):
                    alarm_state["state"] = state_map.get(int(value), "DISARMED")
                alarm_state["timestamp"] = timestamp

            # Handle alarm events
            if measurement_type == "event" and "alarm" in topic:
                event_val = str(value)
                if event_val == "armed":
                    alarm_state["state"] = "ARMED"
                elif event_val == "arming":
                    alarm_state["state"] = "ARMING"
                elif event_val == "alarm_activated":
                    alarm_state["state"] = "ALARM"
                elif event_val == "alarm_deactivated":
                    alarm_state["state"] = "DISARMED"
                    alarm_state["reason"] = ""
                alarm_state["timestamp"] = timestamp

            # Handle alarm reason
            if measurement_type == "reason" and "alarm" in topic:
                alarm_state["reason"] = str(value)
                alarm_state["timestamp"] = timestamp

            # Handle people count
            if measurement_type == "count" and "people" in topic:
                people_state["count"] = int(value) if isinstance(value, (int, float)) else 0
                people_state["timestamp"] = timestamp

            if measurement_type == "event" and "people" in topic:
                people_state["last_direction"] = str(value)
                people_state["timestamp"] = timestamp

            # Handle gyroscope data (Feature 6)
            if measurement_type == "gyroscope" and sensor_id == "GSG":
                try:
                    gsg_data = json.loads(value) if isinstance(value, str) else value
                    sensor_states["GSG"]["value"] = gsg_data
                    sensor_states["GSG"]["timestamp"] = timestamp
                except:
                    pass

            # Handle DHT data (Feature 7)
            if measurement_type == "dht" and sensor_id in ["DHT1", "DHT2", "DHT3"]:
                try:
                    dht_data = json.loads(value) if isinstance(value, str) else value
                    sensor_states[sensor_id]["value"] = dht_data
                    sensor_states[sensor_id]["timestamp"] = timestamp
                except:
                    pass

            # Handle LCD data (Feature 7)
            if measurement_type == "lcd" and sensor_id == "LCD":
                try:
                    lcd_data = json.loads(value) if isinstance(value, str) else value
                    sensor_states["LCD"]["value"] = lcd_data
                    sensor_states["LCD"]["timestamp"] = timestamp
                except:
                    pass

            # Handle 4SD display data (Feature 8)
            if measurement_type == "segment_display" and sensor_id == "4SD":
                try:
                    sd_data = json.loads(value) if isinstance(value, str) else value
                    sensor_states["4SD"]["value"] = sd_data
                    sensor_states["4SD"]["timestamp"] = timestamp
                except:
                    pass

            # Handle timer state (Feature 8)
            if "timer" in topic and measurement_type == "state":
                try:
                    ts_data = json.loads(value) if isinstance(value, str) else value
                    timer_state["remaining"] = ts_data.get("remaining", 0)
                    timer_state["display"] = ts_data.get("display", "00:00")
                    timer_state["running"] = ts_data.get("running", False)
                    timer_state["blinking"] = ts_data.get("blinking", False)
                    timer_state["timestamp"] = timestamp
                except:
                    pass

            # Write to InfluxDB
            tags = {
                "pi_id": pi_id,
                "device_name": device_name,
                "sensor_id": sensor_id,
                "simulated": str(simulated).lower(),
                "unit": unit,
            }
            if isinstance(value, (int, float)):
                fields = {"value": float(value)}
            else:
                fields = {"value_str": str(value), "value": 1.0}

            write_to_influxdb(measurement_type, tags, fields, timestamp)

        # Broadcast to WebSocket clients
        ws_data = {
            "type": measurement_type,
            "topic": topic,
            "readings": readings,
            "alarm": alarm_state,
            "people": people_state,
            "timer": timer_state,
        }
        if event_loop:
            asyncio.run_coroutine_threadsafe(manager.broadcast(ws_data), event_loop)

    except json.JSONDecodeError:
        pass
    except Exception as e:
        print(f"[MQTT] Error: {e}")


mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message


def start_mqtt():
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        mqtt_client.loop_start()
    except Exception as e:
        print(f"[MQTT] Failed: {e}")


# ==================== FastAPI App ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    global event_loop
    event_loop = asyncio.get_event_loop()
    init_influxdb()
    start_mqtt()
    print("[Server] PI1 FastAPI server started")
    yield
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    if influx_client:
        influx_client.close()
    print("[Server] Shutdown complete")


app = FastAPI(title="PI1 Smart Home API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== Request Models ====================
class AlarmDeactivateRequest(BaseModel):
    pin: str


class ActuatorRequest(BaseModel):
    action: str


class TimerRequest(BaseModel):
    action: str
    seconds: int = 0


# ==================== Routes ====================
@app.get("/api/status")
async def get_status():
    return {
        "sensors": sensor_states,
        "alarm": alarm_state,
        "people": people_state,
        "timer": timer_state,
    }


@app.get("/api/alarm/status")
async def get_alarm_status():
    return alarm_state


@app.post("/api/alarm/arm")
async def arm_alarm():
    mqtt_client.publish("pi1/commands/alarm", json.dumps({"action": "arm"}))
    return {"status": "ok", "message": "Arm command sent"}


@app.post("/api/alarm/deactivate")
async def deactivate_alarm(req: AlarmDeactivateRequest):
    mqtt_client.publish("pi1/commands/alarm",
                        json.dumps({"action": "deactivate", "pin": req.pin}))
    return {"status": "ok", "message": "Deactivate command sent"}


@app.get("/api/people-count")
async def get_people_count():
    return people_state


@app.post("/api/led")
async def control_led(req: ActuatorRequest):
    mqtt_client.publish("pi1/commands/led", json.dumps({"action": req.action}))
    return {"status": "ok"}


@app.post("/api/buzzer")
async def control_buzzer(req: ActuatorRequest):
    mqtt_client.publish("pi1/commands/buzzer", json.dumps({"action": req.action}))
    return {"status": "ok"}


@app.get("/api/timer")
async def get_timer_status():
    return timer_state


@app.post("/api/timer")
async def control_timer(req: TimerRequest):
    payload = {"action": req.action}
    if req.action in ["set_time", "add_seconds", "set_btn_seconds"]:
        payload["seconds"] = req.seconds
    mqtt_client.publish("pi1/commands/timer", json.dumps(payload))
    return {"status": "ok", "action": req.action}


@app.get("/api/alarm-events")
async def get_alarm_events():
    if query_api is None:
        return {"events": []}
    try:
        query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
          |> range(start: -24h)
          |> filter(fn: (r) => r["_measurement"] == "event")
          |> filter(fn: (r) => r["sensor_id"] == "ALARM")
          |> sort(columns: ["_time"], desc: true)
          |> limit(n: 50)
        '''
        tables = query_api.query(query, org=INFLUXDB_ORG)
        events = []
        for table in tables:
            for record in table.records:
                events.append({
                    "time": str(record.get_time()),
                    "event": record.get_value(),
                    "field": record.get_field(),
                })
        return {"events": events}
    except Exception as e:
        print(f"[InfluxDB] Query error: {e}")
        return {"events": []}


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "mqtt": mqtt_client.is_connected(),
        "influxdb": influx_client is not None,
    }


# ==================== WebSocket ====================
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    # Send current state on connect
    try:
        await websocket.send_json({
            "type": "initial_state",
            "sensors": sensor_states,
            "alarm": alarm_state,
            "people": people_state,
            "timer": timer_state,
        })
    except Exception:
        pass

    try:
        while True:
            data = await websocket.receive_text()
            # Handle client messages if needed
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
