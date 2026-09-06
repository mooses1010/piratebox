#!/usr/bin/env python3
"""Deterministic tests for piratebox_progression.py (XP/levels/titles/
achievements/rarity-event-engine/persistence/reset-import) plus its
integration points in piratebox_oled_daemon.py - matches the project's
existing dependency-free tools/test_*.py convention (see
tools/test_silly_mode.py). stdlib unittest only, no new dependency.

Run with: python3 tools/test_progression.py

Deliberately does NOT touch the real /var/lib/piratebox-oled or
/tmp/piratebox - every persistence-path test patches the module's own
path constants to a temp directory for the duration of one test, then
restores them. Nothing here starts the daemon's main() loop or opens
real hardware.

Per instruction, this file (like piratebox_progression.py itself) is
allowed to be fully explicit about secret/hidden content - operator-
facing docs and the feature's own final report deliberately are not.
"""

import importlib.util
import json
import os
import random
import shutil
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PROG_PATH = os.path.join(HERE, "..", "piratebox_progression.py")
DAEMON_PATH = os.path.join(HERE, "..", "piratebox_oled_daemon.py")

spec = importlib.util.spec_from_file_location("piratebox_progression", PROG_PATH)
prog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prog)

# piratebox_oled_daemon.py now does a top-level `from piratebox_expressions
# import ...` (Expression Engine v2, 2026-09-04) - see tools/test_silly_
# mode.py's own identical comment for why this line is needed when
# loading the daemon by file path via importlib.
sys.path.insert(0, os.path.dirname(DAEMON_PATH))

daemon_spec = importlib.util.spec_from_file_location("piratebox_oled_daemon", DAEMON_PATH)
oled = importlib.util.module_from_spec(daemon_spec)
daemon_spec.loader.exec_module(oled)


HEALTHY_CTX = {
    "now": 1_800_000_000.0, "dt": 3.0, "tier": "ok", "current_clients": None,
    "ssh_active": False, "idle_seconds": 0.0, "emergency_exercised": False,
    "silly_enabled": False, "external_radio": False, "wake_count_today": 0,
    "hardware": {},
}


def ctx(**overrides):
    c = dict(HEALTHY_CTX)
    c.update(overrides)
    return c


class TempDataDir(unittest.TestCase):
    """Base class: every persistence-touching test gets its own temp
    DATA_DIR/DATA_FILE and the real /tmp/piratebox request-file paths
    redirected too, restored afterward - never touches real device state."""

    def setUp(self):
        self._orig_dir = prog.DATA_DIR
        self._orig_file = prog.DATA_FILE
        self._orig_reset = prog.RESET_REQUEST_FILE
        self._orig_import = prog.IMPORT_REQUEST_FILE
        self.tmp = tempfile.mkdtemp()
        prog.DATA_DIR = self.tmp
        prog.DATA_FILE = os.path.join(self.tmp, "progression.json")
        prog.RESET_REQUEST_FILE = os.path.join(self.tmp, "reset-request")
        prog.IMPORT_REQUEST_FILE = os.path.join(self.tmp, "import-request")

    def tearDown(self):
        prog.DATA_DIR = self._orig_dir
        prog.DATA_FILE = self._orig_file
        prog.RESET_REQUEST_FILE = self._orig_reset
        prog.IMPORT_REQUEST_FILE = self._orig_import
        shutil.rmtree(self.tmp, ignore_errors=True)


class PersistenceTests(TempDataDir):
    def test_missing_file_gives_fresh_default_state(self):
        s = prog.load_state()
        self.assertEqual(s["xp"]["total"], 0)
        self.assertEqual(s["xp"]["level"], 1)
        self.assertEqual(s["achievements"], [])

    def test_corrupt_file_degrades_to_fresh_default_not_a_crash(self):
        with open(prog.DATA_FILE, "w") as f:
            f.write("{not valid json at all")
        s = prog.load_state()
        self.assertEqual(s["xp"]["total"], 0)

    def test_wrong_schema_version_degrades_to_fresh_default(self):
        with open(prog.DATA_FILE, "w") as f:
            json.dump({"schema_version": 999, "xp": {"total": 5000}}, f)
        s = prog.load_state()
        self.assertEqual(s["xp"]["total"], 0)

    def test_save_then_load_round_trips(self):
        s = prog._default_state()
        s["xp"]["total"] = 1234
        s["achievements"] = ["uptime_1d"]
        self.assertTrue(prog.save_state(s))
        loaded = prog.load_state()
        self.assertEqual(loaded["xp"]["total"], 1234)
        self.assertEqual(loaded["achievements"], ["uptime_1d"])

    def test_save_is_atomic_no_temp_file_left_behind(self):
        s = prog._default_state()
        prog.save_state(s)
        leftovers = [f for f in os.listdir(self.tmp) if ".tmp-" in f]
        self.assertEqual(leftovers, [])

    def test_a_future_field_addition_does_not_break_loading_older_files(self):
        # Simulates: a file written by an older version of this schema,
        # missing a key a newer _default_state() has - must merge, not KeyError.
        old_shape = prog._default_state()
        del old_shape["weights"]["resilience"]
        with open(prog.DATA_FILE, "w") as f:
            json.dump(old_shape, f)
        s = prog.load_state()
        self.assertIn("resilience", s["weights"])  # filled back in from the fresh default


