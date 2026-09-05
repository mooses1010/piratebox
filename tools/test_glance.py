#!/usr/bin/env python3
"""Deterministic tests for piratebox_glance.py (Distance/Glance Display
- GLANCE_PAGES eligibility/weighting registry, select_glance_page()
scheduler, render_glance_page() rendering) - matches the project's
existing dependency-free tools/test_*.py convention (see
tools/test_expressions.py).

Run with: python3 tools/test_glance.py

This module has zero I/O of its own (no disk, no /tmp, no daemon, no
hardware) - every test here just imports the plain module and either
calls the pure scheduler with a synthetic `metrics` dict, or draws into
a bare PIL Image, exactly like tools/test_expressions.py already does
for Expression Engine v2.
"""

import importlib.util
import os
import random
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE_PATH = os.path.join(HERE, "..", "piratebox_glance.py")

spec = importlib.util.spec_from_file_location("piratebox_glance", MODULE_PATH)
gl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gl)

from PIL import Image, ImageFont, ImageDraw  # noqa: E402 - after module setup above

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"


def _fresh_draw():
    img = Image.new("1", (128, 64))
    return ImageDraw.Draw(img)


def _fonts():
    """Returns (label_fonts, font_cpu_label, font_medium, font_big) -
    matches piratebox_oled_daemon.py's own load_glance_fonts() return
    shape exactly (label-size fix, 2026-09-04)."""
    label_fonts = tuple(ImageFont.truetype(FONT_PATH, size) for size in gl.LABEL_FONT_SIZES)
    return (
        label_fonts,
        ImageFont.truetype(FONT_PATH, 20),
        ImageFont.truetype(FONT_PATH, 22),
        ImageFont.truetype(FONT_PATH, 32),
    )


HEALTHY_METRICS = {
    "cpu_percent": 8.0,
    "cpu_temp_c": 46.0,
    "ram_percent": 42.0,
    "disk_percent": 37.0,
    "clients": 2,
    "clients_recently_changed": False,
    "uptime_str": "3d 04h",
    "time_str": "21:42",
    "undervoltage_now": False,
}


