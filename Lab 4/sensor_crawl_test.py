#!/usr/bin/env python3
"""
Obstacle-aware crawl: sequential gait (from coordinated_gait_test.py) +
SparkFun Qwiic VCNL4040 proximity (from distance_sensor_test.py / qwiic_distance.py).

Does NOT modify coordinated_gait_test.py, distance_sensor_test.py, or delivery_robot.py.

Gait (strictly sequential, Fast preset):
  CH1 tilt A -> CH0 stroke A -> CH1 tilt B -> CH0 stroke B -> repeat
  One servo moves at a time. No CH0 reposition before CH1 switches sides.

Proximity (higher = closer):
  prox > STOP_THRESHOLD   -> hold pose, stop new movement commands
  prox < RESUME_THRESHOLD -> resume crawling (hysteresis)
  Mid-band keeps the previous crawl/hold state (no chatter).

On obstacle: hold current commanded angles (no abrupt reset to neutral).
On resume: continue the same gait phase toward the same target (does not
reverse a front stroke on the same contact side).

Usage (from Lab 4, with venv activated):
  python sensor_crawl_test.py --sensor-only
  python sensor_crawl_test.py --once
  python sensor_crawl_test.py --loop
  python sensor_crawl_test.py --loop --stop 1000 --resume 700
"""

import sys
import time
import pi_servo_hat
import qwiic_proximity

# =============================================================================
# Channels / servo mapping (match coordinated_gait_test.py)
# =============================================================================
FRONT_CHANNEL = 0
REAR_CHANNEL = 1
SERVO_SWING = 180

FRONT_NEUTRAL = 90
FRONT_MIN = 60
FRONT_MAX = 120

REAR_NEUTRAL = 90
REAR_MIN = 70
REAR_MAX = 110

# Direction mapping -- swap pairs if physical direction is wrong
REAR_A = REAR_MAX    # 110
REAR_B = REAR_MIN    # 70
FRONT_A = FRONT_MAX  # 120
FRONT_B = FRONT_MIN  # 60

# Proven Fast preset from coordinated_gait_test.py
GAIT_STEP = 3
GAIT_STEP_DELAY = 0.01

# Conservative return-to-neutral
NEUTRAL_STEP = 1
NEUTRAL_STEP_DELAY = 0.05
STATE_PAUSE = 0.15
NEUTRAL_HOLD = 1.0

# Proximity hysteresis (higher proximity = closer object)
STOP_THRESHOLD = 1000
RESUME_THRESHOLD = 700

# Check sensor every this many gait micro-steps during a long move
SENSOR_CHECK_EVERY_STEPS = 1


# =============================================================================
# Shared runtime state
# =============================================================================
front_angle = FRONT_NEUTRAL
rear_angle = REAR_NEUTRAL
proximity_sensor = None

# Obstacle FSM: "crawl" or "hold"
motion_mode = "crawl"

# Gait phase index into PHASES (resume continues same phase / same target)
# 0: CH1 -> REAR_A
# 1: CH0 -> FRONT_A
# 2: CH1 -> REAR_B
# 3: CH0 -> FRONT_B
gait_phase = 0

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
    tag = "  [%s | moving=%s | mode=%s]" % (label, moving, motion_mode)
    print("FRONT ch0=%3d deg  REAR ch1=%3d deg%s" % (front_angle, rear_angle, tag))


def set_front(hat, angle, label):
    global front_angle
    front_angle = clamp_front(angle)
    hat.move_servo_position(FRONT_CHANNEL, front_angle, SERVO_SWING)
    _log_pose(label, "CH0")


def set_rear(hat, angle, label):
    global rear_angle
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
# Proximity sensor (reuse course qwiic_proximity pattern)
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
    print("NOTE: higher proximity = closer object")
    return prox


def read_proximity():
    return proximity_sensor.get_proximity()


def update_obstacle_fsm(prox):
    """
    Hysteresis:
      crawl -> hold when prox > STOP_THRESHOLD
      hold  -> crawl when prox < RESUME_THRESHOLD
      otherwise keep current mode
    Returns True if crawling is allowed.
    """
    global motion_mode
    prev = motion_mode
    if motion_mode == "crawl":
        if prox > STOP_THRESHOLD:
            motion_mode = "hold"
    else:
        if prox < RESUME_THRESHOLD:
            motion_mode = "crawl"

    if motion_mode != prev:
        if motion_mode == "hold":
            print("OBSTACLE - holding pose  (proximity=%d > stop=%d)" % (
                prox, STOP_THRESHOLD))
            print("  (no angle reset; waiting until proximity < %d)" % RESUME_THRESHOLD)
        else:
            print("CLEAR - resume crawl  (proximity=%d < resume=%d)" % (
                prox, RESUME_THRESHOLD))
            print("  (continuing gait phase %d toward same target)" % gait_phase)
    return motion_mode == "crawl"


