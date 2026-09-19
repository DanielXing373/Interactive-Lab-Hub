"""Every scene is its own spawn pool, so the auto-pilot has to survive each.

A pool that only rolls hanging obstacles, or only ground strips, produces
corridors the pilot never sees in the mixed greybox pool.
"""

import sys

from bird_clock.config import GameConfig
from bird_clock.game import Game
from bird_clock import scenes

DT = 1.0 / 30.0


def idle_run(scene, seconds=240.0):
    cfg = GameConfig()
    game = Game(cfg)
    game.scene_book.select(scene.key)
    game.pipes.set_pool(scene)
    game.pipes.clear()
    deaths = 0
    seen = set()
    for _ in range(int(seconds / DT)):
        game.update(DT)
        for p in game.pipes.pipes:
            seen.add(p.kind or (
                "ground" if p.is_ground else (p.shape, p.has_bottom, p.has_top)
            ))
        if game.is_dying:
            deaths += 1
            game.enter_idle()
            game.pipes.set_pool(scene)
    kinds = sorted({k for k in seen if k})
    return deaths, kinds


def play_run(scene, seconds=120.0):
    cfg = GameConfig()
    game = Game(cfg)
    game.scene_book.select(scene.key)
    game.pipes.set_pool(scene)
    game.enter_play()
    game.pipes.set_pool(scene)
    eaten = spawned = 0
    real_take = game.pickups.take
    real_spawn = game.pickups._spawn

    def take(bird):
        nonlocal eaten
        t = real_take(bird)
        eaten += len(t)
        return t

    def spawn(pipes):
        nonlocal spawned
        n = len(game.pickups.items)
        real_spawn(pipes)
        spawned += len(game.pickups.items) - n

    game.pickups.take = take
    game.pickups._spawn = spawn
    for i in range(int(seconds / DT)):
        game.handle_input(False, False, (i // 12) % 2 == 0)
        game.update(DT)
        if game.is_dying:
            game.enter_play()
            game.pipes.set_pool(scene)
    return spawned, eaten


if __name__ == "__main__":
    print(f"{'scene':<18}{'idle deaths':>12}  {'pickups':>9}  kinds rolled")
    bad = []
    for scene in scenes.DEFAULT_SCENES:
        deaths, kinds = idle_run(scene)
        spawned, eaten = play_run(scene)
        declared = {k for k, w in scene.weights.items() if w > 0}
        flag = ""
        if deaths:
            bad.append(f"{scene.key}: {deaths} idle deaths")
            flag = "  <-- DIES"
        if spawned == 0:
            bad.append(f"{scene.key}: no pickups spawned")
            flag += "  <-- NO PICKUPS"
        # The whole point of the pool: never show a shape nobody drew.
        undeclared = set(kinds) - declared
        if undeclared:
            bad.append(f"{scene.key}: spawned undeclared {sorted(undeclared)}")
            flag += f"  <-- UNDECLARED {sorted(undeclared)}"
        print(f"{scene.key:<18}{deaths:>12}  {spawned:>4}/{eaten:<4}  "
              f"{','.join(kinds)}{flag}")
    print("FAIL: " + "; ".join(bad) if bad else "every scene survives")
    sys.exit(1 if bad else 0)
