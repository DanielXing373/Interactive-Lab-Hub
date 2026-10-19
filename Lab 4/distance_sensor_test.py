#!/usr/bin/env python3
"""
Distance / proximity sensor test (VCNL4040 via Qwiic).

Uses the same course library as qwiic_distance.py and windmill_coaster.py:
  import qwiic_proximity
  sensor = qwiic_proximity.QwiicProximity()
  sensor.get_proximity()

IMPORTANT — how to read the numbers:
  get_proximity() returns a proximity count, NOT millimeters.
  HIGHER value  => object is CLOSER
  LOWER value   => object is FARTHER / clear

Calibrate STOP_THRESHOLD by watching printed values:
  1) Clear path (no hand/object)  -> note typical "far" reading
  2) Hand/object at stop distance -> note typical "near" reading
  3) Pick a threshold between those two (used later in delivery_robot_v1.py)

Usage:
  python distance_sensor_test.py
"""

import sys
import time
import qwiic_proximity

# Starting guess only — tune after watching live readings.
# windmill_coaster.py uses CUP_THRESHOLD = 100 for a cup on a coaster.
SUGGESTED_STOP_THRESHOLD = 100
POLL_DELAY = 0.2


def main():
    print("SparkFun Qwiic Proximity (VCNL4040) test")
    print("Higher proximity value = closer object\n")

    sensor = qwiic_proximity.QwiicProximity()
    if not sensor.connected:
        print(
            "ERROR: Qwiic proximity sensor not found.\n"
            "Check the Qwiic cable to the Servo pHAT Qwiic port.",
            file=sys.stderr,
        )
        sys.exit(1)

    sensor.begin()
    print(f"Suggested start for STOP_THRESHOLD: {SUGGESTED_STOP_THRESHOLD}")
    print("Wave a hand in front of the sensor. Ctrl+C to exit.\n")

    try:
        while True:
            prox = sensor.get_proximity()
            if prox > SUGGESTED_STOP_THRESHOLD:
                status = "NEAR (would STOP)"
            else:
                status = "FAR  (would CRAWL)"
            print(f"Proximity: {prox:5d}  |  {status}")
            time.sleep(POLL_DELAY)
    except KeyboardInterrupt:
        print("\nEnding distance sensor test.")


if __name__ == "__main__":
    main()
