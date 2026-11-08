#!/usr/bin/env python3
"""Attack Pi: VCNL4040 proximity sensor -> IDD/<team>/mouse-game/attack

    python pi_attack.py               # play
    python pi_attack.py --calibrate   # print readings, publish nothing

Readings are raw proximity counts (higher = closer), as in Lab 4.
Tune with PROX_TRIGGER / PROX_RELEASE environment variables.
"""

import sys
import time

import qwiic_proximity

import config
from controllers import ProximitySwing
from pi_common import Publisher


def main():
    calibrate = "--calibrate" in sys.argv
    sensor = qwiic_proximity.QwiicProximity()
    if not sensor.connected:
        print("VCNL4040 not found. Check the Qwiic cable and `i2cdetect -y 1` (0x60).",
              file=sys.stderr)
        sys.exit(1)
    sensor.begin()
    swing = ProximitySwing()
    print(f"Proximity OK. trigger>={swing.trigger} release<={swing.release} "
          f"confirm={swing.confirm} samples. Starts disarmed until the sensor is clear.")

    publisher = None
    if not calibrate:
        publisher = Publisher("attack")
        if not publisher.wait_connected():
            print("[MQTT] not connected yet; will keep trying in the background")
        print(f"Publishing to {config.TOPIC_ATTACK}. Ctrl+C to stop.")

    period = 1.0 / config.PROX_SAMPLE_HZ
    try:
        while True:
            prox = sensor.get_proximity()
            action = swing.update(prox)
            if calibrate:
                print(f"proximity={prox:5d}  armed={swing.armed!s:5}  {action or ''}")
            elif action:
                publisher.publish(config.TOPIC_ATTACK, {"action": "swing"})
            time.sleep(period)
    except KeyboardInterrupt:
        print("\nStopping attack controller.")
    finally:
        if publisher:
            publisher.close()


if __name__ == "__main__":
    main()
