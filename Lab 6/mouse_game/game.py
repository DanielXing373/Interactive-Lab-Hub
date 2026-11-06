"""Mouse Game rules engine.

Pure Python with no I/O: the caller supplies every timestamp, so the same code
runs under the host's monotonic clock and under the unit tests' fake clock.
"""

import random
import uuid

import config

EPS = 1e-9

READY = "ready"
PLAYING = "playing"
FINISHED = "finished"

CRAVE = "crave"
RETREAT = "retreat"

DIRECTIONS = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}


class Mouse:
    def __init__(self, hole, now, boss=False):
        self.hole = hole
        self.boss = boss
        self.max_hp = config.BOSS_HP if boss else 1
        self.hp = self.max_hp
        self.stage = CRAVE
        self.stage_start = now
        self.stage_end = now + (config.BOSS_CRAVE_SECONDS if boss else config.CRAVE_SECONDS)
        self.stunned = False
        self.frozen_progress = None

    @property
    def retreat_seconds(self):
        return config.BOSS_RETREAT_SECONDS if self.boss else config.RETREAT_SECONDS

    @property
    def carrying(self):
        return self.stage == RETREAT

    def progress(self, now):
        if self.frozen_progress is not None:
            return self.frozen_progress
        span = self.stage_end - self.stage_start
        return max(0.0, min(1.0, (now - self.stage_start) / span))


