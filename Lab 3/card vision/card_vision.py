"""
Standalone Card Vision MVP.

Reuses the original EdjeElectronics OpenCV template-matching pipeline
(Cards.py) and exposes a clean, machine-readable interface for later
integration with a poker state machine.

Output contract (list of dicts, no OpenCV objects):
    [
        {"card": "As", "center": [310, 420]},
        {"card": "Kh", "center": [470, 418]},
        {"card": "10d", "center": [625, 205]},
    ]

Card string format: <rank><suit>
  ranks: A, 2, 3, 4, 5, 6, 7, 8, 9, 10, J, Q, K
  suits: s (spades), h (hearts), d (diamonds), c (clubs)

Example: Ace of spades -> "As", Ten of diamonds -> "10d"

If rank or suit cannot be matched confidently, "card" is "Unknown".
"center" is always [x, y] in image pixel coordinates for future zone mapping.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

import Cards

DEFAULT_EXPORT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "captures"
)

# Compact poker notation maps (original repo uses full names internally)
RANK_TO_CODE = {
    "Ace": "A",
    "Two": "2",
    "Three": "3",
    "Four": "4",
    "Five": "5",
    "Six": "6",
    "Seven": "7",
    "Eight": "8",
    "Nine": "9",
    "Ten": "10",
    "Jack": "J",
    "Queen": "Q",
    "King": "K",
}

SUIT_TO_CODE = {
    "Spades": "s",
    "Hearts": "h",
    "Diamonds": "d",
    "Clubs": "c",
}

DEFAULT_TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "Card_Imgs"
)
# Card_Imgs/*.jpg are the rank and suit samples shipped with
# EdjeElectronics/OpenCV-Playing-Card-Detector. They are the training images,
# not a photo of a table.

# Cached templates so callers can do repeated detect_cards(frame) cheaply
_train_ranks = None
_train_suits = None
_template_dir_loaded = None


def format_card(rank_name: str, suit_name: str) -> str:
    """Convert original repo match names to compact notation, or 'Unknown'."""
    if rank_name == "Unknown" or suit_name == "Unknown":
        return "Unknown"
    rank_code = RANK_TO_CODE.get(rank_name)
    suit_code = SUIT_TO_CODE.get(suit_name)
    if rank_code is None or suit_code is None:
        return "Unknown"
    return f"{rank_code}{suit_code}"


def clear_template_cache() -> None:
    """Drop loaded templates so a newly saved rank image is used immediately."""
    global _train_ranks, _train_suits, _template_dir_loaded
    _train_ranks = None
    _train_suits = None
    _template_dir_loaded = None


def load_templates(template_dir: Optional[str] = None):
    """Load rank/suit train images. Defaults to ./Card_Imgs/."""
    global _train_ranks, _train_suits, _template_dir_loaded

    path = template_dir or DEFAULT_TEMPLATE_DIR
    if not path.endswith(os.sep):
        path = path + os.sep

    if _train_ranks is not None and _template_dir_loaded == path:
        return _train_ranks, _train_suits

    _train_ranks = Cards.load_ranks(path)
    _train_suits = Cards.load_suits(path)
    _template_dir_loaded = path

    # Sanity-check that templates actually loaded
    for tr in _train_ranks:
        if tr.img is None:
            raise FileNotFoundError(
                f"Missing rank template: {path}{tr.name}.jpg"
            )
    for ts in _train_suits:
        if ts.img is None:
            raise FileNotFoundError(
                f"Missing suit template: {path}{ts.name}.jpg"
            )

    return _train_ranks, _train_suits


def detect_cards(
    image: np.ndarray,
    template_dir: Optional[str] = None,
    train_ranks=None,
    train_suits=None,
    min_area: Optional[int] = None,
    max_area: Optional[int] = None,
    include_unknown: bool = True,
) -> List[Dict[str, Any]]:
    """
    Detect and identify playing cards in a BGR image.

    Parameters
    ----------
    image : np.ndarray
        BGR image from cv2.imread / VideoCapture (or equivalent).
    template_dir : str, optional
        Directory containing Ace.jpg ... King.jpg and suit templates.
    train_ranks, train_suits : optional
        Pre-loaded template lists from load_templates(). If omitted, templates
        are loaded (and cached) automatically.
    min_area, max_area : int, optional
        Override Cards.CARD_MIN_AREA / CARD_MAX_AREA for this call.
        Useful when camera distance / resolution differs from the original
        1280x720 PiCamera setup.
    include_unknown : bool
        If True, include detected card-shaped contours that failed matching
        as {"card": "Unknown", "center": [...]}. If False, omit them.

    Returns
    -------
    list of dict
        Each dict: {"card": str, "center": [x, y]}
        Sorted roughly left-to-right by center x (stable for zone mapping demos).
    """
    if image is None or not hasattr(image, "shape") or image.size == 0:
        raise ValueError("detect_cards() requires a non-empty BGR image array")

    # Optionally override area thresholds for this call only
    old_min, old_max = Cards.CARD_MIN_AREA, Cards.CARD_MAX_AREA
    if min_area is not None:
        Cards.CARD_MIN_AREA = int(min_area)
    if max_area is not None:
        Cards.CARD_MAX_AREA = int(max_area)

    try:
        if train_ranks is None or train_suits is None:
            train_ranks, train_suits = load_templates(template_dir)

        pre_proc = Cards.preprocess_image(image)
        cnts_sort, cnt_is_card = Cards.find_cards(pre_proc)

        results: List[Dict[str, Any]] = []
        if len(cnts_sort) == 0:
            return results

        for i in range(len(cnts_sort)):
            if cnt_is_card[i] != 1:
                continue

            qcard = Cards.preprocess_card(cnts_sort[i], image)
            (
                best_rank,
                best_suit,
                rank_diff,
                suit_diff,
                rank_guess,
                suit_guess,
                rank_second_diff,
            ) = Cards.match_card(qcard, train_ranks, train_suits)
            card_str = format_card(best_rank, best_suit)

            if (not include_unknown) and card_str == "Unknown":
                continue

            center = [int(qcard.center[0]), int(qcard.center[1])]
            results.append(
                {
                    "card": card_str,
                    "center": center,
                    # Extra debug fields; safe for downstream to ignore
                    "rank": best_rank,
                    "suit": best_suit,
                    "rank_guess": rank_guess,
                    "suit_guess": suit_guess,
                    "rank_diff": int(rank_diff),
                    "rank_second_diff": int(rank_second_diff),
                    "suit_diff": int(suit_diff),
                }
            )

        # Left-to-right ordering helps later zone / community-card association
        results.sort(key=lambda r: (r["center"][0], r["center"][1]))
        return results

    finally:
        Cards.CARD_MIN_AREA = old_min
        Cards.CARD_MAX_AREA = old_max


def detect_cards_from_path(
    image_path: str,
    **kwargs,
) -> List[Dict[str, Any]]:
    """Load an image from disk and run detect_cards()."""
    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")
    return detect_cards(image, **kwargs)


def open_usb_camera(
    camera_index: int = 0,
    width: int = 1280,
    height: int = 720,
) -> cv2.VideoCapture:
    """Open a USB webcam via OpenCV. Caller must release() when done."""
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError(
            f"Could not open camera index {camera_index}. "
            "Try another index (0, 1, ...) or check USB permissions."
        )
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    return cap


def grab_frame(cap: cv2.VideoCapture, flush_reads: int = 5) -> Optional[np.ndarray]:
    """Read a recent frame from an open VideoCapture (flushes stale buffer)."""
    frame = None
    for _ in range(max(1, flush_reads)):
        ok, frame = cap.read()
        if not ok:
            return None
    return frame


def annotate_frame(
    image: np.ndarray,
    detections: List[Dict[str, Any]],
) -> np.ndarray:
    """
    Return a copy of the frame with card labels + center dots drawn.
    Suitable for demo videos / slides. Does not modify the input image.
    """
    out = image.copy()
    for det in detections:
        x, y = det["center"]
        label = str(det.get("card", "?"))
        cv2.circle(out, (int(x), int(y)), 5, (255, 0, 0), -1)
        cv2.putText(
            out,
            label,
            (int(x) - 40, int(y) - 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (0, 0, 0),
            3,
            cv2.LINE_AA,
        )
        cv2.putText(
            out,
            label,
            (int(x) - 40, int(y) - 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (50, 200, 200),
            2,
            cv2.LINE_AA,
        )
    return out


def annotate_poker_preview(
    image: np.ndarray,
    detections: List[Dict[str, Any]],
    *,
    hole_from: float = 0.68,
    window: Optional[str] = None,
    stable_count: int = 0,
    stable_need: int = 15,
    status_lines: Optional[List[str]] = None,
) -> np.ndarray:
    """Frame for the browser preview: zone cut, card labels, wait status."""
    import zones as zone_mod

    out = annotate_frame(image, detections)
    height, width = out.shape[:2]
    cut = int(height * float(hole_from))
    cv2.line(out, (0, cut), (width - 1, cut), (0, 255, 255), 2)
    cv2.putText(
        out,
        "BOARD (above)",
        (12, max(28, cut - 12)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        out,
        "PI HOLE (below) — put my two cards here",
        (12, min(height - 16, cut + 28)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )
    assigned = zone_mod.assign_zones(detections, image_height=height, hole_from=hole_from)
    hole_txt = ",".join(item.get("card", "?") for item in assigned["pi_hole"]) or "-"
    board_txt = ",".join(item.get("card", "?") for item in assigned["board"]) or "-"
    lines = list(status_lines or [])
    if window:
        lines.append(f"waiting: {window}  stable {stable_count}/{stable_need}")
    else:
        lines.append("camera idle (no card window open)")
    lines.append(f"hole: {hole_txt}")
    lines.append(f"board: {board_txt}")
    for index, line in enumerate(lines):
        origin = (12, 32 + index * 28)
        cv2.putText(out, line, origin, cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(out, line, origin, cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)
    return out


def save_frame(image: np.ndarray, path: str) -> str:
    """Save a BGR frame to disk. Creates parent directories. Returns path."""
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    if not cv2.imwrite(path, image):
        raise IOError(f"Failed to write image: {path}")
    return path


def public_detections(
    detections: List[Dict[str, Any]],
    verbose: bool = False,
) -> List[Dict[str, Any]]:
    """Strip debug fields for downstream / demo JSON unless verbose=True."""
    if verbose:
        return detections
    return [{"card": d["card"], "center": d["center"]} for d in detections]


def assign_zones(
    detections: List[Dict[str, Any]],
    image_height: int = 720,
    hole_from: Optional[float] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Split detections into pi_hole and board. See zones.py."""
    import zones

    if hole_from is None:
        return zones.assign_zones(detections, image_height=image_height)
    return zones.assign_zones(detections, image_height=image_height, hole_from=hole_from)


