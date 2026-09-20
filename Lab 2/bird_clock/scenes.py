"""Scenes: one art skin plus the spawn pool that goes with it.

A scene is what the player sees as "spring" or "christmas": a folder of PNGs
and a weight table over the spawn kinds the engine can build. A
weight of 0 means that shape never spawns, which is what keeps a scene from
showing a greybox block for art nobody drew.

Generic seasons share one lottery (the spring pool). A later pack may
override (christmas already does). Missing PNGs still greybox.

Scene choice, in order:
  1. a manual override (the idle cheat button, for filming)
  2. today's date
  3. the configured fallback
"""

import time
from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Tuple

# Spawn kinds. The tuple is (collision shape, has_bottom, has_top). Vine and
# the ceiling strip reuse rect geometry; PipePair.kind keeps them distinct
# so hanging cherry and hanging vine can use different art.
RECT_BOTH = "rect_both"
RECT_BOTTOM = "rect_bottom"
RECT_TOP = "rect_top"
TRI_BOTH = "tri_both"
TRI_BOTTOM = "tri_bottom"
TRI_TOP = "tri_top"
VINE = "vine"
GROUND = "ground"
GROUND_TOP = "ground_top"

KIND_SHAPES: Dict[str, Tuple[str, bool, bool]] = {
    RECT_BOTH: ("rect", True, True),
    RECT_BOTTOM: ("rect", True, False),
    RECT_TOP: ("rect", False, True),
    TRI_BOTH: ("triangle", True, True),
    TRI_BOTTOM: ("triangle", True, False),
    TRI_TOP: ("triangle", False, True),
    VINE: ("rect", False, True),
    GROUND: ("rect", True, False),
    GROUND_TOP: ("rect", False, True),
}

# Floor strip: only hanging solids. Ceiling strip: only standing solids.
# Bilateral kinds and the other strip stay out so a corridor remains.
TOP_ONLY_KINDS = (RECT_TOP, TRI_TOP, VINE)
BOTTOM_ONLY_KINDS = (RECT_BOTTOM, TRI_BOTTOM)


@dataclass(frozen=True)
class Scene:
    key: str
    label: str
    skin: str
    weights: Dict[str, float]
    # Months this scene covers, for the seasons.
    months: Tuple[int, ...] = ()
    # Explicit (month, day) dates, for festivals. Checked before months.
    dates: Tuple[Tuple[int, int], ...] = ()
    # (min, max) seconds for this scene's ground strip. Empty uses the global
    # PipeConfig range. Christmas keeps an explicit short Santa strip as the
    # documented special case; generic seasons share the default.
    ground_seconds: Tuple[float, ...] = ()
    # Left-edge spawn spacing. None = PipeConfig play / idle ranges.
    # Summer is the documented exception: looser than the shared seasonal
    # density so trees do not stack like the old caterpillar corridor.
    min_spacing: Optional[float] = None
    max_spacing: Optional[float] = None
    idle_min_spacing: Optional[float] = None
    idle_max_spacing: Optional[float] = None
    # False skips coin spawn (winter / christmas have no pickup art yet).
    pickups: bool = True
    # Cosmetic right-to-left banners (christmas text). Not pickups.
    floaters: bool = False
    # Month shown on the idle HUD while the cheat button is cycling scenes.
    # None keeps the real wall-clock date (boot, and festivals without a month).
    clock_month: Optional[int] = None
    # Optional day for a pinned festival date (christmas = 12/25).
    clock_day: Optional[int] = None
    # Idle B / flap steps through these. Lantern and Asian Games stay out.
    in_cycle: bool = True

    def weight(self, kind: str) -> float:
        return float(self.weights.get(kind, 0.0))


