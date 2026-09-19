"""Game modes: idle auto-fly, play, death, then retry or back to idle."""

from enum import Enum, auto

from .auto_pilot import AutoPilot
from .bird import Bird
from .config import GameConfig
from .items import COIN, PickupField
from .pipe import PipeField
from .score import ScoreBoard
from .scenes import SceneBook


class Mode(Enum):
    IDLE = auto()
    PLAY = auto()
    DYING = auto()
    AFTER_DEATH = auto()


class Game:
    def __init__(self, config: GameConfig):
        self.config = config
        self.bird = Bird(config)
        self.pipes = PipeField(config)
        self.pickups = PickupField(config)
        self.scores = ScoreBoard(config)
        self.scene_book = SceneBook(config)
        self.pipes.set_pool(self.scene_book.current)
        self._pilot = AutoPilot(config)
        self.mode = Mode.IDLE
        self._play_elapsed = 0.0
        self._after_death_timer = 0.0
        self._invincible_left = 0.0
        self._flap_held = False
        # Total distance scrolled, for parallax layers.
        self.scroll_x = 0.0
        self.enter_idle()

    @property
    def in_idle(self) -> bool:
        return self.mode == Mode.IDLE

    @property
    def in_play(self) -> bool:
        return self.mode == Mode.PLAY

    @property
    def is_dying(self) -> bool:
        return self.mode in (Mode.DYING, Mode.AFTER_DEATH)

    @property
    def waiting_after_death(self) -> bool:
        return self.mode == Mode.AFTER_DEATH

    @property
    def seconds_until_idle(self) -> float:
        """Countdown shown next to the return hint. 0 outside AFTER_DEATH."""
        if self.mode != Mode.AFTER_DEATH:
            return 0.0
        return max(0.0, self._after_death_timer)

    def pipe_speed(self) -> float:
        pipes = self.config.pipes
        if self.mode == Mode.IDLE:
            return pipes.idle_speed
        if self.mode == Mode.PLAY:
            sped = pipes.play_start_speed + pipes.play_speed_gain * self._play_elapsed
            return min(pipes.play_max_speed, sped)
        return pipes.play_start_speed

    def enter_idle(self):
        self.mode = Mode.IDLE
        self.bird.reset()
        self.bird.set_collision_enabled(False)
        self.pipes.clear()
        self.pickups.clear()
        self.scores.clear_world_popups()
        self._play_elapsed = 0.0
        self._invincible_left = 0.0

    def enter_play(self):
        self.mode = Mode.PLAY
        self.bird.reset()
        self.bird.set_collision_enabled(True)
        self.pipes.clear()
        self.pickups.clear()
        self.scores.reset_play()
        self._play_elapsed = 0.0
        self._invincible_left = 0.0

    @property
    def scene(self):
        return self.scene_book.current

    def next_scene(self):
        """Cheat button. Clears the field so the new pool takes effect at once."""
        scene = self.scene_book.next()
        self.pipes.set_pool(scene)
        self.pipes.clear()
        self.pickups.clear()
        return scene

    def add_bonus_score(self, amount: int, spawn_hud_popup: bool = True):
        self.scores.add_bonus(amount, spawn_hud_popup=spawn_hud_popup)

    def spawn_collect_popup(self, pickup):
        """World-space "+n" at the pickup. Idle and play both show it."""
        if pickup.kind != COIN:
            return
        x = pickup.x + pickup.size * 0.5
        y = pickup.y + pickup.size
        self.scores.add_world_popup(self.config.items.coin_score, x, y)

    def grant_invincibility(self, seconds: float):
        """Reserved. Turns the bird hitbox off for a while."""
        if seconds <= 0:
            return
        self._invincible_left = max(self._invincible_left, seconds)
        self.bird.set_collision_enabled(False)

    def _tick_invincibility(self, dt: float):
        if self._invincible_left <= 0:
            return
        self._invincible_left -= dt
        if self._invincible_left <= 0:
            self._invincible_left = 0.0
            if self.mode == Mode.PLAY:
                self.bird.set_collision_enabled(True)

    def handle_input(self, start_pressed: bool, flap_pressed: bool, flap_held: bool):
        self._flap_held = flap_held
        if self.mode == Mode.IDLE:
            if start_pressed:
                self.enter_play()
            elif flap_pressed:
                # Idle has no use for flap (the auto-pilot flies), so it is
                # the free button: step through scenes for previewing/filming.
                self.next_scene()
            return
        if self.mode == Mode.AFTER_DEATH:
            # After death the buttons swap: A returns to idle, B retries.
            if flap_pressed:
                self.enter_play()
            elif start_pressed:
                self.enter_idle()
            return

    def update(self, dt: float):
        flap_held = self._flap_held
        self.scores.update(dt)
        if self.mode in (Mode.IDLE, Mode.PLAY):
            self.scroll_x += self.pipe_speed() * dt

        if self.mode == Mode.IDLE:
            # Pickups spawn for spectacle. Collecting them must not touch
            # score (the HUD is the wall clock) but still shows a world "+n".
            self.scores.tick_idle(dt)
            flap_held = self._pilot.should_hold_flap(
                self.bird, self.pipes, self.pipe_speed()
            )
            self.bird.update(dt, flap_held=flap_held, dying=False)
            self.pipes.update(dt, self.pipe_speed(), idle=True)
            self.pickups.update(dt, self.pipe_speed(), pipes=self.pipes)
            for pickup in self.pickups.take(self.bird):
                self.spawn_collect_popup(pickup)
            return

        if self.mode == Mode.PLAY:
            self.scores.tick_play(dt)
            self._play_elapsed += dt
            self._tick_invincibility(dt)
            self.bird.update(dt, flap_held=flap_held, dying=False)
            self.pipes.update(dt, self.pipe_speed(), idle=False)
            self.pickups.update(dt, self.pipe_speed(), pipes=self.pipes)
            for pickup in self.pickups.take(self.bird):
                self.spawn_collect_popup(pickup)
                pickup.apply(self)
            if self.config.bounds_kill and self.bird.is_off_screen():
                self._begin_death()
                return
            if self.pipes.hits(self.bird):
                self._begin_death()
            return

        if self.mode == Mode.DYING:
            self.bird.update(dt, flap_held=False, dying=True)
            if self.bird.is_off_screen():
                self.mode = Mode.AFTER_DEATH
                self._after_death_timer = self.config.death.wait_before_idle_seconds
            return

        if self.mode == Mode.AFTER_DEATH:
            self._after_death_timer -= dt
            if self._after_death_timer <= 0:
                self.enter_idle()

    def _begin_death(self):
        self.scores.lock_best_from_current()
        self.mode = Mode.DYING
        self.bird.set_collision_enabled(False)
        self.bird.set_wrap_enabled(False)
        self.bird.vy = min(self.bird.vy, 0.0)
