"""Draw world objects onto the 240x135 landscape buffer."""

from .config import GameConfig


def world_to_screen_y(world_y: float, height: float, obj_h: float) -> float:
    """World +y is up; PIL +y is down. Return the sprite's top edge."""
    return height - world_y - obj_h


class Renderer:
    def __init__(self, display, config: GameConfig):
        self._display = display
        self._cfg = config
        self._colors = config.colors

    def draw(self, game):
        draw = self._display.draw
        w = self._display.width
        h = self._display.height
        draw.rectangle((0, 0, w, h), fill=self._colors.background)

        self._draw_pipes(game)
        self._draw_bird(game)
        self._draw_hud(game)
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

    def _draw_hud(self, game):
        draw = self._display.draw
        font = self._display.font
        c = self._colors.hud
        hint = self._colors.hint
        if game.in_idle:
            draw.text((4, 2), f"IDLE {game.scores.idle_score}", font=font, fill=c)
            draw.text((4, 16), "A start", font=font, fill=hint)
        elif game.in_play:
            draw.text((4, 2), f"S {game.scores.current_score}  B {game.scores.best_score}", font=font, fill=c)
        else:
            draw.text((4, 2), f"S {game.scores.current_score}  B {game.scores.best_score}", font=font, fill=c)
            draw.text((4, 16), "A retry  B idle", font=font, fill=hint)