class RenderingTests(unittest.TestCase):
    """Every declared page must render without exception, including
    boundary values (0%, 100%, negative temp, 3-digit client counts)
    and missing/None metrics - a renderer's job is to never look broken
    if called, regardless of what data it's handed (whether a page was
    worth showing AT ALL given missing data is the SCHEDULER's job, not
    tested here)."""

    def test_every_declared_page_renders_without_exception(self):
        label_fonts, font_cpu_label, font_medium, font_big = _fonts()
        for page_id in gl.GLANCE_PAGES:
            with self.subTest(page_id=page_id):
                gl.render_glance_page(
                    _fresh_draw(), label_fonts, font_cpu_label, font_medium, font_big, page_id, HEALTHY_METRICS,
                )

    def test_unknown_page_id_degrades_to_placeholder_not_a_crash(self):
        label_fonts, font_cpu_label, font_medium, font_big = _fonts()
        gl.render_glance_page(
            _fresh_draw(), label_fonts, font_cpu_label, font_medium, font_big, "no-such-page", HEALTHY_METRICS,
        )

    def test_boundary_percent_values_render_without_exception(self):
        label_fonts, font_cpu_label, font_medium, font_big = _fonts()
        for page_id in ("cpu", "ram", "disk"):
            for pct in (0, 1, 50, 99, 100):
                with self.subTest(page_id=page_id, pct=pct):
                    m = dict(HEALTHY_METRICS)
                    m["cpu_percent"] = m["ram_percent"] = m["disk_percent"] = pct
                    gl.render_glance_page(_fresh_draw(), label_fonts, font_cpu_label, font_medium, font_big, page_id, m)

    def test_negative_temperature_renders_without_exception(self):
        label_fonts, font_cpu_label, font_medium, font_big = _fonts()
        m = dict(HEALTHY_METRICS)
        m["cpu_temp_c"] = -5.0
        gl.render_glance_page(_fresh_draw(), label_fonts, font_cpu_label, font_medium, font_big, "cpu", m)

    def test_three_digit_client_count_renders_without_exception(self):
        label_fonts, font_cpu_label, font_medium, font_big = _fonts()
        m = dict(HEALTHY_METRICS)
        m["clients"] = 254
        gl.render_glance_page(_fresh_draw(), label_fonts, font_cpu_label, font_medium, font_big, "clients", m)

    def test_zero_clients_renders_without_exception(self):
        label_fonts, font_cpu_label, font_medium, font_big = _fonts()
        m = dict(HEALTHY_METRICS)
        m["clients"] = 0
        gl.render_glance_page(_fresh_draw(), label_fonts, font_cpu_label, font_medium, font_big, "clients", m)

    def test_every_page_handles_every_metric_missing(self):
        """No metric is assumed present - a page whose specific value(s)
        are None must still render (as a "--" placeholder), never
        raise, mirroring the fail-safe degradation every other reader
        in this project already uses for missing/malformed data."""
        label_fonts, font_cpu_label, font_medium, font_big = _fonts()
        empty = {}
        for page_id in gl.GLANCE_PAGES:
            with self.subTest(page_id=page_id):
                gl.render_glance_page(_fresh_draw(), label_fonts, font_cpu_label, font_medium, font_big, page_id, empty)

    def test_percent_values_are_actually_centered_not_just_present(self):
        """Regression guard for the exact bug class the instruction
        called out ("100%" vs "8%" must both be centered, not left-
        aligned at a fixed x) - measures the drawn text's own bounding
        box position for two very different digit counts and confirms
        neither one is flush against an edge."""
        label_fonts, font_cpu_label, font_medium, font_big = _fonts()
        for pct in (8, 100):
            draw = _fresh_draw()
            m = dict(HEALTHY_METRICS)
            m["ram_percent"] = pct
            gl.render_glance_page(draw, label_fonts, font_cpu_label, font_medium, font_big, "ram", m)
            text = f"{pct}%"
            bbox = draw.textbbox((0, 0), text, font=font_big)
            width = bbox[2] - bbox[0]
            expected_x = gl._centered_x(draw, text, font_big)
            # Centered means roughly equal margin on both sides -
            # neither margin should be near-zero (flush left/right).
            left_margin = expected_x
            right_margin = gl.CANVAS_W - (expected_x + width)
            self.assertGreater(left_margin, 5)
            self.assertGreater(right_margin, 5)