class XpLevelTitleTests(unittest.TestCase):
    def test_level_1_needs_zero_xp(self):
        self.assertEqual(prog.xp_for_level(1), 0)

    def test_level_curve_is_strictly_increasing(self):
        prev = -1
        for lvl in range(1, 60):
            need = prog.xp_for_level(lvl)
            self.assertGreater(need, prev)
            prev = need

    def test_level_curve_gets_progressively_steeper(self):
        # The GAP between consecutive levels should grow, not stay flat
        # or shrink - "meaningful for months/years," not a flat grind.
        gap_early = prog.xp_for_level(3) - prog.xp_for_level(2)
        gap_late = prog.xp_for_level(30) - prog.xp_for_level(29)
        self.assertGreater(gap_late, gap_early)

    def test_level_for_xp_matches_xp_for_level_inverse(self):
        for lvl in (1, 2, 5, 10, 25, 50):
            xp = prog.xp_for_level(lvl)
            self.assertEqual(prog.level_for_xp(xp), lvl)
            self.assertEqual(prog.level_for_xp(xp - 1), lvl - 1 if lvl > 1 else 1)

    def test_title_for_level_is_monotonic_non_decreasing_in_seniority(self):
        titles_seen = [prog.title_for_level(lvl) for lvl in (1, 5, 15, 30, 60, 120)]
        # Every threshold's title should differ from the very first once
        # level clears it - i.e. titles actually change across this range.
        self.assertGreater(len(set(titles_seen)), 1)

    def test_every_title_fits_the_display_at_font_small(self):
        _, font_small, _ = oled.load_fonts()
        for _, title in prog.TITLES:
            w = font_small.getbbox(title)[2]
            self.assertLessEqual(w, 128, f"Title too wide: {title!r} ({w}px)")


class AntiFarmingTests(unittest.TestCase):
    def test_cooldown_blocks_immediate_repeat(self):
        s = prog._default_state()
        now = 1000.0
        self.assertTrue(prog.award_once(s, "k", now, cooldown_s=100))
        self.assertFalse(prog.award_once(s, "k", now + 50, cooldown_s=100))
        self.assertTrue(prog.award_once(s, "k", now + 150, cooldown_s=100))

    def test_daily_cap_blocks_after_limit_same_day(self):
        s = prog._default_state()
        base = time.mktime((2026, 1, 1, 12, 0, 0, 0, 0, -1))
        for i in range(3):
            self.assertTrue(prog.award_once(s, "k", base + i, daily_cap=3))
        self.assertFalse(prog.award_once(s, "k", base + 3, daily_cap=3))

    def test_daily_cap_resets_on_a_new_day(self):
        s = prog._default_state()
        day1 = time.mktime((2026, 1, 1, 12, 0, 0, 0, 0, -1))
        day2 = time.mktime((2026, 1, 2, 12, 0, 0, 0, 0, -1))
        self.assertTrue(prog.award_once(s, "k", day1, daily_cap=1))
        self.assertFalse(prog.award_once(s, "k", day1 + 10, daily_cap=1))
        self.assertTrue(prog.award_once(s, "k", day2, daily_cap=1))

    def test_bare_award_once_ever_without_cooldown_or_cap(self):
        s = prog._default_state()
        self.assertTrue(prog.award_once(s, "k", 1.0))
        self.assertFalse(prog.award_once(s, "k", 999999.0))

    def test_repeated_identical_client_arrivals_are_capped_per_day(self):
        """Directly exercises the anti-farming requirement: reconnecting
        the same device over and over cannot produce unlimited XP.
        Day 1 legitimately includes one-time bonuses (first encounter,
        10th encounter, first simultaneous-client record) that can't
        recur - those aren't farming, they're real milestones. Day 2
        repeats the identical flapping pattern with no new milestones
        left to claim, isolating the steady-state, ongoing-farming case
        the daily cap actually exists to bound."""
        s = prog._default_state()
        base = time.mktime((2026, 1, 1, 0, 0, 0, 0, 0, -1))
        for i in range(50):  # far more than the daily cap
            t = base + i * 60  # every 60s - a flapping device, not real distinct visitors
            prog.observe_tick(s, ctx(now=t, current_clients=(1 if i % 2 == 0 else 0)))

        xp_before_day2 = s["xp"]["total"]
        day2 = base + 86400
        for i in range(50):
            t = day2 + i * 60
            prog.observe_tick(s, ctx(now=t, current_clients=(1 if i % 2 == 0 else 0)))
        gained_day2 = s["xp"]["total"] - xp_before_day2
        # Only the daily-capped client_arrival source remains available
        # on day 2 (10 awards * 8 XP = 80) - no one-time bonus left to claim.
        self.assertLessEqual(gained_day2, 80)


