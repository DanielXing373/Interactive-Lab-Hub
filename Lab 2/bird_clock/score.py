"""Scoreboard plus the "+1" popups that make the clock readable while playing.

Idle shows the wall clock directly. Play copies that clock into the score
at start, then ticks on game time (plus coins) so it can drift.

Per-second gains spawn a HUD popup next to the seconds feather. Coin
collects spawn a world-space "+N" at the pickup; play still adds the points.
"""

import time
from typing import List

from .clock_display import (
    HOURS_PER_DAY,
    MINUTES_PER_HOUR,
    SECONDS_PER_MINUTE,
)
from .config import GameConfig, HudConfig, ScoreConfig

SECONDS_PER_DAY = SECONDS_PER_MINUTE * MINUTES_PER_HOUR * HOURS_PER_DAY


def wall_clock_score(now: float = None) -> int:
    """Encode local time as the play score: day-of-month days + H:M:S."""
    stamp = time.localtime(time.time() if now is None else now)
    return (
        int(stamp.tm_mday) * SECONDS_PER_DAY
        + int(stamp.tm_hour) * SECONDS_PER_MINUTE * MINUTES_PER_HOUR
        + int(stamp.tm_min) * SECONDS_PER_MINUTE
        + int(stamp.tm_sec)
    )


class ScorePopup:
    """One floating "+n" next to the seconds feather."""

    def __init__(self, amount: int, lifetime: float):
        self.amount = amount
        self.age = 0.0
        self.lifetime = max(lifetime, 1e-3)

    @property
    def alive(self) -> bool:
        return self.age < self.lifetime

    @property
    def progress(self) -> float:
        return min(1.0, self.age / self.lifetime)

    @property
    def text(self) -> str:
        return f"+{self.amount}"


class WorldPopup(ScorePopup):
    """Same fade/rise as the HUD popup, anchored at a world (x, y)."""

    def __init__(self, amount: int, lifetime: float, x: float, y: float):
        super().__init__(amount, lifetime)
        self.x = x
        self.y = y


class ScoreBoard:
    def __init__(self, config: GameConfig):
        self._cfg: ScoreConfig = config.score
        self._hud: HudConfig = config.hud
        self.idle_score = self._cfg.idle_starts_at
        self.current_score = self._cfg.play_starts_at
        self.best_score = 0
        self._play_origin = 0
        self._play_accum = 0.0
        self._last_wall_second = None
        self.popups: List[ScorePopup] = []
        self.world_popups: List[WorldPopup] = []

    def reset_play(self):
        """Stamp the live wall clock, then count on game time from there."""
        self.current_score = wall_clock_score()
        self._play_origin = self.current_score
        self._play_accum = 0.0
        self.popups.clear()
        self.world_popups.clear()

    def clear_world_popups(self):
        self.world_popups.clear()

    def update(self, dt: float):
        """Age popups. Runs in every mode so they finish after a death."""
        if self.popups:
            for popup in self.popups:
                popup.age += dt
            self.popups = [p for p in self.popups if p.alive]
        if self.world_popups:
            for popup in self.world_popups:
                popup.age += dt
            self.world_popups = [p for p in self.world_popups if p.alive]

    def _add_popup(self, amount: int):
        if amount <= 0:
            return
        self.popups.append(ScorePopup(amount, self._hud.popup_seconds))

    def tick_idle(self, dt: float):
        """Idle follows the wall clock, so the popup lands on the second flip."""
        second = time.localtime().tm_sec
        if self._last_wall_second is None:
            self._last_wall_second = second
            return
        if second == self._last_wall_second:
            return
        self._last_wall_second = second
        self.idle_score += self._cfg.points_per_second
        self._add_popup(self._cfg.points_per_second)

    def tick_play(self, dt: float):
        self._play_accum += dt
        step = self._cfg.points_per_second
        while self._play_accum >= 1.0:
            self.current_score += step
            self._add_popup(step)
            self._play_accum -= 1.0

    def add_world_popup(self, amount: int, x: float, y: float):
        """Green "+n" at a world point. Does not change the score."""
        if amount <= 0:
            return
        self.world_popups.append(
            WorldPopup(amount, self._hud.popup_seconds, x, y)
        )

    def add_bonus(self, amount: int, spawn_hud_popup: bool = True):
        """Reserved for coins. HUD popup is optional; world "+n" is separate."""
        self.current_score += amount
        if spawn_hud_popup:
            self._add_popup(amount)

    def lock_best_from_current(self):
        earned = self.current_score - self._play_origin
        if earned > self.best_score:
            self.best_score = earned