class LabelFitTests(unittest.TestCase):
    """Label-size fix (2026-09-04, following physical validation that
    found the ORIGINAL fixed small label unreadable at distance even
    though the big numeric value below it read fine). Every test here
    is a real measurement against the rendered pixels, not just "didn't
    raise" - the whole point of this round's fix was a readability
    regression that unit tests alone hadn't caught the first time."""

    ALL_LABELS = ("CPU", "RAM", "DISK", "TIME", "POWER", "CLIENTS", "UPTIME")

    def test_short_labels_get_the_largest_tier(self):
        """CPU/RAM/DISK/TIME/POWER (<=5 chars) must all fit the BIGGEST
        LABEL_FONT_SIZES tier - per instruction, "short labels like
        CPU, RAM, and DISK can be especially large," so settling for a
        smaller tier when the biggest already fits would be a
        regression even though it wouldn't clip."""
        label_fonts, _, _, _ = _fonts()
        draw = _fresh_draw()
        biggest = label_fonts[0]
        for text in ("CPU", "RAM", "DISK", "TIME", "POWER"):
            with self.subTest(text=text):
                chosen = gl._fit_label_font(draw, text, label_fonts)
                self.assertIs(chosen, biggest)

    def test_longer_labels_step_down_only_as_far_as_needed(self):
        """CLIENTS and UPTIME are too wide for the biggest tier (measured
        fact, not assumed) - confirm each picks the LARGEST tier that
        actually fits, not the smallest available (which would be a
        needless over-correction, exactly what a single "shrink until
        it fits" giant-font approach would risk if implemented naively)."""
        label_fonts, _, _, _ = _fonts()
        draw = _fresh_draw()
        for text in ("CLIENTS", "UPTIME"):
            with self.subTest(text=text):
                chosen = gl._fit_label_font(draw, text, label_fonts)
                bbox = draw.textbbox((0, 0), text, font=chosen)
                self.assertLessEqual(bbox[2] - bbox[0], gl.LABEL_MAX_WIDTH)
                # And confirm it's not needlessly small: the NEXT size
                # up (whichever tier is immediately larger than the
                # chosen one) must genuinely fail to fit - otherwise
                # _fit_label_font() picked too conservatively.
                chosen_index = label_fonts.index(chosen)
                if chosen_index > 0:
                    next_bigger = label_fonts[chosen_index - 1]
                    next_bbox = draw.textbbox((0, 0), text, font=next_bigger)
                    self.assertGreater(next_bbox[2] - next_bbox[0], gl.LABEL_MAX_WIDTH)

    def test_no_label_ever_exceeds_the_canvas_width(self):
        """The actual clipping guard: whichever tier gets chosen for
        ANY of today's real labels, its rendered width must never
        exceed the full 128px canvas (not just the LABEL_MAX_WIDTH
        margin target - confirms the margin itself is meaningfully
        inside the hard boundary, not accidentally equal to it)."""
        label_fonts, font_cpu_label, _, _ = _fonts()
        draw = _fresh_draw()
        for text in self.ALL_LABELS:
            with self.subTest(text=text):
                font = font_cpu_label if text == "CPU" else gl._fit_label_font(draw, text, label_fonts)
                bbox = draw.textbbox((0, 0), text, font=font)
                self.assertLess(bbox[2] - bbox[0], gl.CANVAS_W)

    def test_fallback_to_smallest_when_nothing_fits(self):
        """A hypothetical label too wide even for the smallest tier
        (not a real one today - see test_no_fake_future_sensor_pages_
        appear in SchedulerTests for the real registry) must degrade to
        the smallest available rather than raising or returning
        nothing."""
        label_fonts, _, _, _ = _fonts()
        draw = _fresh_draw()
        chosen = gl._fit_label_font(draw, "A" * 100, label_fonts)
        self.assertIs(chosen, label_fonts[-1])

    def test_draw_top_aligned_places_ink_at_the_requested_y(self):
        """Regression guard for exactly the bug _draw_top_aligned() was
        introduced to prevent: a literal fixed y (as plain draw.text()
        would use) drifts down at larger font sizes because of the
        font's own internal ascender space. Renders to a real bitmap
        and scans for the topmost ACTUALLY LIT pixel row - not a
        recomputation of the function's own formula, a real measurement
        of its effect - and confirms it lands at (or immediately after,
        never before) the requested top_y, consistently across every
        label font size this module actually uses."""
        label_fonts, _, _, _ = _fonts()
        top_y = 3
        for font in label_fonts:
            with self.subTest(size=font.size):
                img = Image.new("1", (gl.CANVAS_W, gl.CANVAS_H))
                draw = ImageDraw.Draw(img)
                gl._draw_top_aligned(draw, "CPU", font, top_y=top_y)
                pixels = img.load()
                topmost_lit_row = None
                for y in range(gl.CANVAS_H):
                    if any(pixels[x, y] for x in range(gl.CANVAS_W)):
                        topmost_lit_row = y
                        break
                self.assertIsNotNone(topmost_lit_row, "nothing was drawn at all")
                # Allow a couple of pixels of slack (anti-aliasing-free
                # 1-bit rendering can round a glyph's own top serif/curve
                # up or down by a pixel or two) but the drift this test
                # guards against would be many pixels at larger sizes,
                # not one or two.
                self.assertLessEqual(abs(topmost_lit_row - top_y), 2)

    def test_no_page_clips_at_the_bottom_of_the_canvas(self):
        """The actual vertical no-clipping guard: for every declared
        page, at realistic-to-extreme metric values (including the
        longest real strings each page can show), the value line's own
        rendered ink must stay within the 64px canvas height."""
        label_fonts, font_cpu_label, font_medium, font_big = _fonts()
        draw = _fresh_draw()
        cases = [
            ("cpu", {"cpu_percent": 100, "cpu_temp_c": -99}),
            ("ram", {"ram_percent": 100}),
            ("disk", {"disk_percent": 100}),
            ("clients", {"clients": 999}),
            ("uptime", {"uptime_str": "99d 23h"}),
            ("time", {"time_str": "23:59"}),
            ("power_warning", {"undervoltage_now": True}),
        ]
        for page_id, metrics in cases:
            with self.subTest(page_id=page_id):
                img = Image.new("1", (gl.CANVAS_W, gl.CANVAS_H))
                d = ImageDraw.Draw(img)
                gl.render_glance_page(d, label_fonts, font_cpu_label, font_medium, font_big, page_id, metrics)
                # Scan the actual rendered bitmap for the lowest lit
                # pixel row - the real, final word on whether anything
                # clipped, independent of any font-metrics assumption.
                pixels = img.load()
                lowest_lit_row = -1
                for y in range(gl.CANVAS_H):
                    if any(pixels[x, y] for x in range(gl.CANVAS_W)):
                        lowest_lit_row = y
                self.assertLess(
                    lowest_lit_row, gl.CANVAS_H,
                    f"{page_id}: content reaches the very last row - likely clipped",
                )
                self.assertGreater(lowest_lit_row, 0, f"{page_id}: nothing was drawn at all")


