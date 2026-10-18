#!/usr/bin/env python3
"""
Strictly sequential alternating crawl gait (CH0 front + CH1 rear).

CH0 and CH1 NEVER change commanded angles in the same movement step.
One servo moves while the other holds its last PWM command.
CH0 is NEVER repositioned before CH1 switches sides.

Start: CH0=90, CH1=90

Single-cycle (one A-side stroke + one B-side stroke):
  1) CH1 90 -> REAR_A;   CH0 holds 90
  2) CH0 90 -> FRONT_A;  CH1 holds REAR_A
  3) CH1 REAR_A -> REAR_B directly;  CH0 holds FRONT_A
  4) CH0 FRONT_A -> FRONT_B directly; CH1 holds REAR_B
  then sequential return to neutral

Continuous --loop continues alternating from there:
  5) CH1 REAR_B -> REAR_A;   CH0 holds FRONT_B
  6) CH0 FRONT_B -> FRONT_A; CH1 holds REAR_A
  7) CH1 REAR_A -> REAR_B;   CH0 holds FRONT_A
  8) CH0 FRONT_A -> FRONT_B; CH1 holds REAR_B
  repeat 5-8 ...

Reuses SparkFun Servo pHAT via pi_servo_hat.
Does NOT use the distance sensor. Does NOT modify delivery_robot.py.

Physical directions are unverified -- flip the mapping constants below
if left/right or front stroke feel reversed.

Usage (from Lab 4, with venv activated):
  python coordinated_gait_test.py --calibrate  # hold both at 90 deg (horn check)
  python coordinated_gait_test.py              # one A+B stroke cycle, then neutral
  python coordinated_gait_test.py --once       # same as default
  python coordinated_gait_test.py --loop       # continuous alternating crawl
"""

import sys
import time
import pi_servo_hat

# =============================================================================
# Channels
# =============================================================================
FRONT_CHANNEL = 0  # CH0 - front legs
REAR_CHANNEL = 1   # CH1 - rear legs

# Explicit swing so angle 90 maps to midpoint of the default 1.0-2.0 ms pulse.
# (Library default swing=90 maps 90 deg to the MAX pulse, not center.)
SERVO_SWING = 180

# =============================================================================
# Angle limits (keep within these clamps)
# =============================================================================
FRONT_NEUTRAL = 90
FRONT_MIN = 60
FRONT_MAX = 120

REAR_NEUTRAL = 90
REAR_MIN = 70
REAR_MAX = 110

# =============================================================================
# Direction mapping -- flip these if the cardboard moves the wrong way
# =============================================================================
# CH1 first tilt extreme (state 1). Swap REAR_A / REAR_B to invert left/right.
REAR_A = REAR_MAX   # 110
REAR_B = REAR_MIN   # 70

# CH0 stroke targets. Swap FRONT_A / FRONT_B to invert stroke direction.
FRONT_A = FRONT_MAX  # 120 -- stroke used while rear is at REAR_A
FRONT_B = FRONT_MIN  # 60  -- opposite stroke while rear is at REAR_B

# =============================================================================
# Timing (slow for calibration)
# =============================================================================
STEP = 1
STEP_DELAY = 0.05
STATE_PAUSE = 0.3       # brief pause between states so motion is easy to watch
NEUTRAL_HOLD = 1.0      # hold resting posture before exit (PWM stays enabled)
CALIBRATE_HOLD = 30.0   # seconds to hold 90/90 for horn alignment check


# -----------------------------------------------------------------------------
# Servo helpers -- always step 1 deg at a time; ONE channel per movement step
# -----------------------------------------------------------------------------

front_angle = FRONT_NEUTRAL
rear_angle = REAR_NEUTRAL


def clamp_front(angle):
    return max(FRONT_MIN, min(FRONT_MAX, int(angle)))


def clamp_rear(angle):
    return max(REAR_MIN, min(REAR_MAX, int(angle)))


def _log_pose(label, moving):
    """ASCII status: which servo is moving (or HOLD)."""
    tag = "  [%s | moving=%s]" % (label, moving)
    print("FRONT ch0=%3d deg  REAR ch1=%3d deg%s" % (front_angle, rear_angle, tag))


def set_front(hat, angle, label):
    """Command CH0 only. CH1 is not written (holds last PWM)."""
    global front_angle
    front_angle = clamp_front(angle)
    hat.move_servo_position(FRONT_CHANNEL, front_angle, SERVO_SWING)
    _log_pose(label, "CH0")


def set_rear(hat, angle, label):
    """Command CH1 only. CH0 is not written (holds last PWM)."""
    global rear_angle
    rear_angle = clamp_rear(angle)
    hat.move_servo_position(REAR_CHANNEL, rear_angle, SERVO_SWING)
    _log_pose(label, "CH1")


