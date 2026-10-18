#!/usr/bin/env python3
"""
Delivery Robot 1.0 -- reliability-focused MVP (standalone).

Integrates proven behavior from:
  - coordinated_gait_test.py  (strictly sequential alternating crawl)
  - low_sway_gait_test.py     (CH1 smooth crawl speed; amplitude tuned to 75-105)
  - sensor_crawl_test.py      (VCNL4040 delivery confirm + rest sequence)

Does NOT import those test scripts. Uses only course libraries:
  pi_servo_hat, qwiic_proximity

Gait (one servo at a time; CH0 never repositioned before CH1 switches):
  CH1 -> A, CH0 stroke A, CH1 -> B (CH0 holds), CH0 stroke B, repeat

On delivery (3 consecutive proximity readings >= threshold):
  stop crawl permanently -> CH0 to 90 -> CH1 to 90 -> hold 1s
  -> print DELIVERY COMPLETE -> exit (no resume)

Usage (from Lab 4, with venv activated):
  python delivery_robot_v1.py
  python delivery_robot_v1.py --threshold 20
"""

import sys
import time
import pi_servo_hat
import qwiic_proximity

# =============================================================================
# Hardware channels
# =============================================================================
FRONT_CHANNEL = 0  # CH0 front
REAR_CHANNEL = 1   # CH1 rear
SERVO_SWING = 180  # 90 deg = midpoint of 1.0-2.0 ms pulse

# =============================================================================
# CH0 front -- proven Fast crawl
# =============================================================================
FRONT_NEUTRAL = 90
FRONT_MIN = 60
FRONT_MAX = 120
FRONT_A = FRONT_MAX  # 120
FRONT_B = FRONT_MIN  # 60
FRONT_STEP = 3
FRONT_STEP_DELAY = 0.01

# =============================================================================
# CH1 rear -- smooth crawl; 75-105 compensates cardboard asymmetry
# =============================================================================
REAR_NEUTRAL = 90
REAR_MIN = 75
REAR_MAX = 105
REAR_A = REAR_MAX  # 105
REAR_B = REAR_MIN  # 75
REAR_STEP = 1
REAR_STEP_DELAY = 0.02

# =============================================================================
# Neutral return / hold (delivery completion + Ctrl+C)
# =============================================================================
NEUTRAL_STEP = 1
NEUTRAL_STEP_DELAY = 0.05
STATE_PAUSE = 0.15
NEUTRAL_HOLD = 1.0

# =============================================================================
# Delivery detection (raw proximity counts; higher = closer)
# =============================================================================
DELIVERY_THRESHOLD = 20
CONFIRM_READINGS = 3
SENSOR_CHECK_EVERY_STEPS = 1

# =============================================================================
# Runtime state
# =============================================================================
front_angle = FRONT_NEUTRAL
rear_angle = REAR_NEUTRAL
proximity_sensor = None
hat = None

delivery_complete = False
delivery_hit_count = 0
gait_phase = 0  # 0 CH1->A, 1 CH0->A, 2 CH1->B, 3 CH0->B

PHASES = (
    ("CH1", "REAR_A", REAR_A, "tilt A"),
    ("CH0", "FRONT_A", FRONT_A, "stroke A"),
    ("CH1", "REAR_B", REAR_B, "tilt B"),
    ("CH0", "FRONT_B", FRONT_B, "stroke B"),
)


def clamp_front(angle):
    return max(FRONT_MIN, min(FRONT_MAX, int(angle)))


def clamp_rear(angle):
    return max(REAR_MIN, min(REAR_MAX, int(angle)))


def _log_pose(label, moving):
    print("FRONT ch0=%3d deg  REAR ch1=%3d deg  [%s | moving=%s]" % (
        front_angle, rear_angle, label, moving))


def set_front(angle, label):
    """Command CH0 only."""
    global front_angle
    if hat is None:
        return
    front_angle = clamp_front(angle)
    hat.move_servo_position(FRONT_CHANNEL, front_angle, SERVO_SWING)
    _log_pose(label, "CH0")


