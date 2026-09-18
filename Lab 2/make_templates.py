"""Generate placeholder PNGs for a skin, at the exact sizes the engine wants.

They are deliberately crude: flat colour, dashed cap line, size label. The
point is to prove the pipeline end to end and to hand over canvases that are
already the right shape. Replace the files one at a time; the game picks up
whatever exists and greyboxes the rest.

    python3 make_templates.py [skin_name]
"""

import json
import os
import sys

from PIL import Image, ImageDraw

from bird_clock.config import GameConfig

CFG = GameConfig()
PIPES = CFG.pipes
ROOT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "bird_clock", CFG.skin.root
)

# Authoring sizes. Width is the widest an obstacle ever gets, height covers the
# tallest it ever gets; the engine rescales down and three-slices as needed.
OBS_W = int(PIPES.max_width)
OBS_H = int(PIPES.uni_max_height)
CAP = 18
GROUND_H = int(PIPES.ground_height)
PICKUP = int(CFG.items.sprite_size)
BIRD_W, BIRD_H = int(CFG.bird.width), int(CFG.bird.height)
SCREEN_W, SCREEN_H = CFG.screen.width, CFG.screen.height

PALETTE = {
    "sprout": "#6FBF5B",
    "vine": "#4E8C42",
    "hill": "#8FCB7A",
    "hill_top": "#A8D89A",
    "ground": "#7A5C3E",
    "pickup": "#F2B5D4",
    "bird": "#F5D76E",
    "sky": "#BFE6F2",
    "far": "#9CCFA6",
}


def _label(img, text):
    d = ImageDraw.Draw(img)
    try:
        d.text((1, 1), text, fill="#00000099")
    except Exception:
        pass


def rect_sprite(path, color, cap_at_top=True):
    img = Image.new("RGBA", (OBS_W, OBS_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, OBS_W - 1, OBS_H - 1), fill=color, outline="#00000055")
    # Mark the cap band: this part keeps its authored size, the rest stretches.
    y = CAP if cap_at_top else OBS_H - CAP
    for x in range(0, OBS_W, 3):
        d.line((x, y, x + 1, y), fill="#FFFFFFAA")
    img.save(path)


def triangle_sprite(path, color, point_up=True):
    img = Image.new("RGBA", (OBS_W, OBS_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if point_up:
        pts = [(0, OBS_H - 1), (OBS_W - 1, OBS_H - 1), (OBS_W // 2, 0)]
    else:
        pts = [(0, 0), (OBS_W - 1, 0), (OBS_W // 2, OBS_H - 1)]
    d.polygon(pts, fill=color, outline="#00000055")
    img.save(path)


def ground_tile(path, color):
    w = 16
    img = Image.new("RGBA", (w, GROUND_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, w - 1, GROUND_H - 1), fill=color, outline="#00000055")
    d.line((0, 0, w - 1, 0), fill="#9C7A55")
    img.save(path)


def pickup_sprite(path, color):
    img = Image.new("RGBA", (PICKUP, PICKUP), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = PICKUP / 2
    d.polygon([(r, 0), (PICKUP - 1, r), (r, PICKUP - 1), (0, r)],
              fill=color, outline="#FFFFFF")
    img.save(path)


def bird_sprite(path, color):
    img = Image.new("RGBA", (BIRD_W, BIRD_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, BIRD_W - 1, BIRD_H - 1), fill=color, outline="#FFFFFF")
    img.save(path)


def sky(path, color):
    img = Image.new("RGBA", (SCREEN_W, SCREEN_H), color)
    img.save(path)


def far(path, color):
    """Tiles horizontally, so the left and right edges must match."""
    w, h = 120, SCREEN_H
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    base = h - 26
    for i in range(0, w + 1, 30):
        d.polygon([(i - 15, h), (i, base), (i + 15, h)], fill=color)
    d.rectangle((0, h - 6, w, h), fill=color)
    img.save(path)


def build(skin="spring"):
    out = os.path.join(ROOT, skin)
    os.makedirs(out, exist_ok=True)
    p = lambda n: os.path.join(out, n)

    rect_sprite(p("sprout.png"), PALETTE["sprout"], cap_at_top=True)
    rect_sprite(p("vine.png"), PALETTE["vine"], cap_at_top=False)
    triangle_sprite(p("hill.png"), PALETTE["hill"], point_up=True)
    triangle_sprite(p("hill_down.png"), PALETTE["hill_top"], point_up=False)
    ground_tile(p("caterpillar.png"), PALETTE["ground"])
    pickup_sprite(p("butterfly.png"), PALETTE["pickup"])
    bird_sprite(p("bird.png"), PALETTE["bird"])
    sky(p("sky.png"), PALETTE["sky"])
    far(p("far.png"), PALETTE["far"])

    manifest = {
        "name": skin,
        "background": PALETTE["sky"],
        "sky": "sky.png",
        "far": "far.png",
        "far_parallax": 0.35,
        "obstacles": {
            # Standing tree: keep canopy + roots, stretch only the trunk band.
            "rect_bottom": {
                "file": ["sprout.png"],
                "stretch_start": 18,
                "stretch_end": 54,
            },
            # Hanging vine: keep the tip; stretch the rope above it.
            # Legacy form also works: {"cap": 18, "cap_at": "bottom"}
            "rect_top": {
                "file": ["vine.png"],
                "stretch_start": 0,
                "stretch_end": 54,
            },
            "tri_bottom": {"file": ["hill.png"]},
            "tri_top": {"file": ["hill_down.png"]},
            "ground": {"file": ["caterpillar.png"]},
        },
        "pickup": {"coin": ["butterfly.png"]},
        "bird": "bird.png",
    }
    with open(p("skin.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)

    print(f"skin written to {out}")
    print(f"  obstacle canvas {OBS_W} x {OBS_H}")
    print(f"  stretch example: canopy [0,{CAP}) trunk [{CAP},{OBS_H - CAP}) roots [{OBS_H - CAP},{OBS_H})")
    print(f"  ground tile 16 x {GROUND_H} (repeats horizontally)")
    print(f"  pickup {PICKUP} x {PICKUP}, bird {BIRD_W} x {BIRD_H}")
    print(f"  sky {SCREEN_W} x {SCREEN_H}, far layer 120 x {SCREEN_H} (must tile)")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "spring")
