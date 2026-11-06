"""Shared settings for the Mouse Game host and the three Pi controllers.

Every value can be overridden with an environment variable of the same name,
e.g. `MOUSE_TEAM=team3 python host.py`.
"""

import os


def _env(name, default):
    raw = os.environ.get(name)
    if raw is None:
        return default
    if isinstance(default, bool):
        return raw.strip().lower() in ("1", "true", "yes", "on")
    return type(default)(raw)


# MQTT (same broker and login as Lab 6 Part A/B)
MQTT_BROKER = _env("MQTT_BROKER", "farlab.infosci.cornell.edu")
MQTT_PORT = _env("MQTT_PORT", 1883)
MQTT_USERNAME = _env("MQTT_USERNAME", "idd")
MQTT_PASSWORD = _env("MQTT_PASSWORD", "device@theFarm")
MOUSE_TEAM = _env("MOUSE_TEAM", "mousegame")

TOPIC_PREFIX = f"IDD/{MOUSE_TEAM}/mouse-game"
TOPIC_AIM = f"{TOPIC_PREFIX}/aim"
TOPIC_ATTACK = f"{TOPIC_PREFIX}/attack"
TOPIC_LIGHT = f"{TOPIC_PREFIX}/light"
TOPIC_STATUS = f"{TOPIC_PREFIX}/status"   # + "/aim", "/attack", "/light"
PI_ROLES = ("aim", "attack", "light")

# Host web server
HOST_PORT = _env("HOST_PORT", 5050)
SNAPSHOT_HZ = _env("SNAPSHOT_HZ", 15.0)

# Game rules (MOUSE_GAME.md section 2)
ROWS = 3
COLS = 3
ROUND_SECONDS = _env("ROUND_SECONDS", 30.0)
START_CHEESE = _env("START_CHEESE", 3)
# Spawn interval is interpolated: SPAWN_DARK at 0% brightness, SPAWN_LIT at 100%.
SPAWN_LIT = _env("SPAWN_LIT", 2.8)
SPAWN_DARK = _env("SPAWN_DARK", 0.4)
# Brightness at or above this counts as "light on" for the stun transition.
LIGHT_ON_THRESHOLD = _env("LIGHT_ON_THRESHOLD", 50)

# Online combo: consecutive successful inputs from connected Pis.
# (minimum combo, score multiplier per hit); the highest matching tier applies.
COMBO_TIERS = ((0, 1.0), (5, 1.2), (10, 1.5), (20, 2.0))
# Keyboard inputs count toward the combo only when this is on (for testing).
COMBO_KEYBOARD = _env("COMBO_KEYBOARD", False)
# Pi MQTT keepalive; the broker announces a dropped Pi after about 1.5x this.
PI_KEEPALIVE = _env("PI_KEEPALIVE", 5)
CRAVE_SECONDS = _env("CRAVE_SECONDS", 1.6)
RETREAT_SECONDS = _env("RETREAT_SECONDS", 0.6)
STUN_SECONDS = _env("STUN_SECONDS", 1.2)
STUN_COOLDOWN = _env("STUN_COOLDOWN", 6.0)
# Red boss mouse: own timer, one every BOSS_INTERVAL +/- BOSS_JITTER seconds, at most one at a time.
BOSS_INTERVAL = _env("BOSS_INTERVAL", 10.0)
BOSS_JITTER = _env("BOSS_JITTER", 3.0)
BOSS_HP = _env("BOSS_HP", 3)
BOSS_CRAVE_SECONDS = _env("BOSS_CRAVE_SECONDS", 4.0)
BOSS_RETREAT_SECONDS = _env("BOSS_RETREAT_SECONDS", 1.2)

# Hit-streak sound (audio only; scoring uses the combo above). The 6-hit D minor pentatonic
# table plays once, then HIT_OCTAVE_GROUPS more times, each 12 semitones higher; a group's
# closing D is the next group's opening D, so later groups start on F. The top D then repeats.
HIT_OCTAVE_GROUPS = _env("HIT_OCTAVE_GROUPS", 2)

# Aim Pi: SparkFun Qwiic Joystick, 10-bit axes (0-1023, rest near 512)
JOY_SAMPLE_HZ = _env("JOY_SAMPLE_HZ", 30.0)
JOY_TRIGGER = _env("JOY_TRIGGER", 0.30)
JOY_DEADZONE = _env("JOY_DEADZONE", 0.15)
JOY_INVERT_X = _env("JOY_INVERT_X", False)
JOY_INVERT_Y = _env("JOY_INVERT_Y", False)

# Attack Pi: VCNL4040 proximity counts (higher = closer).
# Trigger reuses the Lab 4 Patroller DELIVERY_THRESHOLD of 20.
PROX_SAMPLE_HZ = _env("PROX_SAMPLE_HZ", 30.0)
PROX_TRIGGER = _env("PROX_TRIGGER", 20)
PROX_RELEASE = _env("PROX_RELEASE", 10)
PROX_CONFIRM = _env("PROX_CONFIRM", 2)

# Light Pi: USB webcam + MediaPipe Hands (Lab 5 settings)
CAMERA_INDEX = _env("CAMERA_INDEX", 0)
CAMERA_WIDTH = _env("CAMERA_WIDTH", 640)
CAMERA_HEIGHT = _env("CAMERA_HEIGHT", 480)
POSE_CONFIDENCE = _env("POSE_CONFIDENCE", 0.70)
# Finger tip-to-wrist / knuckle-to-wrist ratio that maps to 0% and 100%.
HAND_CLOSED_RATIO = _env("HAND_CLOSED_RATIO", 1.1)
HAND_OPEN_RATIO = _env("HAND_OPEN_RATIO", 1.8)
LIGHT_SMOOTHING = _env("LIGHT_SMOOTHING", 0.5)   # 1.0 = no smoothing
LIGHT_STEP = _env("LIGHT_STEP", 5)               # published values are multiples of this
LIGHT_PUBLISH_HZ = _env("LIGHT_PUBLISH_HZ", 10.0)