def set_rear(angle, label):
    """Command CH1 only."""
    global rear_angle
    if hat is None:
        return
    rear_angle = clamp_rear(angle)
    hat.move_servo_position(REAR_CHANNEL, rear_angle, SERVO_SWING)
    _log_pose(label, "CH1")


def _next_angle(current, target, step_size):
    if current == target:
        return target
    if target > current:
        return min(current + step_size, target)
    return max(current - step_size, target)


# =============================================================================
# Sensor
# =============================================================================

def init_sensor():
    global proximity_sensor
    print("Initializing Qwiic proximity sensor (VCNL4040)...")
    proximity_sensor = qwiic_proximity.QwiicProximity()
    if not proximity_sensor.connected:
        raise RuntimeError(
            "Qwiic proximity sensor not found. "
            "Check the Qwiic cable on the Servo pHAT."
        )
    proximity_sensor.begin()
    prox = proximity_sensor.get_proximity()
    print("Proximity sensor OK. First reading: %d" % prox)
    print("NOTE: higher proximity = closer (raw counts, not cm)")
    return prox


def read_proximity():
    return proximity_sensor.get_proximity()


def check_delivery(prox):
    """
    Confirm delivery after CONFIRM_READINGS consecutive samples
    >= DELIVERY_THRESHOLD. Permanent once set.
    """
    global delivery_hit_count, delivery_complete

    if delivery_complete:
        return True

    if prox >= DELIVERY_THRESHOLD:
        delivery_hit_count += 1
        print("Delivery candidate %d/%d (proximity=%d >= %d)" % (
            delivery_hit_count, CONFIRM_READINGS, prox, DELIVERY_THRESHOLD))
        if delivery_hit_count >= CONFIRM_READINGS:
            delivery_complete = True
            print("Delivery confirmed. Stopping crawl.")
            print("Preserving pose ch0=%d ch1=%d before resting return" % (
                front_angle, rear_angle))
            return True
    else:
        if delivery_hit_count > 0:
            print("Delivery streak reset (proximity=%d < %d)" % (
                prox, DELIVERY_THRESHOLD))
        delivery_hit_count = 0

    return False


# =============================================================================
# Sequential motion (one channel per step; exact target landing)
# =============================================================================

def move_front_to(target, state_name, step_size=None, step_delay=None,
                  check_sensor=True):
    """
    Move CH0 only. Returns True if target reached.
    Returns False if delivery confirmed mid-move (pose held).
    """
    global front_angle
    if step_size is None:
        step_size = FRONT_STEP
    if step_delay is None:
        step_delay = FRONT_STEP_DELAY
    target = clamp_front(target)
    print("  -> MOVING CH0 to %d deg (CH1 holds at %d) step=%d delay=%.3fs" % (
        target, rear_angle, step_size, step_delay))

    if check_sensor and check_delivery(read_proximity()):
        return False

    if front_angle == target:
        set_front(target, state_name)
        return True

    steps = 0
    while front_angle != target:
        if check_sensor and (steps % SENSOR_CHECK_EVERY_STEPS == 0):
            if check_delivery(read_proximity()):
                print("  STOP CH0 at %d deg (delivery; hold pose)" % front_angle)
                return False
        set_front(_next_angle(front_angle, target, step_size), state_name)
        time.sleep(step_delay)
        steps += 1
    return True