def move_front_to(hat, target, state_name):
    """Smoothly walk CH0 to target in 1 deg steps. CH1 never commanded."""
    global front_angle
    target = clamp_front(target)
    print("  -> MOVING CH0 to %d deg (CH1 holds at %d)" % (target, rear_angle))
    if front_angle == target:
        set_front(hat, target, state_name)
        return
    step = STEP if target > front_angle else -STEP
    for angle in range(front_angle, target, step):
        set_front(hat, angle + step, state_name)
        time.sleep(STEP_DELAY)


def move_rear_to(hat, target, state_name):
    """Smoothly walk CH1 to target in 1 deg steps. CH0 never commanded."""
    global rear_angle
    target = clamp_rear(target)
    print("  -> MOVING CH1 to %d deg (CH0 holds at %d)" % (target, front_angle))
    if rear_angle == target:
        set_rear(hat, target, state_name)
        return
    step = STEP if target > rear_angle else -STEP
    for angle in range(rear_angle, target, step):
        set_rear(hat, angle + step, state_name)
        time.sleep(STEP_DELAY)


def return_both_to_neutral(hat, hold=True):
    """
    Strictly sequential return to 90/90:
      1) move CH0 to neutral (CH1 holds)
      2) move CH1 to neutral (CH0 holds)
    Then re-assert each channel separately. Does NOT disable PWM.
    """
    print("--- return to neutral (sequential) ---")
    print("STATE N1: MOVING CH0 to neutral; CH1 holds")
    move_front_to(hat, FRONT_NEUTRAL, "N1 CH0 -> neutral")
    time.sleep(STATE_PAUSE)

    print("STATE N2: MOVING CH1 to neutral; CH0 holds")
    move_rear_to(hat, REAR_NEUTRAL, "N2 CH1 -> neutral")
    time.sleep(STATE_PAUSE)

    print("STATE N3: re-assert neutral (CH0 then CH1, still sequential)")
    set_front(hat, FRONT_NEUTRAL, "N3 HOLD CH0")
    set_rear(hat, REAR_NEUTRAL, "N3 HOLD CH1")
    if hold:
        print("Holding level resting posture (PWM still enabled)...")
        time.sleep(NEUTRAL_HOLD)
        set_front(hat, FRONT_NEUTRAL, "N3 HOLD CH0")
        set_rear(hat, REAR_NEUTRAL, "N3 HOLD CH1")


# -----------------------------------------------------------------------------
# Gait state machine (strictly sequential: never move CH0 and CH1 together)
# No CH0 repositioning between CH1 side switches.
# -----------------------------------------------------------------------------

def run_ab_half_cycle(hat, from_start=False):
    """
    One A-side stroke + one B-side stroke (4 sequential moves).

    If from_start=True (first half from neutral):
      CH1: 90 -> REAR_A, then CH0: 90 -> FRONT_A,
      CH1: REAR_A -> REAR_B, then CH0: FRONT_A -> FRONT_B

    If from_start=False (continuing crawl; CH0 already at FRONT_B, CH1 at REAR_B):
      CH1: REAR_B -> REAR_A, then CH0: FRONT_B -> FRONT_A,
      CH1: REAR_A -> REAR_B, then CH0: FRONT_A -> FRONT_B

    Never moves CH0 before CH1 switches sides. Leaves CH0=FRONT_B, CH1=REAR_B.
    """
    if from_start:
        print("\n=== STATE 1: MOVING CH1 90 -> REAR_A=%d; CH0 holds 90 ===" % REAR_A)
        move_rear_to(hat, REAR_A, "S1 CH1 -> A")
        time.sleep(STATE_PAUSE)

        print("\n=== STATE 2: MOVING CH0 90 -> FRONT_A=%d; CH1 holds %d ===" % (
            FRONT_A, REAR_A))
        move_front_to(hat, FRONT_A, "S2 CH0 stroke A")
        time.sleep(STATE_PAUSE)
    else:
        print("\n=== STATE 1: MOVING CH1 REAR_B -> REAR_A=%d; CH0 holds FRONT_B ===" % (
            REAR_A))
        move_rear_to(hat, REAR_A, "S1 CH1 -> A")
        time.sleep(STATE_PAUSE)

        print("\n=== STATE 2: MOVING CH0 FRONT_B -> FRONT_A=%d; CH1 holds %d ===" % (
            FRONT_A, REAR_A))
        move_front_to(hat, FRONT_A, "S2 CH0 stroke A")
        time.sleep(STATE_PAUSE)

    print("\n=== STATE 3: MOVING CH1 directly to REAR_B=%d; CH0 holds FRONT_A ===" % (
        REAR_B))
    move_rear_to(hat, REAR_B, "S3 CH1 -> B")
    time.sleep(STATE_PAUSE)

    print("\n=== STATE 4: MOVING CH0 directly to FRONT_B=%d; CH1 holds REAR_B ===" % (
        FRONT_B))
    move_front_to(hat, FRONT_B, "S4 CH0 stroke B")
    time.sleep(STATE_PAUSE)


