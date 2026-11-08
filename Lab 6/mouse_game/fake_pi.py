#!/usr/bin/env python3
"""Send or watch Mouse Game MQTT messages without any Pi hardware.

    python fake_pi.py aim up          # up / down / left / right
    python fake_pi.py attack
    python fake_pi.py light 70        # brightness 0-100
    python fake_pi.py offline attack  # pretend that Pi dropped (aim / attack / light)
    python fake_pi.py listen          # print every message on the three topics
"""

import json
import sys
import time

import paho.mqtt.client as mqtt

import config
from pi_common import Publisher

USAGE = __doc__


def listen():
    def on_connect(client, userdata, flags, rc):
        print(f"[MQTT] connected rc={rc}; listening on {config.TOPIC_PREFIX}/#")
        client.subscribe(f"{config.TOPIC_PREFIX}/#")

    def on_message(client, userdata, msg):
        print(f"{time.strftime('%H:%M:%S')}  {msg.topic}  {msg.payload.decode(errors='replace')}"
              f"{'  (retained)' if msg.retain else ''}")

    client = mqtt.Client()
    client.username_pw_set(config.MQTT_USERNAME, config.MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(config.MQTT_BROKER, config.MQTT_PORT, keepalive=60)
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        pass


def main(args):
    if not args:
        print(USAGE)
        return 1
    cmd = args[0]
    if cmd == "listen":
        listen()
        return 0
    if cmd == "aim" and len(args) == 2 and args[1] in ("up", "down", "left", "right"):
        topic, payload = config.TOPIC_AIM, {"direction": args[1]}
    elif cmd == "attack":
        topic, payload = config.TOPIC_ATTACK, {"action": "swing"}
    elif cmd == "light" and len(args) == 2 and args[1].isdigit() and int(args[1]) <= 100:
        topic, payload = config.TOPIC_LIGHT, {"brightness": int(args[1])}
    elif cmd == "offline" and len(args) == 2 and args[1] in config.PI_ROLES:
        topic, payload = f"{config.TOPIC_STATUS}/{args[1]}", {"online": False}
    else:
        print(USAGE)
        return 1
    publisher = Publisher("fake")
    if not publisher.wait_connected():
        print("Could not reach the broker.", file=sys.stderr)
        return 1
    publisher.publish(topic, payload)
    time.sleep(0.3)
    publisher.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