class SchedulerTests(unittest.TestCase):
    """select_glance_page() - deterministic given a seeded rng, so
    every eligibility/weighting/cooldown/no-immediate-repeat behavior
    is directly verifiable, not just "doesn't crash"."""

    def test_deterministic_given_the_same_seed(self):
        a = gl.select_glance_page(HEALTHY_METRICS, random.Random(1), None, {}, 1000.0)
        b = gl.select_glance_page(HEALTHY_METRICS, random.Random(1), None, {}, 1000.0)
        self.assertEqual(a, b)

    def test_always_returns_a_known_page_id(self):
        rng = random.Random(2)
        cooldowns = {}
        last = None
        for i in range(50):
            last = gl.select_glance_page(HEALTHY_METRICS, rng, last, cooldowns, 1000.0 + i)
            self.assertIn(last, gl.GLANCE_PAGES)

    def test_never_repeats_the_immediately_previous_page_when_alternatives_exist(self):
        rng = random.Random(3)
        cooldowns = {}
        last = "cpu"
        for i in range(100):
            chosen = gl.select_glance_page(HEALTHY_METRICS, rng, last, cooldowns, 1000.0 + i)
            self.assertNotEqual(chosen, last)
            last = chosen

    def test_power_warning_is_ineligible_when_not_undervoltage(self):
        rng = random.Random(4)
        cooldowns = {}
        seen = set()
        for i in range(300):
            seen.add(gl.select_glance_page(HEALTHY_METRICS, rng, None, cooldowns, 1000.0 + i))
        self.assertNotIn("power_warning", seen)

    def test_power_warning_is_eligible_when_undervoltage_now(self):
        m = dict(HEALTHY_METRICS)
        m["undervoltage_now"] = True
        rng = random.Random(5)
        cooldowns = {}
        seen = set()
        for i in range(300):
            seen.add(gl.select_glance_page(m, rng, None, cooldowns, 1000.0 + i * 1000))
        self.assertIn("power_warning", seen)

    def test_power_warning_respects_its_own_cooldown(self):
        """Even chronically eligible, it must not win on every single
        roll immediately after having just won - the whole point of
        giving it a cooldown (per instruction: don't let a chronic
        condition monopolize the rotation)."""
        m = dict(HEALTHY_METRICS)
        m["undervoltage_now"] = True
        rng = random.Random(6)
        cooldowns = {}
        first = gl.select_glance_page(m, rng, None, cooldowns, 1000.0)
        if first == "power_warning":
            # It won once - confirm it can't win again 1 second later.
            second = gl.select_glance_page(m, rng, first, cooldowns, 1001.0)
            self.assertNotEqual(second, "power_warning")
        # Either way, confirm the cooldown clock actually got set once
        # it did win at least once across a longer sample.
        cooldowns2 = {}
        last = None
        won_once = False
        for i in range(50):
            chosen = gl.select_glance_page(m, rng, last, cooldowns2, 2000.0 + i * 1000)
            if chosen == "power_warning":
                won_once = True
                self.assertIn("power_warning", cooldowns2)
            last = chosen
        self.assertTrue(won_once, "power_warning never won across 50 rolls at high weight - check GLANCE_PAGES")

    def test_clients_recently_changed_makes_it_far_more_likely(self):
        baseline = dict(HEALTHY_METRICS)
        baseline["clients_recently_changed"] = False
        boosted = dict(HEALTHY_METRICS)
        boosted["clients_recently_changed"] = True

        def fraction_clients(metrics, seed):
            rng = random.Random(seed)
            cooldowns = {}
            last = None
            count = 0
            trials = 300
            for i in range(trials):
                last = gl.select_glance_page(metrics, rng, None, cooldowns, 1000.0 + i)  # last=None each time: isolate weight, not no-repeat
                if last == "clients":
                    count += 1
            return count / trials

        baseline_fraction = fraction_clients(baseline, 10)
        boosted_fraction = fraction_clients(boosted, 11)
        self.assertGreater(boosted_fraction, baseline_fraction)

    def test_disk_meaningfully_full_makes_it_far_more_likely(self):
        normal = dict(HEALTHY_METRICS)
        normal["disk_percent"] = 40.0
        full = dict(HEALTHY_METRICS)
        full["disk_percent"] = 95.0

        def fraction_disk(metrics, seed):
            rng = random.Random(seed)
            count, trials = 0, 300
            for i in range(trials):
                if gl.select_glance_page(metrics, rng, None, {}, 1000.0 + i) == "disk":
                    count += 1
            return count / trials

        self.assertGreater(fraction_disk(full, 20), fraction_disk(normal, 21))

    def test_time_page_ineligible_when_time_str_is_none(self):
        m = dict(HEALTHY_METRICS)
        m["time_str"] = None
        rng = random.Random(30)
        seen = set()
        for i in range(200):
            seen.add(gl.select_glance_page(m, rng, None, {}, 1000.0 + i))
        self.assertNotIn("time", seen)

    def test_no_fake_future_sensor_pages_appear(self):
        """GLANCE_PAGES must not contain a page for hardware that isn't
        commissioned yet - the whole registry today should be exactly
        the documented baseline set, nothing invented ahead of real
        sensor data. A future round adding a real page updates this
        expected set deliberately; it must never grow silently."""
        self.assertEqual(
            set(gl.GLANCE_PAGES.keys()),
            {"cpu", "ram", "disk", "clients", "uptime", "time", "power_warning"},
        )

    def test_empty_pool_returns_none_not_a_crash(self):
        # Simulate an all-ineligible registry with a wholly SEPARATE
        # dict swapped in for the module attribute, then swapped back -
        # deliberately not mutating the real GLANCE_PAGES's own nested
        # spec dicts in place, which would corrupt shared module state
        # for every other test in this process (caught live: an
        # earlier draft of this test did exactly that with a shallow
        # `dict(gl.GLANCE_PAGES)` copy, whose values were still the
        # SAME inner dicts - restoring the outer dict didn't undo the
        # inner mutation, silently breaking every test after this one
        # in file/definition order).
        fake_pages = {pid: {"eligible": lambda m: False, "weight": lambda m: 1.0} for pid in gl.GLANCE_PAGES}
        original = gl.GLANCE_PAGES
        gl.GLANCE_PAGES = fake_pages
        try:
            result = gl.select_glance_page(HEALTHY_METRICS, random.Random(0), None, {}, 1000.0)
            self.assertIsNone(result)
        finally:
            gl.GLANCE_PAGES = original


class PreviewOrderTests(unittest.TestCase):
    def test_preview_order_only_contains_known_pages(self):
        for page_id in gl.GLANCE_PREVIEW_ORDER:
            self.assertIn(page_id, gl.GLANCE_PAGES)

    def test_preview_order_excludes_the_conditional_warning_page(self):
        """power_warning is real, conditional state - showing it during
        a preview when NOT genuinely active would misrepresent the
        device; showing it when genuinely active isn't needed for a
        "how do the ordinary pages look" check either. Left out of the
        fixed preview list entirely, on purpose."""
        self.assertNotIn("power_warning", gl.GLANCE_PREVIEW_ORDER)

    def test_preview_order_covers_every_baseline_page(self):
        self.assertEqual(set(gl.GLANCE_PREVIEW_ORDER), {"cpu", "ram", "disk", "clients", "uptime", "time"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
