"""
The night shift for any source: one look every --interval seconds, YOLO on that frame,
one JSON line per look in logs/<name>.jsonl. report.py turns the log into the morning report.

    python watch.py clip.mp4                                  # a fake night from a video file
    python watch.py https://www.youtube.com/watch?v=...       # a YouTube live stream (or a normal video)
    python watch.py https://example.com/cam/latest.jpg        # a webcam that publishes a JPEG
    python watch.py photos/                                   # a folder of photos
    python watch.py 0                                         # the USB webcam
    python watch.py clip.mp4 --interval 10 --classes zebra,elephant,giraffe
    python watch.py <live url> --duration 28800 --name waterhole   # stop after 8 hours
    python watch.py clip.mp4 --show                           # watch YOLO's boxes in a window (VNC)

Stop it with Ctrl-C; a video file or image folder also stops at its end.

The log, one JSON object per line:
    {"type": "start", "t": ..., "source": ..., "interval": 5, "model": ..., "classes": [...], ...}
    {"type": "frame", "t": "2026-10-31T23:00:05", "pos": 5.0, "counts": {"zebra": 3},
     "objects": [{"cls": "zebra", "conf": 0.82, "box": [0.31, 0.55, 0.12, 0.2], "zone": "left"}, ...],
     "reading": "3 zebra (left, left, center)", "snap": "snaps/<name>/20261031-230005_00001.jpg", "ms": 312}
    {"type": "error", "t": ..., "msg": "no fresh frame (stream dropped, reconnecting)"}
    {"type": "end", "t": ..., "frames": 5760, "reason": "eof" | "duration" | "ctrl-c"}

box is [center x, center y, width, height] as fractions of the frame, so it does not depend
on the stream's resolution. Every look is logged, also the empty ones ("counts": {}):
"nothing there at 03:00" is data too. A snapshot is saved whenever the counts change.
"""
import argparse
import collections
import datetime
import json
import os
import pathlib
import sys
import time

import cv2
from ultralytics import YOLO

from sources import KINDS, open_source

sys.stdout.reconfigure(encoding="utf-8")
parser = argparse.ArgumentParser()
parser.add_argument("source", help="video file, URL, image folder or webcam index (see above)")
parser.add_argument("--interval", type=float, default=5, help="seconds between looks")
parser.add_argument("--duration", type=float, default=0, help="stop after this many seconds (0: until the end or Ctrl-C)")
parser.add_argument("--classes", help="comma-separated COCO names to keep, e.g. person,dog (default: all 80)")
parser.add_argument("--conf", type=float, default=0.35, help="minimum confidence, 0 to 1")
parser.add_argument("--imgsz", type=int, default=640, help="frame size the model looks at; small far-away animals need 640")
parser.add_argument("--model", default="yolo26n_ncnn_model", help="exported in Part A; yolo26n.pt also works")
parser.add_argument("--name", help="run name for logs/<name>.jsonl and snaps/<name>/ (default: date and time)")
parser.add_argument("--kind", choices=KINDS, default="auto", help="force the source type if auto-detect guesses wrong")
parser.add_argument("--max-height", type=int, default=720, help="highest stream resolution to ask YouTube for")
parser.add_argument("--offset", type=float, default=0, help="wait this many seconds before the first look, "
                    "so two watchers on one Pi take turns instead of looking at the same moment")
parser.add_argument("--live-mode", choices=["auto", "continuous", "on-demand"], default="auto",
                    help="live streams: decode all the time, or connect only for each look "
                         "(auto: on-demand when --interval is 15 s or more, which keeps the Pi cool)")
parser.add_argument("--max-temp", type=float, default=80, help="CPU above this many degrees C: skip a look to cool down")
parser.add_argument("--no-snaps", action="store_true", help="do not save a frame when the counts change")
parser.add_argument("--snap-boxes", action="store_true", help="draw YOLO's boxes on the saved frames (default: the raw frame)")
parser.add_argument("--show", action="store_true", help="show the frames with YOLO's boxes (needs VNC)")
args = parser.parse_args()

model = YOLO(args.model, task="detect")
classes = None
if args.classes:
    by_name = {n: i for i, n in model.names.items()}
    unknown = [c for c in args.classes.split(",") if c.strip() not in by_name]
    if unknown:
        raise SystemExit(f"not a COCO class: {', '.join(unknown)}. Known: {', '.join(model.names.values())}")
    classes = [by_name[c.strip()] for c in args.classes.split(",")]

if args.show and sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
    print("no display found (plain ssh?): running without the window. Use VNC to see it.", flush=True)
    args.show = False