# Trees stay single-sided from here on: standing or hanging, never a pair.
# RECT_BOTH / TRI_BOTH stay at weight 0 on every seasonal / festival scene
# (spring already did this; summer / autumn / winter / christmas / asian_games
# follow the same rule). Greybox is the exception — it still rolls both-sides
# so the engine can be tested without art.
#
# One global seasonal lottery (the spring pool). Winter still shares this
# table. Summer and autumn omit vine / strips (no caterpillar corridor) and
# keep their own obstacle mix. Christmas may override kinds/weights. Vine
# hangs only. Missing PNGs still greybox.
_SEASON_TREE = 0.6          # ×2 orientations = 1.2
_SEASON_VINE = 0.65
_SEASON_STRIP = 0.18        # ×2 orientations = 0.36
_SEASON_WEIGHTS = {
    RECT_BOTTOM: _SEASON_TREE, RECT_TOP: _SEASON_TREE,
    TRI_BOTTOM: _SEASON_TREE, TRI_TOP: _SEASON_TREE,
    VINE: _SEASON_VINE,
    GROUND: _SEASON_STRIP, GROUND_TOP: _SEASON_STRIP,
}
# Summer: two trees (equal) > pyramids > thermometer. No vine, no strips.
_SUMMER_WEIGHTS = {
    RECT_BOTTOM: 1.2, RECT_TOP: 1.2,
    TRI_BOTTOM: 0.4, TRI_TOP: 0.4,
}
# Autumn: tree + windmill (equal, share RECT) and pine (TRI). No vine, no strips.
_AUTUMN_WEIGHTS = {
    RECT_BOTTOM: 1.2, RECT_TOP: 1.2,
    TRI_BOTTOM: 0.6, TRI_TOP: 0.6,
}
# Winter: two trees + wheel (equal rects), snow mountain as one native floor
# strip. No vine, no triangles, no ceiling strip.
_WINTER_WEIGHTS = {
    RECT_BOTTOM: 1.2, RECT_TOP: 1.2,
    GROUND: 0.45,
}
DEFAULT_SCENES: Tuple[Scene, ...] = (
    Scene(
        key="spring", label="Spring", skin="spring",
        weights=_SEASON_WEIGHTS,
        months=(3, 4, 5),
        clock_month=3,
    ),
    Scene(
        key="summer", label="Summer", skin="summer",
        weights=_SUMMER_WEIGHTS,
        months=(6, 7, 8),
        clock_month=6,
        min_spacing=80.0,
        max_spacing=108.0,
        idle_min_spacing=76.0,
        idle_max_spacing=100.0,
    ),
    Scene(
        key="autumn", label="Autumn", skin="fall",
        weights=_AUTUMN_WEIGHTS,
        months=(9, 10, 11),
        clock_month=9,
        min_spacing=60.0,
        max_spacing=84.0,
        idle_min_spacing=56.0,
        idle_max_spacing=78.0,
    ),
    Scene(
        key="winter", label="Winter", skin="winter",
        weights=_WINTER_WEIGHTS,
        months=(12, 1, 2),
        clock_month=12,
    ),
    Scene(
        key="christmas", label="Christmas", skin="chrismas",
        weights={RECT_BOTTOM: 1.2, RECT_TOP: 1.2, GROUND: 1.0},
        dates=((12, 24), (12, 25), (12, 26)),
        floaters=True,
        clock_month=12,
        clock_day=25,
    ),
    # Lunar dates are not computed; set them by hand each year or just pick
    # the scene with the cheat button.
    Scene(
        key="spring_festival", label="Spring Festival", skin="chinese_newyear",
        weights={RECT_TOP: 1.2, GROUND: 1.0},
        dates=((2, 6),),
        floaters=True,
        clock_month=2,
        clock_day=6,
    ),
    Scene(
        key="anniversary", label="Anniversary", skin="anniversary",
        weights={RECT_BOTTOM: 1.2, RECT_TOP: 1.2},
        dates=((7, 8),),
        clock_month=7,
        clock_day=8,
        min_spacing=64.0,
        max_spacing=88.0,
        idle_min_spacing=60.0,
        idle_max_spacing=82.0,
    ),
    # Every shape on, for checking the engine itself.
    Scene(
        key="greybox", label="Greybox", skin="_none",
        weights={
            RECT_BOTH: 1.0, RECT_BOTTOM: 1.0, RECT_TOP: 1.0,
            TRI_BOTH: 1.0, TRI_BOTTOM: 1.0, TRI_TOP: 1.0, GROUND: 0.55,
        },
    ),
)


def scene_for_date(scenes: Sequence[Scene], now: Optional[float] = None) -> Optional[Scene]:
    """Festival first, then season by month."""
    stamp = time.localtime(time.time() if now is None else now)
    today = (stamp.tm_mon, stamp.tm_mday)
    for scene in scenes:
        if today in scene.dates:
            return scene
    for scene in scenes:
        if stamp.tm_mon in scene.months:
            return scene
    return None


class SceneBook:
    """Holds the scene list and which one is live."""

    def __init__(self, config):
        cfg = config.scenes
        self.scenes: Tuple[Scene, ...] = tuple(cfg.scenes or DEFAULT_SCENES)
        self._auto = cfg.auto_by_date
        self._fallback = cfg.fallback
        self._index = 0
        self._manual = False
        self.refresh()

    @property
    def current(self) -> Scene:
        return self.scenes[self._index]

    @property
    def manual(self) -> bool:
        """True once the cheat button has taken over from the date."""
        return self._manual

    def refresh(self):
        """Re-pick from the date. No-op once the cheat button has been used."""
        if self._manual:
            return
        chosen = scene_for_date(self.scenes) if self._auto else None
        if chosen is None:
            chosen = self._by_key(self._fallback) or self.scenes[0]
        self._index = self.scenes.index(chosen)

    def next(self) -> Scene:
        """Cheat button: step to the next cycled scene and stop following the clock."""
        self._manual = True
        n = len(self.scenes)
        for _ in range(n):
            self._index = (self._index + 1) % n
            if self.current.in_cycle:
                return self.current
        return self.current

    def select(self, key: str) -> Optional[Scene]:
        scene = self._by_key(key)
        if scene is None:
            return None
        self._manual = True
        self._index = self.scenes.index(scene)
        return scene

    def follow_clock(self):
        self._manual = False
        self.refresh()

    def _by_key(self, key: str) -> Optional[Scene]:
        for scene in self.scenes:
            if scene.key == key:
                return scene
        return None
