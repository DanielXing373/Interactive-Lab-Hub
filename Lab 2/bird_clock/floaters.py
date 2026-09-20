"""Cosmetic banners that drift across the screen.

Christmas text is the first pack: two PNG frames, no hitbox, no score, not
part of the obstacle lottery. The field just emits one every few seconds.
"""

import math
import random
import time
from typing import List

from .config import FloaterConfig, GameConfig


class Floater:
    def __init__(self, x: float, y: float, phase: float = 0.0):
        self.x = x
        self.y = y
        self.phase = phase

    def move(self, dt: float, speed: float):
        self.x -= speed * dt

    def draw_y(self, bob: float, period: float) -> float:
        if bob <= 0 or period <= 0:
            return self.y
        t = time.monotonic() + self.phase
        return self.y + bob * math.sin(2.0 * math.pi * t / period)

    def is_off_left(self, width: float) -> bool:
        return self.x + width < 0


class FloaterField:
    def __init__(self, config: GameConfig):
        self._cfg: FloaterConfig = config.floaters
        self._screen_h = config.screen.height
        self.items: List[Floater] = []
        self._until = 0.0

    def clear(self):
        self.items.clear()
        self._until = 0.4

    def update(self, dt: float, speed: float, enabled: bool = False):
        drift = speed * self._cfg.speed_mul
        for item in self.items:
            item.move(dt, drift)
        max_w = self._cfg.cull_width
        self.items = [i for i in self.items if not i.is_off_left(max_w)]
        if not enabled:
            return
        self._until -= dt
        if self._until > 0:
            return
        self._spawn()
        self._until = self._cfg.interval_seconds

    def _spawn(self):
        lo = self._cfg.edge_margin
        hi = self._screen_h - self._cfg.edge_margin - self._cfg.spawn_height
        if hi < lo:
            hi = lo
        y = random.uniform(lo, hi)
        self.items.append(
            Floater(self._cfg.spawn_x, y, phase=random.random() * 8.0)
        )
