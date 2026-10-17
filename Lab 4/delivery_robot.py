#!/usr/bin/env python3
"""
MVP crawling food-delivery robot (unloaded cardboard test).

Hardware:
  - SparkFun Servo pHAT
  - Front servo: Channel 0
  - Rear servo:  Channel 1
  - SparkFun Qwiic Proximity / VCNL4040 on Servo pHAT Qwiic port

Behavior:
  - If proximity is BELOW STOP_THRESHOLD  -> crawl forward
  - If proximity is ABOVE STOP_THRESHOLD  -> stop (obstacle)
  - Proximity semantics (from course examples): HIGHER = CLOSER

Libraries reused from Lab 4 course code:
  - pi_servo_hat.PiServoHat
  - qwiic_proximity.QwiicProximity

Usage:
  python delivery_robot.py
"""

import sys
import time
import pi_servo_hat
import qwiic_proximity

# =============================================================================
# Configuration — tune these after mechanical calibration
# =============================================================================

FRONT_CHANNEL = 0
REAR_CHANNEL = 1

# Rest / home positions
FRONT_CENTER = 90
REAR_CENTER = 90

# Small crawl stroke (keep modest until cardboard legs are calibrated)
FRONT_FORWARD = 105
FRONT_BACK = 75
REAR_FORWARD = 105
REAR_BACK = 75

MOVE_DELAY = 0.25          # delay between gait half-steps
SENSOR_POLL_DELAY = 0.05   # short pause while checking sensor mid-gait

# Proximity count threshold. HIGHER proximity = CLOSER object.
# Calibrate with: python distance_sensor_test.py
STOP_THRESHOLD = 100

# If True, resume crawling when obstacle is removed.
# Set False to stop once and stay stopped until you restart the script.
AUTO_RESUME = True


# =============================================================================
# Hardware helpers
# =============================================================================

servo_hat = None
proximity_sensor = None


def clamp_angle(angle):
    return max(20, min(120, int(angle)))


def set_front(angle):
    servo_hat.move_servo_position(FRONT_CHANNEL, clamp_angle(angle))


def set_rear(angle):
    servo_hat.move_servo_position(REAR_CHANNEL, clamp_angle(angle))


def stop_robot():
    """Safe resting pose for both legs."""
    set_front(FRONT_CENTER)
    set_rear(REAR_CENTER)


def read_proximity():
    return proximity_sensor.get_proximity()


def obstacle_detected():
    """
    True when an object is closer than STOP_THRESHOLD.
    Because get_proximity() rises as objects approach, we use '>'.
    """
    prox = read_proximity()
    return prox > STOP_THRESHOLD, prox


def wait_and_check(delay):
    """
    Sleep in small slices while polling the sensor so we can abort mid-step.
    Returns (should_stop, proximity).
    """
    elapsed = 0.0
    while elapsed < delay:
        blocked, prox = obstacle_detected()
        if blocked:
            return True, prox
        slice_time = min(SENSOR_POLL_DELAY, delay - elapsed)
        time.sleep(slice_time)
        elapsed += slice_time
    blocked, prox = obstacle_detected()
    return blocked, prox


def crawl_step():
    """
    One Stumble-Bot style gait cycle.
    Sequence: rear -> front -> opposite rear -> opposite front
    Aborts early if an obstacle appears between half-steps.
    Returns False if obstacle aborted the step, True if completed.
    """
    poses = [
        ("rear forward", lambda: set_rear(REAR_FORWARD)),
        ("front forward", lambda: set_front(FRONT_FORWARD)),
        ("rear back", lambda: set_rear(REAR_BACK)),
        ("front back", lambda: set_front(FRONT_BACK)),
    ]

    for label, move in poses:
        blocked, prox = obstacle_detected()
        if blocked:
            print(f"OBSTACLE - stopping  (proximity={prox})")
            stop_robot()
            return False

        move()
        print(f"CLEAR - crawling  [{label}]  (proximity={prox})")
        blocked, prox = wait_and_check(MOVE_DELAY)
        if blocked:
            print(f"OBSTACLE - stopping  (proximity={prox})")
            stop_robot()
            return False

    return True


def init_hardware():
    global servo_hat, proximity_sensor

    print("Initializing proximity sensor...")
    proximity_sensor = qwiic_proximity.QwiicProximity()
    if not proximity_sensor.connected:
        raise RuntimeError(
            "Qwiic proximity sensor not found. "
            "Check the Qwiic cable on the Servo pHAT. "
            "Robot will NOT crawl without a working sensor."
        )
    proximity_sensor.begin()

    # Fail closed: if the first read blows up, do not crawl.
    try:
        first = proximity_sensor.get_proximity()
        print(f"Proximity sensor OK. First reading: {first}")
    except Exception as exc:
        raise RuntimeError(f"Proximity sensor read failed: {exc}") from exc

    print("Initializing Servo pHAT...")
    servo_hat = pi_servo_hat.PiServoHat()
    servo_hat.restart()
    stop_robot()
    time.sleep(0.3)


def main():
    print("=== Delivery Robot MVP ===")
    print(f"STOP_THRESHOLD={STOP_THRESHOLD}  (higher proximity = closer)")
    print(f"AUTO_RESUME={AUTO_RESUME}")
    print("Ctrl+C to rest servos and exit.\n")

    try:
        init_hardware()
    except Exception as exc:
        print(f"ERROR: sensor/servo init failed — {exc}", file=sys.stderr)
        print("Not starting crawl. Fix hardware and retry.", file=sys.stderr)
        # Best-effort rest if servo came up somehow
        if servo_hat is not None:
            try:
                stop_robot()
            except Exception:
                pass
        sys.exit(1)

    stopped_for_obstacle = False

    try:
        while True:
            blocked, prox = obstacle_detected()

            if blocked:
                if not stopped_for_obstacle:
                    print(f"OBSTACLE - stopping  (proximity={prox})")
                    stop_robot()
                    stopped_for_obstacle = True

                if not AUTO_RESUME:
                    print("AUTO_RESUME=False — staying stopped. Ctrl+C to exit.")
                    while True:
                        time.sleep(0.5)
                else:
                    time.sleep(SENSOR_POLL_DELAY)
                continue

            # Path clear
            if stopped_for_obstacle:
                print(f"CLEAR - resuming crawl  (proximity={prox})")
                stopped_for_obstacle = False

            completed = crawl_step()
            if not completed:
                stopped_for_obstacle = True
                if not AUTO_RESUME:
                    print("AUTO_RESUME=False — staying stopped. Ctrl+C to exit.")
                    while True:
                        time.sleep(0.5)

    except KeyboardInterrupt:
        print("\nCtrl+C — resting servos and exiting.")
        try:
            stop_robot()
        except Exception as exc:
            print(f"Warning: could not rest servos: {exc}", file=sys.stderr)
        print("Done.")


if __name__ == "__main__":
    main()
