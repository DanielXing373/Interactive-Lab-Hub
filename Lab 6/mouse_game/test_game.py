"""Acceptance cases from MOUSE_GAME.md, run with a fake clock.

    python -m unittest test_game -v
"""

import os
import random
import tempfile
import unittest

import config
from controllers import BrightnessFilter, JoystickStepper, ProximitySwing, openness_from_ratios
from game import FINISHED, PLAYING, RETREAT, Game, Mouse
from leaderboard import Leaderboard


class GameTestCase(unittest.TestCase):
    def setUp(self):
        self._saved = (config.SPAWN_LIT, config.SPAWN_DARK, config.BOSS_INTERVAL)
        # Keep random spawns out of the way; tests place mice explicitly.
        config.SPAWN_LIT = config.SPAWN_DARK = config.BOSS_INTERVAL = 1000.0
        self.tmp = tempfile.TemporaryDirectory()
        self.board = Leaderboard(os.path.join(self.tmp.name, "lb.json"))
        self.game = Game(rng=random.Random(1), on_finish=self.board.add)
        self.game.start(0.0)

    def tearDown(self):
        config.SPAWN_LIT, config.SPAWN_DARK, config.BOSS_INTERVAL = self._saved
        self.tmp.cleanup()

    def place(self, hole, t):
        self.game.advance(t)
        self.game.mice[hole] = Mouse(hole, t)

    def stun_at(self, t):
        self.game.handle("light", 0, t)
        self.game.handle("light", 100, t + 0.05)


class AcceptanceTests(GameTestCase):
    def test_hit_during_retreat_scores_without_cheese_loss(self):
        self.place((1, 1), 0.0)
        self.game.advance(1.7)
        self.assertEqual(self.game.mice[(1, 1)].stage, RETREAT)
        self.game.handle("attack", "swing", 1.7)
        self.assertEqual((self.game.score, self.game.cheese), (1, config.START_CHEESE))
        self.assertNotIn((1, 1), self.game.mice)

    def test_stun_pauses_bars_then_mice_resume(self):
        self.place((0, 0), 0.0)   # carrying from 1.6, escapes at 2.2 without a stun
        self.place((2, 2), 1.0)   # empty until 2.6
        self.stun_at(1.85)        # stun starts at 1.9
        frozen = {m["hole"][0]: m["progress"] for m in self.game.snapshot()["mice"]}
        end = 1.9 + config.STUN_SECONDS
        self.game.advance(end + 0.01)
        self.assertEqual(set(self.game.mice), {(0, 0), (2, 2)})
        resumed = {m["hole"][0]: m["progress"] for m in self.game.snapshot()["mice"]}
        for row in frozen:
            self.assertLess(resumed[row] - frozen[row], 0.05)
        self.assertEqual(self.game.cheese, config.START_CHEESE)
        self.game.advance(2.2 + config.STUN_SECONDS + 0.01)   # carrier's escape, delayed by the stun
        self.assertNotIn((0, 0), self.game.mice)
        self.assertEqual(self.game.cheese, config.START_CHEESE - 1)

    def test_hit_carrier_during_stun(self):
        self.place((0, 0), 0.0)
        self.place((2, 2), 1.0)
        self.stun_at(1.85)
        self.game.handle("aim", "up", 2.0)
        self.game.handle("aim", "left", 2.0)
        self.game.handle("attack", "swing", 2.0)
        self.assertEqual(self.game.score, 1)
        self.game.advance(1.9 + config.STUN_SECONDS + 0.01)
        self.assertEqual(set(self.game.mice), {(2, 2)})
        self.assertEqual(self.game.cheese, config.START_CHEESE)

    def test_stun_freezes_progress(self):
        self.place((0, 0), 0.0)
        self.stun_at(0.75)
        frozen = self.game.snapshot()["mice"][0]["progress"]
        self.game.advance(1.5)
        self.assertEqual(self.game.snapshot()["mice"][0]["progress"], frozen)

    def test_light_off_during_stun_then_on_does_not_restun(self):
        self.stun_at(1.85)
        stun_end = self.game.stun_until
        self.game.handle("light", 0, 2.0)
        self.assertFalse(self.game.light)
        self.game.handle("light", 100, 2.5)
        self.assertEqual(self.game.stun_until, stun_end)
        self.game.advance(stun_end + 0.01)
        self.assertIsNone(self.game.stun_until)
        self.game.handle("light", 0, 4.0)
        self.game.handle("light", 100, 4.1)
        self.assertIsNone(self.game.stun_until)

    def test_light_left_on_past_cooldown_waits_for_transition(self):
        self.stun_at(1.85)
        self.game.advance(1.9 + config.STUN_COOLDOWN + 0.5)
        snap = self.game.snapshot()
        self.assertTrue(snap["stun_ready"])
        self.assertFalse(snap["stun_active"])
        self.stun_at(9.0)
        self.assertTrue(self.game.snapshot()["stun_active"])

    def test_time_runs_out_during_stun(self):
        end = config.ROUND_SECONDS
        self.place((0, 0), end - 2.0)   # carrying from end - 0.4
        self.stun_at(end - 0.35)
        self.game.advance(config.ROUND_SECONDS + 5)
        self.assertEqual(self.game.phase, FINISHED)
        self.assertEqual(self.game.cheese, config.START_CHEESE)
        self.assertEqual(len(self.board.entries), 1)
        self.assertEqual(self.board.entries[0]["elapsed"], config.ROUND_SECONDS)

    def test_last_cheese_escape_ends_round_once(self):
        self.game.cheese = 1
        self.place((1, 1), 0.0)
        self.game.advance(2.3)
        self.assertEqual(self.game.phase, FINISHED)
        self.assertEqual(self.game.cheese, 0)
        self.game.advance(10.0)
        self.assertFalse(self.game.handle("attack", "swing", 10.0))
        self.assertEqual(len(self.board.entries), 1)

    def test_new_round_and_restart_keep_leaderboard(self):
        self.game.handle("attack", "swing", 1.0)
        self.game.advance(config.ROUND_SECONDS)
        self.assertEqual(self.game.phase, FINISHED)
        self.game.start(70.0)
        self.assertEqual(self.game.phase, PLAYING)
        self.assertEqual((self.game.score, self.game.cheese, self.game.mice,
                          self.game.crosshair, self.game.light),
                         (0, config.START_CHEESE, {}, (1, 1), True))
        reloaded = Leaderboard(self.board.path)
        self.assertEqual(len(reloaded.entries), 1)

    def test_deadline_resolves_before_same_time_input(self):
        self.place((1, 1), 0.0)
        escape_at = config.CRAVE_SECONDS + config.RETREAT_SECONDS
        self.game.handle("attack", "swing", escape_at)
        self.assertEqual((self.game.score, self.game.cheese), (0, config.START_CHEESE - 1))

    def test_aim_clamps_at_edges(self):
        for _ in range(3):
            self.game.handle("aim", "up", 0.1)
        self.assertEqual(self.game.crosshair, (0, 1))


