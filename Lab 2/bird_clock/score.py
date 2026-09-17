"""Scoreboard plus the "+1" popups that make the clock readable while playing.

Idle ticks a fake clock-score; play current starts at 0. Every play gain
(one per second, or a coin bonus) spawns a popup the renderer floats upward.

Later:
- Drive idle_score from a real wall-clock
- Optionally vary rules by time of day (see config module docstring)
"""

import time
from typing import List

from .config import GameConfig, HudConfig, ScoreConfig


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


class ScoreBoard:
    def __init__(self, config: GameConfig):
        self._cfg: ScoreConfig = config.score
        self._hud: HudConfig = config.hud
        self.idle_score = self._cfg.idle_starts_at
        self.current_score = self._cfg.play_starts_at
        self.best_score = 0
        self._play_accum = 0.0
        self._last_wall_second = None
        self.popups: List[ScorePopup] = []

    def reset_play(self):
        self.current_score = self._cfg.play_starts_at
        self._play_accum = 0.0
        self.popups.clear()

    def update(self, dt: float):
        """Age popups. Runs in every mode so they finish after a death."""
        if not self.popups:
            return
        for popup in self.popups:
            popup.age += dt
        self.popups = [p for p in self.popups if p.alive]

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

    def add_bonus(self, amount: int):
        """Reserved for coins."""
        self.current_score += amount
        self._add_popup(amount)

    def lock_best_from_current(self):
        if self.current_score > self.best_score:
            self.best_score = self.current_score
