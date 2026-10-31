"""
The morning: turn a watch.py log into a report. The counting is done here, in Python;
Qwen only gets the finished numbers and a short timeline, and writes them up.

    python report.py logs/20261031-230000.jsonl                         # 3-sentence summary
    python report.py logs/waterhole.jsonl --context "a waterhole in South Africa"
    python report.py logs/waterhole.jsonl --format timeline --sentences 5
    python report.py logs/waterhole.jsonl --format json                 # for a display or a servo
    python report.py logs/waterhole.jsonl --lang Chinese
    python report.py logs/waterhole.jsonl --prompt-file my_prompt.txt   # your own instructions
    python report.py logs/waterhole.jsonl --dry-run                     # show what Qwen would get, do not ask

Formats (--format): summary, timeline, headline, json. A --prompt-file replaces the format's
instructions; it may use {context}, {sentences} and {lang}. The data always goes before the
instructions, because a small model follows what it read last.
The report is printed and saved to reports/<log name>.txt (.json for --format json).

If nothing was seen all night the model is not asked: it would invent something.
"""
import argparse
import collections
import datetime
import itertools
import json
import pathlib
import sys
import time

import requests

sys.stdout.reconfigure(encoding="utf-8")
parser = argparse.ArgumentParser()
parser.add_argument("log", help="a logs/<name>.jsonl written by watch.py")
parser.add_argument("--context", default="a camera", help="what the camera was looking at, in a few words")
parser.add_argument("--format", choices=["summary", "timeline", "headline", "json"], default="summary")
parser.add_argument("--sentences", type=int, default=3, help="length of summary, or number of timeline moments")
parser.add_argument("--lang", default="English", help="language of the report")
parser.add_argument("--question", help="one extra question for the report to answer")
parser.add_argument("--prompt-file", help="your own instructions instead of the format's")
parser.add_argument("--model", default="qwen3.5:0.8b")
parser.add_argument("--max-tokens", type=int, default=300, help="hard cap on the length of the answer")
parser.add_argument("--temperature", type=float, default=0.3)
parser.add_argument("--min-looks", type=int, default=2,
                    help="ignore a change that lasts fewer looks than this (YOLO flickers)")
parser.add_argument("--bucket", type=int, default=0, help="minutes per row in the hourly table (0: pick one)")
parser.add_argument("--max-events", type=int, default=40, help="longest timeline handed to the model")
parser.add_argument("--dry-run", action="store_true", help="print the data and the prompt, do not ask Qwen")
parser.add_argument("--ollama", default="http://localhost:11434")
args = parser.parse_args()

entries = [json.loads(line) for line in open(args.log, encoding="utf-8") if line.strip()]
start = next((e for e in entries if e.get("type") == "start"), {})
looks = [e for e in entries if e.get("type") == "frame"]
errors = [e for e in entries if e.get("type") == "error"]
if not looks:
    raise SystemExit(f"no looks in {args.log}")
for e in looks:
    e["dt"] = datetime.datetime.fromisoformat(e["t"])
interval = start.get("interval") or 5


def hm(dt, seconds=False):
    return dt.strftime("%H:%M:%S" if seconds else "%H:%M")


def says(rng):
    """{"zebra": (1, 7), "elephant": (3, 3)} -> '1-7 zebra, 3 elephant'; None is a gap in the data."""
    if rng is None:
        return "no data"
    parts = [f"{lo}-{hi} {c}" if lo != hi else f"{hi} {c}"
             for c, (lo, hi) in sorted(rng.items(), key=lambda kv: -kv[1][1])]
    return ", ".join(parts) or "nothing"


def duration(seconds):
    h, m = divmod(round(seconds / 60), 60)
    return f"{h} h {m} min" if h else f"{m} min" if m else f"{round(seconds)} s"