class SpawnTests(unittest.TestCase):
    def test_first_mouse_after_lit_interval_and_full_board_skips(self):
        game = Game(rng=random.Random(2))
        game.start(0.0)
        game.advance(config.SPAWN_LIT - 0.01)
        self.assertEqual(len(game.mice), 0)
        game.advance(config.SPAWN_LIT)
        self.assertEqual(len(game.mice), 1)
        for r in range(3):
            for c in range(3):
                game.mice.setdefault((r, c), Mouse((r, c), game.clock))
        game._spawn(game.clock)
        self.assertEqual(len(game.mice), 9)


class ComboTests(GameTestCase):
    def hit(self, hole, t, online=True):
        self.place(hole, t)
        target = self.game.crosshair
        self.game.mice[target] = self.game.mice.pop(hole)
        self.game.mice[target].hole = target
        self.game.handle("attack", "swing", t, online=online)

    def test_online_inputs_build_combo_and_multiplier(self):
        for i in range(4):
            self.game.handle("aim", "up" if i % 2 else "down", 0.1 * i, online=True)
        self.assertEqual(self.game.combo, 4)
        self.hit((0, 0), 1.0)                       # 5th input -> x1.2 tier
        self.assertEqual(self.game.combo, 5)
        self.assertEqual(self.game.score, 1.2)
        for i in range(4):
            self.game.handle("aim", "left" if i % 2 else "right", 1.1 + 0.1 * i, online=True)
        self.hit((0, 0), 2.0)                       # 10th input -> x1.5 tier
        self.assertEqual(self.game.score, 2.7)

    def test_keyboard_aim_does_not_build_combo(self):
        self.game.handle("aim", "up", 0.1, online=True)
        self.game.handle("aim", "down", 0.2, online=False)
        self.game.handle("light", 20, 0.3, online=False)
        self.assertEqual(self.game.combo, 1)

    def test_every_hit_raises_combo_from_any_source(self):
        for i in range(5):
            self.hit((0, 0), 1.0 + i, online=False)
            self.assertEqual(self.game.combo, i + 1)
        self.assertEqual(self.game.score, 4 * 1.0 + 1.2)
        self.game.handle("attack", "swing", 7.0, online=False)   # keyboard miss
        self.assertEqual(self.game.combo, 0)

    def test_online_miss_resets_combo(self):
        self.game.handle("aim", "up", 0.1, online=True)
        self.game.handle("attack", "swing", 0.2, online=True)
        self.assertEqual(self.game.combo, 0)
        self.assertIn("combo_break", [e["type"] for e in self.game.drain_effects()])

    def test_pi_dropping_counts_as_miss_and_resets_combo(self):
        for i in range(3):
            self.game.handle("aim", "up", 0.1 * i, online=True)
        self.assertTrue(self.game.pi_offline("attack", 1.0))
        self.assertEqual(self.game.combo, 0)
        self.assertEqual(self.game.best_combo, 3)
        types = [e["type"] for e in self.game.drain_effects()]
        self.assertIn("pi_offline", types)
        self.assertIn("combo_break", types)

    def test_stolen_cheese_resets_combo(self):
        self.place((0, 0), 0.0)
        for i in range(3):
            self.game.handle("aim", "up", 0.1 * i, online=True)
        self.game.advance(config.CRAVE_SECONDS + config.RETREAT_SECONDS)
        self.assertEqual(self.game.cheese, config.START_CHEESE - 1)
        self.assertEqual(self.game.combo, 0)
        breaks = [e for e in self.game.drain_effects() if e["type"] == "combo_break"]
        self.assertEqual(breaks[0]["reason"], "cheese")

    def test_stunned_carrier_escapes_after_resume_and_resets_combo(self):
        self.place((0, 0), 0.0)
        self.game.handle("aim", "up", 0.1, online=True)
        self.stun_at(1.85)                          # carrier frozen
        self.game.advance(1.9 + config.STUN_SECONDS + 0.01)
        self.assertEqual(self.game.combo, 1)        # the stun itself takes nothing
        self.game.advance(2.2 + config.STUN_SECONDS + 0.01)
        self.assertEqual(self.game.combo, 0)

    def test_stun_with_only_empty_mice_keeps_combo(self):
        self.place((0, 0), 1.0)
        self.game.handle("aim", "up", 1.1, online=True)
        self.stun_at(1.2)
        self.game.advance(1.25 + config.STUN_SECONDS + 0.01)
        self.assertEqual(self.game.combo, 1)

    def test_light_counts_only_when_crossing_threshold(self):
        self.game.handle("light", 80, 0.1, online=True)
        self.game.handle("light", 70, 0.2, online=True)
        self.assertEqual(self.game.combo, 0)
        self.game.handle("light", 20, 0.3, online=True)
        self.assertEqual(self.game.combo, 1)

    def test_round_end_reports_win_when_cheese_survives(self):
        self.game.advance(config.ROUND_SECONDS)
        end = [e for e in self.game.drain_effects() if e["type"] == "round_end"][0]
        self.assertTrue(end["won"])