class AchievementTests(unittest.TestCase):
    def test_no_spurious_unlocks_on_a_fresh_state(self):
        s = prog._default_state()
        self.assertEqual(prog.check_achievements(s, ctx(now=1_700_000_000.0)), [])

    def test_uptime_achievement_unlocks_exactly_once(self):
        s = prog._default_state()
        s["stats"]["lifetime_uptime_seconds"] = 86400
        first = prog.check_achievements(s, ctx())
        self.assertIn("uptime_1d", first)
        second = prog.check_achievements(s, ctx())
        self.assertNotIn("uptime_1d", second)

    def test_unlock_awards_its_xp(self):
        s = prog._default_state()
        s["stats"]["lifetime_uptime_seconds"] = 86400
        before = s["xp"]["total"]
        prog.check_achievements(s, ctx())
        self.assertGreater(s["xp"]["total"], before)

    def test_hidden_leet_does_not_fire_at_zero_uptime(self):
        """Regression guard for a real bug caught during development:
        modulo-based thresholds must not spuriously match at zero."""
        s = prog._default_state()
        self.assertEqual(s["stats"]["lifetime_uptime_seconds"], 0)
        unlocked = prog.check_achievements(s, ctx())
        self.assertNotIn("hidden_leet", unlocked)

    def test_a_bad_predicate_never_crashes_the_check(self):
        s = prog._default_state()
        prog.ACHIEVEMENTS["_test_broken"] = prog._mk(
            "Broken", 1, True, "Test-only description.", lambda s, c: 1 / 0,
        )
        try:
            unlocked = prog.check_achievements(s, ctx())
            self.assertNotIn("_test_broken", unlocked)
        finally:
            del prog.ACHIEVEMENTS["_test_broken"]

    def test_every_achievement_name_fits_the_display_at_font_small(self):
        _, font_small, _ = oled.load_fonts()
        for aid, spec in prog.ACHIEVEMENTS.items():
            w = font_small.getbbox(spec["name"])[2]
            self.assertLessEqual(w, 128, f"{aid}: name too wide ({w}px): {spec['name']!r}")

    def test_every_achievement_has_a_short_spoiler_safe_description(self):
        """2026-09-06, Captain's Log achievement-description round: every
        achievement must carry a non-empty, mobile-length description -
        _mk() now requires one positionally, so a future achievement
        added without one already fails at import time; this test also
        catches an accidentally-blank or unreasonably-long string, which
        a required-argument check alone wouldn't."""
        for aid, spec in prog.ACHIEVEMENTS.items():
            desc = spec.get("description")
            self.assertIsInstance(desc, str, f"{aid}: description is not a string")
            self.assertTrue(desc.strip(), f"{aid}: description is empty")
            self.assertLessEqual(len(desc), 140, f"{aid}: description too long for a mobile card ({len(desc)} chars)")

    def test_hidden_curious_collection_fires_at_the_threshold_not_before(self):
        """Expression Engine v2 (2026-09-04) - ties an achievement to
        the pre-existing rare_events_witnessed counter (already
        incremented by _record_variant_choice() for any rare/legendary/
        secret pick, regardless of which family/variant) rather than
        naming any specific variant, so this predicate stays honest
        about "a real spread of rarity," not one lucky repeat roll."""
        s = prog._default_state()
        s["stats"]["rare_events_witnessed"] = 7
        self.assertEqual(prog.check_achievements(s, ctx()), [])
        s["stats"]["rare_events_witnessed"] = 8
        self.assertIn("hidden_curious_collection", prog.check_achievements(s, ctx()))


