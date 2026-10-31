"""
Where the frames come from. watch.py asks a source for one frame every --interval seconds
and does not care whether it is a video file, a YouTube live stream or a folder of photos.

    video file      clip.mp4                        stepped through by video time, faster than real time
    YouTube         https://youtube.com/watch?v=..  live streams in real time, normal videos like a file
    stream URL      https://.../index.m3u8, rtsp:// HLS, RTSP or any URL ffmpeg can open, in real time
    snapshot URL    https://.../latest.jpg          a webcam JPEG that refreshes, fetched every interval
    image folder    photos/                         every image in the folder, oldest first
    webcam          0                               the USB webcam, as in Part B

Every source returns Frame(image, t, pos, label): t is the time the reading is logged under.
For live sources that is now. A video file has no clock, so t is the start of the run plus
the position in the video: a two-minute clip becomes a two-minute fake night.
"""
import datetime
import pathlib
import subprocess
import sys
import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np
import requests

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
KINDS = ["auto", "file", "youtube", "stream", "snapshot", "folder", "webcam"]


@dataclass
class Frame:
    image: np.ndarray
    t: datetime.datetime
    pos: float | None = None        # seconds into a video file, None for live sources
    label: str | None = None        # file name for image folders


class VideoFile:
    """A finite video (local path or URL), sampled every `interval` seconds of video time."""

    live = False

    def __init__(self, path, name=None):
        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            raise SystemExit(f"cannot open video: {path}")
        self.name = name or str(path)
        self.start = datetime.datetime.now().astimezone().replace(microsecond=0)
        self.pos = 0.0
        fps = self.cap.get(cv2.CAP_PROP_FPS) or 0
        frames = self.cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        self.length = frames / fps if fps > 0 and frames > 0 else None

    def next(self, interval):
        if self.length is not None and self.pos > self.length:
            return None
        self.cap.set(cv2.CAP_PROP_POS_MSEC, self.pos * 1000)
        ok, image = self.cap.read()
        if not ok:
            return None
        frame = Frame(image, self.start + datetime.timedelta(seconds=self.pos), round(self.pos, 2))
        self.pos += interval
        return frame

    def close(self):
        self.cap.release()


class LiveStream:
    """A stream that never ends. A thread keeps reading so the frame we take is the newest one,
    and reconnects (asking `open_url` again, YouTube URLs expire after a few hours) when it drops."""

    live = True

    def __init__(self, open_url, name):
        self.open_url, self.name = open_url, name
        self.latest, self.stamp, self.last_taken = None, 0.0, 0.0
        self.lock = threading.Lock()
        self.stopped = False
        self.status = "connecting"
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while not self.stopped:
            try:
                cap = cv2.VideoCapture(self.open_url())
            except Exception as e:
                self.status = f"cannot resolve stream: {e}"
                time.sleep(15)
                continue
            if not cap.isOpened():
                self.status = "cannot open stream"
                time.sleep(15)
                continue
            self.status = "ok"
            misses = 0
            while not self.stopped and misses < 100:
                ok, image = cap.read()
                if not ok:
                    misses += 1
                    time.sleep(0.1)
                    continue
                misses = 0
                with self.lock:
                    self.latest, self.stamp = image, time.time()
            cap.release()
            self.status = "stream dropped, reconnecting"
            time.sleep(5)

    def next(self, interval):
        wait = self.last_taken + interval - time.time()
        if wait > 0:
            time.sleep(wait)
        deadline = time.time() + max(30, interval)
        while time.time() < deadline:
            with self.lock:
                fresh = self.latest is not None and self.stamp > self.last_taken
                if fresh and time.time() - self.stamp < max(10, 2 * interval):
                    self.last_taken = time.time()
                    return Frame(self.latest.copy(), datetime.datetime.now().astimezone().replace(microsecond=0))
            time.sleep(0.2)
        self.last_taken = time.time()
        raise RuntimeError(f"no fresh frame ({self.status})")

    def close(self):
        self.stopped = True


