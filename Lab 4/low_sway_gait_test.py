#!/usr/bin/env python3
"""
Low-sway gait test: proven sequential crawl from coordinated_gait_test.py,
with independent CH1 amplitude and CH1 crawl-speed experiments.

Fixed:
  - SERVO_SWING=180
  - CH0 Fast crawl: 3 deg steps, 0.01 s delay
  - CH0 range: 60-120 (A=120, B=60), neutral 90
  - Strictly sequential gait (never move both at once)
  - CH0 holds while CH1 switches sides (no CH0 reposition)
  - Neutral return: always 1 deg / 0.05 s, CH0 then CH1

CH1 amplitude presets (--preset):
  original  70-110
  gentle    75-105
  minimal   80-100   (default)

CH1 crawl speed presets (--rear-speed); applied only while crawling:
  fast    3 deg / 0.01 s
  smooth  1 deg / 0.02 s   (default)
  slow    1 deg / 0.05 s

Usage (from Lab 4, with venv activated):
  python low_sway_gait_test.py
  python low_sway_gait_test.py --preset minimal --rear-speed smooth --once
  python low_sway_gait_test.py --preset original --rear-speed fast --loop
  python low_sway_gait_test.py --preset gentle --rear-speed slow --once
"""

import sys
import time
import pi_servo_hat

# =============================================================================
# Channels
# =============================================================================
FRONT_CHANNEL = 0
REAR_CHANNEL = 1
SERVO_SWING = 180

# =============================================================================
# Front (CH0) -- fixed proven Fast crawl
# =============================================================================
FRONT_NEUTRAL = 90
FRONT_MIN = 60
FRONT_MAX = 120
FRONT_A = FRONT_MAX  # 120
FRONT_B = FRONT_MIN  # 60

FRONT_STEP = 3
FRONT_STEP_DELAY = 0.01

# =============================================================================
# Rear (CH1) -- amplitude presets
# =============================================================================
REAR_NEUTRAL = 90

CH1_PRESETS = {
    "original": (70, 110),
    "gentle": (75, 105),
    "minimal": (80, 100),
}
DEFAULT_PRESET = "minimal"

REAR_MIN = CH1_PRESETS[DEFAULT_PRESET][0]
REAR_MAX = CH1_PRESETS[DEFAULT_PRESET][1]
REAR_A = REAR_MAX
REAR_B = REAR_MIN
PRESET_NAME = DEFAULT_PRESET

# =============================================================================
# Rear (CH1) -- crawl speed presets (not used for neutral return)
# =============================================================================
CH1_SPEED_PRESETS = {
    "fast": (3, 0.01),
    "smooth": (1, 0.02),
    "slow": (1, 0.05),
}
DEFAULT_REAR_SPEED = "smooth"

REAR_STEP = CH1_SPEED_PRESETS[DEFAULT_REAR_SPEED][0]
REAR_STEP_DELAY = CH1_SPEED_PRESETS[DEFAULT_REAR_SPEED][1]
REAR_SPEED_NAME = DEFAULT_REAR_SPEED

# Conservative neutral return (both channels)
NEUTRAL_STEP = 1
NEUTRAL_STEP_DELAY = 0.05
STATE_PAUSE = 0.3
NEUTRAL_HOLD = 1.0

front_angle = FRONT_NEUTRAL
rear_angle = REAR_NEUTRAL


def clamp_front(angle):
    return max(FRONT_MIN, min(FRONT_MAX, int(angle)))


def clamp_rear(angle):
    return max(REAR_MIN, min(REAR_MAX, int(angle)))


def _log_pose(label, moving):
    tag = "  [%s | moving=%s]" % (label, moving)
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
    """Advance toward target without overshooting; always can land exactly."""
    if current == target:
        return target
    if target > current:
        return min(current + step_size, target)
    return max(current - step_size, target)