def steady(flags, k):
    """YOLO flickers: fill absences shorter than k looks, then drop appearances shorter than k looks."""
    runs = [[v, len(list(g))] for v, g in itertools.groupby(flags)]
    for i, r in enumerate(runs):
        if not r[0] and r[1] < k and 0 < i < len(runs) - 1:
            r[0] = True
    runs = [[v, sum(n for _, n in g)] for v, g in itertools.groupby(runs, key=lambda r: r[0])]
    for r in runs:
        if r[0] and r[1] < k:
            r[0] = False
    return [v for v, n in runs for _ in range(n)]


first, last = looks[0]["dt"], looks[-1]["dt"]
span = (last - first).total_seconds() + interval
seen = sorted({c for e in looks for c in e["counts"]})

# A gap of more than three intervals between looks (stream down, Pi busy) splits the night into stretches;
# flicker smoothing and visits never reach across a gap.
stretches = [[looks[0]]]
for prev, e in zip(looks, looks[1:]):
    if (e["dt"] - prev["dt"]).total_seconds() > 3 * interval:
        stretches.append([])
    stretches[-1].append(e)

# Timeline: runs of looks with the same set of (steadily) present classes, with the count range in each run.
timeline, visits = [], collections.Counter()
for i, stretch in enumerate(stretches):
    if i:
        timeline.append({"start": stretches[i - 1][-1]["dt"], "end": stretch[0]["dt"], "range": None})
    present = {c: steady([c in e["counts"] for e in stretch], args.min_looks) for c in seen}
    for c in seen:
        visits[c] += sum(1 for v, _ in itertools.groupby(present[c]) if v)
    keys = [frozenset(c for c in seen if present[c][j]) for j in range(len(stretch))]
    j = 0
    for key, group in itertools.groupby(keys):
        n = len(list(group))
        part = stretch[j:j + n]
        j += n
        rng = {c: (min(e["counts"].get(c, 0) for e in part if c in e["counts"]),
                   max(e["counts"].get(c, 0) for e in part))
               for c in key if any(c in e["counts"] for e in part)}
        timeline.append({"start": part[0]["dt"], "end": part[-1]["dt"], "range": rng})

stats = {}
for c in seen:
    present = [e for e in looks if c in e["counts"]]
    peak = max(present, key=lambda e: e["counts"][c])
    stats[c] = {"share": len(present) / len(looks), "visits": visits[c], "max": peak["counts"][c],
                "max_at": peak["dt"], "first": present[0]["dt"], "last": present[-1]["dt"]}