def export_capture(
    frame: np.ndarray,
    detections: Optional[List[Dict[str, Any]]] = None,
    out_dir: Optional[str] = None,
    prefix: Optional[str] = None,
    run_detect: bool = False,
    detect_kwargs: Optional[Dict[str, Any]] = None,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Export one camera/table frame for demos or later re-test.

    Writes under out_dir (default: ./captures/):
      <prefix>.jpg              — raw frame
      <prefix>_annotated.jpg    — frame with labels (if detections available)
      <prefix>.json             — detections + file paths

    Parameters
    ----------
    frame : BGR image
    detections : optional precomputed detect_cards() result
    out_dir : export directory
    prefix : filename stem; default is timestamp YYYYMMDD_HHMMSS
    run_detect : if True and detections is None, call detect_cards(frame)
    detect_kwargs : forwarded to detect_cards when run_detect=True
    verbose : keep rank/suit/diff fields in JSON

    Returns
    -------
    dict with keys: prefix, image, annotated, json, detections
    """
    if frame is None or not hasattr(frame, "shape") or frame.size == 0:
        raise ValueError("export_capture() requires a non-empty BGR frame")

    out_dir = out_dir or DEFAULT_EXPORT_DIR
    os.makedirs(out_dir, exist_ok=True)
    prefix = prefix or datetime.now().strftime("%Y%m%d_%H%M%S")

    if detections is None and run_detect:
        detections = detect_cards(frame, **(detect_kwargs or {}))
    if detections is None:
        detections = []

    result = public_detections(detections, verbose=verbose)
    raw_path = os.path.join(out_dir, f"{prefix}.jpg")
    ann_path = os.path.join(out_dir, f"{prefix}_annotated.jpg")
    json_path = os.path.join(out_dir, f"{prefix}.json")

    save_frame(frame, raw_path)
    annotated = annotate_frame(frame, detections)
    save_frame(annotated, ann_path)

    payload = {
        "prefix": prefix,
        "image": raw_path,
        "annotated": ann_path,
        "detections": result,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    payload["json"] = json_path
    return payload


class SessionRecorder:
    """
    Record a continuous demo video for one play session.

    Typical game-loop usage:
        rec = card_vision.start_session_recording()   # start of hand / demo
        ...
        rec.write(frame)                             # each camera frame
        # or: rec.write(frame, detections=cards)     # burn labels into video
        ...
        info = rec.stop()                            # end of hand / demo
        # info["video"] -> path to .mp4
    """

    def __init__(
        self,
        path: str,
        fps: float = 10.0,
        frame_size: Optional[tuple] = None,
        draw_labels: bool = True,
    ):
        self.path = path
        self.fps = float(fps)
        self.frame_size = frame_size  # (width, height); set from first frame if None
        self.draw_labels = draw_labels
        self._writer = None
        self.frame_count = 0
        self.started_at = datetime.now().isoformat(timespec="seconds")
        self.stopped_at = None

        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)

    @property
    def is_open(self) -> bool:
        return self._writer is not None and self.stopped_at is None

    def _open_writer(self, width: int, height: int) -> None:
        if self.frame_size is None:
            self.frame_size = (int(width), int(height))
        w, h = self.frame_size

        # mp4v is the most portable OpenCV default; fall back to AVI/XVID
        candidates = []
        root, ext = os.path.splitext(self.path)
        if ext.lower() in ("", ".mp4"):
            self.path = root + ".mp4"
            candidates.append(("mp4v", self.path))
            candidates.append(("XVID", root + ".avi"))
        else:
            candidates.append(("XVID", self.path))
            candidates.append(("mp4v", root + ".mp4"))

        last_err = None
        for fourcc_name, path in candidates:
            fourcc = cv2.VideoWriter_fourcc(*fourcc_name)
            writer = cv2.VideoWriter(path, fourcc, self.fps, (w, h))
            if writer.isOpened():
                self.path = path
                self._writer = writer
                return
            last_err = path
            writer.release()

        raise RuntimeError(
            f"Could not open VideoWriter for session recording (tried up to {last_err}). "
            "Check OpenCV video codec support on this Pi image."
        )

    def write(
        self,
        frame: np.ndarray,
        detections: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Append one frame. Optionally burn detection labels into the video."""
        if self.stopped_at is not None:
            raise RuntimeError("SessionRecorder already stopped")
        if frame is None or not hasattr(frame, "shape") or frame.size == 0:
            return

        out = frame
        if self.draw_labels and detections:
            out = annotate_frame(frame, detections)

        h, w = out.shape[:2]
        if self._writer is None:
            self._open_writer(w, h)

        target_w, target_h = self.frame_size
        if (w, h) != (target_w, target_h):
            out = cv2.resize(out, (target_w, target_h))

        self._writer.write(out)
        self.frame_count += 1

    def stop(self) -> Dict[str, Any]:
        """Finalize the file and return export info for demos."""
        if self.stopped_at is not None:
            return self.info()

        self.stopped_at = datetime.now().isoformat(timespec="seconds")
        if self._writer is not None:
            self._writer.release()
            self._writer = None

        return self.info()

    def info(self) -> Dict[str, Any]:
        return {
            "video": self.path,
            "frames": self.frame_count,
            "fps": self.fps,
            "frame_size": list(self.frame_size) if self.frame_size else None,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "exists": os.path.isfile(self.path) if self.path else False,
        }

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.stop()
        return False


def start_session_recording(
    out_dir: Optional[str] = None,
    prefix: Optional[str] = None,
    fps: float = 10.0,
    draw_labels: bool = True,
    frame_size: Optional[tuple] = None,
) -> SessionRecorder:
    """
    Start a new session video under ./captures/ (or out_dir).

    File name default: session_YYYYMMDD_HHMMSS.mp4
    """
    out_dir = out_dir or DEFAULT_EXPORT_DIR
    os.makedirs(out_dir, exist_ok=True)
    prefix = prefix or ("session_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    path = os.path.join(out_dir, f"{prefix}.mp4")
    return SessionRecorder(
        path=path,
        fps=fps,
        frame_size=frame_size,
        draw_labels=draw_labels,
    )
