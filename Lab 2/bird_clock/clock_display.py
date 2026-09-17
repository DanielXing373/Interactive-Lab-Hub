"""Feather-token time readout. Four units, left to right, top-left of screen.

Two sources, one layout:
    idle  -> real wall clock, no arithmetic
    play  -> the score, decomposed base 60 / 60 / 24 so coins just add points

Units are (key, text). Keys pick the feather sprite once art exists:
    date = red, hour = gold, minute = green, second = white.
Drawn glyphs are decoration only and never collide.
"""

import time
from typing import List, Tuple

DATE = "date"
HOUR = "hour"
MINUTE = "minute"
SECOND = "second"

ORDER = (DATE, HOUR, MINUTE, SECOND)

SECONDS_PER_MINUTE = 60
MINUTES_PER_HOUR = 60
HOURS_PER_DAY = 24

Unit = Tuple[str, str]


def wall_clock_units(date_format: str = "%Y/%m/%d", now: float = None) -> List[Unit]:
    """Wall clock straight off the system. Red slot carries the real date."""
    stamp = time.localtime(time.time() if now is None else now)
    return [
        (DATE, time.strftime(date_format, stamp)),
        (HOUR, f"{stamp.tm_hour:02d}"),
        (MINUTE, f"{stamp.tm_min:02d}"),
        (SECOND, f"{stamp.tm_sec:02d}"),
    ]


def score_units(total: int) -> List[Unit]:
    """Score as a sexagesimal clock. One point = one second slot tick."""
    total = max(0, int(total))
    seconds = total % SECONDS_PER_MINUTE
    minutes = (total // SECONDS_PER_MINUTE) % MINUTES_PER_HOUR
    hours = (total // (SECONDS_PER_MINUTE * MINUTES_PER_HOUR)) % HOURS_PER_DAY
    days = total // (SECONDS_PER_MINUTE * MINUTES_PER_HOUR * HOURS_PER_DAY)
    return [
        (DATE, f"{days:02d}"),
        (HOUR, f"{hours:02d}"),
        (MINUTE, f"{minutes:02d}"),
        (SECOND, f"{seconds:02d}"),
    ]


def units_for(game, date_format: str = "%Y/%m/%d") -> List[Unit]:
    if game.in_idle:
        return wall_clock_units(date_format)
    return score_units(game.scores.current_score)
