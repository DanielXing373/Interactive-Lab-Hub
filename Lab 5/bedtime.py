r"""
Part G: the bedtime ritual. Say "good night" to the Pi, it answers out loud and plays a short music intro,
then the night starts.

    tmux new -s night
    cd ~/Interactive-Lab-Hub/Lab\ 5 && source .venv/bin/activate
    python bedtime.py
    python bedtime.py --words "good night,sleep well"      # other trigger phrases
    WAKE=$(date -d '+3 min' +%H:%M) python bedtime.py     # a short night for testing or filming

Speech is recognized on the Pi (faster-whisper base.en, as in Lab 3, primed with the trigger words): the microphone is recorded in short
windows and each window is transcribed; nothing leaves the Pi. The spoken reply uses Piper, the neural voice
from Lab 3; get the voice once with:  python -m piper.download_voices en_US-lessac-medium --data-dir voices After the intro this process becomes
night.sh, so it keeps running inside tmux until WAKE.

Outputs:
  - The spoken answer and the music are the acknowledgement only; nothing in them is logged or used by the report.
  - The real report: night.sh runs watch.py (logs/<night>_A.jsonl, _B.jsonl), then tarot.py prints the card
    and reading to this console and saves reports/<night>_A_tarot.json and _B_tarot.json.
  - Mini PiTFT: demo presentation of that saved A report (pitft_report.py, started by night.sh at the end).
"""
import argparse
import os
import pathlib
import re
import subprocess
import sys

import sounddevice as sd
from faster_whisper import WhisperModel

INTRO_SECONDS = 8
RATE = 16000
VOICE = "en_US-lessac-medium"  # Piper neural voice, as in Lab 3
os.chdir(os.path.dirname(os.path.abspath(__file__)))

parser = argparse.ArgumentParser()
parser.add_argument("--words", default="good night,goodnight", help="comma-separated trigger phrases")
parser.add_argument("--seconds", type=float, default=4, help="length of each listening window")
parser.add_argument("--model", default="base.en", help="faster-whisper model (base.en: tiny.en misses short phrases)")
args = parser.parse_args()
words = [w.strip().lower() for w in args.words.split(",") if w.strip()]

print("loading speech model...", flush=True)
model = WhisperModel(args.model, device="cpu", compute_type="int8")
print(f'say "{words[0]}" to start the night', flush=True)

while True:
    audio = sd.rec(int(args.seconds * RATE), samplerate=RATE, channels=1, dtype="float32")
    sd.wait()
    segments, _ = model.transcribe(audio.reshape(-1), beam_size=1, language="en", hotwords=", ".join(words))
    heard = " ".join(s.text.strip() for s in segments).strip()
    if heard:
        print(f"heard: {heard}", flush=True)
    if any(w in re.sub(r"[^a-z ]", "", heard.lower()) for w in words):
        break

print("good night! playing the intro, then the night begins", flush=True)
subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "50%"],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
voices = next((d for d in (pathlib.Path("voices"), pathlib.Path("../Lab 3/voices"))
               if (d / f"{VOICE}.onnx").exists()), None)
if voices:
    tts = subprocess.Popen([sys.executable, "-m", "piper", "--model", VOICE, "--data-dir", str(voices),
                            "--output-raw", "--", "Good night. I will watch the waterhole for you."],
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    subprocess.run(["aplay", "-q", "-r", "22050", "-f", "S16_LE", "-t", "raw", "-"], stdin=tts.stdout)
    tts.wait()
else:
    print(f"no Piper voice {VOICE} in voices/ (see the top of this file), skipping the spoken reply", flush=True)
subprocess.run(["aplay", "-q", "-D", "pulse", "-d", str(INTRO_SECONDS), "Peaceful_Mind.wav"])

# The real run: the same night.sh as a manual start. Its console output and the files it writes are the report.
os.execvp("bash", ["bash", "night.sh"])
