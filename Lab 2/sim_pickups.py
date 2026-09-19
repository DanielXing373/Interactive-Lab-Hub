"""Headless checks for pickups.

Rules under test:
  - idle still spawns pickups for look, but eating one must not jump score
    or the wall-clock HUD
  - play spawns them reachable (inside the corridor of every obstacle in
    their column) and eating one adds score
"""

import sys

from bird_clock.config import GameConfig
from bird_clock.game import Game

DT = 1.0 / 30.0


def _instrument(game):
    """Count spawns and eats separately; item count alone hides the difference."""
    counts = {"spawned": 0, "eaten": 0}
    real_spawn = game.pickups._spawn
    real_take = game.pickups.take

    def spawn(pipes):
        before = len(game.pickups.items)
        real_spawn(pipes)
        counts["spawned"] += len(game.pickups.items) - before

    def take(bird):
        taken = real_take(bird)
        counts["eaten"] += len(taken)
        return taken

    game.pickups._spawn = spawn
    game.pickups.take = take
    return counts


def _unreachable(game):
    """Live pickups sitting inside an obstacle's solid, which must never happen."""
    bad = 0
    for item in game.pickups.items:
        x0, x1 = item.x, item.x + item.size
        for p in game.pipes.pipes:
            if p.x + p.width < x0 or p.x > x1:
                continue
            lo, hi = p.safe_band(game.config.screen.height)
            if item.y < lo or item.y + item.size > hi:
                bad += 1
    return bad


def run_idle(seconds=300.0):
    game = Game(GameConfig())
    counts = _instrument(game)
    deaths = 0
    max_alive = 0
    clock_jumps = 0
    play_score_moved = 0
    step = game.config.score.points_per_second

    for _ in range(int(seconds / DT)):
        before = game.scores.idle_score
        before_play = game.scores.current_score
        game.update(DT)
        # The idle number may only advance one tick; a bonus would jump it.
        if game.scores.idle_score - before > step:
            clock_jumps += 1
        if game.scores.current_score != before_play:
            play_score_moved += 1
        max_alive = max(max_alive, len(game.pickups.items))
        if game.is_dying:
            deaths += 1
            break

    return dict(
        spawned=counts["spawned"], eaten=counts["eaten"],
        max_alive=max_alive, deaths=deaths, clock_jumps=clock_jumps,
        play_score_moved=play_score_moved,
    )


def run_play(seconds=120.0):
    """Play mode, flap button held in bursts: pickups must add score."""
    game = Game(GameConfig())
    game.enter_play()
    counts = _instrument(game)
    bonus = 0
    unreachable = 0
    for i in range(int(seconds / DT)):
        game.handle_input(False, False, (i // 12) % 2 == 0)
        before = game.scores.current_score
        eaten_before = counts["eaten"]
        game.update(DT)
        if counts["eaten"] > eaten_before:
            bonus += game.scores.current_score - before
        unreachable += _unreachable(game)
        if game.is_dying:
            game.enter_play()
    return dict(
        spawned=counts["spawned"], eaten=counts["eaten"],
        score_from_pickups=bonus, unreachable=unreachable,
    )


def run_idle_after_play(seconds=20.0):
    """Play pickups must clear on entering idle; idle may then spawn its own."""
    game = Game(GameConfig())
    game.enter_play()
    for i in range(int(60.0 / DT)):
        game.handle_input(False, False, (i // 12) % 2 == 0)
        game.update(DT)
        if game.pickups.items and game.in_play:
            break
    carried = len(game.pickups.items)
    game.enter_idle()
    leftover_at_enter = len(game.pickups.items)
    spawned_in_idle = 0
    for _ in range(int(seconds / DT)):
        game.update(DT)
        spawned_in_idle = max(spawned_in_idle, len(game.pickups.items))
    return dict(
        on_screen_at_death=carried,
        leftover_at_enter=leftover_at_enter,
        spawned_in_idle=spawned_in_idle,
    )


def audit_entrance(seconds=300.0):
    """The stab must finish well before an obstacle can reach the bird.

    Collision uses the final shape, so an obstacle still animating at the
    bird's column would hit a hitbox that is not the one being drawn.
    """
    cfg = GameConfig()
    game = Game(cfg)
    game.enter_play()
    nose = cfg.bird.x + cfg.bird.width
    unsettled = 0
    min_margin = None
    for i in range(int(seconds / DT)):
        game.handle_input(False, False, (i // 12) % 2 == 0)
        game.update(DT)
        if game.is_dying:
            game.enter_play()
            continue
        for p in game.pipes.pipes:
            if not p.animates_entrance:
                continue
            ext = p.enter_extension(cfg.pipes.enter_seconds, cfg.pipes.enter_peak)
            if ext < 1.0:
                # How much room was left when it was still moving.
                margin = (p.x + p.width) - nose
                if margin <= 0:
                    unsettled += 1
                if min_margin is None or margin < min_margin:
                    min_margin = margin
    return dict(reached_bird_while_animating=unsettled, min_px_margin=min_margin)


def audit_spawn_placement(trials=4000):
    """Exercise the placement math directly across many obstacle layouts."""
    from bird_clock.items import PickupField
    from bird_clock.pipe import PipeField

    cfg = GameConfig()
    bad = placed = blocked = 0
    for _ in range(trials):
        pipes = PipeField(cfg)
        for _ in range(3):
            pipes.spawn(idle=False, speed=cfg.pipes.play_start_speed)
            for p in pipes.pipes:
                p.x -= 8.0
        field = PickupField(cfg)
        field._spawn(pipes)
        if not field.items:
            blocked += 1
            continue
        item = field.items[-1]
        placed += 1
        x0, x1 = item.x, item.x + item.size
        for p in pipes.pipes:
            if p.x + p.width < x0 or p.x > x1:
                continue
            lo, hi = p.safe_band(cfg.screen.height)
            if item.y < lo or item.y + item.size > hi:
                bad += 1
    return dict(placed=placed, blocked=blocked, bad_placements=bad)


if __name__ == "__main__":
    idle = run_idle()
    play = run_play()
    carry = run_idle_after_play()
    place = audit_spawn_placement()
    enter = audit_entrance()
    print("idle 300s   ", idle)
    print("play 120s   ", play)
    print("death carry ", carry)
    print("placement   ", place)
    print("entrance    ", enter)

    failures = []
    if not idle["spawned"] and not idle["max_alive"]:
        failures.append("no pickups spawned in idle")
    if idle["clock_jumps"]:
        failures.append("idle clock jumped")
    if idle["play_score_moved"]:
        failures.append("idle pickup changed play score")
    if idle["deaths"]:
        failures.append("auto-pilot died")
    if play["unreachable"] or place["bad_placements"]:
        failures.append("pickup placed inside an obstacle")
    if play["eaten"] and not play["score_from_pickups"]:
        failures.append("eating a pickup gave no score")
    if carry["leftover_at_enter"]:
        failures.append("play pickups survived into idle")
    if enter["reached_bird_while_animating"]:
        failures.append("obstacle still animating at the bird: lower enter_seconds")
    print("FAIL: " + "; ".join(failures) if failures else "all checks passed")
    sys.exit(1 if failures else 0)
