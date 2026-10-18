#!/usr/bin/env python3
"""
Delivery crawl: sequential Fast gait + front-mounted VCNL4040 leg detection.

The sensor faces forward and treats a nearby person/leg as the delivery target.
When proximity stays at or above DELIVERY_THRESHOLD for CONFIRM_READINGS
consecutive samples, delivery is confirmed permanently:
  1) stop issuing new crawl commands (hold current pose briefly)
  2) CH0 gradually to 90 while CH1 holds
  3) CH1 gradually to 90 while CH0 holds at 90
  4) hold both at 90 for 1 second
  5) print DELIVERY COMPLETE and exit (no crawl resume)

Neutral return uses 1 deg steps / 0.05 s delays, SERVO_SWING=180,
one servo at a time. Ctrl+C also returns to neutral sequentially.

Gait (strictly sequential, Fast preset from coordinated_gait_test.py):
  CH1 tilt A -> CH0 stroke A -> CH1 tilt B -> CH0 stroke B -> repeat

Usage (from Lab 4, with venv activated):
  python sensor_crawl_test.py --sensor-only
  python sensor_crawl_test.py --once
  python sensor_crawl_test.py --loop
  python sensor_crawl_test.py --loop --threshold 20
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

# Proven Fast preset
GAIT_STEP = 3
GAIT_STEP_DELAY = 0.01

# Conservative return-to-neutral (Ctrl+C / unfinished --once only)
NEUTRAL_STEP = 1
NEUTRAL_STEP_DELAY = 0.05
STATE_PAUSE = 0.15
NEUTRAL_HOLD = 1.0

# Delivery target detection (raw proximity counts, NOT cm)
# Higher value = closer. Front-mounted sensor aiming at a person's leg.
DELIVERY_THRESHOLD = 20
CONFIRM_READINGS = 3  # consecutive samples >= threshold required

SENSOR_CHECK_EVERY_STEPS = 1


# =============================================================================
# Shared runtime state
# =============================================================================
front_angle = FRONT_NEUTRAL
rear_angle = REAR_NEUTRAL
proximity_sensor = None

motion_mode = "crawl"       # "crawl" or "delivered"
delivery_complete = False
delivery_hit_count = 0

# Gait phase: 0 CH1->A, 1 CH0->A, 2 CH1->B, 3 CH0->B
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
# Proximity / delivery confirmation
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
    Require CONFIRM_READINGS consecutive samples >= DELIVERY_THRESHOLD.
    On confirm: set delivery_complete permanently and stop crawl commands.
    Does NOT print DELIVERY COMPLETE yet -- caller runs complete_delivery()
    to return to neutral first.
    Returns True if delivery is confirmed (crawl must stop).
    """
    global delivery_hit_count, delivery_complete, motion_mode

    if delivery_complete:
        return True

    if prox >= DELIVERY_THRESHOLD:
        delivery_hit_count += 1
        print("Delivery candidate %d/%d (proximity=%d >= %d)" % (
            delivery_hit_count, CONFIRM_READINGS, prox, DELIVERY_THRESHOLD))
        if delivery_hit_count >= CONFIRM_READINGS:
            delivery_complete = True
            motion_mode = "delivered"
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


def complete_delivery(hat):
    """
    After confirmation: keep current pose, then sequential rest return:
      CH0 -> 90 (CH1 holds), then CH1 -> 90 (CH0 holds),
      hold 1 s at 90/90, print DELIVERY COMPLETE, do not resume crawl.
    """
    print("Delivery rest sequence: sequential return to 90/90")
    print("STATE D1: MOVING CH0 to 90; CH1 holds at %d" % rear_angle)
    move_front_to(
        hat, FRONT_NEUTRAL, "D1 CH0 -> 90",
        step_size=NEUTRAL_STEP, step_delay=NEUTRAL_STEP_DELAY,
        check_sensor=False)
    time.sleep(STATE_PAUSE)

    print("STATE D2: MOVING CH1 to 90; CH0 holds at 90")
    move_rear_to(
        hat, REAR_NEUTRAL, "D2 CH1 -> 90",
        step_size=NEUTRAL_STEP, step_delay=NEUTRAL_STEP_DELAY,
        check_sensor=False)
    time.sleep(STATE_PAUSE)

    set_front(hat, FRONT_NEUTRAL, "D3 HOLD CH0")
    set_rear(hat, REAR_NEUTRAL, "D3 HOLD CH1")
    print("Holding resting posture for %.1f s..." % NEUTRAL_HOLD)
    time.sleep(NEUTRAL_HOLD)
    set_front(hat, FRONT_NEUTRAL, "D3 HOLD CH0")
    set_rear(hat, REAR_NEUTRAL, "D3 HOLD CH1")
    print("DELIVERY COMPLETE")


# =============================================================================
# Sequential servo moves with mid-move delivery checks
# =============================================================================

def move_front_to(hat, target, state_name, step_size=None, step_delay=None,
                  check_sensor=True):
    """
    Move CH0 only. Returns True if target reached.
    Returns False if delivery confirmed (pose held; no further commands).
    """
    global front_angle
    if step_size is None:
        step_size = GAIT_STEP
    if step_delay is None:
        step_delay = GAIT_STEP_DELAY
    target = clamp_front(target)
    print("  -> MOVING CH0 to %d deg (CH1 holds at %d)" % (target, rear_angle))

    if check_sensor:
        if check_delivery(read_proximity()):
            return False

    if front_angle == target:
        set_front(hat, target, state_name)
        return True

    steps = 0
    while front_angle != target:
        if check_sensor and (steps % SENSOR_CHECK_EVERY_STEPS == 0):
            if check_delivery(read_proximity()):
                print("  STOP CH0 at %d deg (delivery; hold pose)" % front_angle)
                return False
        set_front(hat, _next_angle(front_angle, target, step_size), state_name)
        time.sleep(step_delay)
        steps += 1
    return True


