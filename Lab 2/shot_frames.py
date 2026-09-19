"""Render play-mode frames to PNG so pickups can be eyeballed without the Pi.

Play mode so eating them shows the +N score popup. Idle also spawns pickups,
but those are cosmetic.
"""

import os

from PIL import Image

from bird_clock.config import GameConfig
from bird_clock.game import Game
from bird_clock.renderer import Renderer

DT = 1.0 / 30.0
OUT = "/tmp/bird_shots"


class FakeDisplay:
    def __init__(self, cfg):
        from PIL import ImageDraw, ImageFont

        self.width = cfg.screen.width
        self.height = cfg.screen.height
        self.image = Image.new("RGB", (self.width, self.height), cfg.colors.background)
        self.draw = ImageDraw.Draw(self.image)
        try:
            self.font = ImageFont.load_default()
        except Exception:
            self.font = None
        self._cfg = cfg

    def clear(self, color):
        self.draw.rectangle((0, 0, self.width, self.height), fill=color)

    def show(self):
        pass


def main():
    os.makedirs(OUT, exist_ok=True)
    cfg = GameConfig()
    game = Game(cfg)
    game.enter_play()
    disp = FakeDisplay(cfg)
    renderer = Renderer(disp, cfg)

    saved = 0
    frames = []
    for i in range(int(180.0 / DT)):
        game.handle_input(False, False, (i // 12) % 2 == 0)
        game.update(DT)
        if game.is_dying:
            game.enter_play()
            continue
        # Grab frames where a pickup is close to the bird: the interesting ones.
        near = [p for p in game.pickups.items if 0 <= p.x - game.bird.x < 70]
        if near and i % 7 == 0 and saved < 6:
            renderer.draw(game)
            path = f"{OUT}/play_{saved:02d}.png"
            disp.image.resize((disp.width * 3, disp.height * 3), Image.NEAREST).save(path)
            frames.append(path)
            saved += 1
    print("\n".join(frames))

    # One contact sheet so it is a single image to look at.
    if frames:
        ims = [Image.open(p) for p in frames]
        w, h = ims[0].size
        cols, rows = 2, (len(ims) + 1) // 2
        sheet = Image.new("RGB", (w * cols, h * rows), "#000000")
        for i, im in enumerate(ims):
            sheet.paste(im, ((i % cols) * w, (i // cols) * h))
        sheet.save(f"{OUT}/sheet.png")
        print(f"{OUT}/sheet.png")


if __name__ == "__main__":
    main()