def move_rear_to(target, state_name, step_size=None, step_delay=None,
                 check_sensor=True):
    """
    Move CH1 only. Returns True if target reached.
    Returns False if delivery confirmed mid-move (pose held).
    """
    global rear_angle
    if step_size is None:
        step_size = REAR_STEP
    if step_delay is None:
        step_delay = REAR_STEP_DELAY
    target = clamp_rear(target)
    print("  -> MOVING CH1 to %d deg (CH0 holds at %d) step=%d delay=%.3fs" % (
        target, front_angle, step_size, step_delay))

    if check_sensor and check_delivery(read_proximity()):
        return False

    if rear_angle == target:
        set_rear(target, state_name)
        return True

    steps = 0
    while rear_angle != target:
        if check_sensor and (steps % SENSOR_CHECK_EVERY_STEPS == 0):
            if check_delivery(read_proximity()):
                print("  STOP CH1 at %d deg (delivery; hold pose)" % rear_angle)
                return False
        set_rear(_next_angle(rear_angle, target, step_size), state_name)
        time.sleep(step_delay)
        steps += 1
    return True


def return_both_to_neutral(hold=True):
    """
    Sequential conservative return to 90/90 (Ctrl+C).
    Sensor checks disabled so cleanup cannot re-trigger delivery logic.
    """
    print("--- return to neutral (sequential, conservative) ---")
    print("STATE N1: MOVING CH0 to 90; CH1 holds")
    move_front_to(
        FRONT_NEUTRAL, "N1 CH0 -> 90",
        step_size=NEUTRAL_STEP, step_delay=NEUTRAL_STEP_DELAY,
        check_sensor=False)
    time.sleep(STATE_PAUSE)
    print("STATE N2: MOVING CH1 to 90; CH0 holds")
    move_rear_to(
        REAR_NEUTRAL, "N2 CH1 -> 90",
        step_size=NEUTRAL_STEP, step_delay=NEUTRAL_STEP_DELAY,
        check_sensor=False)
    time.sleep(STATE_PAUSE)
    set_front(FRONT_NEUTRAL, "N3 HOLD CH0")
    set_rear(REAR_NEUTRAL, "N3 HOLD CH1")
    if hold:
        print("Holding resting posture for %.1f s..." % NEUTRAL_HOLD)
        time.sleep(NEUTRAL_HOLD)
        set_front(FRONT_NEUTRAL, "N3 HOLD CH0")
        set_rear(REAR_NEUTRAL, "N3 HOLD CH1")


def complete_delivery():
    """
    After confirm: keep current pose, then CH0->90, CH1->90,
    hold 1s, print DELIVERY COMPLETE. No crawl resume.
    """
    print("Delivery rest sequence: sequential return to 90/90")
    print("STATE D1: MOVING CH0 to 90; CH1 holds at %d" % rear_angle)
    move_front_to(
        FRONT_NEUTRAL, "D1 CH0 -> 90",
        step_size=NEUTRAL_STEP, step_delay=NEUTRAL_STEP_DELAY,
        check_sensor=False)
    time.sleep(STATE_PAUSE)

    print("STATE D2: MOVING CH1 to 90; CH0 holds at 90")
    move_rear_to(
        REAR_NEUTRAL, "D2 CH1 -> 90",
        step_size=NEUTRAL_STEP, step_delay=NEUTRAL_STEP_DELAY,
        check_sensor=False)
    time.sleep(STATE_PAUSE)

    set_front(FRONT_NEUTRAL, "D3 HOLD CH0")
    set_rear(REAR_NEUTRAL, "D3 HOLD CH1")
    print("Holding resting posture for %.1f s..." % NEUTRAL_HOLD)
    time.sleep(NEUTRAL_HOLD)
    set_front(FRONT_NEUTRAL, "D3 HOLD CH0")
    set_rear(REAR_NEUTRAL, "D3 HOLD CH1")
    print("DELIVERY COMPLETE")


def go_to_start_pose():
    """Safe startup: command both to tracked neutral 90/90 sequentially."""
    print("=== START POSE: sequential move to 90/90 ===")
    move_front_to(
        FRONT_NEUTRAL, "S0a CH0 -> 90",
        step_size=NEUTRAL_STEP, step_delay=NEUTRAL_STEP_DELAY,
        check_sensor=False)
    time.sleep(STATE_PAUSE)
    move_rear_to(
        REAR_NEUTRAL, "S0b CH1 -> 90",
        step_size=NEUTRAL_STEP, step_delay=NEUTRAL_STEP_DELAY,
        check_sensor=False)
    time.sleep(0.3)


