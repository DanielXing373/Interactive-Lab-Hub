#!/usr/bin/env python3
"""
Servo jitter diagnosis: command CH0 and CH1 to 90 deg once, then hold.

Reuses SparkFun Servo pHAT via pi_servo_hat (same init as coordinated_gait_test.py).
Does NOT sweep. Does NOT send repeated angle commands during the hold.
ASCII-only terminal output.

Usage (from Lab 4, with venv activated):
  python dual_servo_hold_test.py
"""

import time
import pi_servo_hat

FRONT_CHANNEL = 0
REAR_CHANNEL = 1
HOLD_ANGLE = 90
HOLD_SECONDS = 10


def main():
    print("Initializing Servo pHAT...")
    hat = pi_servo_hat.PiServoHat()
    hat.restart()

    print("Commanding CH0 and CH1 to %d deg (once)." % HOLD_ANGLE)
    hat.move_servo_position(FRONT_CHANNEL, HOLD_ANGLE)
    hat.move_servo_position(REAR_CHANNEL, HOLD_ANGLE)
    print("Hold start: both servos at %d deg. No further commands for %d s." % (
        HOLD_ANGLE, HOLD_SECONDS))
    print("Watch for jitter. Ctrl+C to exit early.\n")

    try:
        # Sleep only -- do not re-send angle commands during the hold.
        elapsed = 0
        while elapsed < HOLD_SECONDS:
            time.sleep(1)
            elapsed += 1
            print("Holding... %d / %d s" % (elapsed, HOLD_SECONDS))
        print("Hold complete. Exiting (last commanded angle was %d deg)." % HOLD_ANGLE)
    except KeyboardInterrupt:
        print("\nCtrl+C - exiting hold test.")
        print("Last commanded angle was %d deg on CH0 and CH1." % HOLD_ANGLE)


if __name__ == "__main__":
    main()
