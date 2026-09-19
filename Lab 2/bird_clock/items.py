"""Pickups: butterfly, popsicle, maple leaf, glove, gift, tangyuan, ring, ball.

To the engine they are all one thing: a small box that triggers on overlap and
never blocks flight (shape "拾取触发" in the asset table). Art swaps by kind,
behaviour comes from ItemConfig.

Placement is checked against the live corridor at spawn. After that pickups
scroll faster than obstacles (ItemConfig.speed_mul), so relative x vs pipes
is allowed to drift — they read as flying toward the bird.
"""

import random
from typing import List, Optional, Tuple

from .collision import wrap_y_spans
from .config import GameConfig, ItemConfig

COIN = "coin"
INVINCIBLE = "invincible"


class Pickup:
    def __init__(self, x: float, y: float, size: float, kind: str = COIN):
        self.x = x
        self.y = y
        self.size = size
        self.kind = kind

    @property
    def hitbox(self) -> Tuple[float, float, float, float]:
        return (self.x, self.y, self.x + self.size, self.y + self.size)

    @property
    def center_y(self) -> float:
        return self.y + self.size / 2.0

    def move(self, dt: float, speed: float):
        self.x -= speed * dt

    def is_off_left(self) -> bool:
        return self.x + self.size < 0

    def overlaps(self, box) -> bool:
        left, bottom, right, top = box
        return not (
            right < self.x
            or left > self.x + self.size
            or top < self.y
            or bottom > self.y + self.size
        )

    def apply(self, game) -> None:
        cfg = game.config.items
        if self.kind == INVINCIBLE:
            game.grant_invincibility(cfg.invincible_seconds)
        else:
            game.add_bonus_score(cfg.coin_score, spawn_hud_popup=False)


class PickupField:
    def __init__(self, config: GameConfig):
        self._cfg: ItemConfig = config.items
        self._screen_h = config.screen.height
        self._screen_w = config.screen.width
        self._bird_h = config.bird.height
        self.items: List[Pickup] = []
        self._distance_until_spawn = 0.0

    def clear(self):
        self.items.clear()
        self._distance_until_spawn = 0.0

    def update(self, dt: float, speed: float, pipes):
        """Scroll and spawn. Score is applied by the game, not here.

        `speed` is the obstacle scroll. Pickups use ItemConfig.speed_mul times
        that so they fly left faster than the corridor they spawned in.
        """
        pickup_speed = speed * self._cfg.speed_mul
        for item in self.items:
            item.move(dt, pickup_speed)
        self.items = [i for i in self.items if not i.is_off_left()]
        self._resolve_spawn_collisions(pipes)
        if not self._cfg.spawn_enabled:
            return
        self._distance_until_spawn -= pickup_speed * dt
        if self._distance_until_spawn > 0:
            return
        self._spawn(pipes)
        self._distance_until_spawn = random.uniform(
            self._cfg.min_spacing, self._cfg.max_spacing
        )

    def _resolve_spawn_collisions(self, pipes):
        """Obstacles spawn in the same column as pickups, so one can land on a
        pickup that appeared a frame or two earlier: the pickup has moved only
        a few pixels and its right edge is still in the spawn column. After
        that they scroll together and it would sit inside the solid forever.

        Only pickups still touching the right edge can be newly hit; once past
        it, nothing can spawn on top of them again.
        """
        if not self.items:
            return
        keep = []
        for item in self.items:
            if item.x + item.size < self._screen_w:
                keep.append(item)
                continue
            band = self._free_band(pipes.pipes, item.x, item.x + item.size)
            if band is None:
                continue
            lo, hi = band
            item.y = min(max(item.y, lo), hi - item.size)
            keep.append(item)
        self.items = keep

    def _free_band(self, pipes, x0: float, x1: float) -> Optional[Tuple[float, float]]:
        """Clear y range across the obstacles this pickup will travel with.

        Uses the flight corridor (aim_band), not the whole clear span: a pickup
        parked in a corner the auto-pilot never visits would go uneaten on
        camera, and a human would have to leave the safe line to reach it.
        """
        clear = self._cfg.clearance
        lo = self._cfg.edge_margin
        hi = self._screen_h - self._cfg.edge_margin
        need = self._cfg.size + 2.0 * clear
        for pipe in pipes:
            if pipe.x + pipe.width < x0 or pipe.x > x1:
                continue
            plo, phi = pipe.aim_band(self._screen_h, self._bird_h, clear)
            lo = max(lo, plo)
            hi = min(hi, phi)
            if hi - lo < need:
                return None
        if hi - lo < self._cfg.size:
            return None
        return lo, hi

    def _spawn(self, pipes):
        x = self._cfg.spawn_x
        band = self._free_band(pipes.pipes, x, x + self._cfg.size)
        if band is None:
            # Blocked this time; try again after a short gap.
            self._distance_until_spawn = self._cfg.retry_spacing
            return
        lo, hi = band
        y = random.uniform(lo, max(lo, hi - self._cfg.size))
        kind = INVINCIBLE if random.random() < self._cfg.invincible_chance else COIN
        self.items.append(Pickup(x, y, self._cfg.size, kind))

    def take(self, bird) -> List[Pickup]:
        """Remove and return everything the bird is touching right now."""
        if not self.items:
            return []
        boxes = [
            (bird.x, bottom, bird.x + bird.width, top)
            for bottom, top in wrap_y_spans(bird.y, bird.height, self._screen_h, True)
        ]
        taken = [i for i in self.items if any(i.overlaps(b) for b in boxes)]
        if taken:
            self.items = [i for i in self.items if i not in taken]
        return taken