def move_front_to(hat, target, state_name, step_size=None, step_delay=None):
    """CH0 crawl defaults to fixed Fast settings. Always hits exact target."""
    global front_angle
    if step_size is None:
        step_size = FRONT_STEP
    if step_delay is None:
        step_delay = FRONT_STEP_DELAY
    target = clamp_front(target)
    print("  -> MOVING CH0 to %d deg (CH1 holds at %d) step=%d delay=%.3fs" % (
        target, rear_angle, step_size, step_delay))
    if front_angle == target:
        set_front(hat, target, state_name)
        return
    while front_angle != target:
        set_front(hat, _next_angle(front_angle, target, step_size), state_name)
        time.sleep(step_delay)


def move_rear_to(hat, target, state_name, step_size=None, step_delay=None):
    """CH1 crawl defaults to selected --rear-speed. Always hits exact target."""
    global rear_angle
    if step_size is None:
        step_size = REAR_STEP
    if step_delay is None:
        step_delay = REAR_STEP_DELAY
    target = clamp_rear(target)
    print("  -> MOVING CH1 to %d deg (CH0 holds at %d) step=%d delay=%.3fs" % (
        target, front_angle, step_size, step_delay))
    if rear_angle == target:
        set_rear(hat, target, state_name)
        return
    while rear_angle != target:
        set_rear(hat, _next_angle(rear_angle, target, step_size), state_name)
        time.sleep(step_delay)


def return_both_to_neutral(hat, hold=True):
    """Sequential conservative return: CH0 to 90, then CH1 to 90."""
    print("--- return to neutral (sequential, conservative) ---")
    print("STATE N1: MOVING CH0 to neutral; CH1 holds")
    move_front_to(
        hat, FRONT_NEUTRAL, "N1 CH0 -> neutral",
        step_size=NEUTRAL_STEP, step_delay=NEUTRAL_STEP_DELAY)
    time.sleep(STATE_PAUSE)
    print("STATE N2: MOVING CH1 to neutral; CH0 holds")
    move_rear_to(
        hat, REAR_NEUTRAL, "N2 CH1 -> neutral",
        step_size=NEUTRAL_STEP, step_delay=NEUTRAL_STEP_DELAY)
    time.sleep(STATE_PAUSE)
    set_front(hat, FRONT_NEUTRAL, "N3 HOLD CH0")
    set_rear(hat, REAR_NEUTRAL, "N3 HOLD CH1")
    if hold:
        print("Holding level resting posture (PWM still enabled)...")
        time.sleep(NEUTRAL_HOLD)
        set_front(hat, FRONT_NEUTRAL, "N3 HOLD CH0")
        set_rear(hat, REAR_NEUTRAL, "N3 HOLD CH1")


