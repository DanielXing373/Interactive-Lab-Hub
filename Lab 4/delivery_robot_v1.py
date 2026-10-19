#!/usr/bin/env python3
"""
Delivery Robot 1.0 -- production entry point (standalone).

Sequential crawl + VCNL4040 delivery detection.
Uses course libraries only: pi_servo_hat, qwiic_proximity.

Gait (one servo at a time; CH0 holds during CH1 side switch):
  CH1 -> A, CH0 stroke A, CH1 -> B, CH0 stroke B, repeat

Delivery (3 consecutive proximity readings >= 20):
  stop crawl -> CH0 to 90 -> CH1 to 90 -> hold 1s
  -> print DELIVERY COMPLETE -> exit

Usage (from Lab 4, with venv activated):
  python delivery_robot_v1.py
  python delivery_robot_v1.py --self-check
"""

import sys
import time

# Hardware libs imported lazily so --self-check runs without Pi packages.

# =============================================================================
# Hardware
# =============================================================================
FRONT_CHANNEL = 0
REAR_CHANNEL = 1
SERVO_SWING = 180

# CH0 Fast crawl
FRONT_NEUTRAL = 90
FRONT_MIN = 60
FRONT_MAX = 120
FRONT_A = 120
FRONT_B = 60
FRONT_STEP = 3
FRONT_STEP_DELAY = 0.01

# CH1 Smooth crawl (asymmetric calibration)
REAR_NEUTRAL = 90
REAR_MIN = 75
REAR_MAX = 110
REAR_A = 110
REAR_B = 75
REAR_STEP = 1
REAR_STEP_DELAY = 0.02

# Neutral return (delivery completion + Ctrl+C)
NEUTRAL_STEP = 1
NEUTRAL_STEP_DELAY = 0.05
STATE_PAUSE = 0.15
NEUTRAL_HOLD = 1.0

# Delivery detection (raw counts; higher = closer)
DELIVERY_THRESHOLD = 20
CONFIRM_READINGS = 3

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

# (channel, target, label)
PHASES = (
    ("CH1", REAR_A, "tilt A"),
    ("CH0", FRONT_A, "stroke A"),
    ("CH1", REAR_B, "tilt B"),
    ("CH0", FRONT_B, "stroke B"),
)


def clamp_front(angle):
    return max(FRONT_MIN, min(FRONT_MAX, int(angle)))


def clamp_rear(angle):
    return max(REAR_MIN, min(REAR_MAX, int(angle)))


def set_front(angle, label=None):
    """Command CH0 only. Optional label logs once (not every micro-step)."""
    global front_angle
    if hat is None:
        return
    front_angle = clamp_front(angle)
    hat.move_servo_position(FRONT_CHANNEL, front_angle, SERVO_SWING)
    if label is not None:
        print("FRONT ch0=%3d deg  REAR ch1=%3d deg  [%s | moving=CH0]" % (
            front_angle, rear_angle, label))


def set_rear(angle, label=None):
    """Command CH1 only. Optional label logs once (not every micro-step)."""
    global rear_angle
    if hat is None:
        return
    rear_angle = clamp_rear(angle)
    hat.move_servo_position(REAR_CHANNEL, rear_angle, SERVO_SWING)
    if label is not None:
        print("FRONT ch0=%3d deg  REAR ch1=%3d deg  [%s | moving=CH1]" % (
            front_angle, rear_angle, label))


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
    import qwiic_proximity
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
    """Confirm after CONFIRM_READINGS consecutive samples >= threshold."""
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
# Sequential motion
# =============================================================================

def move_front_to(target, state_name, step_size=None, step_delay=None,
                  check_sensor=True):
    """Move CH0 only. False if delivery confirmed mid-move."""
    global front_angle
    if step_size is None:
        step_size = FRONT_STEP
    if step_delay is None:
        step_delay = FRONT_STEP_DELAY
    target = clamp_front(target)
    print("  -> MOVING CH0 to %d deg (CH1 holds at %d)" % (target, rear_angle))

    if check_sensor and check_delivery(read_proximity()):
        return False

    if front_angle == target:
        set_front(target, state_name)
        return True

    while front_angle != target:
        if check_sensor and check_delivery(read_proximity()):
            print("  STOP CH0 at %d deg (delivery; hold pose)" % front_angle)
            return False
        set_front(_next_angle(front_angle, target, step_size))
        time.sleep(step_delay)

    set_front(front_angle, state_name)
    return True


