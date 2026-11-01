r"""
Part G: the bedtime ritual. Make a Quiet Coyote at the webcam, hear a short music intro, and the night starts.

    tmux new -s night
    cd ~/Interactive-Lab-Hub/Lab\ 5 && source .venv/bin/activate
    python bedtime.py --web          # --web: watch the camera in a browser at http://<pi>:8000

After the intro this process becomes night.sh, so it keeps running inside tmux until WAKE.
Quiet Coyote: thumb touching middle and ring fingers (the snout), index and pinky up (the ears).

Outputs:
  - Browser view (--web): demo only. It shows the camera and the gesture; nothing in it is logged or used by the report.
  - The real report: night.sh runs watch.py (logs/<night>_A.jsonl, _B.jsonl), then tarot.py prints the card
    and reading to this console and saves reports/<night>_A_tarot.json and _B_tarot.json.
  - Mini PiTFT: demo presentation of that saved A report (pitft_report.py, started by night.sh at the end).
"""
import math
import os
import subprocess
import sys

import cv2
import HandTrackingModule as htm

INTRO_SECONDS = 8
os.chdir(os.path.dirname(os.path.abspath(__file__)))

if "--web" in sys.argv:  # demo-only screen display; the report never reads from it
    from web_preview import WebPreview
    preview = WebPreview(8000)
    print("open", preview.start(), "in a browser", flush=True)
else:
    preview = None


def quiet_coyote(lm):
    d = lambda a, b: math.hypot(lm[a][1] - lm[b][1], lm[a][2] - lm[b][2])
    # same rule as hand_pose.py: 4 thumb, 8 index, 12 middle, 16 ring, 20 pinky
    return d(4, 8) > 100 and d(8, 12) > 100 and d(12, 16) < 100 and d(16, 20) > 100 and d(4, 16) < 100


cap = cv2.VideoCapture(0)
cap.set(3, 640)
cap.set(4, 480)
detector = htm.handDetector(detectionCon=int(0.7))
print("make a quiet coyote to start the night", flush=True)

while True:
    ok, img = cap.read()
    if not ok:
        sys.exit("could not read from the camera (is another script using it?)")
    img = detector.findHands(img)
    lm = detector.findPosition(img, draw=False)
    if lm and quiet_coyote(lm):
        break
    if preview:  # demo-only screen display
        cv2.putText(img, "make a quiet coyote to start", (20, 40), cv2.FONT_HERSHEY_COMPLEX, 0.8, (255, 255, 255), 2)
        preview.update(img)

cv2.putText(img, "good night", (20, 40), cv2.FONT_HERSHEY_COMPLEX, 1, (255, 255, 255), 2)
if preview:  # demo-only screen display
    preview.update(img)
cap.release()
print("quiet coyote! playing the intro, then the night begins", flush=True)
subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "50%"],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
subprocess.run(["aplay", "-q", "-D", "pulse", "-d", str(INTRO_SECONDS), "Peaceful_Mind.wav"])

# The real run: the same night.sh as a manual start. Its console output and the files it writes are the report.
os.execvp("bash", ["bash", "night.sh"])
