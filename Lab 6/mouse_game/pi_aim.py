#!/usr/bin/env python3
"""Aim Pi: SparkFun Qwiic Joystick -> IDD/<team>/mouse-game/aim

    python pi_aim.py               # play
    python pi_aim.py --calibrate   # print readings and directions, publish nothing

Keep the stick centered for the first second while it measures the rest position.
If a direction comes out reversed, set JOY_INVERT_X=1 or JOY_INVERT_Y=1.
"""

import sys
import time

import qwiic_joystick

import config
from controllers import JoystickStepper
from pi_common import Publisher


def measure_center(joystick, samples=20):
    xs, ys = [], []
    for _ in range(samples):
        xs.append(joystick.horizontal)
        ys.append(joystick.vertical)
        time.sleep(0.05)
    return sum(xs) / len(xs), sum(ys) / len(ys)


def main():
    calibrate = "--calibrate" in sys.argv
    joystick = qwiic_joystick.QwiicJoystick()
    if not joystick.connected:
        print("Qwiic Joystick not found. Check the Qwiic cable and `i2cdetect -y 1` (0x20).",
              file=sys.stderr)
        sys.exit(1)
    joystick.begin()
    print(f"Joystick firmware {joystick.version}. Keep it centered...")
    cx, cy = measure_center(joystick)
    stepper = JoystickStepper(cx, cy)
    print(f"Center x={cx:.0f} y={cy:.0f}  trigger={stepper.trigger:.0%}  deadzone={stepper.deadzone:.0%}")

    publisher = None
    if not calibrate:
        publisher = Publisher("aim")
        if not publisher.wait_connected():
            print("[MQTT] not connected yet; will keep trying in the background")
        print(f"Publishing to {config.TOPIC_AIM}. Ctrl+C to stop.")

    period = 1.0 / config.JOY_SAMPLE_HZ
    try:
        while True:
            x, y = joystick.horizontal, joystick.vertical
            direction = stepper.update(x, y)
            if calibrate:
                nx, ny = stepper.normalize(x, y)
                print(f"raw x={x:4d} y={y:4d}  norm x={nx:+.2f} y={ny:+.2f}  "
                      f"armed={stepper.armed!s:5}  {direction or ''}")
            elif direction:
                publisher.publish(config.TOPIC_AIM, {"direction": direction})
            time.sleep(period)
    except KeyboardInterrupt:
        print("\nStopping aim controller.")
    finally:
        if publisher:
            publisher.close()


if __name__ == "__main__":
    main()