def go_to_start_pose(hat):
    """Sequential park at neutral before the first gait cycle."""
    print("=== START POSE: sequential move to 90/90 ===")
    print("STATE S0a: MOVING CH0 to neutral; CH1 not yet commanded this step")
    move_front_to(hat, FRONT_NEUTRAL, "S0a CH0 -> neutral")
    time.sleep(STATE_PAUSE)
    print("STATE S0b: MOVING CH1 to neutral; CH0 holds")
    move_rear_to(hat, REAR_NEUTRAL, "S0b CH1 -> neutral")
    time.sleep(0.5)


def run_calibrate(hat):
    """
    Safe calibration-only mode: command both servos to 90 deg sequentially
    (swing=180) and hold. No gait, no sweeping.
    """
    print("CALIBRATE mode: both servos to %d deg (swing=%d)." % (
        FRONT_NEUTRAL, SERVO_SWING))
    print("Check physical horn alignment / level resting posture.")
    print("No sweeping. Ctrl+C to exit early.\n")

    print("STATE C1: MOVING CH0 to 90; CH1 not commanded this step")
    set_front(hat, FRONT_NEUTRAL, "C1 CH0 = 90")
    time.sleep(0.2)
    print("STATE C2: MOVING CH1 to 90; CH0 holds")
    set_rear(hat, REAR_NEUTRAL, "C2 CH1 = 90")

    # Do not re-send angle commands during the hold (jitter diagnosis friendly).
    try:
        elapsed = 0
        hold_s = int(CALIBRATE_HOLD)
        while elapsed < hold_s:
            time.sleep(1)
            elapsed += 1
            print("Holding neutral... %d / %d s (no new servo commands)" % (
                elapsed, hold_s))
        print("Calibration hold complete. PWM last commanded at 90/90. Done.")
    except KeyboardInterrupt:
        print("\nCtrl+C - ending calibration hold.")
        print("STATE C3: sequential re-assert 90/90")
        set_front(hat, FRONT_NEUTRAL, "C3 HOLD CH0")
        set_rear(hat, REAR_NEUTRAL, "C3 HOLD CH1")
        print("Done.")


def main():
    args = sys.argv[1:]
    if "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)

    calibrate = "--calibrate" in args
    loop = "--loop" in args
    # Default and --once: single cycle
    once = (not loop) or ("--once" in args)

    print("Initializing Servo pHAT...")
    print("SERVO_SWING=%d (90 deg = midpoint of 1.0-2.0 ms pulse)" % SERVO_SWING)
    print("FRONT CH%d: %d-%d, neutral %d" % (
        FRONT_CHANNEL, FRONT_MIN, FRONT_MAX, FRONT_NEUTRAL))
    print("REAR  CH%d: %d-%d, neutral %d" % (
        REAR_CHANNEL, REAR_MIN, REAR_MAX, REAR_NEUTRAL))
    print("Mapping: REAR_A=%d REAR_B=%d  FRONT_A=%d FRONT_B=%d" % (
        REAR_A, REAR_B, FRONT_A, FRONT_B))
    print("Gait: STRICTLY SEQUENTIAL alternating crawl (no CH0 reposition)")
    if calibrate:
        print("Mode: calibrate-only (hold 90/90, no gait)")
    else:
        print("Mode: %s" % ("continuous --loop" if loop else "single cycle --once"))
    print("Distance sensor NOT used. Ctrl+C -> sequential return to neutral.\n")

    hat = pi_servo_hat.PiServoHat()
    hat.restart()

    if calibrate:
        run_calibrate(hat)
        return

    go_to_start_pose(hat)

    try:
        cycle = 0
        from_start = True
        while True:
            cycle += 1
            print("\n########## GAIT CYCLE %d (A stroke + B stroke) ##########" % cycle)
            run_ab_half_cycle(hat, from_start=from_start)
            from_start = False  # later cycles continue from FRONT_B / REAR_B

            if once and not loop:
                print("\nSingle-cycle mode: one A + one B stroke done.")
                print("Sequential return to neutral.")
                return_both_to_neutral(hat, hold=True)
                print("Resting posture ready for next test. Done.")
                return

            # Continuous: no CH0 reposition / no bridge to neutral.
            # Next cycle starts with CH1 REAR_B -> REAR_A while CH0 holds FRONT_B.

    except KeyboardInterrupt:
        print("\nCtrl+C - stopping gait...")
        try:
            return_both_to_neutral(hat, hold=True)
        except Exception as exc:
            print("Warning: could not return to neutral: %s" % exc, file=sys.stderr)
        print("Resting posture held. Done.")



if __name__ == "__main__":
    main()
