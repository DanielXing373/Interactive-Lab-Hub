#!/usr/bin/env python3
"""
First coordinated walking / gait test (CH0 front + CH1 rear).

Reuses SparkFun Servo pHAT via pi_servo_hat (same as rear/front_servo_test.py).
Does NOT use the distance sensor. Does NOT modify delivery_robot.py.

Gait (discrete state machine):
  1) CH1 neutral -> tilt A; CH0 stays neutral
  2) Hold CH1 at A; CH0 short stroke toward FRONT_A
  3) CH1 A -> B while CH0 reverses toward FRONT_B
  4) Hold CH1 at B; CH0 opposite short stroke toward FRONT_B
     (completes / holds the B stroke, then for a clean cycle
      both return toward neutral before the next cycle)
  5) Repeat (continuous mode) or stop (single-cycle mode)

Physical directions are unverified — flip the mapping constants below
if left/right or front stroke feel reversed.

Usage (from Lab 4, with venv activated):
  python coordinated_gait_test.py           # one safe cycle, then neutral
  python coordinated_gait_test.py --once    # same as default
  python coordinated_gait_test.py --loop    # repeat until Ctrl+C
"""

import sys
import time
import pi_servo_hat

# =============================================================================
# Channels
# =============================================================================
FRONT_CHANNEL = 0  # CH0 — front legs
REAR_CHANNEL = 1   # CH1 — rear legs

# =============================================================================
# Angle limits (keep within these clamps)
# =============================================================================
FRONT_NEUTRAL = 90
FRONT_MIN = 80
FRONT_MAX = 100

REAR_NEUTRAL = 90
REAR_MIN = 70
REAR_MAX = 110

# =============================================================================
# Direction mapping — flip these if the cardboard moves the wrong way
# =============================================================================
# CH1 first tilt extreme (state 1). Swap REAR_A / REAR_B to invert left/right.
REAR_A = REAR_MAX   # 110
REAR_B = REAR_MIN   # 70

# CH0 stroke targets. Swap FRONT_A / FRONT_B to invert stroke direction.
FRONT_A = FRONT_MAX  # 100 — stroke used while rear is at REAR_A
FRONT_B = FRONT_MIN  # 80  — opposite stroke while rear is at REAR_B

# =============================================================================
# Timing (slow for calibration)
# =============================================================================
STEP = 1
STEP_DELAY = 0.05
STATE_PAUSE = 0.3  # brief pause between states so motion is easy to watch


# -----------------------------------------------------------------------------
# Servo helpers — always step 1° at a time (no abrupt jumps)
# -----------------------------------------------------------------------------

front_angle = FRONT_NEUTRAL
rear_angle = REAR_NEUTRAL


def clamp_front(angle):
    return max(FRONT_MIN, min(FRONT_MAX, int(angle)))


def clamp_rear(angle):
    return max(REAR_MIN, min(REAR_MAX, int(angle)))


def apply_angles(hat, front=None, rear=None, label=""):
    """Write current (or updated) angles to the pHAT and log."""
    global front_angle, rear_angle
    if front is not None:
        front_angle = clamp_front(front)
        hat.move_servo_position(FRONT_CHANNEL, front_angle)
    if rear is not None:
        rear_angle = clamp_rear(rear)
        hat.move_servo_position(REAR_CHANNEL, rear_angle)
    tag = f"  [{label}]" if label else ""
    print(f"FRONT ch0={front_angle:3d}°  REAR ch1={rear_angle:3d}°{tag}")


def move_front_to(hat, target, state_name):
    """Smoothly walk CH0 to target in 1° steps. CH1 unchanged."""
    global front_angle
    target = clamp_front(target)
    if front_angle == target:
        apply_angles(hat, front=target, label=state_name)
        return
    step = STEP if target > front_angle else -STEP
    for angle in range(front_angle, target, step):
        apply_angles(hat, front=angle + step, label=state_name)
        time.sleep(STEP_DELAY)


def move_rear_to(hat, target, state_name):
    """Smoothly walk CH1 to target in 1° steps. CH0 unchanged."""
    global rear_angle
    target = clamp_rear(target)
    if rear_angle == target:
        apply_angles(hat, rear=target, label=state_name)
        return
    step = STEP if target > rear_angle else -STEP
    for angle in range(rear_angle, target, step):
        apply_angles(hat, rear=angle + step, label=state_name)
        time.sleep(STEP_DELAY)


