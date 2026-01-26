import os

# MQTT Configuration
MQTT_BROKER = os.environ.get("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))

# InfluxDB Configuration
INFLUXDB_URL = os.environ.get("INFLUXDB_URL", "http://localhost:8086")
INFLUXDB_TOKEN = os.environ.get("INFLUXDB_TOKEN", "my-super-secret-token")
INFLUXDB_ORG = os.environ.get("INFLUXDB_ORG", "pi1_org")
INFLUXDB_BUCKET = os.environ.get("INFLUXDB_BUCKET", "pi1_data")

# Flask Configuration
FLASK_HOST = os.environ.get("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.environ.get("FLASK_PORT", 5000))
FLASK_DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
