"""Scrolling obstacles: bi/uni rects & triangles, plus a long bottom ground bar."""

import random
from typing import List, Optional, Tuple

from .collision import hits_pipe
from .config import GameConfig, PipeConfig
from .items import Item, maybe_roll_item


class PipePair:
    def __init__(
        self,
        x: float,
        width: float,
        gap_bottom: float,
        gap_top: float,
        item: Optional[Item] = None,
        shape: str = "rect",
        has_bottom: bool = True,
        has_top: bool = True,
        is_ground: bool = False,
    ):
        self.x = x
        self.width = width
        self.gap_bottom = gap_bottom
        self.gap_top = gap_top
        self.item = item
        self.shape = shape
        self.has_bottom = has_bottom
        self.has_top = has_top
        self.is_ground = is_ground
        self.passed = False

    def safe_band(self, screen_h: float) -> Tuple[float, float]:
        """Y range that clears this obstacle (triangles: apex constriction)."""
        if self.has_bottom and self.has_top:
            return self.gap_bottom, self.gap_top
        if self.has_bottom:
            return self.gap_bottom, screen_h
        if self.has_top:
            # gap_bottom carries the floor under a top-only obstacle (ground strip).
            return self.gap_bottom, self.gap_top
        return 0.0, screen_h

    def aim_band(self, screen_h: float, bird_h: float, margin: float = 2.0) -> Tuple[float, float]:
        """Narrow fly corridor for the autopilot.

        Bilateral: the gap. Single-sided: hug the solid, but keep a tall enough
        band that the bird stays near mid-screen — not pinned to the floor or
        ceiling where the next obstacle will clip it.
        """
        pad = bird_h + 2.0 * margin
        corridor = max(48.0, bird_h * 6.0)
        if self.has_bottom and self.has_top:
            return self.gap_bottom, self.gap_top
        if self.has_bottom:
            lo = self.gap_bottom
            hi = min(screen_h - margin, max(lo + pad + corridor, 72.0))
            if hi < lo + bird_h:
                hi = min(screen_h, lo + bird_h + margin)
            return lo, hi
        if self.has_top:
            hi = self.gap_top
            floor = max(margin, self.gap_bottom)
            lo = max(floor, min(hi - pad - corridor, screen_h - 72.0))
            if lo > hi - bird_h:
                lo = max(self.gap_bottom, hi - bird_h - margin)
            return lo, hi
        return 0.0, screen_h

    @property
    def gap_center(self) -> float:
        return (self.gap_bottom + self.gap_top) / 2.0

    def aim_center(self, screen_h: float, bird_h: float = 8.0) -> float:
        lo, hi = self.aim_band(screen_h, bird_h)
        return 0.5 * (lo + hi)

    def move(self, dt: float, speed: float):
        self.x -= speed * dt

    def is_off_left(self) -> bool:
        return self.x + self.width < 0

    def collides(self, hitbox, screen_height: float) -> bool:
        return hits_pipe(
            hitbox,
            self.x,
            self.width,
            self.gap_bottom,
            self.gap_top,
            screen_height,
            shape=self.shape,
            has_bottom=self.has_bottom,
            has_top=self.has_top,
        )


