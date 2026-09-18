"""Render one controlled frame per obstacle slot, to check each sprite path."""

import os

from PIL import Image, ImageDraw

from bird_clock.config import GameConfig
from bird_clock.game import Game
from bird_clock.pipe import PipePair
from bird_clock.renderer import Renderer
from shot_frames import FakeDisplay

OUT = "/tmp/bird_shots"
ZOOM = 3

CASES = [
    ("rect_both", dict(shape="rect", has_bottom=True, has_top=True,
                       gap_bottom=45, gap_top=95)),
    ("rect_bottom", dict(shape="rect", has_bottom=True, has_top=False,
                         gap_bottom=55, gap_top=135)),
    ("rect_top", dict(shape="rect", has_bottom=False, has_top=True,
                      gap_bottom=0, gap_top=80)),
    ("tri_both", dict(shape="triangle", has_bottom=True, has_top=True,
                      gap_bottom=45, gap_top=95)),
    ("tri_bottom", dict(shape="triangle", has_bottom=True, has_top=False,
                        gap_bottom=60, gap_top=135)),
    ("tri_top", dict(shape="triangle", has_bottom=False, has_top=True,
                     gap_bottom=0, gap_top=75)),
    ("ground", dict(shape="rect", has_bottom=True, has_top=False,
                    gap_bottom=18, gap_top=135, is_ground=True)),
]


def main():
    os.makedirs(OUT, exist_ok=True)
    cfg = GameConfig()
    tiles = []
    for name, kw in CASES:
        game = Game(cfg)
        game.enter_play()
        game.pipes.pipes.clear()
        game.pickups.items.clear()
        width = 300.0 if kw.get("is_ground") else 20.0
        for i in range(3):
            p = PipePair(x=70.0 + i * 70.0, width=width, **kw)
            p.enter_age = 99.0  # fully seated, animation out of the way
            game.pipes.pipes.append(p)
            if kw.get("is_ground"):
                break
        disp = FakeDisplay(cfg)
        Renderer(disp, cfg).draw(game)
        tiles.append((name, disp.image.copy()))

    w, h = tiles[0][1].size
    tw, th = w * ZOOM, h * ZOOM
    cols = 2
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (tw * cols, (th + 16) * rows), "#333333")
    pen = ImageDraw.Draw(sheet)
    for i, (name, im) in enumerate(tiles):
        x = (i % cols) * tw
        y = (i // cols) * (th + 16)
        pen.text((x + 4, y + 4), name, fill="#FFFFFF")
        sheet.paste(im.resize((tw, th), Image.NEAREST), (x, y + 16))
    path = f"{OUT}/slots.png"
    sheet.save(path)
    print(path)


if __name__ == "__main__":
    main()