bucket = args.bucket or next((m for m in (1, 5, 10, 15, 30, 60, 120) if span / 60 / m <= 12), 120)
rows = collections.OrderedDict()
for e in looks:
    minute = (e["dt"].hour * 60 + e["dt"].minute) // bucket * bucket
    key = e["dt"].replace(hour=minute // 60, minute=minute % 60, second=0)
    rows.setdefault(key, []).append(e["counts"])

lines = [f"Watched {args.context} from {hm(first)} to {hm(last)} ({duration(span)}), "
         f"one look every {interval:g} s, {len(looks)} looks."]
if errors:
    lines.append(f"The feed failed {len(errors)} times (first at {hm(datetime.datetime.fromisoformat(errors[0]['t']))}).")
gaps = [r for r in timeline if r["range"] is None]
if gaps:
    lines.append("No data: " + ", ".join(f"{hm(g['start'])}-{hm(g['end'])}" for g in gaps) + ".")
lines.append("")
lines.append("What was seen:")
for c, s in sorted(stats.items(), key=lambda kv: -kv[1]["share"]):
    times = "1 time" if s["visits"] == 1 else f"{s['visits']} separate times"
    lines.append(f"- {c}: in view {s['share']:.0%} of the time, came {times}, at most {s['max']} at once "
                 f"(at {hm(s['max_at'])}), first seen {hm(s['first'])}, last seen {hm(s['last'])}")
lines.append("")
lines.append(f"Every {bucket} min (average number in view per look):")
for key, counts in rows.items():
    avg = {c: sum(x.get(c, 0) for x in counts) / len(counts) for c in seen}
    lines.append(f"{hm(key)} " + (", ".join(f"{c} {v:.1f}" for c, v in avg.items() if v >= 0.05) or "nothing"))
dropped = 0
if len(timeline) > args.max_events:
    keep = sorted(sorted(timeline, key=lambda r: -(r["end"] - r["start"]).total_seconds())[:args.max_events],
                  key=lambda r: r["start"])
    dropped, timeline = len(timeline) - len(keep), keep
lines.append("")
lines.append("Timeline (from-to: what was in view):")
for r in timeline:
    lines.append(f"{hm(r['start'], True)}-{hm(r['end'], True)} {says(r['range'])}")
if dropped:
    lines.append(f"({dropped} shorter moments left out)")
data = "\n".join(lines)

if not seen:
    quiet = f"Quiet night. Watched {args.context} from {hm(first)} to {hm(last)} ({len(looks)} looks) and saw nothing."
    report = json.dumps({"headline": quiet, "nothing_happened": True}) if args.format == "json" else quiet
    print(data + "\n\n" + report)
    raise SystemExit

FORMATS = {
    "summary": "Using only the facts in the data, write exactly {sentences} short, friendly sentences for the owner: "
               "what was seen and how many, the busiest moment with its time, and one change from the timeline.",
    "timeline": "List the {sentences} most notable moments from the timeline, one per line, "
                "with the real time from the data, like '04:52 - three zebra arrived'. "
                "Then add one sentence about the night as a whole.",
    "headline": "Write a single headline for the night, under fifteen words.",
    "json": "Fill in the fields. Use real times from the data as HH:MM.",
}
SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "highlights": {"type": "array", "items": {"type": "object",
                       "properties": {"time": {"type": "string"}, "what": {"type": "string"}},
                       "required": ["time", "what"]}},
        "busiest_time": {"type": "string"},
        "unusual": {"type": "boolean"},
        "nothing_happened": {"type": "boolean"},
    },
    "required": ["headline", "highlights", "busiest_time", "unusual", "nothing_happened"],
}

instructions = open(args.prompt_file, encoding="utf-8").read() if args.prompt_file else FORMATS[args.format]
instructions = instructions.format(context=args.context, sentences=args.sentences, lang=args.lang)
if args.question:
    instructions += f"\nAlso answer: {args.question}"
system = (f"You report what an object detector saw on {args.context}. "
          f"The detector only tells which objects were in view, how many, and when. You know nothing else: "
          f"no light, weather, sounds, scenery or feelings. Never invent objects or events that are not in the data. "
          f"Answer in {args.lang}.")
prompt = f"Data:\n{data}\n\n{instructions}"

if args.dry_run:
    print(f"[system]\n{system}\n\n[prompt]\n{prompt}")
    raise SystemExit

request = {"model": args.model, "system": system, "prompt": prompt, "think": False, "stream": False,
           "options": {"temperature": args.temperature, "num_predict": args.max_tokens, "num_ctx": 8192}}
if args.format == "json":
    request["format"] = SCHEMA
t0 = time.time()
r = requests.post(f"{args.ollama}/api/generate", json=request, timeout=900)
r.raise_for_status()
reply = r.json()
report = reply["response"].strip()
if args.format == "json":
    try:
        report = json.dumps(json.loads(report), indent=2, ensure_ascii=False)
    except json.JSONDecodeError:
        pass

out = pathlib.Path("reports") / (pathlib.Path(args.log).stem + (".json" if args.format == "json" else ".txt"))
out.parent.mkdir(exist_ok=True)
out.write_text(report + "\n", encoding="utf-8")
note = ", cut off by --max-tokens" if reply.get("done_reason") == "length" else ""
print(f"{data}\n\n{report}\n\n[{args.model}, {time.time() - t0:.1f} s{note}, saved to {out.as_posix()}]")
