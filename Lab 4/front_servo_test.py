#!/usr/bin/env python3
"""
Slow continuous back-and-forth test for the FRONT servo only (Channel 0).

Reuses SparkFun Servo pHAT via pi_servo_hat (same as rear_servo_test.py).
Does NOT touch Channel 1 (rear) or the distance sensor.

Sweep: 80° <-> 100°, 1° steps, 0.05 s per step. Starts and stops at 90°.

Usage (from Lab 4, with venv activated):
  python front_servo_test.py
"""

import time
import pi_servo_hat

FRONT_CHANNEL = 0
NEUTRAL = 90
ANGLE_MIN = 80
ANGLE_MAX = 100
STEP = 1
STEP_DELAY = 0.05  # seconds between 1° increments


def set_front(hat, angle):
    """Command CH0 only; clamp hard to the allowed 80–100° window."""
    angle = max(ANGLE_MIN, min(ANGLE_MAX, int(angle)))
    hat.move_servo_position(FRONT_CHANNEL, angle)
    return angle


def return_to_neutral(hat, current):
    """Smoothly walk CH0 back to 90° in 1° steps."""
    current = int(current)
    if current == NEUTRAL:
        set_front(hat, NEUTRAL)
        print(f"FRONT ch{FRONT_CHANNEL}: {NEUTRAL} deg (neutral)")
        return

    step = STEP if current < NEUTRAL else -STEP
    for angle in range(current, NEUTRAL, step):
        next_angle = angle + step
        set_front(hat, next_angle)
        print(f"FRONT ch{FRONT_CHANNEL}: {next_angle} deg (returning)")
        time.sleep(STEP_DELAY)


def main():
    print("Initializing Servo pHAT...")
    print(f"FRONT only: Channel {FRONT_CHANNEL}")
    print(f"Sweep {ANGLE_MIN}° <-> {ANGLE_MAX}°, {STEP}° / {STEP_DELAY}s")
    print("Rear (CH1) and distance sensor are NOT used.")
    print("Ctrl+C to return to 90° and exit.\n")

    hat = pi_servo_hat.PiServoHat()
    hat.restart()

    current = set_front(hat, NEUTRAL)
    print(f"FRONT ch{FRONT_CHANNEL}: {current} deg (start)")
    time.sleep(0.5)

    direction = 1  # +1 toward ANGLE_MAX, -1 toward ANGLE_MIN

    try:
        while True:
            next_angle = current + (STEP * direction)

            if next_angle > ANGLE_MAX:
                direction = -1
                next_angle = current + (STEP * direction)
            elif next_angle < ANGLE_MIN:
                direction = 1
                next_angle = current + (STEP * direction)

            current = set_front(hat, next_angle)
            print(f"FRONT ch{FRONT_CHANNEL}: {current} deg")
            time.sleep(STEP_DELAY)

    except KeyboardInterrupt:
        print("\nCtrl+C — returning FRONT to 90°...")
        return_to_neutral(hat, current)
        print("Done.")


if __name__ == "__main__":
    main()