class BossTests(GameTestCase):
    def place_boss(self, t):
        self.game.advance(t)
        hole = self.game.crosshair
        self.game.mice[hole] = Mouse(hole, t, boss=True)
        return hole

    def test_boss_takes_three_hits_each_scoring(self):
        hole = self.place_boss(0.0)
        for i in range(config.BOSS_HP - 1):
            self.game.handle("attack", "swing", 0.5 + i * 0.1)
            self.assertEqual(self.game.mice[hole].hp, config.BOSS_HP - 1 - i)
        self.game.handle("attack", "swing", 1.0)
        self.assertNotIn(hole, self.game.mice)
        self.assertEqual(self.game.score, config.BOSS_HP)
        hits = [e for e in self.game.drain_effects() if e["type"] == "hit"]
        self.assertEqual([e["killed"] for e in hits], [False] * (config.BOSS_HP - 1) + [True])
        self.assertTrue(all(e["boss"] for e in hits))

    def test_boss_has_longer_bars(self):
        hole = self.place_boss(0.0)
        self.game.advance(config.CRAVE_SECONDS + 0.1)
        self.assertFalse(self.game.mice[hole].carrying)
        self.game.advance(config.BOSS_CRAVE_SECONDS + 0.01)
        self.assertTrue(self.game.mice[hole].carrying)
        self.game.advance(config.BOSS_CRAVE_SECONDS + config.BOSS_RETREAT_SECONDS + 0.01)
        self.assertNotIn(hole, self.game.mice)
        self.assertEqual(self.game.cheese, config.START_CHEESE - 1)

    def test_boss_timer_spawns_about_every_interval(self):
        config.BOSS_INTERVAL = 10.0
        game = Game(rng=random.Random(5))
        game.start(0.0)
        spawns = []
        t = 0.0
        while t < 200 and game.phase == PLAYING:
            t += 0.5
            game.advance(t)
            for e in game.drain_effects():
                if e["type"] == "spawn" and e.get("boss"):
                    spawns.append(t)
            for h in [h for h, m in game.mice.items() if m.boss]:
                game.mice.pop(h)
            game.cheese = config.START_CHEESE
            game.start_time = t     # keep the round open
        gaps = [b - a for a, b in zip(spawns, spawns[1:])]
        self.assertGreater(len(gaps), 10)
        self.assertTrue(all(config.BOSS_INTERVAL - config.BOSS_JITTER - 0.5 <= g
                            <= config.BOSS_INTERVAL + config.BOSS_JITTER + 0.5 for g in gaps))