def run_ab_half_cycle(hat, from_start=False):
    """
    Proven sequential gait:
      CH1 -> A (CH0 holds), CH0 -> A (CH1 holds),
      CH1 -> B directly (CH0 holds at A), CH0 -> B (CH1 holds).
    No CH0 reposition before CH1 switches sides.
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
    print("=== START POSE: sequential move to 90/90 (conservative) ===")
    move_front_to(
        hat, FRONT_NEUTRAL, "S0a CH0 -> neutral",
        step_size=NEUTRAL_STEP, step_delay=NEUTRAL_STEP_DELAY)
    time.sleep(STATE_PAUSE)
    move_rear_to(
        hat, REAR_NEUTRAL, "S0b CH1 -> neutral",
        step_size=NEUTRAL_STEP, step_delay=NEUTRAL_STEP_DELAY)
    time.sleep(0.5)


def apply_preset(name):
    global REAR_MIN, REAR_MAX, REAR_A, REAR_B, PRESET_NAME
    name = name.lower()
    if name not in CH1_PRESETS:
        print("Error: unknown preset '%s'. Choose: %s" % (
            name, ", ".join(sorted(CH1_PRESETS.keys()))), file=sys.stderr)
        sys.exit(1)
    REAR_MIN, REAR_MAX = CH1_PRESETS[name]
    REAR_A = REAR_MAX
    REAR_B = REAR_MIN
    PRESET_NAME = name


def apply_rear_speed(name):
    global REAR_STEP, REAR_STEP_DELAY, REAR_SPEED_NAME
    name = name.lower()
    if name not in CH1_SPEED_PRESETS:
        print("Error: unknown --rear-speed '%s'. Choose: %s" % (
            name, ", ".join(sorted(CH1_SPEED_PRESETS.keys()))), file=sys.stderr)
        sys.exit(1)
    REAR_STEP, REAR_STEP_DELAY = CH1_SPEED_PRESETS[name]
    REAR_SPEED_NAME = name


def parse_args(args):
    if "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)

    loop = "--loop" in args
    once = "--once" in args or (not loop)

    preset = DEFAULT_PRESET
    if "--preset" in args:
        i = args.index("--preset")
        if i + 1 >= len(args):
            print("Error: --preset requires original|gentle|minimal", file=sys.stderr)
            sys.exit(1)
        preset = args[i + 1]
    apply_preset(preset)

    rear_speed = DEFAULT_REAR_SPEED
    if "--rear-speed" in args:
        i = args.index("--rear-speed")
        if i + 1 >= len(args):
            print("Error: --rear-speed requires fast|smooth|slow", file=sys.stderr)
            sys.exit(1)
        rear_speed = args[i + 1]
    apply_rear_speed(rear_speed)

    return once, loop


def main():
    once, loop = parse_args(sys.argv[1:])

    print("Initializing low-sway gait test...")
    print("SERVO_SWING=%d" % SERVO_SWING)
    print("CH0 crawl: fast fixed (step=%d deg, delay=%.3f s)" % (
        FRONT_STEP, FRONT_STEP_DELAY))
    print("FRONT CH0: %d-%d neutral %d  (A=%d B=%d) -- fixed" % (
        FRONT_MIN, FRONT_MAX, FRONT_NEUTRAL, FRONT_A, FRONT_B))
    print("REAR  CH1 amplitude preset=%s: %d-%d neutral %d  (A=%d B=%d)" % (
        PRESET_NAME, REAR_MIN, REAR_MAX, REAR_NEUTRAL, REAR_A, REAR_B))
    print("REAR  CH1 crawl speed=%s (step=%d deg, delay=%.3f s)" % (
        REAR_SPEED_NAME, REAR_STEP, REAR_STEP_DELAY))
    print("Neutral return: always conservative (step=%d deg, delay=%.3f s)" % (
        NEUTRAL_STEP, NEUTRAL_STEP_DELAY))
    print("Gait: STRICTLY SEQUENTIAL (CH0 holds while CH1 switches sides)")
    print("Mode: %s" % ("continuous --loop" if loop else "single cycle --once"))
    print("Ctrl+C / exit -> sequential return to neutral.\n")

    hat = pi_servo_hat.PiServoHat()
    hat.restart()
    go_to_start_pose(hat)

    try:
        cycle = 0
        from_start = True
        while True:
            cycle += 1
            print("\n########## GAIT CYCLE %d preset=%s rear-speed=%s ##########" % (
                cycle, PRESET_NAME, REAR_SPEED_NAME))
            run_ab_half_cycle(hat, from_start=from_start)
            from_start = False

            if once and not loop:
                print("\nSingle-cycle done. Returning to neutral.")
                return_both_to_neutral(hat, hold=True)
                print("Done.")
                return

    except KeyboardInterrupt:
        print("\nCtrl+C - stopping...")
        try:
            return_both_to_neutral(hat, hold=True)
        except Exception as exc:
            print("Warning: could not return to neutral: %s" % exc, file=sys.stderr)
        print("Done.")


if __name__ == "__main__":
    main()
