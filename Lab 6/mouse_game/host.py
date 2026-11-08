#!/usr/bin/env python3
"""Mouse Game host: MQTT inputs + keyboard -> one game loop -> browser.

    python host.py              # http://<this-machine>:5050
    python host.py --no-mqtt    # keyboard only, no broker connection
"""

import json
import os
import queue
import sys
import threading
import time
import uuid

import paho.mqtt.client as mqtt
from flask import Flask, render_template
from flask_socketio import SocketIO

import config
from game import DIRECTIONS, PLAYING, Game
from leaderboard import Leaderboard

HERE = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, template_folder=os.path.join(HERE, "templates"))
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

inputs = queue.Queue()
leaderboard = Leaderboard(os.path.join(HERE, "leaderboard.json"))
game = Game(on_finish=leaderboard.add)
state_lock = threading.Lock()
mqtt_status = {"connected": False}
pi_online = {role: None for role in config.PI_ROLES}   # None = not heard from yet
BUILD_ID = uuid.uuid4().hex   # pages from an older host run reload themselves


def parse_input(kind, data):
    """Return the validated input value, or None if the payload is malformed."""
    if not isinstance(data, dict):
        return None
    if kind == "aim":
        value = data.get("direction")
        return value if value in DIRECTIONS else None
    if kind == "attack":
        return "swing" if data.get("action") == "swing" else None
    if kind == "light":
        value = data.get("brightness")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return value if 0 <= value <= 100 else None
    return None


def full_state():
    with state_lock:
        state = game.snapshot()
    state["leaderboard"] = leaderboard.ranked()
    state["mqtt_connected"] = mqtt_status["connected"]
    state["pis"] = dict(pi_online)
    state["build"] = BUILD_ID
    return state


# ---------------------------------------------------------------- MQTT input

TOPIC_KINDS = {config.TOPIC_AIM: "aim", config.TOPIC_ATTACK: "attack",
               config.TOPIC_LIGHT: "light"}


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        mqtt_status["connected"] = True
        print(f"[MQTT] connected to {config.MQTT_BROKER}:{config.MQTT_PORT}")
        for topic in list(TOPIC_KINDS) + [f"{config.TOPIC_STATUS}/+"]:
            client.subscribe(topic, qos=0)
            print(f"[MQTT] subscribed {topic}")
    else:
        print(f"[MQTT] connection failed rc={rc}")


def on_disconnect(client, userdata, rc):
    mqtt_status["connected"] = False
    print(f"[MQTT] disconnected rc={rc}")
    # The host can no longer hear the Pis, so every connected one counts as dropped.
    for role, online in pi_online.items():
        if online:
            pi_online[role] = False
            inputs.put((time.monotonic(), "offline", role, False))


def on_status(role, data):
    online = data.get("online") if isinstance(data, dict) else None
    if role not in pi_online or not isinstance(online, bool):
        return
    was = pi_online[role]
    pi_online[role] = online
    print(f"[MQTT] {role} Pi {'online' if online else 'OFFLINE'}")
    if was is not False and not online:
        inputs.put((time.monotonic(), "offline", role, False))


def on_message(client, userdata, msg):
    received = time.monotonic()
    if msg.retain:
        return
    if msg.topic.startswith(config.TOPIC_STATUS + "/"):
        try:
            on_status(msg.topic.rsplit("/", 1)[1], json.loads(msg.payload.decode("utf-8")))
        except (ValueError, UnicodeDecodeError):
            pass
        return
    kind = TOPIC_KINDS.get(msg.topic)
    if kind is None:
        return
    try:
        data = json.loads(msg.payload.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        print(f"[MQTT] ignored malformed payload on {msg.topic}: {msg.payload!r}")
        return
    value = parse_input(kind, data)
    if value is None:
        print(f"[MQTT] ignored invalid payload on {msg.topic}: {data!r}")
        return
    print(f"[MQTT] {kind} {value}")
    pi_online[kind] = True
    inputs.put((received, kind, value, True))


def start_mqtt():
    client = mqtt.Client(f"mouse-host-{uuid.uuid4().hex[:8]}")
    client.username_pw_set(config.MQTT_USERNAME, config.MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.connect_async(config.MQTT_BROKER, config.MQTT_PORT, keepalive=60)
    client.loop_start()
    return client


# ---------------------------------------------------------------- browser I/O

@app.route("/")
def index():
    hit_sound = {"octave_groups": config.HIT_OCTAVE_GROUPS}
    return render_template("game.html", build=BUILD_ID, hit_sound=hit_sound)


@socketio.on("connect")
def handle_connect():
    socketio.emit("state", full_state())


@socketio.on("key_input")
def handle_key_input(data):
    received = time.monotonic()
    kind = data.get("kind") if isinstance(data, dict) else None
    value = parse_input(kind, data.get("payload")) if kind else None
    if value is not None:
        inputs.put((received, kind, value, config.COMBO_KEYBOARD))


@socketio.on("start_round")
def handle_start_round():
    inputs.put((time.monotonic(), "start", None, False))


# ---------------------------------------------------------------- game loop

def game_loop():
    period = 1.0 / config.SNAPSHOT_HZ
    next_snapshot = 0.0
    while True:
        try:
            item = inputs.get(timeout=0.01)
        except queue.Empty:
            item = None
        with state_lock:
            if item is None:
                game.advance(time.monotonic())
            else:
                received, kind, value, online = item
                if kind == "start":
                    game.advance(received)
                    game.start(received)
                elif kind == "offline":
                    game.pi_offline(value, received)
                else:
                    game.handle(kind, value, received, online=online)
            effects = game.drain_effects()
        if effects:
            socketio.emit("effects", effects)
        now = time.monotonic()
        if effects or now >= next_snapshot:
            socketio.emit("state", full_state())
            next_snapshot = now + period


def main():
    sys.stdout.reconfigure(line_buffering=True)
    use_mqtt = "--no-mqtt" not in sys.argv
    print("=" * 60)
    print("  Mouse Game host")
    print(f"  Open http://<this-machine-ip>:{config.HOST_PORT}")
    if use_mqtt:
        print(f"  Topics: {config.TOPIC_PREFIX}/{{aim,attack,light}}")
        start_mqtt()
    else:
        print("  MQTT disabled (keyboard only)")
    print("  Keys: arrows aim, Space swing, O light 100%, P light 0%, "
          "1-9 light 10-90%, Enter start")
    print("=" * 60)
    socketio.start_background_task(game_loop)
    socketio.run(app, host="0.0.0.0", port=config.HOST_PORT,
                 allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    main()
