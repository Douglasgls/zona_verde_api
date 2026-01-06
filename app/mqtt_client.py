import paho.mqtt.client as mqtt

BROKER_HOST = "localhost"
BROKER_PORT = 1883

mqttc = mqtt.Client()


def on_connect(client, userdata, flags, reason_code, properties=None):
    print(f"Connected with result code {reason_code}")


mqttc.on_connect = on_connect