class OnDemandStream:
    """A stream opened only for the moment of each look: connect, take one frame, disconnect.
    Between looks nothing is decoded, so the Pi stays cool. Worth it for intervals of 15 s and more."""

    live = True

    def __init__(self, open_url, name):
        self.open_url, self.name = open_url, name
        self.url, self.last_taken = None, 0.0

    def _grab(self):
        cap = cv2.VideoCapture(self.url)
        try:
            for _ in range(10):         # the first reads after connecting can come back empty
                ok, image = cap.read()
                if ok:
                    return image
            return None
        finally:
            cap.release()

    def next(self, interval):
        wait = self.last_taken + interval - time.time()
        if wait > 0:
            time.sleep(wait)
        self.last_taken = time.time()
        if self.url is None:
            self.url = self.open_url()
        image = self._grab()
        if image is None:               # YouTube URLs expire after a few hours: ask again once
            self.url = self.open_url()
            image = self._grab()
        if image is None:
            raise RuntimeError("stream gave no frame")
        return Frame(image, datetime.datetime.now().astimezone().replace(microsecond=0))

    def close(self):
        pass


class Snapshot:
    """A webcam that publishes one JPEG at a fixed URL and refreshes it every few seconds."""

    live = True

    def __init__(self, url):
        self.url = self.name = url
        self.last_taken = 0.0

    def next(self, interval):
        wait = self.last_taken + interval - time.time()
        if wait > 0:
            time.sleep(wait)
        self.last_taken = time.time()
        r = requests.get(self.url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        image = cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise RuntimeError("snapshot URL did not return an image")
        return Frame(image, datetime.datetime.now().astimezone().replace(microsecond=0))

    def close(self):
        pass


class ImageFolder:
    """Every image in a folder, oldest first, logged under the file's modification time.
    The interval does not apply: the night is as long as it takes to get through them."""

    live = False

    def __init__(self, folder):
        self.name = str(folder)
        self.files = sorted((p for p in pathlib.Path(folder).iterdir() if p.suffix.lower() in IMAGE_EXT),
                            key=lambda p: p.stat().st_mtime)
        if not self.files:
            raise SystemExit(f"no images in {folder}")

    def next(self, interval):
        while self.files:
            p = self.files.pop(0)
            image = cv2.imread(str(p))
            if image is not None:
                t = datetime.datetime.fromtimestamp(p.stat().st_mtime).astimezone().replace(microsecond=0)
                return Frame(image, t, label=p.name)
        return None

    def close(self):
        pass


def youtube(url, max_height):
    """Ask yt-dlp for a URL OpenCV can read, and whether the video is live."""
    h = max_height      # H.264 first: the Pi's OpenCV may not decode AV1, and H.264 is the cheapest to decode
    fmt = (f"best[height<={h}][vcodec^=avc1]/bv*[height<={h}][vcodec^=avc1]/"
           f"best[height<={h}][vcodec!=none]/bv*[height<={h}]/best")
    out = subprocess.run([sys.executable, "-m", "yt_dlp", "-f", fmt, "--no-playlist",
                          "--print", "is_live", "--print", "url", url],
                         capture_output=True, text=True, timeout=120)
    lines = out.stdout.strip().splitlines()
    if out.returncode != 0 or len(lines) < 2:
        raise RuntimeError(out.stderr.strip().splitlines()[-1] if out.stderr.strip() else "yt-dlp failed")
    return lines[-2] == "True", lines[-1]


def detect_kind(spec):
    if spec.isdigit():
        return "webcam"
    p = pathlib.Path(spec)
    if p.is_dir():
        return "folder"
    if p.exists():
        return "file"
    low = spec.lower().split("?")[0]
    if "youtube.com/" in low or "youtu.be/" in low:
        return "youtube"
    if any(low.endswith(ext) for ext in IMAGE_EXT):
        return "snapshot"
    if any(low.endswith(ext) for ext in VIDEO_EXT):
        return "file"
    return "stream"


def open_source(spec, kind="auto", max_height=720, on_demand=False):
    """on_demand: for live streams, connect only for each look instead of decoding all the time."""
    kind = detect_kind(spec) if kind == "auto" else kind
    stream = OnDemandStream if on_demand else LiveStream
    if kind == "file":
        return VideoFile(spec)
    if kind == "folder":
        return ImageFolder(spec)
    if kind == "snapshot":
        return Snapshot(spec)
    if kind == "webcam":
        return LiveStream(lambda: int(spec), f"webcam {spec}")
    if kind == "stream":
        return stream(lambda: spec, spec)
    if kind == "youtube":
        is_live, url = youtube(spec, max_height)
        if not is_live:
            return VideoFile(url, name=spec)
        return stream(lambda: youtube(spec, max_height)[1], spec)
    raise SystemExit(f"unknown source kind: {kind}")
