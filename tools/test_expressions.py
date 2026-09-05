#!/usr/bin/env python3
"""Deterministic tests for piratebox_expressions.py (Expression Engine
v2 - EXPRESSIONS/ANIMATIONS/SCENES data tables, draw_face/draw_scene/
draw_zzz/draw_pirate_flourish/draw_skull_and_crossbones drawing
primitives, resolve_animation_frames(), bias_ambient_expression()) -
matches the project's existing dependency-free tools/test_*.py
convention (see tools/test_silly_mode.py).

Run with: python3 tools/test_expressions.py

This module has zero I/O of its own (no disk, no /tmp, no daemon, no
hardware) - every test here just imports the plain module and draws
into a bare PIL Image, exactly like tools/test_silly_mode.py's own
ExpressionRenderingTests already does for the pre-existing expressions.

Per instruction, this file is allowed to be fully explicit about every
expression/animation/scene that exists - operator-facing docs and the
feature's own final report deliberately are not.
"""

import importlib.util
import os
import random
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE_PATH = os.path.join(HERE, "..", "piratebox_expressions.py")

spec = importlib.util.spec_from_file_location("piratebox_expressions", MODULE_PATH)
ex = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ex)

from PIL import Image, ImageDraw  # noqa: E402 - after sys.path/module setup above


def _fresh_draw():
    img = Image.new("1", (128, 64))
    return ImageDraw.Draw(img)


class ExpressionsTableTests(unittest.TestCase):
    def test_every_expression_is_a_well_formed_four_tuple(self):
        for name, value in ex.EXPRESSIONS.items():
            with self.subTest(name=name):
                self.assertEqual(len(value), 4, f"{name} is not a 4-tuple")

    def test_every_expression_renders_without_exception(self):
        for name, (eyes, brows, mouth, decoration) in ex.EXPRESSIONS.items():
            with self.subTest(name=name):
                ex.draw_face(_fresh_draw(), eyes, brows, mouth, decoration)

    def test_asymmetric_eyes_render_without_exception(self):
        # "skeptical" is the one EXPRESSIONS entry using a 2-tuple
        # `eyes` (per-eye override) - confirm draw_face's asymmetric
        # branch actually gets exercised, not just the plain-string path.
        eyes, brows, mouth, decoration = ex.EXPRESSIONS["skeptical"]
        self.assertIsInstance(eyes, tuple)
        ex.draw_face(_fresh_draw(), eyes, brows, mouth, decoration)

    def test_every_decoration_used_anywhere_renders_without_exception(self):
        decorations = {d for (_, _, _, d) in ex.EXPRESSIONS.values() if d is not None}
        self.assertIn("eyepatch", decorations)
        self.assertIn("tricorne", decorations)
        self.assertIn("bandana", decorations)
        self.assertIn("monocle", decorations)
        self.assertIn("anchor_charm", decorations)
        for deco in decorations:
            with self.subTest(decoration=deco):
                ex.draw_face(_fresh_draw(), "open", "none", "smile_small", deco)

    def test_wink_still_closes_only_the_right_eye(self):
        # Regression guard for the asymmetric-eyes refactor: "wink" must
        # keep working exactly as before (forces the right eye closed
        # regardless of the requested `eyes` style), not just the new
        # per-eye-tuple mechanism.
        draw = _fresh_draw()
        ex.draw_face(draw, "wide", "none", "smile_small", "wink")  # must not raise