def move_both_to(hat, front_target, rear_target, state_name):
    """
    Move CH0 and CH1 together toward targets without jumps.
    Interpolates over the longer travel so both finish together.
    """
    global front_angle, rear_angle
    front_target = clamp_front(front_target)
    rear_target = clamp_rear(rear_target)
    f0, r0 = front_angle, rear_angle
    n = max(abs(front_target - f0), abs(rear_target - r0), 1)
    for i in range(1, n + 1):
        f = int(round(f0 + (front_target - f0) * i / n))
        r = int(round(r0 + (rear_target - r0) * i / n))
        apply_angles(hat, front=f, rear=r, label=state_name)
        time.sleep(STEP_DELAY)


def return_both_to_neutral(hat):
    """Smoothly return both servos to 90° (used on Ctrl+C and end of --once)."""
    print("--- returning both servos to neutral ---")
    move_both_to(hat, FRONT_NEUTRAL, REAR_NEUTRAL, "NEUTRAL")


# -----------------------------------------------------------------------------
# Gait state machine
# -----------------------------------------------------------------------------

def run_one_cycle(hat):
    """Execute states 1–4 once. Leaves legs at end-of-state-4 pose."""
    print("\n=== STATE 1: rear tilt to A; front stays neutral ===")
    move_front_to(hat, FRONT_NEUTRAL, "S1 hold front")
    move_rear_to(hat, REAR_A, "S1 rear -> A")
    time.sleep(STATE_PAUSE)

    print("\n=== STATE 2: hold rear at A; front stroke toward A ===")
    move_front_to(hat, FRONT_A, "S2 front stroke A")
    time.sleep(STATE_PAUSE)

    print("\n=== STATE 3: rear A->B while front reverses toward B ===")
    move_both_to(hat, FRONT_B, REAR_B, "S3 shift to B")
    time.sleep(STATE_PAUSE)

    print("\n=== STATE 4: hold rear at B; opposite front stroke at B ===")
    # Opposite stroke target is FRONT_B (reached during state 3).
    # Re-assert / finish at FRONT_B while rear holds REAR_B — no jump.
    move_front_to(hat, FRONT_B, "S4 front stroke B")
    time.sleep(STATE_PAUSE)


def main():
    args = sys.argv[1:]
    if "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)

    loop = "--loop" in args
    # Default and --once: single cycle
    once = (not loop) or ("--once" in args)

    print("Initializing Servo pHAT...")
    print(f"FRONT CH{FRONT_CHANNEL}: {FRONT_MIN}–{FRONT_MAX}, neutral {FRONT_NEUTRAL}")
    print(f"REAR  CH{REAR_CHANNEL}: {REAR_MIN}–{REAR_MAX}, neutral {REAR_NEUTRAL}")
    print(f"Mapping: REAR_A={REAR_A} REAR_B={REAR_B}  FRONT_A={FRONT_A} FRONT_B={FRONT_B}")
    print(f"Mode: {'continuous --loop' if loop else 'single cycle --once'}")
    print("Distance sensor NOT used. Ctrl+C -> both to neutral.\n")

    hat = pi_servo_hat.PiServoHat()
    hat.restart()
    apply_angles(hat, front=FRONT_NEUTRAL, rear=REAR_NEUTRAL, label="start")
    time.sleep(0.5)

    try:
        cycle = 0
        while True:
            cycle += 1
            print(f"\n########## GAIT CYCLE {cycle} ##########")
            run_one_cycle(hat)

            if once and not loop:
                print("\nSingle-cycle mode: returning to neutral and exiting.")
                return_both_to_neutral(hat)
                print("Done.")
                return

            # Continuous: return front to neutral, then rear B -> A via next cycle's state 1.
            # Bridge: front to neutral while rear holds B so state 1 starts cleanly.
            print("\n=== BRIDGE: front to neutral before next cycle ===")
            move_front_to(hat, FRONT_NEUTRAL, "bridge")
            # Next state 1 moves rear B -> A (via move_rear_to from current).

    except KeyboardInterrupt:
        print("\nCtrl+C — stopping gait...")
        try:
            return_both_to_neutral(hat)
        except Exception as exc:
            print(f"Warning: could not return to neutral: {exc}", file=sys.stderr)
        print("Done.")


if __name__ == "__main__":
    main()