name = args.name or datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
log_path = pathlib.Path("logs") / f"{name}.jsonl"
snap_dir = pathlib.Path("snaps") / name
log_path.parent.mkdir(exist_ok=True)
if not args.no_snaps:
    snap_dir.mkdir(parents=True, exist_ok=True)
log = open(log_path, "a", encoding="utf-8")


def write(entry):
    log.write(json.dumps(entry, ensure_ascii=False) + "\n")
    log.flush()


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def cpu_temp():
    try:
        return round(int(open("/sys/class/thermal/thermal_zone0/temp").read()) / 1000, 1)
    except OSError:
        return None             # not a Pi


def interpret(r):
    """Turn one YOLO result into counts, objects and a short reading in words.
    The reading is what a person (or Qwen) reads; counts and objects are what report.py computes on."""
    h, w = r.orig_shape
    objects = []
    for box in r.boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        cx = (x1 + x2) / 2 / w
        objects.append({
            "cls": model.names[int(box.cls)],
            "conf": round(float(box.conf), 2),
            "box": [round(cx, 3), round((y1 + y2) / 2 / h, 3), round((x2 - x1) / w, 3), round((y2 - y1) / h, 3)],
            "zone": "left" if cx < 1 / 3 else "right" if cx > 2 / 3 else "center",
        })
    objects.sort(key=lambda o: (o["cls"], o["box"][0]))
    counts = dict(collections.Counter(o["cls"] for o in objects))
    parts = []
    for cls, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        zones = ", ".join(o["zone"] for o in objects if o["cls"] == cls)
        parts.append(f"{n} {cls} ({zones})")
    return counts, objects, "; ".join(parts) or "nothing"


print(f"opening {args.source} ...", flush=True)
on_demand = args.live_mode == "on-demand" or (args.live_mode == "auto" and args.interval >= 15)
source = open_source(args.source, args.kind, args.max_height, on_demand)
write({"type": "start", "t": now(), "source": source.name, "live": source.live,
       "interval": args.interval, "model": args.model, "imgsz": args.imgsz, "conf": args.conf,
       "classes": [model.names[c] for c in classes] if classes else None, "temp_c": cpu_temp()})
print(f"watching {source.name}, one look every {args.interval:g} s, log in {log_path}. Ctrl-C to stop.", flush=True)

t_start, frames, last_counts, reason = time.time(), 0, None, "ctrl-c"
try:
    time.sleep(args.offset)
    while True:
        if args.duration and time.time() - t_start >= args.duration:
            reason = "duration"
            break
        temp = cpu_temp()
        if temp and temp > args.max_temp:
            write({"type": "error", "t": now(), "msg": f"too hot ({temp} C), skipping a look", "temp_c": temp})
            print(f"too hot ({temp} C), skipping a look", flush=True)
            time.sleep(args.interval)
            continue
        try:
            frame = source.next(args.interval)
        except Exception as e:
            write({"type": "error", "t": now(), "msg": str(e)})
            print("hiccup:", e, flush=True)
            continue
        if frame is None:
            reason = "eof"
            break
        t0 = time.time()
        r = model.predict(frame.image, imgsz=args.imgsz, conf=args.conf, classes=classes, verbose=False)[0]
        ms = round((time.time() - t0) * 1000)
        counts, objects, reading = interpret(r)
        entry = {"type": "frame", "t": frame.t.isoformat(timespec="seconds"), "pos": frame.pos,
                 "counts": counts, "objects": objects, "reading": reading, "snap": None, "ms": ms,
                 "temp_c": temp}
        if frame.label:
            entry["label"] = frame.label
        if counts != last_counts and counts and not args.no_snaps:
            snap = snap_dir / f"{frame.t:%Y%m%d-%H%M%S}_{frames:05d}.jpg"
            cv2.imwrite(str(snap), r.plot() if args.snap_boxes else frame.image)
            entry["snap"] = snap.as_posix()
        if counts != last_counts:
            print(f"{frame.t:%H:%M:%S} {reading}", flush=True)
        last_counts = counts
        write(entry)
        frames += 1
        if args.show:
            view = r.plot()
            cv2.putText(view, reading[:80], (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.imshow("watch", view)
            if cv2.waitKey(1) == ord("q"):
                break
except KeyboardInterrupt:
    pass
finally:
    write({"type": "end", "t": now(), "frames": frames, "reason": reason})
    source.close()
    if args.show:
        cv2.destroyAllWindows()
    print(f"\n{frames} looks logged to {log_path} ({reason}). Next: python report.py {log_path.as_posix()}")