class EventEngineTests(unittest.TestCase):
    def test_every_family_always_returns_something_when_it_has_a_plain_default(self):
        s = prog._default_state()
        rng = random.Random(7)
        for family in ("client_arrival", "wake", "flourish"):
            v = prog.roll_event(family, s, ctx(), rng)
            self.assertIsNotNone(v)

    def test_ambient_family_usually_returns_none(self):
        s = prog._default_state()
        rng = random.Random(3)
        none_count = sum(1 for _ in range(200) if prog.roll_event("ambient", s, ctx(), rng) is None)
        self.assertGreater(none_count, 150)

    def test_unknown_family_returns_none(self):
        s = prog._default_state()
        self.assertIsNone(prog.roll_event("no_such_family", s, ctx(), random.Random()))

    def test_min_level_gates_a_variant_out(self):
        s = prog._default_state()
        s["xp"]["level"] = 1
        rng = random.Random(0)
        seen_ids = set()
        for _ in range(500):
            v = prog.roll_event("client_arrival", s, ctx(), rng)
            if v:
                seen_ids.add(v["id"])
        self.assertNotIn("client_arrival.rare_royal", seen_ids)  # min_level=5

    def test_condition_gates_a_variant_out(self):
        s = prog._default_state()
        s["xp"]["level"] = 99
        s["stats"]["total_client_encounters"] = 0  # rare_royal requires >= 10
        rng = random.Random(0)
        for _ in range(300):
            v = prog.roll_event("client_arrival", s, ctx(), rng)
            self.assertNotEqual((v or {}).get("id"), "client_arrival.rare_royal")

    def test_cooldown_suppresses_a_variant_right_after_it_fires(self):
        s = prog._default_state()
        prog.force_next_event("wake", "wake.uncommon_groggy")
        v1 = prog.roll_event("wake", s, ctx(now=1000.0), random.Random(1))
        self.assertEqual(v1["id"], "wake.uncommon_groggy")
        # Immediately after, a normal (non-forced) roll must not pick the
        # same variant again - its cooldown was just set.
        seen = {prog.roll_event("wake", s, ctx(now=1005.0), random.Random(i))["id"] for i in range(200)}
        self.assertNotIn("wake.uncommon_groggy", seen)

    def test_force_next_event_is_exact_and_one_shot(self):
        s = prog._default_state()
        prog.force_next_event("flourish", "flourish.common")
        v = prog.roll_event("flourish", s, ctx(), random.Random())
        self.assertEqual(v["id"], "flourish.common")
        # The queue is now empty - the NEXT roll is a real (unforced) roll.
        self.assertEqual(prog._forced_queue, [])

    def test_seen_events_history_is_recorded(self):
        s = prog._default_state()
        prog.force_next_event("flourish", "flourish.common")
        prog.roll_event("flourish", s, ctx(now=42.0), random.Random())
        self.assertEqual(s["seen_events"]["flourish.common"]["count"], 1)
        self.assertEqual(s["seen_events"]["flourish.common"]["last"], 42.0)

    def test_every_render_spec_is_drawable(self):
        """Every variant across every family must produce a render dict
        the OLED daemon can actually draw (regression guard for the
        expression/scene-name typo class of bug) - extended for
        Expression Engine v2's {"anim": ...} shape (2026-09-04): those
        never reach build_frame() directly in production (main() always
        resolves "anim" into a concrete frame first via
        play_animation_burst()/resolve_animation_frames() - see that
        module's own header for why), so this test resolves and draws
        every one of an anim's own frames instead of calling
        build_frame() with the unresolved {"anim": ...} dict itself
        (which build_frame has no "anim" branch for at all - passing it
        straight through would silently draw a blank face, defeating
        the whole point of this typo guard)."""
        class FakeDevice:
            mode, size = "1", (128, 64)
        font, font_small, font_big = oled.load_fonts()
        dev = FakeDevice()
        for family, variants in prog.EVENT_FAMILIES.items():
            for v in variants:
                render = v["render"]
                if "expression" in render and render["expression"] != "pirate_flourish":
                    self.assertIn(render["expression"], oled.EXPRESSIONS, f"{v['id']}: unknown expression")
                elif "anim" in render:
                    self.assertIn(render["anim"], oled.ANIMATIONS, f"{v['id']}: unknown animation")
                    specs, gap, hold = oled.resolve_animation_frames(
                        render["anim"], "ok", quip=render.get("quip"),
                    )
                    self.assertIsNotNone(specs, f"{v['id']}: animation failed to resolve")
                    for spec in specs:
                        img = oled.build_frame(
                            dev, "silly", font, font_small, font_big, None, False, "normal",
                            alive_on=True, extra=spec,
                        )
                        self.assertEqual(img.size, (128, 64))
                    continue
                img = oled.build_frame(
                    dev, "silly", font, font_small, font_big, None, False, "normal",
                    alive_on=True, extra={"render": render, "tier": "ok"},
                )
                self.assertEqual(img.size, (128, 64))


