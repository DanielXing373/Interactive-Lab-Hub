"""Split a camera frame into the Pi's hole cards and the board.

The camera sits on the Pi's side of the table. In the 1280x720 sample,
the two hole cards sit low in the frame (y about 590-605) and the board
sits higher (y about 268-378). The cut is 68% of the image height.
The board zone commonly holds five card backs; faces still down read as
Unknown until that street is revealed. Human cards are face down and are
not a third band in that sample.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

HOLE_Y_FRACTION = 0.68


def assign_zones(
    detections: List[Dict[str, Any]],
    image_height: int = 720,
    hole_from: float = HOLE_Y_FRACTION,
) -> Dict[str, List[Dict[str, Any]]]:
    """Place every detection into pi_hole or board by its center y."""
    cut = float(image_height) * float(hole_from)
    pi_hole: List[Dict[str, Any]] = []
    board: List[Dict[str, Any]] = []
    unknown: List[Dict[str, Any]] = []
    for det in detections:
        center = det.get("center") or [0, 0]
        y = float(center[1])
        bucket = pi_hole if y >= cut else board
        bucket.append(det)
        if det.get("card") == "Unknown":
            unknown.append(det)
    pi_hole.sort(key=lambda item: item["center"][0])
    board.sort(key=lambda item: item["center"][0])
    return {
        "pi_hole": pi_hole,
        "board": board,
        "ignored": [],
        "unassigned": [],
        "unknown": unknown,
    }


def check_sample() -> None:
    sample = [
        {"card": "Unknown", "center": [205, 284]},
        {"card": "4d", "center": [396, 268]},
        {"card": "6s", "center": [455, 593]},
        {"card": "10s", "center": [580, 280]},
        {"card": "7c", "center": [643, 605]},
        {"card": "8d", "center": [763, 297]},
        {"card": "7d", "center": [907, 378]},
    ]
    zones = assign_zones(sample, image_height=720)
    assert [item["card"] for item in zones["pi_hole"]] == ["6s", "7c"]
    assert [item["card"] for item in zones["board"]] == [
        "Unknown",
        "4d",
        "10s",
        "8d",
        "7d",
    ]
    assert zones["unknown"] == [{"card": "Unknown", "center": [205, 284]}]
    assert zones["ignored"] == []
    assert zones["unassigned"] == []
