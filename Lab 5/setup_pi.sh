#!/bin/bash
# Part A in one go, on a fresh Raspberry Pi 5:
#   cd ~/Interactive-Lab-Hub/Lab\ 5 && bash setup_pi.sh
# Safe to re-run: every step skips what is already done.
set -euo pipefail
cd "$(dirname "$0")"

echo "== 1/6 system packages"
sudo apt-get update
# tmux: Part H overnight run; zstd: Ollama installer; pulseaudio-utils/alsa-utils: pactl and aplay for hand_pose.py
sudo apt-get install -y git curl tmux zstd python3-venv pulseaudio-utils alsa-utils

echo "== 2/6 UTF-8 locale (avoids ultralytics' UnicodeEncodeError log spam)"
for line in 'export LANG=C.UTF-8' 'export LC_ALL=C.UTF-8' 'export PYTHONIOENCODING=utf-8'; do
    grep -qxF "$line" ~/.bashrc || echo "$line" >> ~/.bashrc
done
export LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONIOENCODING=utf-8

echo "== 3/6 Python venv + requirements"
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
# mediapipe 0.10.18 only ships wheels up to Python 3.12; Pi OS Trixie's python3 is 3.13
if [ ! -d .venv ]; then
    if python3 -c 'import sys; sys.exit(sys.version_info < (3, 13))'; then
        uv venv --seed --python 3.12 .venv
    else
        uv venv --seed --python "$(command -v python3)" .venv
    fi
fi
source .venv/bin/activate
uv pip install -r requirements.txt
python -c "import cv2, mediapipe, ultralytics; print('cv2', cv2.__version__, '| mediapipe', mediapipe.__version__, '| ultralytics', ultralytics.__version__)"

echo "== 4/6 YOLO26 nano -> NCNN"
if [ ! -d yolo26n_ncnn_model ]; then
    yolo export model=yolo26n.pt format=ncnn
fi
yolo predict model=yolo26n_ncnn_model source=https://ultralytics.com/images/bus.jpg project="$PWD"

echo "== 5/6 Ollama + Qwen"
command -v ollama >/dev/null || curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3.5:0.8b
ollama pull qwen3:0.6b
ollama list

echo "== 6/6 Part C helper"
chmod +x loop_audio.sh

echo
echo "Done. Next: 'source .venv/bin/activate', then 'python snap.py --delay 3' and screenshot 'ollama list' for the README."
