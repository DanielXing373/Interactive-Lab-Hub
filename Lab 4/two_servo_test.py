#!/usr/bin/env python3
"""
Two-servo hardware test for the cardboard crawling robot.

Uses SparkFun Servo pHAT via the course library `pi_servo_hat`
(same API as pi_servo_hat_test.py and windmill_coaster.py).

Channels:
  FRONT = Channel 0
  REAR  = Channel 1

Usage (from Lab 4, with venv activated):
  python two_servo_test.py front   # A: front servo only
  python two_servo_test.py rear    # B: rear servo only
  python two_servo_test.py both    # D: both servos
"""

import sys
import time
import pi_servo_hat

# --- Channels ---
FRONT_CHANNEL = 0
REAR_CHANNEL = 1

# --- Conservative angles (safe for cardboard; tune later) ---
# Course examples treat ~60 as a comfortable center for 0-120 micro servos.
FRONT_CENTER = 90
REAR_CENTER = 90
FRONT_DELTA = 15  # +/- from center
REAR_DELTA = 15
MOVE_DELAY = 0.6  # seconds between poses (slow enough to see clearly)


def clamp_angle(angle):
    """Keep angles inside a conservative micro-servo range."""
    return max(20, min(120, int(angle)))


def set_servo(hat, channel, angle, label):
    angle = clamp_angle(angle)
    hat.move_servo_position(channel, angle)
    print(f"  {label}: ch{channel} -> {angle} deg")


def rest(hat):
    set_servo(hat, FRONT_CHANNEL, FRONT_CENTER, "FRONT rest")
    set_servo(hat, REAR_CHANNEL, REAR_CENTER, "REAR  rest")


def move_front_only(hat):
    """Obvious FRONT motion: center -> forward -> back -> center."""
    print("\n=== FRONT servo test (Channel 0) ===")
    set_servo(hat, FRONT_CHANNEL, FRONT_CENTER, "FRONT center")
    time.sleep(MOVE_DELAY)
    set_servo(hat, FRONT_CHANNEL, FRONT_CENTER + FRONT_DELTA, "FRONT forward")
    time.sleep(MOVE_DELAY)
    set_servo(hat, FRONT_CHANNEL, FRONT_CENTER - FRONT_DELTA, "FRONT back")
    time.sleep(MOVE_DELAY)
    set_servo(hat, FRONT_CHANNEL, FRONT_CENTER, "FRONT center")
    time.sleep(MOVE_DELAY)


def move_rear_only(hat):
    """Obvious REAR motion: center -> forward -> back -> center."""
    print("\n=== REAR servo test (Channel 1) ===")
    set_servo(hat, REAR_CHANNEL, REAR_CENTER, "REAR  center")
    time.sleep(MOVE_DELAY)
    set_servo(hat, REAR_CHANNEL, REAR_CENTER + REAR_DELTA, "REAR  forward")
    time.sleep(MOVE_DELAY)
    set_servo(hat, REAR_CHANNEL, REAR_CENTER - REAR_DELTA, "REAR  back")
    time.sleep(MOVE_DELAY)
    set_servo(hat, REAR_CHANNEL, REAR_CENTER, "REAR  center")
    time.sleep(MOVE_DELAY)


def move_both(hat):
    """Simple coordinated crawl preview (not obstacle-aware)."""
    print("\n=== BOTH servos crawl preview ===")
    # Stumble-Bot inspired: rear, front, opposite rear, opposite front
    set_servo(hat, REAR_CHANNEL, REAR_CENTER + REAR_DELTA, "REAR  forward")
    time.sleep(MOVE_DELAY)
    set_servo(hat, FRONT_CHANNEL, FRONT_CENTER + FRONT_DELTA, "FRONT forward")
    time.sleep(MOVE_DELAY)
    set_servo(hat, REAR_CHANNEL, REAR_CENTER - REAR_DELTA, "REAR  back")
    time.sleep(MOVE_DELAY)
    set_servo(hat, FRONT_CHANNEL, FRONT_CENTER - FRONT_DELTA, "FRONT back")
    time.sleep(MOVE_DELAY)
    rest(hat)
    time.sleep(MOVE_DELAY)


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("front", "rear", "both"):
        print(__doc__)
        print("Error: choose mode: front | rear | both")
        sys.exit(1)

    mode = sys.argv[1]
    print("Initializing Servo pHAT...")
    hat = pi_servo_hat.PiServoHat()
    hat.restart()
    rest(hat)
    time.sleep(0.5)

    print(f"Mode: {mode}")
    print("Ctrl+C to stop and return servos to rest.\n")

    try:
        while True:
            if mode == "front":
                move_front_only(hat)
            elif mode == "rear":
                move_rear_only(hat)
            else:
                move_both(hat)
            print("--- cycle complete ---\n")
    except KeyboardInterrupt:
        print("\nStopping. Moving servos to rest...")
        rest(hat)
        print("Done.")


if __name__ == "__main__":
    main()
