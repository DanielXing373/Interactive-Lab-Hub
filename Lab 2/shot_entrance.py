"""Frame strip of the obstacle entrance animation, for eyeballing the timing."""

import os

from PIL import Image

from bird_clock.config import GameConfig
from bird_clock.game import Game
from bird_clock.renderer import Renderer
from shot_frames import FakeDisplay

DT = 1.0 / 30.0
OUT = "/tmp/bird_shots"
ZOOM = 3


def capture(shape_wanted, frames=8, stride=None):
    """Catch an obstacle of the given shape mid-entrance and hold the camera."""
    cfg = GameConfig()
    if stride is None:
        # Spread the frames over the animation plus a little settle time.
        span = cfg.pipes.enter_seconds * 1.4 / DT
        stride = max(1, round(span / (frames - 1)))
    game = Game(cfg)
    disp = FakeDisplay(cfg)
    renderer = Renderer(disp, cfg)

    shots = []
    watching = None
    for _ in range(int(240.0 / DT)):
        game.update(DT)
        if watching is None:
            for p in game.pipes.pipes:
                same = p.shape == shape_wanted
                started = 0.0 < p.enter_age <= DT * 1.5
                if same and started and p.animates_entrance:
                    watching = p
                    break
        if watching is not None:
            if len(shots) < frames and len(shots) * stride <= int(
                round(watching.enter_age / DT)
            ):
                renderer.draw(game)
                ext = watching.enter_extension(
                    cfg.pipes.enter_seconds, cfg.pipes.enter_peak
                )
                shots.append((disp.image.copy(), watching.enter_age, ext))
            if len(shots) >= frames:
                break
    return shots


def strip(shots, path, label, crop_w=70):
    """Filmstrip left to right, cropped to the right edge where entry happens."""
    if not shots:
        print(f"no frames for {label}")
        return
    from PIL import ImageDraw

    w, h = shots[0][0].size
    cw = min(crop_w, w)
    tile_w, tile_h = cw * ZOOM, h * ZOOM
    pad = 4
    sheet = Image.new(
        "RGB", (tile_w * len(shots) + pad * (len(shots) - 1), tile_h + 14), "#444444"
    )
    pen = ImageDraw.Draw(sheet)
    for i, (im, age, ext) in enumerate(shots):
        tile = im.crop((w - cw, 0, w, h)).resize((tile_w, tile_h), Image.NEAREST)
        x = i * (tile_w + pad)
        sheet.paste(tile, (x, 14))
        pen.text((x + 2, 3), f"{age * 1000:.0f}ms  x{ext:.2f}", fill="#FFFFFF")
        print(f"  {label} frame {i}: t={age * 1000:5.0f}ms  extension={ext:.2f}")
    sheet.save(path)
    print(path)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for shape in ("rect", "triangle"):
        strip(capture(shape), f"{OUT}/enter_{shape}.png", shape)