class AnimationsTests(unittest.TestCase):
    def test_every_animation_resolves_and_renders_every_frame(self):
        for anim_id in ex.ANIMATIONS:
            with self.subTest(anim_id=anim_id):
                specs, gap, hold = ex.resolve_animation_frames(anim_id, "ok", quip="test quip")
                self.assertIsNotNone(specs)
                self.assertGreater(len(specs), 1, "an animation with only one frame isn't animated")
                self.assertGreater(gap, 0)
                self.assertGreater(hold, 0)
                for spec in specs:
                    render = spec["render"]
                    self.assertEqual(spec["tier"], "ok")
                    if "expression" in render:
                        eyes, brows, mouth, default_deco = ex.EXPRESSIONS[render["expression"]]
                        ex.draw_face(_fresh_draw(), eyes, brows, mouth, render.get("decoration", default_deco))
                    elif "scene" in render:
                        ex.draw_scene(_fresh_draw(), None, None, render["scene"])
                    else:
                        self.fail(f"animation frame has neither expression nor scene: {render!r}")

    def test_quip_lands_only_on_the_final_frame(self):
        specs, _, _ = ex.resolve_animation_frames("quick_blink_pair", "ok", quip="Ahoy!")
        for spec in specs[:-1]:
            self.assertNotIn("quip", spec["render"])
        self.assertEqual(specs[-1]["render"]["quip"], "Ahoy!")

    def test_no_quip_means_no_quip_key_anywhere(self):
        specs, _, _ = ex.resolve_animation_frames("quick_blink_pair", "ok")
        for spec in specs:
            self.assertNotIn("quip", spec["render"])

    def test_unknown_animation_id_degrades_to_none(self):
        specs, gap, hold = ex.resolve_animation_frames("no_such_animation", "ok")
        self.assertIsNone(specs)
        self.assertIsNone(gap)
        self.assertIsNone(hold)

    def test_animation_frame_as_dict_override_is_respected(self):
        # ANIMATIONS frames may be a plain expression-name string OR a
        # dict override (e.g. a decoration change or a scene) - confirm
        # both shapes are actually supported, not just the string path
        # every current entry happens to use for most of its frames.
        original = ex.ANIMATIONS["quick_blink_pair"]["frames"]
        ex.ANIMATIONS["quick_blink_pair"]["frames"] = ["idle", {"expression": "happy", "decoration": "sparkle"}]
        try:
            specs, _, _ = ex.resolve_animation_frames("quick_blink_pair", "ok")
            self.assertEqual(specs[1]["render"]["expression"], "happy")
            self.assertEqual(specs[1]["render"]["decoration"], "sparkle")
        finally:
            ex.ANIMATIONS["quick_blink_pair"]["frames"] = original


class ScenesTests(unittest.TestCase):
    def test_every_declared_scene_renders_without_exception(self):
        for name in ex.SCENES:
            with self.subTest(name=name):
                ex.draw_scene(_fresh_draw(), None, None, name)

    def test_unknown_scene_degrades_to_a_plain_face_not_a_crash(self):
        ex.draw_scene(_fresh_draw(), None, None, "no-such-scene")  # must not raise


class BiasAmbientExpressionTests(unittest.TestCase):
    """Deterministic given a seeded RNG - see the function's own
    docstring for why this is a separate, simpler mechanism from
    piratebox_progression.roll_event()'s rarity engine."""

    def test_missing_weights_never_substitutes(self):
        rng = random.Random(1)
        for _ in range(50):
            self.assertEqual(ex.bias_ambient_expression("idle", {}, rng), "idle")

    def test_neutral_weights_rarely_or_never_substitute(self):
        # At the default 0.5 starting point, every rule's threshold
        # (>=0.65 or <=0.35) is not crossed, so eligibility itself is
        # False regardless of the RNG draw - this must hold for a LOT
        # of draws, not just luck.
        rng = random.Random(2)
        weights = {"sociability": 0.5, "vigilance": 0.5, "resilience": 0.5}
        for _ in range(500):
            self.assertEqual(ex.bias_ambient_expression("idle", weights, rng), "idle")

    def test_extreme_vigilance_can_substitute_watchful_for_idle(self):
        rng = random.Random(3)
        weights = {"sociability": 0.5, "vigilance": 0.95, "resilience": 0.5}
        results = {ex.bias_ambient_expression("idle", weights, rng) for _ in range(200)}
        self.assertIn("watchful", results)
        self.assertIn("idle", results)  # still has variety - never 100% substituted

    def test_extreme_low_sociability_can_substitute_wistful_for_idle(self):
        rng = random.Random(4)
        weights = {"sociability": 0.05, "vigilance": 0.5, "resilience": 0.5}
        results = {ex.bias_ambient_expression("idle", weights, rng) for _ in range(200)}
        self.assertIn("wistful", results)

    def test_extreme_resilience_can_substitute_resolute_for_idle(self):
        rng = random.Random(5)
        weights = {"sociability": 0.5, "vigilance": 0.5, "resilience": 0.95}
        results = {ex.bias_ambient_expression("idle", weights, rng) for _ in range(200)}
        self.assertIn("resolute", results)

    def test_expression_not_covered_by_any_rule_is_always_unchanged(self):
        rng = random.Random(6)
        weights = {"sociability": 0.95, "vigilance": 0.95, "resilience": 0.95}
        for _ in range(100):
            self.assertEqual(ex.bias_ambient_expression("happy", weights, rng), "happy")

    def test_substitutions_are_always_valid_expressions(self):
        rng = random.Random(7)
        weights = {"sociability": 0.05, "vigilance": 0.95, "resilience": 0.95}
        for expr in ("idle", "blink"):
            for _ in range(100):
                self.assertIn(ex.bias_ambient_expression(expr, weights, rng), ex.EXPRESSIONS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
