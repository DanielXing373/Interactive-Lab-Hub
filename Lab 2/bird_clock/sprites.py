"""Skin loading: PNGs in, pre-scaled RGBA tiles out.

Every lookup may return None. A missing file, a missing manifest, or no Pillow
at all just means the renderer keeps drawing its greybox shapes, so the game
never breaks because art is unfinished.

Obstacle heights are random, so sprites are scaled to the live box. By default
that is a uniform nearest-neighbor resize (the spawner already picks width from
the PNG aspect, so trees stay proportional).

Optional vertical 3-slice (off unless `"slice": true` on the slot):

    stretch_start / stretch_end   source-pixel y range that may stretch
    [0, stretch_start)            preserved (canopy, tip, …)
    [stretch_start, stretch_end)  stretched to fill leftover height
    [stretch_end, H)              preserved (roots, knot, …)

Legacy `cap` + `cap_at` still map onto those bands when slice is on.

Scaling is cached because the Pi cannot afford to resize every frame.
"""

import json
import math
import os
import time
from typing import Dict, List, Optional, Tuple

try:
    from PIL import Image
except ImportError:  # pragma: no cover - Pillow is present on both targets
    Image = None

# Legacy one-sided cap: which end of the authored image stays unstretched.
CAP_TOP = "top"
CAP_BOTTOM = "bottom"

_DEFAULT_CAP_AT = {
    "rect_bottom": CAP_TOP,
    "rect_top": CAP_BOTTOM,
    "tri_bottom": CAP_TOP,
    "tri_top": CAP_BOTTOM,
}


def _variant_art(spec: dict, filename: Optional[str]) -> dict:
    """Per-file overlay from a slot's `file` list (slice, stretch_*, …)."""
    if not spec or not filename:
        return {}
    raw = spec.get("file")
    items = raw if isinstance(raw, (list, tuple)) else [raw]
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("file")
        if name == filename:
            return item
        if isinstance(name, (list, tuple)) and filename in name:
            return item
    return {}


def _filenames(value) -> List[str]:
    """`file` may be a string, a list, or a dict with a `file` key.

    Two list meanings, by slot — do not mix them:

    * `rect_*` / `tri_*` / `vine`: spawn variants. The engine picks one name
      per PipePair and passes it into obstacle(); extra names are not frames
      unless a variant dict sets `file` to a list (autumn windmill flipbook).
    * Pickup lists and `ground` / `ground_top` strip lists: animation frames,
      played in order. A pickup dict may also carry swing_degrees /
      swing_seconds for a one-file rotate.

    Collision does not change when a second file appears. Bird still uses the
    first name.
    """
    if not value:
        return []
    if isinstance(value, dict):
        return _filenames(value.get("file"))
    if isinstance(value, (list, tuple)):
        names = []
        for item in value:
            if isinstance(item, dict):
                names.extend(_filenames(item.get("file")))
            elif item:
                names.append(item)
        return names
    return [value]


def _stretch_band(spec: dict, slot: str, img_h: int) -> Optional[Tuple[int, int]]:
    """Return (stretch_start, stretch_end) in source pixels, or None to scale all.

    Prefer stretch_start / stretch_end. Fall back to legacy cap + cap_at so old
    skin.json files keep the previous one-sided preserve behaviour.
    """
    if "stretch_start" in spec or "stretch_end" in spec:
        start = int(spec.get("stretch_start", 0))
        end = int(spec.get("stretch_end", img_h))
        start = max(0, min(start, img_h))
        end = max(start, min(end, img_h))
        return start, end

    cap = int(spec.get("cap", 0))
    if cap <= 0:
        return None
    cap = min(cap, img_h)
    cap_at = spec.get("cap_at", _DEFAULT_CAP_AT.get(slot, CAP_TOP))
    if cap_at == CAP_BOTTOM:
        # Preserve the tip at the bottom; stretch everything above it.
        return 0, img_h - cap
    # Preserve the crown at the top; stretch everything below it.
    return cap, img_h


