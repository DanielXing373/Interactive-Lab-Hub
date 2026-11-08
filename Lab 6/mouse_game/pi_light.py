#!/usr/bin/env python3
"""Light Pi: USB webcam + MediaPipe Hands -> IDD/<team>/mouse-game/light

    python pi_light.py               # play
    python pi_light.py --calibrate   # print hand openness, publish nothing
    python pi_light.py --web         # also stream the annotated camera to http://<pi>:8000

Hand openness sets the brightness: open hand = 100, closed fist = 0, partly
open = in between. Payload: {"brightness": 0-100}.
"""

import math
import sys
import time

import cv2
import mediapipe as mp

import config
from controllers import BrightnessFilter, openness_from_ratios
from pi_common import Publisher
from web_preview import WebPreview

FINGERS = ((8, 5), (12, 9), (16, 13), (20, 17))  # (tip, knuckle) for index..pinky
WRIST = 0


def finger_ratios(landmarks):
    """Tip-to-wrist distance divided by knuckle-to-wrist distance, per finger."""
    wrist = landmarks[WRIST]

    def dist(i):
        p = landmarks[i]
        return math.hypot(p.x - wrist.x, p.y - wrist.y)

    return [dist(tip) / (dist(knuckle) or 1e-6) for tip, knuckle in FINGERS]


def main():
    calibrate = "--calibrate" in sys.argv
    preview = None
    if "--web" in sys.argv:
        preview = WebPreview(8000)
        print("Camera preview at", preview.start())

    cap = cv2.VideoCapture(config.CAMERA_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
    if not cap.isOpened():
        print(f"Camera {config.CAMERA_INDEX} not found. Try CAMERA_INDEX=1.", file=sys.stderr)
        sys.exit(1)

    hands = mp.solutions.hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        model_complexity=0,
        min_detection_confidence=config.POSE_CONFIDENCE,
        min_tracking_confidence=0.5,
    )
    draw = mp.solutions.drawing_utils
    light = BrightnessFilter()
    print(f"closed ratio={config.HAND_CLOSED_RATIO} open ratio={config.HAND_OPEN_RATIO} "
          f"step={light.step}% max {config.LIGHT_PUBLISH_HZ:g} msgs/s")

    publisher = None
    if not calibrate:
        publisher = Publisher("light")
        if not publisher.wait_connected():
            print("[MQTT] not connected yet; will keep trying in the background")
        print(f"Publishing to {config.TOPIC_LIGHT}. Ctrl+C to stop.")

    last_print = 0.0
    frames = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.05)
                continue
            frames += 1
            results = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            now = time.monotonic()
            score, ratios, level = 0.0, None, None
            if results.multi_hand_landmarks:
                score = results.multi_handedness[0].classification[0].score
                ratios = finger_ratios(results.multi_hand_landmarks[0].landmark)
                level = openness_from_ratios(ratios)
                if preview:
                    draw.draw_landmarks(frame, results.multi_hand_landmarks[0],
                                        mp.solutions.hands.HAND_CONNECTIONS)

            brightness = None
            if ratios is None:
                light.update(None, now)
            elif score >= config.POSE_CONFIDENCE:
                brightness = light.update(level, now)
            if brightness is not None:
                if calibrate:
                    print(f"SEND -> brightness {brightness}")
                else:
                    publisher.publish(config.TOPIC_LIGHT, {"brightness": brightness})

            if now - last_print >= 0.5:
                fps = frames / (now - last_print) if last_print else 0.0
                if ratios is None:
                    print(f"no hand  fps={fps:4.1f}")
                else:
                    print(f"openness={level:5.1f}  conf={score:.2f}  "
                          f"ratios={' '.join(f'{r:.2f}' for r in ratios)}  fps={fps:4.1f}")
                last_print, frames = now, 0

            if preview:
                label = "no hand" if level is None else f"{level:.0f}% conf {score:.2f}"
                cv2.putText(frame, label, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
                preview.update(frame)
    except KeyboardInterrupt:
        print("\nStopping light controller.")
    finally:
        cap.release()
        hands.close()
        if publisher:
            publisher.close()


if __name__ == "__main__":
    main()