class HitStreakTests(GameTestCase):
    hit = ComboTests.hit

    def streaks(self):
        return [e["streak"] for e in self.game.drain_effects() if e["type"] == "hit"]

    def test_hits_count_up_and_miss_resets(self):
        for i in range(3):
            self.hit((0, 0), 1.0 + i, online=False)
        self.assertEqual(self.streaks(), [1, 2, 3])
        self.game.handle("attack", "swing", 4.0)
        self.assertEqual(self.game.hit_streak, 0)
        self.hit((0, 0), 5.0)
        self.assertEqual(self.streaks(), [1])

    def test_stolen_cheese_resets_streak(self):
        self.hit((0, 0), 0.5)
        self.hit((0, 0), 0.6)
        self.place((0, 0), 1.0)                       # not under the crosshair, escapes
        self.game.advance(1.0 + config.CRAVE_SECONDS + config.RETREAT_SECONDS + 0.1)
        self.assertLess(self.game.cheese, config.START_CHEESE)
        self.assertEqual(self.game.hit_streak, 0)
        self.game.drain_effects()
        self.hit((0, 0), 4.0)
        self.assertEqual(self.streaks(), [1])

    def test_dropped_pi_resets_streak(self):
        self.hit((0, 0), 0.5)
        self.game.pi_offline("light", 1.0)
        self.assertEqual(self.game.hit_streak, 0)

    def test_stun_alone_leaves_streak_alone(self):
        self.hit((0, 0), 0.5)
        self.hit((0, 0), 0.6)
        self.game.drain_effects()
        self.place((2, 2), 1.0)
        self.stun_at(1.1)
        self.game.advance(1.2 + config.STUN_SECONDS)
        self.assertEqual(self.game.hit_streak, 2)
        types = [e["type"] for e in self.game.drain_effects()]
        self.assertIn("stun_end", types)
        self.assertNotIn("hit", types)

    def test_hit_during_stun_counts(self):
        self.hit((0, 0), 0.5)
        self.place((2, 2), 1.0)
        self.stun_at(1.1)
        self.hit((0, 1), 1.3)
        self.assertIsNotNone(self.game.stun_until)
        self.assertEqual(self.streaks(), [1, 2])

    def test_new_round_resets_streak(self):
        self.hit((0, 0), 0.5)
        self.game.advance(config.ROUND_SECONDS + 1)
        self.game.start(config.ROUND_SECONDS + 2)
        self.assertEqual(self.game.hit_streak, 0)


