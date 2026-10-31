#!/bin/bash
# Rehearsal before the real night, about 5 minutes on the Pi:
#   cd ~/Interactive-Lab-Hub/Lab\ 5 && bash mock_test.sh
# 1. checks the tools, 2. a video with animals (should draw a Minor Arcana card),
# 3. both live streams for 2 minutes taking turns (at our evening it is night in Africa,
#    so expect "nothing" and a Major Arcana card: that tests the quiet-night path).
set -u
cd "$(dirname "$0")"
source .venv/bin/activate
A=${A:-https://www.youtube.com/watch?v=XyPU5-pNg5E}     # Amboseli, Tortilis Camp (Kenya)
B=${B:-https://www.youtube.com/watch?v=JMMoRwYo5kE}     # Okaukuejo, Etosha (Namibia)
rm -f logs/mock_*.jsonl reports/mock_*

echo "== 1/4 tools"
python -c "import cv2, ultralytics, yt_dlp; print('python packages ok')"
ls -d yolo26n_ncnn_model tarot/the_fool.jpg
curl -s localhost:11434/api/tags | grep -q 'qwen3.5:0.8b' && echo "ollama + qwen3.5:0.8b ok" || echo "!! ollama or qwen3.5:0.8b missing"
vcgencmd measure_temp

echo "== 2/4 a video with zebras and elephants"
python watch.py "https://www.youtube.com/watch?v=Jl435_WOTlA" --interval 5 --duration 120 --name mock_video
python tarot.py logs/mock_video.jsonl

echo "== 3/4 two live streams, 2 minutes, one look every 30 s, taking turns"
python watch.py "$A" --interval 30 --duration 120 --max-height 480 --name mock_A &
python watch.py "$B" --interval 30 --duration 120 --max-height 480 --offset 15 --name mock_B &
wait
vcgencmd measure_temp

echo "== 4/4 cards from the live streams"
python tarot.py logs/mock_A.jsonl --dry-run
python tarot.py logs/mock_B.jsonl --context "the Okaukuejo waterhole in Etosha, Namibia" --dry-run

echo
echo "Done. Saved frames with animals are in snaps/mock_*/, readings in reports/."
