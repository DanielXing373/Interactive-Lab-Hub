"""Player / auto-pilot bird. Physics live here; drawing does not."""

from .collision import wrap_y_spans
from .config import BirdConfig, GameConfig


class Bird:
    def __init__(self, config: GameConfig):
        self._cfg: BirdConfig = config.bird
        self._wrap_allowed = config.vertical_wrap
        self._wrap = config.vertical_wrap
        self._screen_h = config.screen.height
        self.x = self._cfg.x
        self.y = self._cfg.start_y
        self.vy = 0.0
        self.collision_enabled = True
        self.width = self._cfg.width
        self.height = self._cfg.height

    def set_wrap_enabled(self, enabled: bool):
        self._wrap = bool(enabled) and self._wrap_allowed

    def reset(self, y=None):
        self.x = self._cfg.x
        self.y = self._cfg.start_y if y is None else y
        self.vy = 0.0
        self.collision_enabled = True
        self.set_wrap_enabled(True)

    def set_collision_enabled(self, enabled: bool):
        """Item / idle hook: turn hitbox on or off without touching physics."""
        self.collision_enabled = enabled

    def update(self, dt: float, flap_held: bool, dying: bool = False):
        if dying:
            self.vy += self._cfg.death_gravity * dt
            self.y += self.vy * dt
            return

        accel = self._cfg.flap_accel if flap_held else self._cfg.gravity
        self.vy += accel * dt
        self.vy = max(self._cfg.max_down_speed, min(self._cfg.max_up_speed, self.vy))
        self.y += self.vy * dt

        if self._wrap:
            self.y %= self._screen_h
            if self.y < 0:
                self.y += self._screen_h

    def segments(self):
        """World rectangles actually drawn. No wrap while falling off-screen."""
        spans = wrap_y_spans(self.y, self.height, self._screen_h, self._wrap)
        return [(self.x, bottom, self.width, top - bottom) for bottom, top in spans]

    def hitboxes(self):
        """Axis-aligned boxes (left, bottom, right, top) matching what is drawn."""
        return [(x, y, x + w, y + h) for x, y, w, h in self.segments()]

    @property
    def hitbox(self):
        return self.hitboxes()[0]

    def is_off_screen(self) -> bool:
        return self.y + self.height < 0 or self.y > self._screen_h
