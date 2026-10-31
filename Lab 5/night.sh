#!/bin/bash
# The real night: two live streams taking turns until WAKE, then a tarot card from each log.
# Start it inside tmux so it survives closing the laptop:
#   tmux new -s night
#   cd ~/Interactive-Lab-Hub/Lab\ 5 && bash night.sh
# Detach with Ctrl-b d, come back with: tmux attach -t night
# Change a setting for one night like this: WAKE=06:30 INTERVAL=20 bash night.sh
set -u
cd "$(dirname "$0")"
source .venv/bin/activate
A=${A:-https://www.youtube.com/watch?v=XyPU5-pNg5E}     # Amboseli, Tortilis Camp (Kenya)
A_CONTEXT=${A_CONTEXT:-"a waterhole in Amboseli, Kenya, below Mount Kilimanjaro"}
B=${B:-https://www.youtube.com/watch?v=JMMoRwYo5kE}     # Okaukuejo, Etosha (Namibia)
B_CONTEXT=${B_CONTEXT:-"the Okaukuejo waterhole in Etosha, Namibia"}
WAKE=${WAKE:-06:45}            # stop watching here, so the card is ready by 7
INTERVAL=${INTERVAL:-30}       # seconds between looks at each stream
QUESTION=${QUESTION:-"What does today hold for me?"}

end=$(date -d "$WAKE" +%s)
[ "$end" -le "$(date +%s)" ] && end=$(date -d "tomorrow $WAKE" +%s)
duration=$(( end - $(date +%s) ))
night=$(date +%Y%m%d)
echo "watching until $(date -d @"$end" '+%a %H:%M') ($((duration / 60)) min), one look every $INTERVAL s per stream"
vcgencmd measure_temp

python watch.py "$A" --interval "$INTERVAL" --duration "$duration" --max-height 480 \
    --name "${night}_A" > "logs/${night}_A.out" 2>&1 &
python watch.py "$B" --interval "$INTERVAL" --duration "$duration" --max-height 480 \
    --offset $(( INTERVAL / 2 )) --name "${night}_B" > "logs/${night}_B.out" 2>&1 &
echo "running. Follow along with: tail -f logs/${night}_A.out logs/${night}_B.out"
wait

echo "== morning"
vcgencmd measure_temp
python tarot.py "logs/${night}_A.jsonl" --context "$A_CONTEXT" --question "$QUESTION"
python tarot.py "logs/${night}_B.jsonl" --context "$B_CONTEXT" --question "$QUESTION"