class BrightnessTests(unittest.TestCase):
    def setUp(self):
        self.game = Game(rng=random.Random(3))
        self.game.start(0.0)

    def test_spawn_interval_interpolates_with_brightness(self):
        g = self.game
        for level, expected in ((100, config.SPAWN_LIT), (0, config.SPAWN_DARK),
                                (50, (config.SPAWN_LIT + config.SPAWN_DARK) / 2)):
            g.brightness = level
            self.assertAlmostEqual(g.snapshot()["spawn_interval"], round(expected, 2))

    def test_change_within_lit_range_keeps_timer_and_skips_stun(self):
        g = self.game
        g.handle("light", 80, 1.0)
        self.assertEqual(g.spawn_ref, 0.0)
        self.assertIsNone(g.stun_until)
        expected = config.SPAWN_DARK + (config.SPAWN_LIT - config.SPAWN_DARK) * 0.8
        self.assertAlmostEqual(g.next_spawn_at, expected)

    def test_crossing_threshold_upward_triggers_stun(self):
        g = self.game
        g.handle("light", config.LIGHT_ON_THRESHOLD - 10, 1.0)
        self.assertFalse(g.light)
        self.assertEqual(g.spawn_ref, 1.0)
        g.handle("light", config.LIGHT_ON_THRESHOLD + 10, 1.2)
        self.assertIsNotNone(g.stun_until)

    def test_overdue_shorter_interval_spawns_now(self):
        g = self.game
        g.handle("light", 80, 0.1)          # still lit, timer kept at 0.0
        g.advance(1.9)
        g.handle("light", 50, 1.9)          # interval shrinks below 1.9 s
        g.advance(1.9)
        self.assertEqual(len(g.mice), 1)
        self.assertEqual(g.spawn_ref, 1.9)

    def test_out_of_range_input_is_clamped(self):
        self.game.handle("light", 250, 1.0)
        self.assertEqual(self.game.brightness, 100)


class ControllerTests(unittest.TestCase):
    def test_joystick_one_step_per_push(self):
        stick = JoystickStepper(512, 512)
        self.assertEqual(stick.update(1023, 512), "right")
        self.assertIsNone(stick.update(1023, 512))
        self.assertIsNone(stick.update(600, 512))   # still outside dead zone
        self.assertIsNone(stick.update(520, 512))   # rearmed
        self.assertEqual(stick.update(512, 0), "down")

    def test_joystick_larger_axis_wins_and_tie_is_horizontal(self):
        self.assertEqual(JoystickStepper(512, 512).update(300, 1023), "up")
        self.assertEqual(JoystickStepper(512, 512).update(1023, 1023), "right")

    def test_proximity_one_swing_per_approach(self):
        prox = ProximitySwing(trigger=20, release=10, confirm=2)
        self.assertIsNone(prox.update(50))          # starts disarmed
        for reading in (5, 5):
            prox.update(reading)
        self.assertTrue(prox.armed)
        self.assertIsNone(prox.update(30))
        self.assertEqual(prox.update(30), "swing")
        for _ in range(10):
            self.assertIsNone(prox.update(30))
        prox.update(3)
        prox.update(3)
        prox.update(25)
        self.assertEqual(prox.update(25), "swing")

    def test_openness_maps_fist_to_0_and_open_hand_to_100(self):
        self.assertEqual(openness_from_ratios([1.0] * 4, closed=1.1, opened=1.8), 0.0)
        self.assertEqual(openness_from_ratios([2.2] * 4, closed=1.1, opened=1.8), 100.0)
        self.assertAlmostEqual(openness_from_ratios([1.45] * 4, closed=1.1, opened=1.8), 50.0)
        self.assertAlmostEqual(openness_from_ratios([1.8, 1.8, 1.1, 1.1],
                                                    closed=1.1, opened=1.8), 50.0)

    def test_brightness_filter_steps_rate_limits_and_rearms(self):
        light = BrightnessFilter(smoothing=1.0, step=5, publish_hz=10)
        self.assertEqual(light.update(73, 0.0), 75)
        self.assertIsNone(light.update(74, 0.5))      # same step, no repeat
        self.assertIsNone(light.update(20, 0.05))     # within 0.1 s of last send
        self.assertEqual(light.update(20, 0.2), 20)
        self.assertIsNone(light.update(None, 0.3))    # hand left, light stays
        self.assertEqual(light.update(20, 0.5), 20)   # fresh hand resends

    def test_brightness_filter_smooths(self):
        light = BrightnessFilter(smoothing=0.5, step=5, publish_hz=0)
        self.assertEqual(light.update(0, 0.0), 0)
        self.assertEqual(light.update(100, 1.0), 50)
        self.assertEqual(light.update(100, 2.0), 75)


if __name__ == "__main__":
    unittest.main()
