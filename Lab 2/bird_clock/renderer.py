"""Draw world objects onto the 240x135 landscape buffer."""

import time

from PIL import ImageColor

from . import clock_display
from .config import GameConfig
from .sprites import SpriteSet


def world_to_screen_y(world_y: float, height: float, obj_h: float) -> float:
    """World +y is up; PIL +y is down. Return the sprite's top edge."""
    return height - world_y - obj_h


class Renderer:
    def __init__(self, display, config: GameConfig):
        self._display = display
        self._cfg = config
        self._hud = config.hud
        self._colors = config.colors
        # One set per skin, kept so stepping through scenes does not re-read
        # PNGs every time.
        self._skins = {}
        self._sprites = self._skin_for(config.scenes.fallback)
        self._feather_colors = {
            clock_display.DATE: config.colors.feather_date,
            clock_display.HOUR: config.colors.feather_hour,
            clock_display.MINUTE: config.colors.feather_minute,
            clock_display.SECOND: config.colors.feather_second,
        }

    def _skin_for(self, name: str) -> SpriteSet:
        if name not in self._skins:
            self._skins[name] = SpriteSet(self._cfg, name)
        return self._skins[name]

    def draw(self, game):
        self._sprites = self._skin_for(game.scene.skin)
        self._draw_background(game)
        self._draw_pipes(game)
        self._draw_floaters(game)
        self._draw_pickups(game)
        self._draw_bird(game)
        self._draw_world_popups(game)
        self._draw_clock(game)
        self._draw_best(game)
        self._draw_hints(game)
        self._display.show()

    def _paste(self, sprite, x: float, y: float):
        """Alpha-composite a sprite onto the frame buffer at integer pixels."""
        if sprite is None:
            return False
        self._display.image.paste(sprite, (int(round(x)), int(round(y))), sprite)
        return True

    def _draw_background(self, game):
        """Flat fill, then sky, then the parallax far layer. None of it collides."""
        w = self._display.width
        h = self._display.height
        fill = self._sprites.background or self._colors.background
        self._display.draw.rectangle((0, 0, w, h), fill=fill)

        self._paste(self._sprites.sky(), 0, 0)

        far = self._sprites.far()
        if far is None:
            return
        offset = (game.scroll_x * self._sprites.far_parallax) % far.width
        x = -offset
        while x < w:
            self._paste(far, x, h - far.height)
            x += far.width

    def _draw_pipes(self, game):
        """Solids slide in from the edge they belong to, then settle.

        The shape is translated, not scaled, so a triangle looks pushed up
        through the floor instead of growing. Offsets are cosmetic: the pipe
        geometry the physics reads is untouched.
        """
        draw = self._display.draw
        h = self._display.height
        color = self._colors.pipe
        cfg = self._cfg.pipes
        for pipe in game.pipes.pipes:
            x0 = pipe.x
            x1 = pipe.x + pipe.width
            mid = pipe.x + pipe.width * 0.5
            ext = pipe.enter_extension(cfg.enter_seconds, cfg.enter_peak)
            # Down for the floor side, up for the ceiling side.
            drop = (1.0 - ext) * pipe.gap_bottom
            lift = (1.0 - ext) * (h - pipe.gap_top)

            if pipe.is_ground and pipe.has_bottom:
                if self._draw_ground(pipe, h, drop):
                    continue
            if pipe.is_ceiling and pipe.has_top:
                if self._draw_ceiling(pipe, h, lift):
                    continue

            tri = pipe.shape == "triangle"
            if pipe.has_bottom and pipe.gap_bottom > 0:
                slot = pipe.bottom_slot or ("tri_bottom" if tri else "rect_bottom")
                top_y = h - pipe.gap_bottom + drop
                if not self._draw_pipe_art(
                    pipe,
                    slot,
                    x0,
                    top_y,
                    int(round(pipe.width)),
                    int(round(pipe.gap_bottom)),
                    pipe.bottom_file,
                    pipe.bottom_frames,
                    getattr(pipe, "bottom_flip", None),
                ):
                    if tri:
                        # World: base on floor, apex at gap_bottom.
                        draw.polygon(
                            [(x0, h + drop), (x1, h + drop), (mid, top_y)], fill=color
                        )
                    else:
                        draw.rectangle((x0, top_y, x1, h + drop), fill=color)

            if pipe.has_top and pipe.gap_top < h:
                slot = pipe.top_slot or ("tri_top" if tri else "rect_top")
                solid_h = h - pipe.gap_top
                if not self._draw_pipe_art(
                    pipe,
                    slot,
                    x0,
                    -lift,
                    int(round(pipe.width)),
                    int(round(solid_h)),
                    pipe.top_file,
                    pipe.top_frames,
                    getattr(pipe, "top_flip", None),
                ):
                    if tri:
                        draw.polygon(
                            [(x0, -lift), (x1, -lift), (mid, solid_h - lift)],
                            fill=color,
                        )
                    else:
                        draw.rectangle((x0, -lift, x1, solid_h - lift), fill=color)

    def _draw_pipe_art(
        self,
        pipe,
        slot: str,
        x0: float,
        top_y: float,
        box_w: int,
        box_h: int,
        filename: str,
        frames,
        flip_y,
    ) -> bool:
        """Paste one obstacle PNG. Flipbook frames keep their own aspect."""
        keep_aspect = bool(frames) and len(frames) > 1
        sprite = self._sprites.obstacle(
            slot,
            box_w,
            box_h,
            filename=self._obstacle_frame(
                filename,
                frames,
                pipe.obstacle_frame_seconds,
                getattr(pipe, "obstacle_anim_phase", 0.0),
            ),
            flip_y=flip_y,
            keep_aspect=keep_aspect,
        )
        if sprite is None:
            return False
        x = x0
        if keep_aspect:
            x = x0 + (pipe.width - sprite.width) * 0.5
        return self._paste(sprite, x, top_y)

    def _obstacle_frame(
        self,
        filename,
        frames,
        seconds: float = 0.0,
        phase: float = 0.0,
    ):
        """Current PNG for a still variant or a two-file obstacle flipbook."""
        name = filename or None
        if not frames or len(frames) < 2:
            return name
        period = seconds if seconds > 0 else 0.37
        idx = int((time.monotonic() + phase) / period) % len(frames)
        return frames[idx]

    def _draw_ground(self, pipe, h: float, drop: float) -> bool:
        """Floor strip: tile like the caterpillar, or one native PNG (mountain)."""
        if self._sprites.slot_native("ground"):
            sprite = self._sprites.native_strip(
                "ground",
                self._obstacle_frame(
                    pipe.bottom_file,
                    getattr(pipe, "bottom_frames", ()),
                    getattr(pipe, "obstacle_frame_seconds", 0.0),
                    getattr(pipe, "obstacle_anim_phase", 0.0),
                ),
                int(round(pipe.width)),
                int(round(pipe.gap_bottom)),
            )
            if sprite is None:
                return False
            top_y = h - sprite.height + drop
            return self._paste(sprite, pipe.x, top_y)
        tile = self._strip_tile("ground", int(round(pipe.gap_bottom)))
        if tile is None:
            return False
        top_y = h - pipe.gap_bottom + drop
        self._tile_strip(tile, pipe.x, pipe.width, top_y)
        return True

    def _draw_ceiling(self, pipe, h: float, lift: float) -> bool:
        """Same tiling as the floor strip, hung from the top edge."""
        if self._sprites.slot_native("ground_top"):
            sprite = self._sprites.native_strip(
                "ground_top",
                self._obstacle_frame(
                    pipe.top_file,
                    getattr(pipe, "top_frames", ()),
                    getattr(pipe, "obstacle_frame_seconds", 0.0),
                    getattr(pipe, "obstacle_anim_phase", 0.0),
                ),
                int(round(pipe.width)),
                int(round(h - pipe.gap_top)),
            )
            if sprite is None:
                return False
            return self._paste(sprite, pipe.x, -lift)
        solid_h = int(round(h - pipe.gap_top))
        tile = self._strip_tile("ground_top", solid_h)
        if tile is None:
            return False
        self._tile_strip(tile, pipe.x, pipe.width, -lift)
        return True

    def _strip_tile(self, slot: str, h: int):
        """Time-based strip frame, same clock for floor and ceiling.

        Loop length is PipeConfig.strip_anim_seconds; each file gets an equal
        share (two frames → 0.2s each). Tiles across one strip stay in step.
        """
        n = self._sprites.strip_frame_count(slot)
        loop = self._cfg.pipes.strip_anim_seconds
        if n <= 0:
            return None
        frame_s = (loop / n) if loop > 0 else 0.0
        frame = int(time.monotonic() / frame_s) if frame_s > 0 else 0
        return self._sprites.strip_tile(slot, h, frame)

    def _tile_strip(self, tile, x: float, width: float, top_y: float):
        end = min(x + width, self._display.width)
        if x < 0:
            x += (-x // tile.width) * tile.width
        while x < end:
            self._paste(tile, x, top_y)
            x += tile.width

    def _draw_floaters(self, game):
        """Banners: two-frame loop plus a small bob. Never collides."""
        cfg = self._cfg.floaters
        period = self._sprites.floater_frame_seconds() or cfg.anim_frame_seconds
        frame = int(time.monotonic() / period) if period > 0 else 0
        h = self._display.height
        for item in game.floaters.items:
            sprite = self._sprites.floater(frame)
            if sprite is None:
                continue
            y = item.draw_y(cfg.bob_pixels, cfg.bob_seconds)
            top = world_to_screen_y(y, h, sprite.height)
            self._paste(sprite, item.x, top)

    def _draw_pickups(self, game):
        """Drawn bigger than the hitbox and centred on it, so it may overlap
        obstacles: a pickup reads as a foreground layer, not part of the wall."""
        draw = self._display.draw
        h = self._display.height
        art = int(round(self._cfg.items.sprite_size))
        period = self._cfg.items.anim_frame_seconds
        frame = int(time.monotonic() / period) if period > 0 else 0
        for item in game.pickups.items:
            top = world_to_screen_y(item.y, h, item.size)
            cx = item.x + item.size / 2.0
            cy = top + item.size / 2.0
            sprite = self._sprites.pickup(item.kind, art, frame)
            # Rotated (expand) tiles are larger than sprite_size; keep the
            # pivot on the hitbox centre either way.
            if sprite is not None and self._paste(
                sprite, cx - sprite.width / 2.0, cy - sprite.height / 2.0
            ):
                continue
            r = art / 2.0
            color = (
                self._colors.pickup_invincible
                if item.kind == "invincible"
                else self._colors.pickup
            )
            draw.polygon(
                [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)],
                fill=color,
                outline=self._colors.bird_outline,
            )

    def _draw_bird(self, game):
        draw = self._display.draw
        h = self._display.height
        bird = game.bird
        fill = self._colors.death if game.is_dying else self._colors.bird
        outline = self._colors.bird_outline
        segments = bird.segments()
        sprite = self._sprites.bird(
            int(round(bird.width)),
            int(round(bird.height)),
            frame=bird.wing_frame,
        )
        if sprite is not None:
            # Paste whole, not per wrap segment, so the art is never sliced.
            # Two segments means the bird straddles an edge, so draw the copy
            # on the far side too and let PIL clip both.
            # Keep each flap PNG's authored size; centre it on the hitbox.
            x = bird.x + (bird.width - sprite.width) / 2.0
            bottom = bird.y + (bird.height - sprite.height) / 2.0
            top = world_to_screen_y(bottom, h, sprite.height)
            offsets = (0, -h, h) if len(segments) > 1 else (0,)
            for dy in offsets:
                self._paste(sprite, x, top + dy)
            return
        for x, y, w, bh in segments:
            top = world_to_screen_y(y, h, bh)
            draw.rectangle(
                (x, top, x + w, top + bh),
                fill=fill,
                outline=outline,
            )

    def _feather(self, x: int, y: int, color: str):
        """Placeholder gem: a small diamond with a dark edge so it pops."""
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
            outline=self._colors.clock_stroke,
        )

    def _draw_clock(self, game):
        """Gem tokens for date / hour / minute / second, top-left."""
        draw = self._display.draw
        font = self._display.font
        hud = self._hud
        x = hud.margin_x
        y = hud.clock_y
        for key, text in clock_display.units_for(game, hud.date_format):
            self._feather(x, y + 1, self._feather_colors[key])
            x += hud.feather_w + hud.feather_text_gap
            draw.text(
                (x, y),
                text,
                font=font,
                fill=self._colors.clock_text,
                stroke_width=1,
                stroke_fill=self._colors.clock_stroke,
            )
            x += self._text_width(text) + hud.group_gap
        self._draw_popups(game, x - hud.group_gap + hud.popup_gap, y)

    def _popup_style(self, progress: float):
        """Gold fade and hop shared by HUD and world "+n"."""
        rise = self._hud.popup_rise * (1.0 - (1.0 - progress) ** 2)
        fill = self._mix_to_bg(self._colors.score_popup, progress)
        stroke = self._mix_to_bg(self._colors.clock_stroke, progress)
        return rise, fill, stroke

    def _mix_to_bg(self, color: str, progress: float):
        base = ImageColor.getrgb(color)
        bg = ImageColor.getrgb(self._colors.background)
        return tuple(int(b + (g - b) * progress) for b, g in zip(base, bg))

    def _draw_popups(self, game, x: int, y: int):
        """Gold "+n" right of the seconds gem: jumps up, then vanishes."""
        popups = game.scores.popups
        if not popups:
            return
        draw = self._display.draw
        font = self._display.font
        for popup in popups:
            rise, fill, stroke = self._popup_style(popup.progress)
            draw.text(
                (x, y - rise),
                popup.text,
                font=font,
                fill=fill,
                stroke_width=1,
                stroke_fill=stroke,
            )

    def _draw_world_popups(self, game):
        """Gold "+n" at the collected pickup, same look as the HUD popup."""
        popups = game.scores.world_popups
        if not popups:
            return
        draw = self._display.draw
        font = self._display.font
        h = self._display.height
        for popup in popups:
            rise, fill, stroke = self._popup_style(popup.progress)
            text = popup.text
            x = popup.x - self._text_width(text) / 2.0
            y = world_to_screen_y(popup.y, h, 0) - rise
            draw.text(
                (x, y),
                text,
                font=font,
                fill=fill,
                stroke_width=1,
                stroke_fill=stroke,
            )

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
            # Flap does nothing in idle, so the button steps scenes instead.
            bottom_text = f"<- {game.scene.label}"
        elif game.waiting_after_death:
            top_text = f"<- return {game.seconds_until_idle:.0f}s"
            bottom_text = "<- retry"
        else:
            return

        draw.text((hud.margin_x, hud.hint_top_y), top_text, font=font, fill=color)
        draw.text((hud.margin_x, hud.hint_bottom_y), bottom_text, font=font, fill=color)
