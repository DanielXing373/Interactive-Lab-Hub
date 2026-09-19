"""Scrolling obstacles: bi/uni rects & triangles, plus floor/ceiling strips."""

import json
import os
import random
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

from . import scenes
from .collision import hits_pipe
from .config import GameConfig, PipeConfig

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None


@lru_cache(maxsize=8)
def _back_constant(peak: float) -> float:
    """easeOutBack constant whose curve tops out at `peak`.

    The curve is 1 + (c+1)u^3 + c*u^2 with u = p-1, whose maximum works out to
    1 + 4c^3 / (27(c+1)^2). That does not invert cleanly, so bisect it once and
    cache: callers get to say "120%" instead of guessing at a magic constant.
    """
    if peak <= 1.0:
        return 0.0
    target = peak - 1.0
    lo, hi = 0.0, 50.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if 4.0 * mid ** 3 / (27.0 * (mid + 1.0) ** 2) < target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


class PipePair:
    def __init__(
        self,
        x: float,
        width: float,
        gap_bottom: float,
        gap_top: float,
        shape: str = "rect",
        has_bottom: bool = True,
        has_top: bool = True,
        is_ground: bool = False,
        is_ceiling: bool = False,
        kind: str = "",
        bottom_slot: str = "",
        top_slot: str = "",
        bottom_file: str = "",
        top_file: str = "",
        hit_inset: float = 0.0,
    ):
        self.x = x
        self.width = width
        self.gap_bottom = gap_bottom
        self.gap_top = gap_top
        self.shape = shape
        self.has_bottom = has_bottom
        self.has_top = has_top
        self.is_ground = is_ground
        self.is_ceiling = is_ceiling
        self.kind = kind
        self.bottom_slot = bottom_slot
        self.top_slot = top_slot
        # One PNG from the slot's `file` list (rect/tri/vine variants).
        # Empty → sprites use the first name. Ground/pickup lists stay frames.
        self.bottom_file = bottom_file
        self.top_file = top_file
        # Inward collision shrink in pixels per side. Draw/spawn box stays full
        # size; only collides() uses this. 0 = hitbox matches the sprite.
        self.hit_inset = max(0.0, float(hit_inset))
        self.passed = False
        # Seconds since the obstacle cleared the right edge; drives the
        # entrance animation only, never collision.
        self.enter_age = 0.0

    @property
    def animates_entrance(self) -> bool:
        """Long strips are one band, so stabbing them in looks wrong."""
        return not self.is_ground and not self.is_ceiling

    def enter_extension(self, seconds: float, peak: float) -> float:
        """0 = still outside the screen edge, 1 = seated. Overshoots to `peak`."""
        if not self.animates_entrance or seconds <= 0:
            return 1.0
        p = self.enter_age / seconds
        if p >= 1.0:
            return 1.0
        c = _back_constant(peak)
        inv = p - 1.0
        return 1.0 + (c + 1.0) * inv ** 3 + c * inv ** 2

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

    def collision_geom(self, screen_height: float) -> Tuple[float, float, float, float]:
        """x, width, gap_bottom, gap_top used by hits_pipe.

        `hit_inset` pulls each free edge inward. Floor/ceiling attachment stays
        put so a wrapped bird cannot slip through the trunk. Renderer still
        reads the un-inset fields.
        """
        inset = self.hit_inset
        if inset <= 0:
            return self.x, self.width, self.gap_bottom, self.gap_top
        # Keep at least a pixel of solid so a huge inset cannot invert the box.
        inset_x = min(inset, max(0.0, (self.width - 1.0) * 0.5))
        x = self.x + inset_x
        width = max(1.0, self.width - 2.0 * inset_x)
        gap_bottom = self.gap_bottom
        gap_top = self.gap_top
        if self.has_bottom:
            gap_bottom = max(0.0, gap_bottom - inset)
        if self.has_top:
            gap_top = min(screen_height, gap_top + inset)
        if self.has_bottom and self.has_top and gap_bottom > gap_top:
            mid = 0.5 * (self.gap_bottom + self.gap_top)
            gap_bottom = gap_top = mid
        return x, width, gap_bottom, gap_top

    def collides(self, hitbox, screen_height: float) -> bool:
        x, width, gap_bottom, gap_top = self.collision_geom(screen_height)
        return hits_pipe(
            hitbox,
            x,
            width,
            gap_bottom,
            gap_top,
            screen_height,
            shape=self.shape,
            has_bottom=self.has_bottom,
            has_top=self.has_top,
        )