class PipeField:
    def __init__(self, config: GameConfig):
        self._cfg: PipeConfig = config.pipes
        self._items_cfg = config.items
        self._screen_h = config.screen.height
        self._bird_h = config.bird.height
        self.pipes: List[PipePair] = []
        self._distance_until_spawn = 0.0

    def clear(self):
        self.pipes.clear()
        self._distance_until_spawn = 0.0

    def update(self, dt: float, speed: float, idle: bool):
        for pipe in self.pipes:
            pipe.move(dt, speed)
        self.pipes = [p for p in self.pipes if not p.is_off_left()]
        self._distance_until_spawn -= speed * dt
        if self._distance_until_spawn <= 0:
            self.spawn(idle=idle, speed=speed)
            if idle:
                spacing = random.uniform(self._cfg.idle_min_spacing, self._cfg.idle_max_spacing)
            else:
                spacing = random.uniform(self._cfg.min_spacing, self._cfg.max_spacing)
            self._distance_until_spawn = spacing

    def ground_at_spawn(self) -> Optional[PipePair]:
        """Ground strip still covering the spawn column, if any."""
        x = self._cfg.spawn_x
        for p in self.pipes:
            if p.is_ground and p.x <= x <= p.x + p.width:
                return p
        return None

    def _pick_kind(self) -> Tuple[str, bool, bool]:
        """Return (shape, has_bottom, has_top). shape 'ground' is bottom rect strip.

        While a ground strip runs under the spawn column, only top-side
        obstacles are allowed: a second floor solid would leave no corridor.
        """
        cfg = self._cfg
        if self.ground_at_spawn() is not None:
            choices = [
                ("rect", False, True, cfg.weight_rect_top),
                ("triangle", False, True, cfg.weight_tri_top),
            ]
        else:
            choices = [
                ("rect", True, True, cfg.weight_rect_both),
                ("rect", True, False, cfg.weight_rect_bottom),
                ("rect", False, True, cfg.weight_rect_top),
                ("triangle", True, True, cfg.weight_tri_both),
                ("triangle", True, False, cfg.weight_tri_bottom),
                ("triangle", False, True, cfg.weight_tri_top),
                ("ground", True, False, cfg.weight_ground),
            ]
        weights = [c[3] for c in choices]
        shape, has_bottom, has_top, _ = random.choices(choices, weights=weights, k=1)[0]
        return shape, has_bottom, has_top

    def _bilateral_gap(self, idle: bool) -> Tuple[float, float]:
        usable = self._screen_h - 2 * self._cfg.edge_margin
        floor = self._bird_h + self._cfg.gap_over_bird
        if idle:
            lo, hi = self._cfg.idle_min_gap, self._cfg.idle_max_gap
        else:
            lo, hi = self._cfg.min_gap, self._cfg.max_gap
        min_gap = min(max(lo, floor), usable)
        max_gap = min(max(hi, min_gap), usable)
        gap = random.uniform(min_gap, max_gap)
        max_bottom = self._screen_h - self._cfg.edge_margin - gap
        min_bottom = self._cfg.edge_margin
        if max_bottom < min_bottom:
            gap_bottom = min_bottom
            gap = usable
        else:
            gap_bottom = random.uniform(min_bottom, max_bottom)
        return gap_bottom, gap_bottom + gap

    def _uni_height(self, floor: float = 0.0) -> float:
        """Single-sided solid height, leaving a bird-sized corridor above floor."""
        clear = self._bird_h + self._cfg.gap_over_bird + self._cfg.edge_margin
        max_h = max(self._cfg.uni_min_height, self._screen_h - floor - clear)
        hi = min(self._cfg.uni_max_height, max_h)
        lo = min(self._cfg.uni_min_height, hi)
        return random.uniform(lo, hi)

    def spawn(self, idle: bool, speed: float = 32.0):
        kind, has_bottom, has_top = self._pick_kind()
        item = maybe_roll_item(self._items_cfg)
        width = random.uniform(self._cfg.min_width, self._cfg.max_width)

        if kind == "ground":
            duration = random.uniform(self._cfg.ground_min_seconds, self._cfg.ground_max_seconds)
            ground_width = max(self._cfg.min_width, max(speed, 1.0) * duration)
            height = self._cfg.ground_height
            self.pipes.append(
                PipePair(
                    x=self._cfg.spawn_x,
                    width=ground_width,
                    gap_bottom=height,
                    gap_top=self._screen_h,
                    item=item,
                    shape="rect",
                    has_bottom=True,
                    has_top=False,
                    is_ground=True,
                )
            )
            return

        if has_bottom and has_top:
            gap_bottom, gap_top = self._bilateral_gap(idle)
        elif has_bottom:
            gap_bottom, gap_top = self._uni_height(), self._screen_h
        else:
            ground = self.ground_at_spawn()
            floor = ground.gap_bottom if ground is not None else 0.0
            gap_bottom, gap_top = floor, self._screen_h - self._uni_height(floor)

        self.pipes.append(
            PipePair(
                x=self._cfg.spawn_x,
                width=width,
                gap_bottom=gap_bottom,
                gap_top=gap_top,
                item=item,
                shape=kind,
                has_bottom=has_bottom,
                has_top=has_top,
            )
        )

    def next_ahead(self, bird_x: float) -> Optional[PipePair]:
        ahead = self.upcoming(bird_x, limit=1)
        return ahead[0] if ahead else None

    def upcoming(self, bird_x: float, limit: int = 3) -> List[PipePair]:
        ahead = [p for p in self.pipes if p.x + p.width >= bird_x]
        ahead.sort(key=lambda p: p.x)
        return ahead[:limit]

    def hits(self, bird) -> bool:
        if not bird.collision_enabled:
            return False
        return any(
            p.collides(box, self._screen_h)
            for box in bird.hitboxes()
            for p in self.pipes
        )