class HardwareSignalTests(unittest.TestCase):
    def tearDown(self):
        prog.HARDWARE_SIGNALS.clear()

    def test_starts_empty(self):
        self.assertEqual(prog.HARDWARE_SIGNALS, {})

    def test_register_and_read(self):
        prog.register_hardware_signal("fake_temp_c", lambda: 21.5)
        self.assertEqual(prog.read_hardware_signals(), {"fake_temp_c": 21.5})

    def test_a_raising_reader_degrades_to_none_not_a_crash(self):
        prog.register_hardware_signal("broken", lambda: 1 / 0)
        self.assertEqual(prog.read_hardware_signals(), {"broken": None})

    def test_hardware_gated_ambient_variant_is_permanently_ineligible_uncommissioned(self):
        """Expression Engine v2 (2026-09-04): ambient.secret_night_watch
        is gated on ctx["hardware"]["ambient_lux"], which is always None
        until a real BH1750 reader is registered (HARDWARE_SIGNALS
        starts empty - see this class's own test_starts_empty). This
        must hold across many rolls at a level/state that satisfies
        every OTHER gate the variant has, so the only thing keeping it
        out is the missing hardware signal itself."""
        s = prog._default_state()
        s["xp"]["level"] = 99
        rng = random.Random(11)
        seen = set()
        for _ in range(500):
            v = prog.roll_event("ambient", s, ctx(hardware={}), rng)
            if v:
                seen.add(v["id"])
        self.assertNotIn("ambient.secret_night_watch", seen)

    def test_hardware_gated_ambient_condition_itself_responds_to_a_real_signal(self):
        """The other half of the guarantee above, checked at the right
        level: force_next_event() bypasses EVERY condition/cooldown/
        min_level check by design (see roll_event()'s own forced-dispatch
        branch), so dispatching it forced would prove nothing about the
        condition itself. Instead, call the variant's own `condition`
        callable directly with a qualifying reading - proving that once
        a real BH1750 reader eventually supplies one, this gate opens on
        its own with no code change needed here, exactly the point of
        the HARDWARE_SIGNALS registry."""
        s = prog._default_state()
        spec = next(v for v in prog.EVENT_FAMILIES["ambient"] if v["id"] == "ambient.secret_night_watch")
        self.assertFalse(spec["condition"](s, ctx(hardware={})))
        self.assertFalse(spec["condition"](s, ctx(hardware={"ambient_lux": 50})))  # too bright
        self.assertTrue(spec["condition"](s, ctx(hardware={"ambient_lux": 2})))    # dark enough


class PersonalityWeightTests(unittest.TestCase):
    def test_nudge_moves_toward_target(self):
        s = prog._default_state()
        before = s["weights"]["sociability"]
        prog.nudge_weight(s, "sociability", 1.0)
        self.assertGreater(s["weights"]["sociability"], before)

    def test_weights_stay_clamped_after_many_nudges(self):
        s = prog._default_state()
        for _ in range(10000):
            prog.nudge_weight(s, "sociability", 1.0)
        self.assertLessEqual(s["weights"]["sociability"], 1.0)
        for _ in range(10000):
            prog.nudge_weight(s, "sociability", 0.0)
        self.assertGreaterEqual(s["weights"]["sociability"], 0.0)


class ObserveTickIntegrationTests(unittest.TestCase):
    def test_passive_xp_accrues_only_in_ok_or_warning_tier(self):
        s = prog._default_state()
        prog.observe_tick(s, ctx(tier="fault", dt=3600.0))
        self.assertEqual(s["xp"]["total"], 0)
        prog.observe_tick(s, ctx(tier="ok", dt=3600.0))
        self.assertGreater(s["xp"]["total"], 0)

    def test_lifetime_uptime_accrues_regardless_of_tier(self):
        s = prog._default_state()
        prog.observe_tick(s, ctx(tier="fault", dt=100.0))
        self.assertEqual(s["stats"]["lifetime_uptime_seconds"], 100.0)

    def test_client_arrival_from_zero_increments_encounters_and_xp(self):
        s = prog._default_state()
        prog.observe_tick(s, ctx(current_clients=0))
        before = s["xp"]["total"]
        prog.observe_tick(s, ctx(current_clients=1))
        self.assertEqual(s["stats"]["total_client_encounters"], 1)
        self.assertGreater(s["xp"]["total"], before)

    def test_simultaneous_record_is_monotonic_and_ungated(self):
        s = prog._default_state()
        prog.observe_tick(s, ctx(current_clients=3))
        self.assertEqual(s["stats"]["max_simultaneous_clients"], 3)
        prog.observe_tick(s, ctx(current_clients=2))
        self.assertEqual(s["stats"]["max_simultaneous_clients"], 3)  # never decreases
        prog.observe_tick(s, ctx(current_clients=5))
        self.assertEqual(s["stats"]["max_simultaneous_clients"], 5)

    def test_emergency_exercise_increments_stat_and_resilience(self):
        s = prog._default_state()
        before = s["weights"]["resilience"]
        prog.observe_tick(s, ctx(emergency_exercised=True))
        self.assertEqual(s["stats"]["emergency_exercises"], 1)
        self.assertGreater(s["weights"]["resilience"], before)

    def test_external_radio_flag_is_sticky_once_true(self):
        s = prog._default_state()
        prog.observe_tick(s, ctx(external_radio=True))
        self.assertTrue(s["stats"]["external_radio_commissioned"])
        prog.observe_tick(s, ctx(external_radio=False))
        self.assertTrue(s["stats"]["external_radio_commissioned"])  # never un-set

    def test_level_up_is_reported_when_a_threshold_is_crossed(self):
        s = prog._default_state()
        s["xp"]["total"] = prog.xp_for_level(2) - 1
        s["xp"]["level"] = 1
        # A big single tick (an hour of "ok" tier = 2 XP) may not be
        # enough - directly add_xp to cross the boundary deterministically.
        leveled = prog.add_xp(s, 5)
        self.assertTrue(leveled)
        self.assertEqual(s["xp"]["level"], 2)