class PipeField:
    def __init__(self, config: GameConfig):
        self._cfg: PipeConfig = config.pipes
        self._skin_root = config.skin.root
        self._screen_h = config.screen.height
        self._screen_w = config.screen.width
        self._bird_h = config.bird.height
        self.pipes: List[PipePair] = []
        self._distance_until_spawn = 0.0
        self._scene = scenes.DEFAULT_SCENES[-1]  # greybox until a scene is set
        # slot -> first-file aspect, used when a spawn has no chosen PNG.
        self._aspects: Dict[str, float] = {}
        # filename -> aspect, so a random variant can size to its own PNG.
        self._file_aspects: Dict[str, float] = {}
        # slot -> skin.json file list (variants for rect/tri/vine; frames for strips).
        self._slot_files: Dict[str, List[str]] = {}
        # slot -> collision inset (px per side). Missing / 0 = full visual box.
        self._hit_insets: Dict[str, float] = {}
        # slot -> uniform scale after aspect-fit. Missing / 1 = unchanged.
        self._size_muls: Dict[str, float] = {}

    def clear(self):
        self.pipes.clear()
        self._distance_until_spawn = 0.0

    def set_pool(self, scene):
        """Swap the lottery pool and reload sprite aspects for this skin."""
        self._scene = scene
        (
            self._aspects,
            self._hit_insets,
            self._file_aspects,
            self._slot_files,
            self._size_muls,
        ) = self._load_skin_metrics(scene.skin)

    def update(self, dt: float, speed: float, idle: bool):
        for pipe in self.pipes:
            pipe.move(dt, speed)
            # Hold the animation until the whole obstacle is inside the right
            # edge, otherwise it plays out of frame and reads as a pop-in.
            trigger = self._screen_w - self._cfg.enter_margin_x
            if pipe.animates_entrance and pipe.x + pipe.width <= trigger:
                pipe.enter_age += dt
        self.pipes = [p for p in self.pipes if not p.is_off_left()]
        self._distance_until_spawn -= speed * dt
        if self._distance_until_spawn <= 0:
            if not self.spawn(idle=idle, speed=speed):
                # Nothing legal for this scene right now (usually a ground
                # strip with no hanging obstacle to pair it with). Look again
                # shortly rather than burn a whole spacing interval.
                self._distance_until_spawn = self._cfg.spawn_retry_spacing
            else:
                lo, hi = self._spacing_range(idle)
                self._distance_until_spawn = random.uniform(lo, hi)

    def _spacing_range(self, idle: bool) -> Tuple[float, float]:
        """Play / idle left-edge spacing. Scene fields win when set."""
        scene = self._scene
        if idle:
            lo = (
                scene.idle_min_spacing
                if scene.idle_min_spacing is not None
                else self._cfg.idle_min_spacing
            )
            hi = (
                scene.idle_max_spacing
                if scene.idle_max_spacing is not None
                else self._cfg.idle_max_spacing
            )
        else:
            lo = (
                scene.min_spacing
                if scene.min_spacing is not None
                else self._cfg.min_spacing
            )
            hi = (
                scene.max_spacing
                if scene.max_spacing is not None
                else self._cfg.max_spacing
            )
        return lo, hi

    def _strip_at_spawn(self, ceiling: bool) -> Optional[PipePair]:
        x = self._cfg.spawn_x
        for p in self.pipes:
            if ceiling:
                if p.is_ceiling and p.x <= x <= p.x + p.width:
                    return p
            elif p.is_ground and p.x <= x <= p.x + p.width:
                return p
        return None

    def ground_at_spawn(self) -> Optional[PipePair]:
        """Floor strip still covering the spawn column, if any."""
        return self._strip_at_spawn(False)

    def ceiling_at_spawn(self) -> Optional[PipePair]:
        """Ceiling strip still covering the spawn column, if any."""
        return self._strip_at_spawn(True)

    def _load_skin_metrics(
        self, skin: str
    ) -> Tuple[
        Dict[str, float],
        Dict[str, float],
        Dict[str, float],
        Dict[str, List[str]],
        Dict[str, float],
    ]:
        """PNG aspects, per-slot file lists, hit_inset, and size_mul from skin.json.

        hit_inset / size_mul do not need Pillow; aspect still does. Every name
        in a slot's `file` list is measured so a random variant can keep its
        own proportions. Missing art keeps the greybox random width and a
        full-size hitbox. Missing size_mul is 1.0 (spring unchanged).
        """
        aspects: Dict[str, float] = {}
        insets: Dict[str, float] = {}
        file_aspects: Dict[str, float] = {}
        slot_files: Dict[str, List[str]] = {}
        size_muls: Dict[str, float] = {}
        folder = os.path.join(os.path.dirname(__file__), self._skin_root, skin)
        path = os.path.join(folder, "skin.json")
        if not os.path.isfile(path):
            return aspects, insets, file_aspects, slot_files, size_muls
        try:
            with open(path, encoding="utf-8") as fh:
                manifest = json.load(fh)
        except (OSError, ValueError):
            return aspects, insets, file_aspects, slot_files, size_muls
        for slot, spec in (manifest.get("obstacles") or {}).items():
            if not isinstance(spec, dict):
                continue
            raw = spec.get("hit_inset")
            if raw is not None:
                try:
                    inset = float(raw)
                except (TypeError, ValueError):
                    inset = 0.0
                if inset > 0:
                    insets[slot] = inset
            raw_mul = spec.get("size_mul")
            if raw_mul is not None:
                try:
                    mul = float(raw_mul)
                except (TypeError, ValueError):
                    mul = 1.0
                if mul > 0:
                    size_muls[slot] = mul
            names = spec.get("file")
            if isinstance(names, (list, tuple)):
                file_list = [n for n in names if n]
            elif names:
                file_list = [names]
            else:
                file_list = []
            if file_list:
                slot_files[slot] = file_list
            if Image is None:
                continue
            for name in file_list:
                if name in file_aspects:
                    continue
                try:
                    with Image.open(os.path.join(folder, name)) as im:
                        if im.height > 0:
                            file_aspects[name] = im.width / float(im.height)
                except (OSError, ValueError):
                    continue
            first = file_list[0] if file_list else None
            if first and first in file_aspects:
                aspects[slot] = file_aspects[first]
        return aspects, insets, file_aspects, slot_files, size_muls

    def _slot_size_mul(self, slot: str) -> float:
        """Uniform scale after aspect-fit. Missing / invalid → 1.0."""
        mul = self._size_muls.get(slot, 1.0)
        return mul if mul > 0 else 1.0

    def _apply_size_mul(
        self,
        slot: str,
        width: float,
        solid: float,
        max_solid: float,
    ) -> Tuple[float, float]:
        """Scale fitted width/height together, then keep a bird corridor.

        Collision and the drawn sprite both read these numbers, so one mul
        keeps them the same geometry. max_solid is the tallest column that
        still leaves bird + gap_over_bird + edge_margin on a 135px screen.
        """
        mul = self._slot_size_mul(slot)
        if mul != 1.0:
            width *= mul
            solid *= mul
        if max_solid > 0 and solid > max_solid:
            scale = max_solid / solid
            width *= scale
            solid = max_solid
        return max(1.0, width), max(1.0, solid)

    def _slot_hit_inset(self, bottom_slot: str, top_slot: str) -> float:
        """Largest inset declared on this obstacle's art slots (usually one)."""
        inset = 0.0
        if bottom_slot:
            inset = max(inset, self._hit_insets.get(bottom_slot, 0.0))
        if top_slot:
            inset = max(inset, self._hit_insets.get(top_slot, 0.0))
        return inset

    def _slot_name(self, kind_key: str, shape: str, has_bottom: bool, has_top: bool) -> str:
        if kind_key == scenes.VINE:
            return "vine"
        if kind_key == scenes.GROUND_TOP:
            return "ground_top"
        if kind_key == scenes.GROUND:
            return "ground"
        if kind_key == scenes.TRI_BOTH:
            return "tri_bottom"
        if kind_key == scenes.RECT_BOTH:
            return "rect_bottom"
        if shape == "triangle":
            return "tri_bottom" if has_bottom else "tri_top"
        return "rect_bottom" if has_bottom else "rect_top"

    def _is_variant_slot(self, slot: str) -> bool:
        """rect_* / tri_* / vine lists are visual variants, not flipbooks.

        `ground` / `ground_top` keep their file lists as animation frames.
        """
        return (
            slot.startswith("rect_")
            or slot.startswith("tri_")
            or slot == "vine"
        )

    def _pick_variant(self, slot: str) -> str:
        """One filename from the slot's `file` list, or empty if none."""
        if not slot or not self._is_variant_slot(slot):
            return ""
        names = self._slot_files.get(slot) or []
        if not names:
            return ""
        if len(names) == 1:
            return names[0]
        return random.choice(names)

    def _fit_aspect(
        self,
        slot: str,
        solid_h: float,
        min_h: Optional[float] = None,
        max_h: Optional[float] = None,
        min_w: Optional[float] = None,
        max_w: Optional[float] = None,
        filename: Optional[str] = None,
    ) -> Tuple[float, float]:
        """Return (width, solid_h) matching the sprite, clamped to the band.

        Prefer the chosen variant's PNG aspect; otherwise the slot's first
        file. No aspect (missing art / greybox) falls back to a random width.
        """
        lo = self._cfg.uni_min_height if min_h is None else min_h
        hi = self._cfg.uni_max_height if max_h is None else max_h
        min_width = self._cfg.min_width if min_w is None else min_w
        max_width = self._cfg.max_width if max_w is None else max_w
        aspect = self._file_aspects.get(filename) if filename else None
        if aspect is None or aspect <= 0:
            aspect = self._aspects.get(slot)
        if aspect is None or aspect <= 0 or solid_h <= 0:
            return random.uniform(min_width, max_width), solid_h
        width = solid_h * aspect
        if width < min_width:
            width = min_width
            solid_h = width / aspect
        elif width > max_width:
            width = max_width
            solid_h = width / aspect
        if solid_h > hi:
            solid_h = hi
            width = min(max_width, max(min_width, solid_h * aspect))
        elif solid_h < lo:
            solid_h = lo
            width = min(max_width, max(min_width, solid_h * aspect))
        return width, solid_h

    def _pool(self) -> List[Tuple[str, float]]:
        """Candidate kinds and weights, filtered to what may spawn right now.

        A floor strip only pairs with hanging solids; a ceiling strip only
        with standing ones. The other strip and bilateral kinds stay out so
        a corridor remains.
        """
        floor = self.ground_at_spawn() is not None
        ceil = self.ceiling_at_spawn() is not None
        if floor and ceil:
            allowed = ()
        elif floor:
            allowed = scenes.TOP_ONLY_KINDS
        elif ceil:
            allowed = scenes.BOTTOM_ONLY_KINDS
        else:
            allowed = tuple(scenes.KIND_SHAPES)
        scene = self._scene
        return [(k, scene.weight(k)) for k in allowed if scene.weight(k) > 0]

    def _pick_kind(self) -> Optional[str]:
        """Chosen kind key, or None to spawn nothing.

        None happens when a scene has no art for anything legal right now -
        typically a floor strip with no hanging obstacle. Skipping is
        correct: substituting a shape the scene never declared would put an
        undrawn greybox block on screen.
        """
        pool = self._pool()
        if not pool:
            return None
        return random.choices([k for k, _ in pool], weights=[w for _, w in pool], k=1)[0]

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

    def _uni_height(
        self,
        floor: float = 0.0,
        ceiling: Optional[float] = None,
        min_h: Optional[float] = None,
        max_h: Optional[float] = None,
    ) -> float:
        """Single-sided solid height, leaving a bird-sized corridor in the open."""
        if ceiling is None:
            ceiling = self._screen_h
        lo = self._cfg.uni_min_height if min_h is None else min_h
        hi_cfg = self._cfg.uni_max_height if max_h is None else max_h
        clear = self._bird_h + self._cfg.gap_over_bird + self._cfg.edge_margin
        room = max(lo, ceiling - floor - clear)
        hi = min(hi_cfg, room)
        lo = min(lo, hi)
        return random.uniform(lo, hi)

    def _append_strip(self, kind_key: str, speed: float) -> bool:
        span = self._scene.ground_seconds or (
            self._cfg.ground_min_seconds, self._cfg.ground_max_seconds
        )
        duration = random.uniform(span[0], span[1])
        ground_width = max(self._cfg.min_width, max(speed, 1.0) * duration)
        height = self._cfg.ground_height
        if kind_key == scenes.GROUND_TOP:
            self.pipes.append(
                PipePair(
                    x=self._cfg.spawn_x,
                    width=ground_width,
                    gap_bottom=0.0,
                    gap_top=self._screen_h - height,
                    shape="rect",
                    has_bottom=False,
                    has_top=True,
                    is_ceiling=True,
                    kind=kind_key,
                    top_slot="ground_top",
                )
            )
        else:
            self.pipes.append(
                PipePair(
                    x=self._cfg.spawn_x,
                    width=ground_width,
                    gap_bottom=height,
                    gap_top=self._screen_h,
                    shape="rect",
                    has_bottom=True,
                    has_top=False,
                    is_ground=True,
                    kind=kind_key,
                    bottom_slot="ground",
                )
            )
        return True

    def spawn(self, idle: bool, speed: float = 32.0) -> bool:
        kind_key = self._pick_kind()
        if kind_key is None:
            return False
        shape, has_bottom, has_top = scenes.KIND_SHAPES[kind_key]
        slot = self._slot_name(kind_key, shape, has_bottom, has_top)

        if kind_key in (scenes.GROUND, scenes.GROUND_TOP):
            return self._append_strip(kind_key, speed)

        bottom_slot = ""
        top_slot = ""
        if has_bottom:
            bottom_slot = "tri_bottom" if shape == "triangle" else "rect_bottom"
        if has_top:
            if kind_key == scenes.VINE:
                top_slot = "vine"
            else:
                top_slot = "tri_top" if shape == "triangle" else "rect_top"
        bottom_file = self._pick_variant(bottom_slot) if bottom_slot else ""
        top_file = self._pick_variant(top_slot) if top_slot else ""
        art_file = top_file if slot == top_slot else bottom_file

        size = {}
        if kind_key == scenes.VINE:
            size = dict(
                min_h=self._cfg.vine_min_height,
                max_h=self._cfg.vine_max_height,
                min_w=self._cfg.vine_min_width,
                max_w=self._cfg.vine_max_width,
            )

        if has_bottom and has_top:
            gap_bottom, gap_top = self._bilateral_gap(idle)
            solid = max(gap_bottom, self._screen_h - gap_top)
            width, _ = self._fit_aspect(slot, solid, filename=art_file)
        elif has_bottom:
            ceil = self.ceiling_at_spawn()
            ceiling = ceil.gap_top if ceil is not None else self._screen_h
            solid = self._uni_height(
                ceiling=ceiling, min_h=size.get("min_h"), max_h=size.get("max_h")
            )
            width, solid = self._fit_aspect(slot, solid, filename=art_file, **size)
            max_solid = ceiling - (
                self._bird_h + self._cfg.gap_over_bird + self._cfg.edge_margin
            )
            if solid > max_solid > 0:
                solid = max_solid
                width, solid = self._fit_aspect(slot, solid, filename=art_file, **size)
            width, solid = self._apply_size_mul(slot, width, solid, max_solid)
            gap_bottom, gap_top = solid, self._screen_h
        else:
            ground = self.ground_at_spawn()
            floor = ground.gap_bottom if ground is not None else 0.0
            solid = self._uni_height(
                floor, min_h=size.get("min_h"), max_h=size.get("max_h")
            )
            width, solid = self._fit_aspect(slot, solid, filename=art_file, **size)
            max_solid = self._screen_h - floor - (
                self._bird_h + self._cfg.gap_over_bird + self._cfg.edge_margin
            )
            if solid > max_solid > 0:
                solid = max_solid
                width, solid = self._fit_aspect(slot, solid, filename=art_file, **size)
            width, solid = self._apply_size_mul(slot, width, solid, max_solid)
            gap_bottom, gap_top = floor, self._screen_h - solid

        self.pipes.append(
            PipePair(
                x=self._cfg.spawn_x,
                width=width,
                gap_bottom=gap_bottom,
                gap_top=gap_top,
                shape=shape,
                has_bottom=has_bottom,
                has_top=has_top,
                kind=kind_key,
                bottom_slot=bottom_slot,
                top_slot=top_slot,
                bottom_file=bottom_file,
                top_file=top_file,
                hit_inset=self._slot_hit_inset(bottom_slot, top_slot),
            )
        )
        return True

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
