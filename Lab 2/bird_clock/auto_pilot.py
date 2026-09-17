"""Idle auto-pilot.

Next pipe is a hard constraint. Later pipes only break ties among paths
that already clear the next gap. Aim at the gap wall toward the following
pipe (skim / early turn) instead of the gap center.

Single-sided obstacles use a narrow corridor hugging the solid — not the
entire open half of the screen — so the bird does not climb through tops.
"""

from itertools import product

from .collision import hits_pipe, wrap_y_spans
from .config import AutoPilotConfig, BirdConfig, GameConfig, ScreenConfig
from .pipe import PipeField


class AutoPilot:
    def __init__(self, config: GameConfig):
        self._auto: AutoPilotConfig = config.auto_pilot
        self._bird_cfg: BirdConfig = config.bird
        self._screen: ScreenConfig = config.screen
        self._wrap = config.vertical_wrap

    def should_hold_flap(self, bird, pipes: PipeField, pipe_speed: float) -> bool:
        upcoming = pipes.upcoming(bird.x, limit=self._auto.pipes_ahead)
        if not upcoming or pipe_speed <= 1e-3:
            return self._greedy_target(bird, self._auto.hover_y)

        lo, hi = self._constraint_band(bird, upcoming, pipe_speed)
        target = 0.5 * (lo + hi)
        y_center = bird.y + bird.height / 2.0
        pad = bird.height / 2.0 + self._auto.skim_margin

        # Hard clamp to the aim corridor. The short-horizon search otherwise
        # treats a one-frame flap as free, then climbs through top solids.
        if y_center >= hi - pad:
            return False
        if y_center <= lo + pad:
            return True

        greedy = self._greedy_target(bird, target)
        snapshots = [
            (p.x, p.width, p.gap_bottom, p.gap_top, p.shape, p.has_bottom, p.has_top)
            for p in upcoming
        ]
        n = self._auto.chunks
        chunk_times = [self._auto.sim_dt] + [self._auto.chunk_seconds] * (n - 1)

        best_key = None
        best_hold = greedy
        for pattern in product((False, True), repeat=n):
            key = self._rollout(
                bird.y,
                bird.vy,
                bird.x,
                bird.width,
                bird.height,
                snapshots,
                pipe_speed,
                pattern,
                chunk_times,
            )
            if best_key is None or key > best_key:
                best_key = key
                best_hold = pattern[0]

        if best_key is None or best_key[0] < 2:
            return greedy
        return best_hold

    def _aim_band_pipe(self, pipe, bird_h):
        return pipe.aim_band(self._screen.height, bird_h, self._auto.skim_margin)

    def _constraint_band(self, bird, upcoming, pipe_speed):
        """Intersect the corridors of every obstacle arriving within reaction time.

        A long ground strip alone would allow climbing to mid-screen; the top
        obstacle right behind it allows much less. Only the intersection is safe.
        """
        h = self._screen.height
        need = bird.height + 2.0 * self._auto.skim_margin
        horizon = pipe_speed * self._auto.reaction_seconds
        lo, hi = 0.0, float(h)
        used = False
        for pipe in upcoming:
            if pipe.x - (bird.x + bird.width) > horizon:
                break
            plo, phi = self._aim_band_pipe(pipe, bird.height)
            nlo, nhi = max(lo, plo), min(hi, phi)
            if nhi - nlo < need:
                # Corridors conflict: the nearest obstacle wins.
                break
            lo, hi = nlo, nhi
            used = True
        if not used:
            lo, hi = self._aim_band_pipe(upcoming[0], bird.height)
        return lo, hi

    def _aim_band_snap(self, snap, bird_h):
        _, _, gap_b, gap_t, _, has_b, has_t = snap
        return self._aim_from_flags(gap_b, gap_t, has_b, has_t, bird_h)

    def _aim_from_flags(self, gap_b, gap_t, has_b, has_t, bird_h):
        h = self._screen.height
        margin = self._auto.skim_margin
        pad = bird_h + 2.0 * margin
        corridor = max(48.0, bird_h * 6.0)
        if has_b and has_t:
            return gap_b, gap_t
        if has_b:
            lo = gap_b
            hi = min(h - margin, max(lo + pad + corridor, 72.0))
            return lo, hi
        if has_t:
            hi = gap_t
            floor = max(margin, gap_b)
            lo = max(floor, min(hi - pad - corridor, h - 72.0))
            return lo, hi
        return 0.0, h

    def _skim_aim(self, gap_bottom, gap_top, following, bird_h) -> float:
        """Aim inside this corridor, toward the next corridor center when possible."""
        pad = bird_h / 2.0 + self._auto.skim_margin
        lo = gap_bottom + pad
        hi = gap_top - pad
        if hi < lo:
            return 0.5 * (gap_bottom + gap_top)
        mid = 0.5 * (gap_bottom + gap_top)
        if following is None:
            return mid
        if hasattr(following, "aim_band"):
            flo, fhi = following.aim_band(self._screen.height, bird_h, self._auto.skim_margin)
            nxt = 0.5 * (flo + fhi)
        else:
            nxt = self._band_mid(following, bird_h)
        # Stay inside this corridor; do not hug the far wall past the next gap.
        if nxt < lo:
            return lo
        if nxt > hi:
            return hi
        return nxt

    def _band_mid(self, snap, bird_h) -> float:
        lo, hi = self._aim_band_snap(snap, bird_h)
        return 0.5 * (lo + hi)

    def _follow_tuple(self, pipes, i):
        if i + 1 >= len(pipes):
            return None
        return pipes[i + 1]

    def _greedy_target(self, bird, target_y: float) -> bool:
        # Bang-bang on current center. Ballistic look-ahead overshoots when the
        # target is far below and keeps holding flap into the ceiling.
        y_center = bird.y + bird.height / 2.0
        return y_center < target_y - self._auto.aim_slack

    def _rollout(self, y, vy, bird_x, bw, bh, pipes, pipe_speed, pattern, chunk_times):
        dt = self._auto.sim_dt
        n_pipes = len(pipes)
        cleared = [None] * n_pipes
        err = [1.0e9] * n_pipes
        t = 0.0

        for hold, chunk_t in zip(pattern, chunk_times):
            remaining = chunk_t
            while remaining > 1e-6:
                step = min(dt, remaining)
                y, vy = self._integrate(y, vy, hold, step)
                t += step
                remaining -= step
                cy = y + bh / 2.0
                for i, snap in enumerate(pipes):
                    x, width, gap_b, gap_t, shape, has_b, has_t = snap
                    x_now = x - pipe_speed * t
                    if not self._overlaps_x(bird_x, bw, x_now, width):
                        continue
                    if self._hits_pipe(y, bird_x, bw, bh, x_now, width, gap_b, gap_t, shape, has_b, has_t):
                        cleared[i] = False
                    elif cleared[i] is not False:
                        cleared[i] = True
                        follow = self._follow_tuple(pipes, i)
                        lo, hi = self._aim_from_flags(gap_b, gap_t, has_b, has_t, bh)
                        aim = self._skim_aim(lo, hi, follow, bh)
                        err[i] = min(err[i], (cy - aim) ** 2)

        keys = []
        for i in range(n_pipes):
            keys.extend(self._pipe_key(cleared[i], err[i]))
        keys.append(-self._auto.exit_speed_weight * (vy ** 2))
        return tuple(keys)

    def _pipe_key(self, cleared, err):
        if cleared is True:
            survive = 2
        elif cleared is None:
            survive = 1
        else:
            survive = 0
        return (survive, -err)

    def _integrate(self, y, vy, hold, dt):
        accel = self._bird_cfg.flap_accel if hold else self._bird_cfg.gravity
        vy += accel * dt
        vy = max(self._bird_cfg.max_down_speed, min(self._bird_cfg.max_up_speed, vy))
        y += vy * dt
        if self._wrap:
            h = self._screen.height
            y %= h
            if y < 0:
                y += h
        return y, vy

    def _overlaps_x(self, bird_x, bw, pipe_x, pipe_w) -> bool:
        return not (bird_x + bw < pipe_x or bird_x > pipe_x + pipe_w)

    def _hits_pipe(self, y, bird_x, bw, bh, pipe_x, pipe_w, gap_b, gap_t, shape, has_b, has_t) -> bool:
        h = self._screen.height
        for bottom, top in wrap_y_spans(y, bh, h, self._wrap):
            box = (bird_x, bottom, bird_x + bw, top)
            if hits_pipe(box, pipe_x, pipe_w, gap_b, gap_t, h, shape, has_b, has_t):
                return True
        return False