class ResetImportTests(TempDataDir):
    def test_reset_request_without_correct_token_is_ignored(self):
        s = prog._default_state()
        s["xp"]["total"] = 500
        with open(prog.RESET_REQUEST_FILE, "w") as f:
            f.write("not the real token")
        self.assertFalse(prog.check_reset_request(s, {}))
        self.assertEqual(s["xp"]["total"], 500)

    def test_reset_request_with_correct_token_wipes_state(self):
        s = prog._default_state()
        s["xp"]["total"] = 500
        s["achievements"] = ["uptime_1d"]
        with open(prog.RESET_REQUEST_FILE, "w") as f:
            f.write(prog.RESET_CONFIRM_TOKEN)
        self.assertTrue(prog.check_reset_request(s, {}))
        self.assertEqual(s["xp"]["total"], 0)
        self.assertEqual(s["achievements"], [])
        # And it was actually saved to disk, not just mutated in memory.
        self.assertEqual(prog.load_state()["xp"]["total"], 0)

    def test_reset_request_only_applies_once_per_file_write(self):
        s = prog._default_state()
        with open(prog.RESET_REQUEST_FILE, "w") as f:
            f.write(prog.RESET_CONFIRM_TOKEN)
        markers = {}
        self.assertTrue(prog.check_reset_request(s, markers))
        s["xp"]["total"] = 42  # simulate activity after the reset
        self.assertFalse(prog.check_reset_request(s, markers))  # same file, same mtime
        self.assertEqual(s["xp"]["total"], 42)  # not wiped again

    def test_missing_reset_request_file_is_a_silent_no_op(self):
        s = prog._default_state()
        self.assertFalse(prog.check_reset_request(s, {}))

    def test_import_rejects_invalid_json(self):
        s = prog._default_state()
        s["xp"]["total"] = 777
        with open(prog.IMPORT_REQUEST_FILE, "w") as f:
            f.write("{not json")
        self.assertFalse(prog.check_import_request(s, {}))
        self.assertEqual(s["xp"]["total"], 777)

    def test_import_rejects_wrong_schema_version(self):
        s = prog._default_state()
        s["xp"]["total"] = 777
        with open(prog.IMPORT_REQUEST_FILE, "w") as f:
            json.dump({"schema_version": 999, "xp": {"total": 1}, "stats": {}, "achievements": []}, f)
        self.assertFalse(prog.check_import_request(s, {}))
        self.assertEqual(s["xp"]["total"], 777)

    def test_import_rejects_malformed_achievements_field(self):
        s = prog._default_state()
        candidate = prog._default_state()
        candidate["achievements"] = [1, 2, 3]  # must be strings
        with open(prog.IMPORT_REQUEST_FILE, "w") as f:
            json.dump(candidate, f)
        self.assertFalse(prog.check_import_request(s, {}))

    def test_import_accepts_a_valid_export(self):
        exported = prog._default_state()
        exported["xp"]["total"] = 9001
        exported["achievements"] = ["uptime_1d", "encounter_1"]
        with open(prog.IMPORT_REQUEST_FILE, "w") as f:
            json.dump(exported, f)
        s = prog._default_state()
        self.assertTrue(prog.check_import_request(s, {}))
        self.assertEqual(s["xp"]["total"], 9001)
        self.assertEqual(prog.load_state()["xp"]["total"], 9001)