def move_rear_to(target, state_name, step_size=None, step_delay=None,
                 check_sensor=True):
    """Move CH1 only. False if delivery confirmed mid-move."""
    global rear_angle
    if step_size is None:
        step_size = REAR_STEP
    if step_delay is None:
        step_delay = REAR_STEP_DELAY
    target = clamp_rear(target)
    print("  -> MOVING CH1 to %d deg (CH0 holds at %d)" % (target, front_angle))

    if check_sensor and check_delivery(read_proximity()):
        return False

    if rear_angle == target:
        set_rear(target, state_name)
        return True

    while rear_angle != target:
        if check_sensor and check_delivery(read_proximity()):
            print("  STOP CH1 at %d deg (delivery; hold pose)" % rear_angle)
            return False
        set_rear(_next_angle(rear_angle, target, step_size))
        time.sleep(step_delay)

    set_rear(rear_angle, state_name)
    return True


def return_both_to_neutral(hold=True):
    """Sequential return to 90/90 (Ctrl+C). Sensor checks off."""
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
    """CH0->90, CH1->90, hold 1s, print DELIVERY COMPLETE."""
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
    """Safe startup: sequential 90/90."""
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


def run_current_phase():
    """One gait phase. False if delivery confirmed."""
    global gait_phase
    channel, target, desc = PHASES[gait_phase]
    print("\n=== PHASE %d: %s -> %d (%s) ===" % (
        gait_phase, channel, target, desc))

    if channel == "CH1":
        ok = move_rear_to(target, "P%d CH1" % gait_phase)
    else:
        ok = move_front_to(target, "P%d CH0" % gait_phase)

    if not ok:
        return False

    time.sleep(STATE_PAUSE)
    gait_phase = (gait_phase + 1) % len(PHASES)
    return True


def self_check():
    """Hardware-independent checks of pure motion / delivery logic."""
    global delivery_complete, delivery_hit_count, front_angle, rear_angle

    assert clamp_front(200) == FRONT_MAX
    assert clamp_front(0) == FRONT_MIN
    assert clamp_rear(200) == REAR_MAX
    assert clamp_rear(0) == REAR_MIN
    assert _next_angle(90, 120, 3) == 93
    assert _next_angle(118, 120, 3) == 120
    assert _next_angle(110, 75, 1) == 109
    assert _next_angle(76, 75, 1) == 75
    assert REAR_A == 110 and REAR_B == 75
    assert FRONT_A == 120 and FRONT_B == 60
    assert FRONT_STEP == 3 and FRONT_STEP_DELAY == 0.01
    assert REAR_STEP == 1 and REAR_STEP_DELAY == 0.02
    assert SERVO_SWING == 180
    assert PHASES[0][0] == "CH1" and PHASES[1][0] == "CH0"
    assert PHASES[2][0] == "CH1" and PHASES[3][0] == "CH0"

    delivery_complete = False
    delivery_hit_count = 0
    front_angle = 100
    rear_angle = 90
    assert check_delivery(10) is False
    assert delivery_hit_count == 0
    assert check_delivery(25) is False
    assert delivery_hit_count == 1
    assert check_delivery(25) is False
    assert delivery_hit_count == 2
    assert check_delivery(25) is True
    assert delivery_complete is True

    delivery_complete = False
    delivery_hit_count = 0
    assert check_delivery(25) is False
    assert check_delivery(5) is False
    assert delivery_hit_count == 0

    print("SELF_CHECK PASS")
    return 0


def main():
    global hat, gait_phase, delivery_complete, delivery_hit_count

    args = sys.argv[1:]
    if "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)
    if "--self-check" in args:
        sys.exit(self_check())

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

    try:
        init_sensor()
    except Exception as exc:
        print("ERROR: sensor init failed -- %s" % exc, file=sys.stderr)
        print("Not starting crawl without a working sensor.", file=sys.stderr)
        sys.exit(1)

    try:
        import pi_servo_hat
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
        try:
            if hat is not None:
                set_front(front_angle, "ERR HOLD CH0")
                set_rear(rear_angle, "ERR HOLD CH1")
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
