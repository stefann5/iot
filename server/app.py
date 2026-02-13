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
    "DS1": {"value": 0, "name": "Door Sensor", "type": "button", "timestamp": None},
    "DL": {"value": 0, "name": "Door Light", "type": "led", "timestamp": None},
    "DUS1": {"value": 0, "name": "Ultrasonic Sensor", "type": "ultrasonic", "timestamp": None},
    "DB": {"value": 0, "name": "Door Buzzer", "type": "buzzer", "timestamp": None},
    "DPIR1": {"value": 0, "name": "PIR Motion Sensor", "type": "pir", "timestamp": None},
    "DMS": {"value": "", "name": "Membrane Switch", "type": "membrane_switch", "timestamp": None},
}

alarm_state = {"state": "DISARMED", "timestamp": None}
people_state = {"count": 0, "last_direction": None, "timestamp": None}

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

            # Handle alarm state
            if measurement_type == "state" and "alarm" in topic:
                alarm_state["state"] = "ALARM" if value == 1 else "DISARMED"
                alarm_state["timestamp"] = timestamp

            # Handle alarm events
            if measurement_type == "event" and "alarm" in topic:
                event_val = str(value)
                if event_val == "armed":
                    alarm_state["state"] = "ARMED"
                elif event_val == "alarm_activated":
                    alarm_state["state"] = "ALARM"
                elif event_val == "alarm_deactivated":
                    alarm_state["state"] = "DISARMED"
                alarm_state["timestamp"] = timestamp

            # Handle people count
            if measurement_type == "count" and "people" in topic:
                people_state["count"] = int(value) if isinstance(value, (int, float)) else 0
                people_state["timestamp"] = timestamp

            if measurement_type == "event" and "people" in topic:
                people_state["last_direction"] = str(value)
                people_state["timestamp"] = timestamp

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


# ==================== Routes ====================
@app.get("/api/status")
async def get_status():
    return {
        "sensors": sensor_states,
        "alarm": alarm_state,
        "people": people_state,
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
