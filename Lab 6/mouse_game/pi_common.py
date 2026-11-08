"""MQTT publishing shared by the three Pi controllers (Lab 6 broker settings)."""

import json
import sys
import time
import uuid

import paho.mqtt.client as mqtt

import config

sys.stdout.reconfigure(line_buffering=True)

class Publisher:
    """MQTT publisher for one Pi role.

    The status topic carries {"online": true} on connect and {"online": false}
    on a clean exit; the broker sends the same "false" as a last will if the
    connection drops, so the host can break the combo.
    """

    def __init__(self, role):
        self.role = role
        self.status_topic = f"{config.TOPIC_STATUS}/{role}"
        self.client = mqtt.Client(f"mouse-{role}-{uuid.uuid4().hex[:8]}")
        self.client.username_pw_set(config.MQTT_USERNAME, config.MQTT_PASSWORD)
        self.client.will_set(self.status_topic, json.dumps({"online": False}), qos=1, retain=False)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.connect_async(config.MQTT_BROKER, config.MQTT_PORT,
                                  keepalive=config.PI_KEEPALIVE)
        self.client.loop_start()

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"[MQTT] connected to {config.MQTT_BROKER}:{config.MQTT_PORT}")
            client.publish(self.status_topic, json.dumps({"online": True}), qos=1, retain=False)
        else:
            print(f"[MQTT] connection failed rc={rc}")

    @staticmethod
    def _on_disconnect(client, userdata, rc):
        print(f"[MQTT] disconnected rc={rc} (actions are dropped until reconnect)")

    def wait_connected(self, timeout=5.0):
        deadline = time.monotonic() + timeout
        while not self.client.is_connected() and time.monotonic() < deadline:
            time.sleep(0.1)
        return self.client.is_connected()

    def publish(self, topic, payload):
        if not self.client.is_connected():
            print(f"[MQTT] offline, dropped {payload}")
            return False
        self.client.publish(topic, json.dumps(payload), qos=0, retain=False)
        print(f"[MQTT] {topic} {payload}")
        return True

    def close(self):
        if self.client.is_connected():
            self.client.publish(self.status_topic, json.dumps({"online": False}),
                                qos=1, retain=False).wait_for_publish(timeout=2)
        self.client.loop_stop()
        self.client.disconnect()