class HistoryTests(unittest.TestCase):
    """Captain's Log: sparse, bounded, spoiler-safe entries."""

    def test_achievement_unlock_is_logged_with_its_display_name(self):
        s = prog._default_state()
        s["stats"]["lifetime_uptime_seconds"] = 86400
        prog.check_achievements(s, ctx())
        kinds = [(e["kind"], e["label"]) for e in s["history"]]
        self.assertIn(("achievement", "First Full Day"), kinds)

    def test_achievement_unlock_records_a_timestamp(self):
        s = prog._default_state()
        s["stats"]["lifetime_uptime_seconds"] = 86400
        prog.check_achievements(s, ctx(now=12345.0))
        self.assertEqual(s["achievement_unlocked_at"]["uptime_1d"], 12345.0)

    def test_level_up_is_logged(self):
        s = prog._default_state()
        prog.add_xp(s, prog.xp_for_level(2))
        # add_xp alone doesn't log (only observe_tick does) - simulate
        # the same crossing through the real entrypoint instead.
        s2 = prog._default_state()
        s2["xp"]["total"] = prog.xp_for_level(2) - 5
        s2["xp"]["level"] = 1
        prog.observe_tick(s2, ctx(tier="ok", dt=3600 * 10))  # enough passive XP to cross
        kinds = [e["kind"] for e in s2["history"]]
        self.assertIn("level_up", kinds)

    def test_title_change_is_logged_only_when_the_title_actually_changes(self):
        s = prog._default_state()
        # Jump straight to a level whose title differs from level 1's.
        target_level = next(lvl for lvl, _ in prog.TITLES if lvl > 1)
        s["xp"]["total"] = prog.xp_for_level(target_level) - 5
        s["xp"]["level"] = 1
        prog.observe_tick(s, ctx(tier="ok", dt=3600 * 1000))
        kinds = [e["kind"] for e in s["history"]]
        self.assertIn("title_change", kinds)

    def test_history_is_bounded_by_count(self):
        s = prog._default_state()
        for i in range(prog.HISTORY_MAX_ENTRIES + 50):
            prog._append_history(s, "achievement", f"Entry {i}", float(i))
        self.assertEqual(len(s["history"]), prog.HISTORY_MAX_ENTRIES)
        self.assertEqual(s["history"][-1]["label"], f"Entry {prog.HISTORY_MAX_ENTRIES + 49}")

    def test_rare_event_choice_is_logged_and_counted(self):
        s = prog._default_state()
        prog.force_next_event("wake", "wake.rare_startled")
        prog.roll_event("wake", s, ctx(now=1.0), random.Random())
        self.assertEqual(s["stats"]["rare_events_witnessed"], 1)
        kinds = [e["kind"] for e in s["history"]]
        self.assertIn("rare_event", kinds)

    def test_common_event_choice_is_not_logged(self):
        s = prog._default_state()
        prog.force_next_event("wake", "wake.common")
        prog.roll_event("wake", s, ctx(now=1.0), random.Random())
        self.assertEqual(s["history"], [])
        self.assertEqual(s["stats"]["rare_events_witnessed"], 0)

    def test_rare_event_log_label_never_contains_the_internal_id(self):
        s = prog._default_state()
        prog.force_next_event("wake", "wake.rare_startled")
        prog.roll_event("wake", s, ctx(now=1.0), random.Random())
        for e in s["history"]:
            self.assertNotIn("wake.rare_startled", e["label"])


class PersonalityTraitTests(unittest.TestCase):
    def test_default_weights_give_balanced_labels(self):
        traits = prog.personality_traits({"sociability": 0.5, "vigilance": 0.5, "resilience": 0.5})
        self.assertEqual(traits["sociability"], "Balanced")

    def test_high_weight_gives_the_high_label(self):
        traits = prog.personality_traits({"sociability": 0.9})
        self.assertEqual(traits["sociability"], "Social")

    def test_low_weight_gives_the_low_label(self):
        traits = prog.personality_traits({"vigilance": 0.1})
        self.assertEqual(traits["vigilance"], "Relaxed")

    def test_missing_weight_defaults_to_balanced_midpoint(self):
        traits = prog.personality_traits({})
        self.assertEqual(traits["resilience"], "Steady")