def wait_while_holding():
    """Poll sensor until path is clear (or KeyboardInterrupt)."""
    while True:
        prox = read_proximity()
        if update_obstacle_fsm(prox):
            return prox
        print("HOLD pose ch0=%d ch1=%d  proximity=%d" % (
            front_angle, rear_angle, prox))
        time.sleep(0.05)


# =============================================================================
# Sequential servo moves with mid-move sensor checks
# =============================================================================

def move_front_to(hat, target, state_name, step_size=None, step_delay=None,
                  check_sensor=True):
    """
    Move CH0 only toward target. Returns True if target reached,
    False if aborted for obstacle (pose held at current angle).
    """
    global front_angle
    if step_size is None:
        step_size = GAIT_STEP
    if step_delay is None:
        step_delay = GAIT_STEP_DELAY
    target = clamp_front(target)
    print("  -> MOVING CH0 to %d deg (CH1 holds at %d)" % (target, rear_angle))

    if check_sensor:
        prox = read_proximity()
        if not update_obstacle_fsm(prox):
            return False

    if front_angle == target:
        set_front(hat, target, state_name)
        return True

    steps = 0
    while front_angle != target:
        if check_sensor and (steps % SENSOR_CHECK_EVERY_STEPS == 0):
            prox = read_proximity()
            if not update_obstacle_fsm(prox):
                print("  ABORT CH0 move at %d deg (hold pose)" % front_angle)
                return False
        set_front(hat, _next_angle(front_angle, target, step_size), state_name)
        time.sleep(step_delay)
        steps += 1
    return True


def move_rear_to(hat, target, state_name, step_size=None, step_delay=None,
                 check_sensor=True):
    """
    Move CH1 only toward target. Returns True if target reached,
    False if aborted for obstacle (pose held at current angle).
    """
    global rear_angle
    if step_size is None:
        step_size = GAIT_STEP
    if step_delay is None:
        step_delay = GAIT_STEP_DELAY
    target = clamp_rear(target)
    print("  -> MOVING CH1 to %d deg (CH0 holds at %d)" % (target, front_angle))

    if check_sensor:
        prox = read_proximity()
        if not update_obstacle_fsm(prox):
            return False

    if rear_angle == target:
        set_rear(hat, target, state_name)
        return True

    steps = 0
    while rear_angle != target:
        if check_sensor and (steps % SENSOR_CHECK_EVERY_STEPS == 0):
            prox = read_proximity()
            if not update_obstacle_fsm(prox):
                print("  ABORT CH1 move at %d deg (hold pose)" % rear_angle)
                return False
        set_rear(hat, _next_angle(rear_angle, target, step_size), state_name)
        time.sleep(step_delay)
        steps += 1
    return True


def return_both_to_neutral(hat, hold=True):
    """Sequential conservative return to 90/90. No sensor gating."""
    print("--- return to neutral (sequential, conservative) ---")
    print("STATE N1: MOVING CH0 to neutral; CH1 holds")
    move_front_to(
        hat, FRONT_NEUTRAL, "N1 CH0 -> neutral",
        step_size=NEUTRAL_STEP, step_delay=NEUTRAL_STEP_DELAY,
        check_sensor=False)
    time.sleep(STATE_PAUSE)
    print("STATE N2: MOVING CH1 to neutral; CH0 holds")
    move_rear_to(
        hat, REAR_NEUTRAL, "N2 CH1 -> neutral",
        step_size=NEUTRAL_STEP, step_delay=NEUTRAL_STEP_DELAY,
        check_sensor=False)
    time.sleep(STATE_PAUSE)
    set_front(hat, FRONT_NEUTRAL, "N3 HOLD CH0")
    set_rear(hat, REAR_NEUTRAL, "N3 HOLD CH1")
    if hold:
        print("Holding level resting posture (PWM still enabled)...")
        time.sleep(NEUTRAL_HOLD)
        set_front(hat, FRONT_NEUTRAL, "N3 HOLD CH0")
        set_rear(hat, REAR_NEUTRAL, "N3 HOLD CH1")


def go_to_start_pose(hat):
    print("=== START POSE: sequential move to 90/90 ===")
    move_front_to(
        hat, FRONT_NEUTRAL, "S0a CH0 -> neutral",
        step_size=NEUTRAL_STEP, step_delay=NEUTRAL_STEP_DELAY,
        check_sensor=False)
    time.sleep(STATE_PAUSE)
    move_rear_to(
        hat, REAR_NEUTRAL, "S0b CH1 -> neutral",
        step_size=NEUTRAL_STEP, step_delay=NEUTRAL_STEP_DELAY,
        check_sensor=False)
    time.sleep(0.3)


# =============================================================================
# Gait driver with obstacle-aware phase resume
# =============================================================================

