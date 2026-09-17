"""Game modes: idle auto-fly, play, death, then retry or back to idle."""

from enum import Enum, auto

from .auto_pilot import AutoPilot
from .bird import Bird
from .config import GameConfig
from .items import PickupField
from .pipe import PipeField
from .score import ScoreBoard


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
        self._pilot = AutoPilot(config)
        self.mode = Mode.IDLE
        self._play_elapsed = 0.0
        self._after_death_timer = 0.0
        self._invincible_left = 0.0
        self._flap_held = False
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

    def add_bonus_score(self, amount: int):
        self.scores.add_bonus(amount)

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
        if self.mode == Mode.IDLE and start_pressed:
            self.enter_play()
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

        if self.mode == Mode.IDLE:
            # No pickups here on purpose: the idle number is the wall clock,
            # and bonus score would make the displayed time a lie.
            self.scores.tick_idle(dt)
            flap_held = self._pilot.should_hold_flap(
                self.bird, self.pipes, self.pipe_speed()
            )
            self.bird.update(dt, flap_held=flap_held, dying=False)
            self.pipes.update(dt, self.pipe_speed(), idle=True)
            return

        if self.mode == Mode.PLAY:
            self.scores.tick_play(dt)
            self._play_elapsed += dt
            self._tick_invincibility(dt)
            self.bird.update(dt, flap_held=flap_held, dying=False)
            self.pipes.update(dt, self.pipe_speed(), idle=False)
            self.pickups.update(dt, self.pipe_speed(), pipes=self.pipes)
            for pickup in self.pickups.take(self.bird):
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
