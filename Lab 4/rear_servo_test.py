#!/usr/bin/env python3
"""
Slow continuous back-and-forth test for the REAR servo only (Channel 1).

Reuses SparkFun Servo pHAT via pi_servo_hat (same as two_servo_test.py).
Does NOT touch Channel 0 (front) or the distance sensor.

Usage (from Lab 4, with venv activated):
  python rear_servo_test.py
"""

import time
import pi_servo_hat

# --- Tunable calibration constants ---
REAR_CHANNEL = 1
MIN_ANGLE = 70
MAX_ANGLE = 110
CENTER_ANGLE = 90
STEP = 1
STEP_DELAY = 0.05  # seconds between 1° increments


def set_rear(hat, angle):
    """Command CH1 only; clamp hard to MIN_ANGLE–MAX_ANGLE."""
    angle = max(MIN_ANGLE, min(MAX_ANGLE, int(angle)))
    hat.move_servo_position(REAR_CHANNEL, angle)
    return angle


def return_to_center(hat, current):
    """Smoothly walk CH1 back to CENTER_ANGLE in 1° steps."""
    current = int(current)
    if current == CENTER_ANGLE:
        set_rear(hat, CENTER_ANGLE)
        print(f"REAR ch{REAR_CHANNEL}: {CENTER_ANGLE} deg (center)")
        return

    step = STEP if current < CENTER_ANGLE else -STEP
    for angle in range(current, CENTER_ANGLE, step):
        next_angle = angle + step
        set_rear(hat, next_angle)
        print(f"REAR ch{REAR_CHANNEL}: {next_angle} deg (returning)")
        time.sleep(STEP_DELAY)


def main():
    print("Initializing Servo pHAT...")
    print(f"REAR only: Channel {REAR_CHANNEL}")
    print(f"Sweep {MIN_ANGLE}° <-> {MAX_ANGLE}°, center {CENTER_ANGLE}°")
    print(f"Step {STEP}° / {STEP_DELAY}s")
    print("Front (CH0) and distance sensor are NOT used.")
    print(f"Ctrl+C to return to {CENTER_ANGLE}° and exit.\n")

    hat = pi_servo_hat.PiServoHat()
    hat.restart()

    current = set_rear(hat, CENTER_ANGLE)
    print(f"REAR ch{REAR_CHANNEL}: {current} deg (start)")
    time.sleep(0.5)

    direction = 1  # +1 toward MAX_ANGLE, -1 toward MIN_ANGLE

    try:
        while True:
            next_angle = current + (STEP * direction)

            if next_angle > MAX_ANGLE:
                direction = -1
                next_angle = current + (STEP * direction)
            elif next_angle < MIN_ANGLE:
                direction = 1
                next_angle = current + (STEP * direction)

            current = set_rear(hat, next_angle)
            print(f"REAR ch{REAR_CHANNEL}: {current} deg")
            time.sleep(STEP_DELAY)

    except KeyboardInterrupt:
        print(f"\nCtrl+C — returning REAR to {CENTER_ANGLE}°...")
        return_to_center(hat, current)
        print("Done.")


if __name__ == "__main__":
    main()