def run_current_phase(hat):
    """
    Execute gait_phase toward its fixed target.
    If interrupted, leave gait_phase unchanged so resume continues
    toward the same target (no reverse on the same contact side).
    Returns True if phase completed, False if held for obstacle.
    """
    global gait_phase
    channel, name, target, desc = PHASES[gait_phase]
    print("\n=== PHASE %d: %s -> %s=%d (%s) ===" % (
        gait_phase, channel, name, target, desc))

    if channel == "CH1":
        ok = move_rear_to(hat, target, "P%d CH1 -> %s" % (gait_phase, name))
    else:
        ok = move_front_to(hat, target, "P%d CH0 -> %s" % (gait_phase, name))

    if not ok:
        return False

    time.sleep(STATE_PAUSE)
    gait_phase = (gait_phase + 1) % len(PHASES)
    return True


def run_one_ab_cycle(hat):
    """
    Run until phases 0..3 have each completed once from the current phase.
    For --once starting at phase 0: one A stroke + one B stroke.
    """
    completed = 0
    needed = len(PHASES)
    while completed < needed:
        prox = read_proximity()
        if not update_obstacle_fsm(prox):
            wait_while_holding()
            continue
        if run_current_phase(hat):
            completed += 1
        else:
            wait_while_holding()
            # Resume same phase (completed not incremented)


def run_sensor_only():
    """Sensor detection test without moving servos."""
    print("SENSOR-ONLY mode (no servo motion)")
    print("STOP when proximity > %d" % STOP_THRESHOLD)
    print("RESUME when proximity < %d" % RESUME_THRESHOLD)
    print("Higher value = closer. Ctrl+C to exit.\n")
    init_sensor()
    try:
        while True:
            prox = read_proximity()
            allowed = update_obstacle_fsm(prox)
            if allowed:
                status = "CLEAR (would CRAWL)"
            else:
                status = "NEAR  (would HOLD)"
            print("Proximity: %5d  |  mode=%s  |  %s" % (
                prox, motion_mode, status))
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nEnding sensor-only test.")


def parse_args(args):
    global STOP_THRESHOLD, RESUME_THRESHOLD
    if "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)

    sensor_only = "--sensor-only" in args
    loop = "--loop" in args
    once = "--once" in args or (not loop and not sensor_only)

    if "--stop" in args:
        i = args.index("--stop")
        STOP_THRESHOLD = int(args[i + 1])
    if "--resume" in args:
        i = args.index("--resume")
        RESUME_THRESHOLD = int(args[i + 1])

    if RESUME_THRESHOLD >= STOP_THRESHOLD:
        print("Error: resume threshold (%d) must be < stop threshold (%d)" % (
            RESUME_THRESHOLD, STOP_THRESHOLD), file=sys.stderr)
        sys.exit(1)

    return sensor_only, once, loop


def main():
    global gait_phase, motion_mode

    sensor_only, once, loop = parse_args(sys.argv[1:])

    if sensor_only:
        run_sensor_only()
        return

    print("Initializing obstacle-aware crawl...")
    print("SERVO_SWING=%d" % SERVO_SWING)
    print("Speed: fast (step=%d deg, delay=%.3f s)" % (GAIT_STEP, GAIT_STEP_DELAY))
    print("FRONT CH0: %d-%d neutral %d  (A=%d B=%d)" % (
        FRONT_MIN, FRONT_MAX, FRONT_NEUTRAL, FRONT_A, FRONT_B))
    print("REAR  CH1: %d-%d neutral %d  (A=%d B=%d)" % (
        REAR_MIN, REAR_MAX, REAR_NEUTRAL, REAR_A, REAR_B))
    print("Stop threshold: %d  Resume threshold: %d  (hysteresis)" % (
        STOP_THRESHOLD, RESUME_THRESHOLD))
    print("Gait: sequential alternating crawl; one servo at a time")
    print("Mode: %s" % ("continuous --loop" if loop else "single-cycle --once"))
    print("Ctrl+C -> sequential return to neutral.\n")

    try:
        init_sensor()
    except Exception as exc:
        print("ERROR: sensor init failed -- %s" % exc, file=sys.stderr)
        print("Not starting crawl without a working sensor.", file=sys.stderr)
        sys.exit(1)

    hat = pi_servo_hat.PiServoHat()
    hat.restart()
    go_to_start_pose(hat)
    gait_phase = 0
    motion_mode = "crawl"

    try:
        if once and not loop:
            print("\n########## SINGLE CYCLE (A + B strokes) ##########")
            run_one_ab_cycle(hat)
            print("\nSingle-cycle done. Returning to neutral.")
            return_both_to_neutral(hat, hold=True)
            print("Done.")
            return

        cycle = 0
        while True:
            cycle += 1
            print("\n########## CRAWL LOOP %d (phase=%d) ##########" % (
                cycle, gait_phase))
            prox = read_proximity()
            if not update_obstacle_fsm(prox):
                wait_while_holding()
                continue
            if not run_current_phase(hat):
                wait_while_holding()

    except KeyboardInterrupt:
        print("\nCtrl+C - stopping...")
        try:
            return_both_to_neutral(hat, hold=True)
        except Exception as exc:
            print("Warning: could not return to neutral: %s" % exc, file=sys.stderr)
        print("Done.")


if __name__ == "__main__":
    main()