class PublicSummaryTests(unittest.TestCase):
    """The one function every web-facing consumer goes through - the
    highest-stakes spoiler boundary in this whole file."""

    def test_available_true_on_a_normal_state(self):
        s = prog._default_state()
        summary = prog.build_public_summary(s, now=1000.0)
        self.assertTrue(summary["available"])

    def test_never_exposes_the_total_achievement_count(self):
        s = prog._default_state()
        summary = prog.build_public_summary(s, now=1000.0)
        dumped = json.dumps(summary)
        # The total number of achievements that exist must never leak,
        # whether directly or as a suspiciously-specific denominator.
        self.assertNotIn(str(len(prog.ACHIEVEMENTS)), dumped)

    def test_only_unlocked_achievements_appear(self):
        s = prog._default_state()
        s["achievements"] = ["uptime_1d"]
        summary = prog.build_public_summary(s, now=1000.0)
        names = [a["name"] for a in summary["achievements"]]
        self.assertEqual(names, ["First Full Day"])

    def test_no_internal_achievement_or_event_ids_leak(self):
        s = prog._default_state()
        s["achievements"] = list(prog.ACHIEVEMENTS.keys())
        s["seen_events"] = {"wake.rare_startled": {"count": 1, "last": 1.0}}
        summary = prog.build_public_summary(s, now=1000.0)
        dumped = json.dumps(summary)
        self.assertNotIn("seen_events", dumped)
        self.assertNotIn("cooldowns", dumped)
        for aid in prog.ACHIEVEMENTS:
            self.assertNotIn(f'"{aid}"', dumped)  # the id string itself, not the name

    def test_discovered_achievement_exposes_its_description(self):
        """2026-09-06: the core positive case for the new feature - a
        discovered achievement's safe description must actually reach
        the public export, verbatim from its catalog entry."""
        s = prog._default_state()
        s["achievements"] = ["uptime_1d"]
        summary = prog.build_public_summary(s, now=1000.0)
        self.assertEqual(
            summary["achievements"][0]["description"],
            prog.ACHIEVEMENTS["uptime_1d"]["description"],
        )
        self.assertTrue(summary["achievements"][0]["description"])

    def test_undiscovered_achievement_name_and_description_never_appear(self):
        """2026-09-06: the core negative case - with only ONE achievement
        unlocked, no other achievement's name or description string may
        appear anywhere in the exported JSON, discovered or not. This is
        the test that must keep failing if a future round ever changes
        build_public_summary() to iterate the full catalog instead of
        only the device's own unlocked list."""
        s = prog._default_state()
        s["achievements"] = ["uptime_1d"]
        summary = prog.build_public_summary(s, now=1000.0)
        dumped = json.dumps(summary)
        for aid, spec in prog.ACHIEVEMENTS.items():
            if aid == "uptime_1d":
                continue
            self.assertNotIn(spec["name"], dumped, f"{aid}: undiscovered name leaked")
            self.assertNotIn(spec["description"], dumped, f"{aid}: undiscovered description leaked")

    def test_exported_achievement_has_exactly_the_safe_fields(self):
        """Guards against a future edit accidentally spreading the whole
        catalog spec (e.g. `spec` itself, or its `check` lambda) into the
        export instead of hand-picking safe fields - `check`/`xp` must
        never appear on the exported dict, discovered or not."""
        s = prog._default_state()
        s["achievements"] = ["uptime_1d"]
        summary = prog.build_public_summary(s, now=1000.0)
        self.assertEqual(
            set(summary["achievements"][0].keys()),
            {"name", "hidden", "unlocked_at", "description"},
        )

    def test_pre_existing_unlock_without_a_timestamp_shows_none(self):
        """Backward compatibility: achievements unlocked before this
        feature existed have no achievement_unlocked_at entry."""
        s = prog._default_state()
        s["achievements"] = ["uptime_1d"]  # no matching achievement_unlocked_at entry
        summary = prog.build_public_summary(s, now=1000.0)
        self.assertIsNone(summary["achievements"][0]["unlocked_at"])

    def test_progress_fraction_is_between_zero_and_one(self):
        s = prog._default_state()
        s["xp"]["total"] = 50
        s["xp"]["level"] = 1
        summary = prog.build_public_summary(s, now=1000.0)
        self.assertGreaterEqual(summary["xp"]["progress_fraction"], 0.0)
        self.assertLessEqual(summary["xp"]["progress_fraction"], 1.0)

    def test_traits_are_labels_not_raw_floats(self):
        s = prog._default_state()
        summary = prog.build_public_summary(s, now=1000.0)
        for v in summary["traits"].values():
            self.assertIsInstance(v, str)

    def test_history_entries_carry_only_the_three_safe_fields(self):
        s = prog._default_state()
        prog._append_history(s, "achievement", "Test Entry", 5.0)
        summary = prog.build_public_summary(s, now=1000.0)
        self.assertEqual(set(summary["history"][0].keys()), {"ts", "kind", "label"})

    def test_cli_entrypoint_prints_valid_json(self):
        import subprocess
        out = subprocess.run(
            [sys.executable, PROG_PATH], capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(out.returncode, 0)
        parsed = json.loads(out.stdout)
        self.assertIn("available", parsed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