class Game:
    def __init__(self, rng=None, on_finish=None):
        self.rng = rng or random.Random()
        self.on_finish = on_finish
        self.phase = READY
        self.round_id = None
        self.clock = 0.0
        self.effects = []
        self.last_result = None
        self._reset_round_values(0.0)

    def _reset_round_values(self, now):
        self.start_time = now
        self.end_time = None
        self.score = 0
        self.combo = 0
        self.best_combo = 0
        # Drives the hit sound only: +1 per hit, 0 whenever the combo breaks or a round starts.
        self.hit_streak = 0
        self.cheese = config.START_CHEESE
        self.crosshair = (config.ROWS // 2, config.COLS // 2)
        self.brightness = 100
        self.mice = {}
        self.stun_until = None
        self.stun_started = None
        self.stun_ready_at = now
        self.spawn_ref = now
        self.next_boss_at = now + self._boss_gap()

    def _boss_gap(self):
        return self.rng.uniform(config.BOSS_INTERVAL - config.BOSS_JITTER,
                                config.BOSS_INTERVAL + config.BOSS_JITTER)

    @property
    def light(self):
        return self.brightness >= config.LIGHT_ON_THRESHOLD

    @property
    def next_spawn_at(self):
        if self.spawn_ref is None:
            return None
        return self.spawn_ref + self._spawn_interval()

    # ------------------------------------------------------------------ rounds

    def start(self, now):
        if self.phase == PLAYING:
            return False
        self.clock = max(self.clock, now)
        self._reset_round_values(self.clock)
        self.round_id = uuid.uuid4().hex
        self.phase = PLAYING
        self.last_result = None
        self.effects.append({"type": "round_start"})
        return True

    def _finish(self, t):
        self.phase = FINISHED
        self.end_time = t
        self.stun_until = None
        self.spawn_ref = None
        self.next_boss_at = None
        self.last_result = {
            "round_id": self.round_id,
            "score": self.score,
            "cheese": self.cheese,
            "elapsed": round(min(t - self.start_time, config.ROUND_SECONDS), 2),
            "best_combo": self.best_combo,
        }
        self.effects.append({"type": "round_end", "won": self.cheese > 0, **self.last_result})
        if self.on_finish:
            self.on_finish(dict(self.last_result))

    # ------------------------------------------------------------------ timers

    def _spawn_interval(self):
        level = self.brightness / 100.0
        return config.SPAWN_DARK + (config.SPAWN_LIT - config.SPAWN_DARK) * level

    def _next_deadlines(self):
        """Earliest pending deadline per category, in tie-break priority order."""
        mouse_due = [m.stage_end for m in self.mice.values() if not m.stunned]
        boss_due = self.next_boss_at
        if boss_due is not None and self.stun_until is not None:
            boss_due = max(boss_due, self.stun_until)   # no spawns while stunned
        return [
            ("round", self.start_time + config.ROUND_SECONDS),
            ("stun", self.stun_until),
            ("mouse", min(mouse_due) if mouse_due else None),
            ("spawn", self.next_spawn_at),
            ("boss", boss_due),
        ]

    def advance(self, now):
        """Resolve every deadline up to and including `now`."""
        while self.phase == PLAYING:
            deadlines = [(kind, t) for kind, t in self._next_deadlines() if t is not None]
            t = min(t for _, t in deadlines)
            if t > now + EPS:
                break
            kind = next(k for k, dt in deadlines if abs(dt - t) <= EPS)
            self.clock = max(self.clock, t)
            if kind == "round":
                self._finish(t)
            elif kind == "stun":
                self._end_stun(t)
            elif kind == "mouse":
                self._advance_mice(t)
            elif kind == "spawn":
                self._spawn(t)
            else:
                self._spawn_boss(t)
        self.clock = max(self.clock, now)

    def _advance_mice(self, t):
        escaped = []
        for mouse in list(self.mice.values()):
            if mouse.stunned or abs(mouse.stage_end - t) > EPS:
                continue
            if mouse.stage == CRAVE:
                mouse.stage = RETREAT
                mouse.stage_start = t
                mouse.stage_end = t + mouse.retreat_seconds
                self.effects.append({"type": "grab", "hole": list(mouse.hole)})
            else:
                escaped.append(mouse)
        for mouse in escaped:
            del self.mice[mouse.hole]
            self.cheese = max(0, self.cheese - 1)
            self.effects.append({"type": "escape", "hole": list(mouse.hole)})
        if escaped:
            self._break_combo("cheese")
        if escaped and self.cheese <= 0:
            self._finish(t)

    def _spawn(self, t):
        empty = [(r, c) for r in range(config.ROWS) for c in range(config.COLS)
                 if (r, c) not in self.mice]
        if empty:
            hole = self.rng.choice(empty)
            self.mice[hole] = Mouse(hole, t)
            self.effects.append({"type": "spawn", "hole": list(hole)})
        self.spawn_ref = t

    def _spawn_boss(self, t):
        empty = [(r, c) for r in range(config.ROWS) for c in range(config.COLS)
                 if (r, c) not in self.mice]
        if not empty or any(m.boss for m in self.mice.values()):
            self.next_boss_at = t + 1.0
            return
        hole = self.rng.choice(empty)
        self.mice[hole] = Mouse(hole, t, boss=True)
        self.effects.append({"type": "spawn", "hole": list(hole), "boss": True})
        self.next_boss_at = t + self._boss_gap()

    def _start_stun(self, t):
        self.stun_until = t + config.STUN_SECONDS
        self.stun_started = t
        self.stun_ready_at = t + config.STUN_COOLDOWN
        self.spawn_ref = None
        for mouse in self.mice.values():
            mouse.frozen_progress = mouse.progress(t)
            mouse.stunned = True
        self.effects.append({"type": "stun_start",
                             "holes": [list(h) for h in self.mice]})

    def _end_stun(self, t):
        """Stun only pauses: every frozen mouse resumes where its bar stopped."""
        paused = t - self.stun_started
        self.stun_until = None
        self.stun_started = None
        stunned = [m for m in self.mice.values() if m.stunned]
        for mouse in stunned:
            mouse.stage_start += paused
            mouse.stage_end += paused
            mouse.stunned = False
            mouse.frozen_progress = None
        self.effects.append({"type": "stun_end", "holes": [list(m.hole) for m in stunned]})
        self.spawn_ref = t

    # ------------------------------------------------------------------ inputs

    @property
    def multiplier(self):
        return max(mult for need, mult in config.COMBO_TIERS if self.combo >= need)

    def _bump_combo(self):
        self.combo += 1
        self.best_combo = max(self.best_combo, self.combo)

    def _break_combo(self, reason, role=None):
        if self.combo:
            self.effects.append({"type": "combo_break", "reason": reason,
                                 "combo": self.combo, "role": role})
        self.combo = 0
        self.hit_streak = 0

    def handle(self, kind, value, now, online=False):
        """Apply one player input received at host time `now`.

        `online` marks inputs from a connected Pi; only those build the combo.
        """
        if self.phase != PLAYING:
            return False
        self.advance(now)
        if self.phase != PLAYING:
            return False
        t = self.clock
        if kind == "aim":
            dr, dc = DIRECTIONS[value]
            r, c = self.crosshair
            self.crosshair = (min(max(r + dr, 0), config.ROWS - 1),
                              min(max(c + dc, 0), config.COLS - 1))
            if online:
                self._bump_combo()
        elif kind == "attack":
            hole = self.crosshair
            # Swings count toward the combo from any source; aim and light only from Pis.
            if hole in self.mice:
                mouse = self.mice[hole]
                mouse.hp -= 1
                if mouse.hp <= 0:
                    del self.mice[hole]
                self._bump_combo()
                self.hit_streak += 1
                points = self.multiplier
                self.score = round(self.score + points, 1)
                self.effects.append({"type": "hit", "hole": list(hole), "points": points,
                                     "combo": self.combo, "streak": self.hit_streak,
                                     "boss": mouse.boss, "hp": mouse.hp,
                                     "killed": mouse.hp <= 0})
            else:
                self.effects.append({"type": "miss", "hole": list(hole)})
                self._break_combo("miss")
        elif kind == "light":
            crossed = self._set_brightness(value, t)
            if online and crossed:
                self._bump_combo()
        else:
            return False
        return True

    def pi_offline(self, role, now):
        """A Pi dropped off MQTT: counts as a miss and resets the combo."""
        if self.phase != PLAYING:
            return False
        self.advance(now)
        if self.phase != PLAYING:
            return False
        self.effects.append({"type": "pi_offline", "role": role})
        self._break_combo("offline", role)
        return True

    def _set_brightness(self, level, t):
        """Returns True when the change crosses the light on/off threshold."""
        level = int(round(min(max(level, 0), 100)))
        if level == self.brightness:
            return False
        was_lit = self.light
        self.brightness = level
        self.effects.append({"type": "light", "brightness": level, "on": self.light})
        if self.stun_until is None and self.spawn_ref is not None:
            if self.light != was_lit:
                self.spawn_ref = t
            elif self.spawn_ref + self._spawn_interval() < t:
                # A shorter interval that is already overdue spawns now, not in the past.
                self.spawn_ref = t - self._spawn_interval()
        if self.light and not was_lit and self.stun_until is None \
                and t + EPS >= self.stun_ready_at:
            self._start_stun(t)
        return self.light != was_lit

    # ------------------------------------------------------------------ output

    def snapshot(self):
        now = self.clock
        if self.phase == PLAYING:
            remaining = max(0.0, self.start_time + config.ROUND_SECONDS - now)
        elif self.phase == FINISHED:
            remaining = max(0.0, self.start_time + config.ROUND_SECONDS - self.end_time)
        else:
            remaining = config.ROUND_SECONDS
        cooldown = 0.0
        if self.phase == PLAYING:
            cooldown = max(0.0, self.stun_ready_at - now)
        return {
            "phase": self.phase,
            "round_id": self.round_id,
            "rows": config.ROWS,
            "cols": config.COLS,
            "time_remaining": round(remaining, 2),
            "score": self.score,
            "combo": self.combo,
            "best_combo": self.best_combo,
            "hit_streak": self.hit_streak,
            "multiplier": self.multiplier,
            "round_seconds": config.ROUND_SECONDS,
            "cheese": self.cheese,
            "start_cheese": config.START_CHEESE,
            "crosshair": list(self.crosshair),
            "light": self.light,
            "brightness": self.brightness,
            "spawn_interval": round(self._spawn_interval(), 2),
            "stun_active": self.stun_until is not None,
            "stun_cooldown": round(cooldown, 2),
            "stun_ready": self.phase == PLAYING and self.stun_until is None and cooldown <= 0,
            "mice": [
                {
                    "hole": list(m.hole),
                    "stage": m.stage,
                    "carrying": m.carrying,
                    "progress": round(m.progress(now), 3),
                    "stunned": m.stunned,
                    "boss": m.boss,
                    "hp": m.hp,
                    "max_hp": m.max_hp,
                }
                for m in self.mice.values()
            ],
            "result": self.last_result,
        }

    def drain_effects(self):
        effects, self.effects = self.effects, []
        return effects
