#!/usr/bin/env python3
"""
Rear-balance calibration: continuous CH1 sway while CH0 stays at 90 deg.

Startup: CH0 then CH1 to 90 sequentially.
Loop: CH1 -> 105 (hold 3 s) -> CH1 -> 75 (hold 3 s) -> repeat
Crawl moves: 1 deg / 0.02 s
Ctrl+C: CH1 smoothly to 90 at 1 deg / 0.05 s

Never moves both servos in the same step.
SERVO_SWING=180. Uses SparkFun pi_servo_hat only.

Usage (from Lab 4, with venv activated):
  python rear_balance_calibration.py
"""

import sys
import time
import pi_servo_hat

FRONT_CHANNEL = 0
REAR_CHANNEL = 1
SERVO_SWING = 180

FRONT_NEUTRAL = 90
REAR_NEUTRAL = 90
REAR_HIGH = 105
REAR_LOW = 75

CRAWL_STEP = 1
CRAWL_STEP_DELAY = 0.02
HOLD_SECONDS = 3.0

NEUTRAL_STEP = 1
NEUTRAL_STEP_DELAY = 0.05

front_angle = FRONT_NEUTRAL
rear_angle = REAR_NEUTRAL
hat = None


def set_front(angle, label):
    global front_angle
    front_angle = int(angle)
    hat.move_servo_position(FRONT_CHANNEL, front_angle, SERVO_SWING)
    print("FRONT ch0=%3d deg  REAR ch1=%3d deg  [%s | moving=CH0]" % (
        front_angle, rear_angle, label))


def set_rear(angle, label):
    global rear_angle
    rear_angle = int(angle)
    hat.move_servo_position(REAR_CHANNEL, rear_angle, SERVO_SWING)
    print("FRONT ch0=%3d deg  REAR ch1=%3d deg  [%s | moving=CH1]" % (
        front_angle, rear_angle, label))


def move_rear_to(target, label, step_size, step_delay):
    """Move CH1 only to exact target. CH0 is never commanded."""
    global rear_angle
    target = int(target)
    print("CH1 target=%d deg (CH0 holds at %d)" % (target, front_angle))
    if rear_angle == target:
        set_rear(target, label)
        return
    while rear_angle != target:
        if target > rear_angle:
            next_angle = min(rear_angle + step_size, target)
        else:
            next_angle = max(rear_angle - step_size, target)
        set_rear(next_angle, label)
        time.sleep(step_delay)


def go_to_start_pose():
    print("=== START: sequential park at 90/90 ===")
    print("STATE S0a: MOVING CH0 to 90")
    set_front(FRONT_NEUTRAL, "S0a CH0 -> 90")
    time.sleep(0.3)
    print("STATE S0b: MOVING CH1 to 90 (CH0 holds)")
    move_rear_to(
        REAR_NEUTRAL, "S0b CH1 -> 90",
        step_size=NEUTRAL_STEP, step_delay=NEUTRAL_STEP_DELAY)
    time.sleep(0.3)


def main():
    global hat

    print("Initializing Servo pHAT...")
    print("SERVO_SWING=%d" % SERVO_SWING)
    print("CH0 fixed at %d deg." % FRONT_NEUTRAL)
    print("CH1 loop: %d <-> %d  (step=%d delay=%.2fs, hold=%.1fs)" % (
        REAR_HIGH, REAR_LOW, CRAWL_STEP, CRAWL_STEP_DELAY, HOLD_SECONDS))
    print("Ctrl+C -> CH1 return to 90 (step=%d delay=%.2fs).\n" % (
        NEUTRAL_STEP, NEUTRAL_STEP_DELAY))

    hat = pi_servo_hat.PiServoHat()
    hat.restart()
    go_to_start_pose()

    try:
        cycle = 0
        while True:
            cycle += 1
            print("\n########## CYCLE %d ##########" % cycle)

            print("=== MOVING CH1 to %d ===" % REAR_HIGH)
            move_rear_to(
                REAR_HIGH, "CH1 -> 105",
                step_size=CRAWL_STEP, step_delay=CRAWL_STEP_DELAY)
            print("Holding CH1 at %d for %.1f s..." % (rear_angle, HOLD_SECONDS))
            time.sleep(HOLD_SECONDS)

            print("=== MOVING CH1 to %d ===" % REAR_LOW)
            move_rear_to(
                REAR_LOW, "CH1 -> 75",
                step_size=CRAWL_STEP, step_delay=CRAWL_STEP_DELAY)
            print("Holding CH1 at %d for %.1f s..." % (rear_angle, HOLD_SECONDS))
            time.sleep(HOLD_SECONDS)

    except KeyboardInterrupt:
        print("\nCtrl+C - returning CH1 to 90...")
        try:
            move_rear_to(
                REAR_NEUTRAL, "EXIT CH1 -> 90",
                step_size=NEUTRAL_STEP, step_delay=NEUTRAL_STEP_DELAY)
        except Exception as exc:
            print("Warning: could not return CH1 to 90: %s" % exc, file=sys.stderr)
        print("Done.")


if __name__ == "__main__":
    main()