class SpriteSet:
    def __init__(self, config, skin: str):
        self._cfg = config.skin
        self._items = config.items
        self._skin = skin
        self._screen = config.screen
        self._manifest: Dict = {}
        self._raw: Dict[str, Optional["Image.Image"]] = {}
        self._cache: Dict[Tuple, Optional["Image.Image"]] = {}
        # Obstacle heights are continuous, so every distinct pixel height is a
        # new entry. Drop the lot when it grows past this rather than let it
        # creep for hours; a rebuild costs a few resizes of tiny images.
        self._cache_limit = 512
        self.root = ""
        self.loaded = False
        self.missing: list = []
        if self._cfg.enabled:
            self._load_manifest()

    # ---------------------------------------------------------------- load

    def _load_manifest(self):
        base = os.path.join(os.path.dirname(__file__), self._cfg.root)
        self.root = os.path.join(base, self._skin)
        path = os.path.join(self.root, "skin.json")
        if Image is None or not os.path.isfile(path):
            return
        try:
            with open(path, encoding="utf-8") as fh:
                self._manifest = json.load(fh)
            self.loaded = True
        except (OSError, ValueError):
            self._manifest = {}

    def _open(self, filename: Optional[str]):
        if not filename or Image is None:
            return None
        if filename in self._raw:
            return self._raw[filename]
        path = os.path.join(self.root, filename)
        img = None
        try:
            img = Image.open(path).convert("RGBA")
            img.load()
        except (OSError, ValueError):
            self.missing.append(filename)
        self._raw[filename] = img
        return img

    # ------------------------------------------------------------- lookups

    @property
    def background(self) -> Optional[str]:
        """Flat colour behind everything, when the skin sets one."""
        return self._manifest.get("background")

    @property
    def far_parallax(self) -> float:
        return float(self._manifest.get("far_parallax", 0.35))

    def sky(self):
        return self._fit("sky", self._manifest.get("sky"),
                         self._screen.width, self._screen.height)

    def far(self):
        """Far layer keeps its authored width so it can tile horizontally."""
        img = self._open(self._manifest.get("far"))
        if img is None:
            return None
        key = ("far", img.width, self._screen.height)
        if key not in self._cache:
            scale = self._screen.height / img.height
            w = max(1, int(round(img.width * scale)))
            self._cache[key] = img.resize((w, self._screen.height), Image.NEAREST)
        return self._cache[key]

    def bird(self, w: int, h: int):
        names = _filenames(self._manifest.get("bird"))
        return self._fit("bird", names[0] if names else None, w, h)

    def pickup(self, kind: str, size: int, frame: int = 0, now: Optional[float] = None):
        """Scaled pickup tile.

        Multi-file lists stay a flipbook: `frame` indexes the skin.json name
        list, wrapping. A one-file slot with swing_degrees > 0 adds a rotate
        overlay about the image centre (nearest-neighbor, expand as needed).
        """
        table = self._manifest.get("pickup") or {}
        spec = table.get(kind)
        names = _filenames(spec)
        if not names:
            return None
        filename = names[frame % len(names)]
        raw = self._open(filename)
        if raw is None:
            return None
        scale = min(size / float(raw.width), size / float(raw.height))
        dw = max(1, int(round(raw.width * scale)))
        dh = max(1, int(round(raw.height * scale)))
        img = self._fit(f"pickup:{kind}:{filename}", filename, dw, dh)
        if img is None or len(names) != 1:
            return img
        return self._swing(img, spec, now)

    def floater(self, frame: int = 0):
        """Native-size banner frame. Missing skin key → None (no greybox)."""
        spec = self._manifest.get("floater")
        names = _filenames(spec)
        if not names:
            return None
        filename = names[frame % len(names)]
        return self._open(filename)

    def floater_frame_seconds(self) -> float:
        """Seconds per banner frame. 0 = use FloaterConfig.anim_frame_seconds."""
        spec = self._manifest.get("floater")
        if not isinstance(spec, dict):
            return 0.0
        raw = spec.get("anim_seconds")
        if raw is None:
            return 0.0
        if isinstance(raw, (list, tuple)):
            raw = raw[0] if raw else 0.0
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return 0.0
        return value if value > 0 else 0.0

    def _pickup_swing(self, spec) -> Tuple[float, float]:
        degrees = float(self._items.swing_degrees)
        seconds = float(self._items.swing_seconds)
        if isinstance(spec, dict):
            if "swing_degrees" in spec:
                degrees = float(spec["swing_degrees"])
            if "swing_seconds" in spec:
                seconds = float(spec["swing_seconds"])
        return degrees, seconds

    def _swing(self, img, spec, now: Optional[float]):
        """Ping-pong rotate: 0 → +deg → 0 → −deg → 0 over swing_seconds."""
        degrees, seconds = self._pickup_swing(spec)
        if not degrees or seconds <= 0 or Image is None:
            return img
        t = time.monotonic() if now is None else now
        angle = degrees * math.sin(2.0 * math.pi * t / seconds)
        if abs(angle) < 1e-4:
            return img
        return img.rotate(angle, resample=Image.NEAREST, expand=True)

    def obstacle(
        self,
        slot: str,
        w: int,
        h: int,
        filename: Optional[str] = None,
        flip_y: Optional[bool] = None,
        keep_aspect: bool = False,
    ):
        """Sprite for one solid, scaled to the obstacle box.

        `filename` is the variant the spawner picked from this slot's `file`
        list. Missing / unknown names fall back to the first file (spring
        cherry, one-item lists, greybox shot scripts). Ground/pickup lists
        are not drawn here — they stay animation frames.

        Default stretches to (w, h). Flipbook frames pass keep_aspect so each
        PNG keeps its own width (windmill sails) instead of matching the
        collision box. Height still matches the solid.

        The old vertical 3-slice path is still here: set `"slice": true` plus
        stretch_start/stretch_end (or legacy cap) on the slot to turn it back on.
        """
        spec = (self._manifest.get("obstacles") or {}).get(slot)
        if not spec or w <= 0 or h <= 0:
            return None
        names = _filenames(spec.get("file"))
        if filename and filename in names:
            chosen = filename
        else:
            chosen = names[0] if names else None
        do_flip = spec.get("flip_y") if flip_y is None else flip_y
        overlay = _variant_art(spec, chosen)
        merged = {**spec, **overlay}
        slice_on = bool(merged.get("slice")) and not keep_aspect
        key = (
            slot,
            chosen,
            w,
            h,
            slice_on,
            bool(do_flip),
            keep_aspect,
            merged.get("stretch_start"),
            merged.get("stretch_end"),
        )
        if key in self._cache:
            return self._cache[key]
        img = self._open(chosen)
        if img is None:
            return self._store(key, None)
        # stretch_* is authored on the upright source. Flip the band with the
        # image so hanging trees can reuse the same numbers as standing ones.
        band = _stretch_band(merged, slot, img.height) if slice_on else None
        if do_flip:
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
            if band is not None:
                start, end = band
                band = (img.height - end, img.height - start)
        if keep_aspect and img.height > 0:
            draw_w = max(1, int(round(h * img.width / float(img.height))))
            out = img.resize((draw_w, h), Image.NEAREST)
        elif band is None:
            out = img.resize((w, h), Image.NEAREST)
        else:
            out = _three_slice(img, w, h, band[0], band[1])
        return self._store(key, out)

    def ground_tile(self, h: int, frame: int = 0):
        """Floor strip tile. Prefer strip_tile(slot, h) for ceiling strips."""
        return self.strip_tile("ground", h, frame)

    def strip_frame_count(self, slot: str) -> int:
        spec = (self._manifest.get("obstacles") or {}).get(slot)
        if not spec:
            return 0
        return len(_filenames(spec.get("file")))

    def slot_native(self, slot: str) -> bool:
        spec = (self._manifest.get("obstacles") or {}).get(slot) or {}
        return bool(spec.get("native"))

    def native_strip(
        self,
        slot: str,
        filename: Optional[str] = None,
        w: int = 0,
        h: int = 0,
    ):
        """One PNG, optionally resized as a whole to the solid box. Never tiled."""
        spec = (self._manifest.get("obstacles") or {}).get(slot)
        if not spec:
            return None
        names = _filenames(spec.get("file"))
        if not names:
            return None
        chosen = filename if filename and filename in names else names[0]
        flip = bool(spec.get("flip_y"))
        key = (slot, chosen, "native", flip, int(w), int(h))
        if key in self._cache:
            return self._cache[key]
        img = self._open(chosen)
        if img is None:
            return self._store(key, None)
        if flip:
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
        if w > 0 and h > 0 and (img.width != w or img.height != h):
            img = img.resize((w, h), Image.NEAREST)
        return self._store(key, img)

    def strip_tile(self, slot: str, h: int, frame: int = 0):
        """Single tile scaled to the strip height; the renderer repeats it.

        `frame` indexes the skin.json file list, wrapping — floor and ceiling
        share the renderer's clock so a flipped strip stays in step.
        """
        spec = (self._manifest.get("obstacles") or {}).get(slot)
        if not spec or h <= 0:
            return None
        names = _filenames(spec.get("file"))
        if not names:
            return None
        filename = names[frame % len(names)]
        img = self._open(filename)
        if img is None:
            return None
        flip = bool(spec.get("flip_y"))
        key = (slot, filename, h, flip)
        if key not in self._cache:
            if flip:
                img = img.transpose(Image.FLIP_TOP_BOTTOM)
            scale = h / img.height
            w = max(1, int(round(img.width * scale)))
            self._cache[key] = img.resize((w, h), Image.NEAREST)
        return self._cache[key]

    def _store(self, key: Tuple, value):
        if len(self._cache) >= self._cache_limit:
            self._cache.clear()
        self._cache[key] = value
        return value

    def _fit(self, key_name: str, filename: Optional[str], w: int, h: int):
        if not filename or w <= 0 or h <= 0:
            return None
        key = (key_name, w, h)
        if key in self._cache:
            return self._cache[key]
        img = self._open(filename)
        return self._store(key, None if img is None else img.resize((w, h), Image.NEAREST))


def _three_slice(
    img, w: int, h: int, stretch_start: int, stretch_end: int
):
    """Build a w×h sprite: keep head/tail, nearest-neighbor stretch the middle.

    stretch_start / stretch_end are y coordinates in the (width-scaled) source.
    If the preserved bands already fill or exceed `h`, fall back to a plain
    resize so a short obstacle never clips into nonsense.
    """
    if img.width != w:
        img = img.resize((w, img.height), Image.NEAREST)
    src_h = img.height
    start = max(0, min(int(stretch_start), src_h))
    end = max(start, min(int(stretch_end), src_h))

    top_h = start
    mid_src = end - start
    bot_h = src_h - end
    fixed = top_h + bot_h
    if fixed >= h or mid_src <= 0:
        return img.resize((w, h), Image.NEAREST)

    mid_h = h - fixed
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    y = 0
    if top_h > 0:
        out.paste(img.crop((0, 0, w, top_h)), (0, 0))
        y = top_h
    if mid_h > 0:
        mid = img.crop((0, start, w, end)).resize((w, mid_h), Image.NEAREST)
        out.paste(mid, (0, y))
        y += mid_h
    if bot_h > 0:
        out.paste(img.crop((0, end, w, src_h)), (0, y))
    return out