def move_rear_to(hat, target, state_name, step_size=None, step_delay=None,
                 check_sensor=True):
    """
    Move CH1 only. Returns True if target reached.
    Returns False if delivery confirmed (pose held; no further commands).
    """
    global rear_angle
    if step_size is None:
        step_size = GAIT_STEP
    if step_delay is None:
        step_delay = GAIT_STEP_DELAY
    target = clamp_rear(target)
    print("  -> MOVING CH1 to %d deg (CH0 holds at %d)" % (target, front_angle))

    if check_sensor:
        if check_delivery(read_proximity()):
            return False

    if rear_angle == target:
        set_rear(hat, target, state_name)
        return True

    steps = 0
    while rear_angle != target:
        if check_sensor and (steps % SENSOR_CHECK_EVERY_STEPS == 0):
            if check_delivery(read_proximity()):
                print("  STOP CH1 at %d deg (delivery; hold pose)" % rear_angle)
                return False
        set_rear(hat, _next_angle(rear_angle, target, step_size), state_name)
        time.sleep(step_delay)
        steps += 1
    return True


def return_both_to_neutral(hat, hold=True):
    """Sequential conservative return to 90/90 (Ctrl+C / unfinished --once)."""
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
# Gait driver
# =============================================================================

def run_current_phase(hat):
    """
    Execute current gait phase. Returns:
      True  - phase completed
      False - delivery confirmed (crawl finished; pose held)
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
    One A + one B stroke (4 phases), or stop early on delivery.
    Returns True if delivery completed during the cycle.
    """
    completed = 0
    needed = len(PHASES)
    while completed < needed:
        if delivery_complete:
            return True
        if check_delivery(read_proximity()):
            return True
        if run_current_phase(hat):
            completed += 1
        else:
            return True  # delivery during move
    return delivery_complete


def run_sensor_only():
    """Calibrate delivery threshold without moving servos."""
    print("SENSOR-ONLY mode (no servo motion)")
    print("Delivery when proximity >= %d for %d consecutive readings" % (
        DELIVERY_THRESHOLD, CONFIRM_READINGS))
    print("Higher value = closer. Ctrl+C to exit.\n")
    init_sensor()
    try:
        while True:
            prox = read_proximity()
            done = check_delivery(prox)
            if done:
                status = "CONFIRMED (would rest then DELIVERY COMPLETE)"
            elif prox >= DELIVERY_THRESHOLD:
                status = "NEAR candidate %d/%d" % (
                    delivery_hit_count, CONFIRM_READINGS)
            else:
                status = "FAR (would CRAWL)"
            print("Proximity: %5d  |  mode=%s  |  %s" % (
                prox, motion_mode, status))
            if done:
                print("DELIVERY COMPLETE")
                print("Sensor-only: no servo motion. Exiting.")
                return
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nEnding sensor-only test.")


def parse_args(args):
    global DELIVERY_THRESHOLD
    if "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)

    sensor_only = "--sensor-only" in args
    loop = "--loop" in args
    once = "--once" in args or (not loop and not sensor_only)

    if "--threshold" in args:
        i = args.index("--threshold")
        DELIVERY_THRESHOLD = int(args[i + 1])

    return sensor_only, once, loop


def main():
    global gait_phase, motion_mode, delivery_complete, delivery_hit_count

    sensor_only, once, loop = parse_args(sys.argv[1:])

    if sensor_only:
        run_sensor_only()
        return

    print("Initializing delivery crawl...")
    print("SERVO_SWING=%d" % SERVO_SWING)
    print("Speed: fast (step=%d deg, delay=%.3f s)" % (GAIT_STEP, GAIT_STEP_DELAY))
    print("FRONT CH0: %d-%d neutral %d  (A=%d B=%d)" % (
        FRONT_MIN, FRONT_MAX, FRONT_NEUTRAL, FRONT_A, FRONT_B))
    print("REAR  CH1: %d-%d neutral %d  (A=%d B=%d)" % (
        REAR_MIN, REAR_MAX, REAR_NEUTRAL, REAR_A, REAR_B))
    print("Delivery threshold: %d (raw)  confirm: %d consecutive readings" % (
        DELIVERY_THRESHOLD, CONFIRM_READINGS))
    print("Gait: sequential alternating crawl; one servo at a time")
    print("Mode: %s" % ("continuous --loop" if loop else "single-cycle --once"))
    print("On delivery: stop crawl, sequential rest to 90/90, then DELIVERY COMPLETE.")
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
    delivery_complete = False
    delivery_hit_count = 0

    try:
        if once and not loop:
            print("\n########## SINGLE CYCLE (A + B strokes) ##########")
            delivered = run_one_ab_cycle(hat)
            if delivered:
                complete_delivery(hat)
                print("Done.")
                return
            print("\nSingle-cycle done without delivery. Returning to neutral.")
            return_both_to_neutral(hat, hold=True)
            print("Done.")
            return

        cycle = 0
        while not delivery_complete:
            cycle += 1
            print("\n########## CRAWL LOOP %d (phase=%d) ##########" % (
                cycle, gait_phase))
            if check_delivery(read_proximity()):
                break
            if not run_current_phase(hat):
                break

        if delivery_complete:
            complete_delivery(hat)
        print("Done.")

    except KeyboardInterrupt:
        print("\nCtrl+C - stopping...")
        try:
            return_both_to_neutral(hat, hold=True)
        except Exception as exc:
            print("Warning: could not return to neutral: %s" % exc, file=sys.stderr)
        print("Done.")



if __name__ == "__main__":
    main()
