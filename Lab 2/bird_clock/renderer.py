"""Draw world objects onto the 240x135 landscape buffer."""

from PIL import ImageColor

from . import clock_display
from .config import GameConfig


def world_to_screen_y(world_y: float, height: float, obj_h: float) -> float:
    """World +y is up; PIL +y is down. Return the sprite's top edge."""
    return height - world_y - obj_h


class Renderer:
    def __init__(self, display, config: GameConfig):
        self._display = display
        self._cfg = config
        self._hud = config.hud
        self._colors = config.colors
        self._feather_colors = {
            clock_display.DATE: config.colors.feather_date,
            clock_display.HOUR: config.colors.feather_hour,
            clock_display.MINUTE: config.colors.feather_minute,
            clock_display.SECOND: config.colors.feather_second,
        }

    def draw(self, game):
        draw = self._display.draw
        w = self._display.width
        h = self._display.height
        draw.rectangle((0, 0, w, h), fill=self._colors.background)

        self._draw_pipes(game)
        self._draw_bird(game)
        self._draw_clock(game)
        self._draw_best(game)
        self._draw_hints(game)
        self._display.show()

    def _draw_pipes(self, game):
        draw = self._display.draw
        h = self._display.height
        color = self._colors.pipe
        for pipe in game.pipes.pipes:
            x0 = pipe.x
            x1 = pipe.x + pipe.width
            mid = pipe.x + pipe.width * 0.5
            if pipe.shape == "triangle":
                if pipe.has_bottom and pipe.gap_bottom > 0:
                    # World: base on floor, apex at gap_bottom.
                    draw.polygon(
                        [
                            (x0, h),
                            (x1, h),
                            (mid, h - pipe.gap_bottom),
                        ],
                        fill=color,
                    )
                if pipe.has_top and pipe.gap_top < h:
                    draw.polygon(
                        [
                            (x0, 0),
                            (x1, 0),
                            (mid, h - pipe.gap_top),
                        ],
                        fill=color,
                    )
            else:
                if pipe.has_bottom:
                    draw.rectangle((x0, h - pipe.gap_bottom, x1, h), fill=color)
                if pipe.has_top:
                    draw.rectangle((x0, 0, x1, h - pipe.gap_top), fill=color)

    def _draw_bird(self, game):
        draw = self._display.draw
        h = self._display.height
        bird = game.bird
        fill = self._colors.death if game.is_dying else self._colors.bird
        outline = self._colors.bird_outline
        for x, y, w, bh in bird.segments():
            top = world_to_screen_y(y, h, bh)
            draw.rectangle(
                (x, top, x + w, top + bh),
                fill=fill,
                outline=outline,
            )

    def _feather(self, x: int, y: int, color: str):
        """Placeholder feather: quill plus a leaf. Swap for a sprite later."""
        draw = self._display.draw
        hud = self._hud
        w = hud.feather_w
        h = hud.feather_h
        draw.polygon(
            [
                (x + w / 2.0, y),
                (x + w, y + h * 0.45),
                (x + w / 2.0, y + h),
                (x, y + h * 0.45),
            ],
            fill=color,
        )
        draw.line((x + w / 2.0, y, x + w / 2.0, y + h), fill=color)

    def _draw_clock(self, game):
        """Feather tokens for date / hour / minute / second, top-left."""
        draw = self._display.draw
        font = self._display.font
        hud = self._hud
        x = hud.margin_x
        y = hud.clock_y
        for key, text in clock_display.units_for(game, hud.date_format):
            self._feather(x, y + 2, self._feather_colors[key])
            x += hud.feather_w + hud.feather_text_gap
            draw.text((x, y), text, font=font, fill=self._colors.hud)
            x += self._text_width(text) + hud.group_gap
        self._draw_popups(game, x - hud.group_gap + hud.popup_gap, y)

    def _draw_popups(self, game, x: int, y: int):
        """Green "+n" right of the seconds feather: jumps up, then vanishes."""
        popups = game.scores.popups
        if not popups:
            return
        draw = self._display.draw
        font = self._display.font
        base = ImageColor.getrgb(self._colors.score_popup)
        bg = ImageColor.getrgb(self._colors.background)
        for popup in popups:
            p = popup.progress
            # Fast hop out, slow settle, then fade into the background.
            rise = self._hud.popup_rise * (1.0 - (1.0 - p) ** 2)
            color = tuple(
                int(b + (g - b) * p) for b, g in zip(base, bg)
            )
            draw.text((x, y - rise), popup.text, font=font, fill=color)

    def _draw_best(self, game):
        """Best run, top-right. The clock already carries the live score."""
        if game.in_idle:
            return
        text = f"B {game.scores.best_score}"
        x = self._display.width - self._hud.best_margin_x - self._text_width(text)
        self._display.draw.text(
            (x, self._hud.clock_y), text, font=self._display.font, fill=self._colors.hint
        )

    def _text_width(self, text: str) -> int:
        font = self._display.font
        try:
            left, _, right, _ = font.getbbox(text)
            return int(right - left)
        except AttributeError:
            return len(text) * 6

    def _draw_hints(self, game):
        """Left-edge arrows for the two buttons. Hidden while playing."""
        draw = self._display.draw
        font = self._display.font
        hud = self._hud
        color = self._colors.hint

        if game.in_idle:
            top_text = "<- start"
            bottom_text = "<- fly"
        elif game.waiting_after_death:
            top_text = f"<- return {game.seconds_until_idle:.0f}s"
            bottom_text = "<- retry"
        else:
            return

        draw.text((hud.margin_x, hud.hint_top_y), top_text, font=font, fill=color)
        draw.text((hud.margin_x, hud.hint_bottom_y), bottom_text, font=font, fill=color)