# =============================================================================
# Gait
# =============================================================================

def run_current_phase():
    """
    Execute one gait phase. Returns True if completed,
    False if delivery confirmed (pose held).
    """
    global gait_phase
    channel, name, target, desc = PHASES[gait_phase]
    print("\n=== PHASE %d: %s -> %s=%d (%s) ===" % (
        gait_phase, channel, name, target, desc))

    if channel == "CH1":
        ok = move_rear_to(target, "P%d CH1 -> %s" % (gait_phase, name))
    else:
        ok = move_front_to(target, "P%d CH0 -> %s" % (gait_phase, name))

    if not ok:
        return False

    time.sleep(STATE_PAUSE)
    gait_phase = (gait_phase + 1) % len(PHASES)
    return True


def parse_args(args):
    global DELIVERY_THRESHOLD
    if "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)
    if "--threshold" in args:
        i = args.index("--threshold")
        DELIVERY_THRESHOLD = int(args[i + 1])


def main():
    global hat, gait_phase, delivery_complete, delivery_hit_count

    parse_args(sys.argv[1:])

    print("=== Delivery Robot 1.0 ===")
    print("SERVO_SWING=%d" % SERVO_SWING)
    print("CH0 Fast: %d-%d (A=%d B=%d) step=%d delay=%.3fs" % (
        FRONT_MIN, FRONT_MAX, FRONT_A, FRONT_B, FRONT_STEP, FRONT_STEP_DELAY))
    print("CH1 Smooth: %d-%d (A=%d B=%d) step=%d delay=%.3fs" % (
        REAR_MIN, REAR_MAX, REAR_A, REAR_B, REAR_STEP, REAR_STEP_DELAY))
    print("Delivery: threshold=%d confirm=%d consecutive" % (
        DELIVERY_THRESHOLD, CONFIRM_READINGS))
    print("Gait: sequential; CH0 holds during CH1 side switch")
    print("Ctrl+C -> sequential return to neutral.\n")

    # Sensor first: fail closed (do not crawl blind)
    try:
        init_sensor()
    except Exception as exc:
        print("ERROR: sensor init failed -- %s" % exc, file=sys.stderr)
        print("Not starting crawl without a working sensor.", file=sys.stderr)
        sys.exit(1)

    try:
        print("Initializing Servo pHAT...")
        hat = pi_servo_hat.PiServoHat()
        hat.restart()
    except Exception as exc:
        print("ERROR: Servo pHAT init failed -- %s" % exc, file=sys.stderr)
        sys.exit(1)

    try:
        go_to_start_pose()
        gait_phase = 0
        delivery_complete = False
        delivery_hit_count = 0

        cycle = 0
        while not delivery_complete:
            cycle += 1
            print("\n########## CRAWL LOOP %d (phase=%d) ##########" % (
                cycle, gait_phase))
            if check_delivery(read_proximity()):
                break
            if not run_current_phase():
                break

        if delivery_complete:
            complete_delivery()
        print("Done.")

    except KeyboardInterrupt:
        print("\nCtrl+C - stopping...")
        try:
            if hat is not None:
                return_both_to_neutral(hold=True)
        except Exception as exc:
            print("Warning: could not return to neutral: %s" % exc, file=sys.stderr)
        print("Done.")
    except Exception as exc:
        print("ERROR during crawl: %s" % exc, file=sys.stderr)
        # Best-effort hold current pose only (no unexpected large jump).
        # Re-assert last commanded angles if possible; do not invent new targets.
        try:
            if hat is not None:
                set_front(front_angle, "ERR HOLD CH0")
                set_rear(rear_angle, "ERR HOLD CH1")
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
