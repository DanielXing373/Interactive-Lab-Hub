"""Scoreboard. Idle ticks a fake clock-score; play current starts at 0.

Later:
- Drive idle_score from a real wall-clock
- Render with a sexagesimal / fruit-token encoding instead of raw digits
- Optionally vary rules by time of day (see config module docstring)
"""

from .config import GameConfig, ScoreConfig


class ScoreBoard:
    def __init__(self, config: GameConfig):
        self._cfg: ScoreConfig = config.score
        self.idle_score = self._cfg.idle_starts_at
        self.current_score = self._cfg.play_starts_at
        self.best_score = 0
        self._idle_accum = 0.0
        self._play_accum = 0.0

    def reset_play(self):
        self.current_score = self._cfg.play_starts_at
        self._play_accum = 0.0

    def tick_idle(self, dt: float):
        self._idle_accum += dt
        step = self._cfg.points_per_second
        while self._idle_accum >= 1.0:
            self.idle_score += step
            self._idle_accum -= 1.0

    def tick_play(self, dt: float):
        self._play_accum += dt
        step = self._cfg.points_per_second
        while self._play_accum >= 1.0:
            self.current_score += step
            self._play_accum -= 1.0

    def add_bonus(self, amount: int):
        """Reserved for coins."""
        self.current_score += amount

    def lock_best_from_current(self):
        if self.current_score > self.best_score:
            self.best_score = self.current_score
