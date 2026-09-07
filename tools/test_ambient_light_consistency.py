#!/usr/bin/env python3
"""
Cross-language consistency contract between the two independent
ambient-light classification implementations (2026-09-07):
  - piratebox_glance.py's _classify_ambient_light_label() (OLED glance page)
  - includes/sensors.php's piratebox_classify_ambient_light() (Environment web UI)

These are deliberately kept as two separate implementations rather than
one shared file across Python and PHP (see piratebox_glance.py's own
header comment for why - introducing a shared data file/parser on both
sides for five static boundary numbers was judged more architectural
complexity than it removes). What must never drift is the actual
BOUNDARY VALUES - which lux value falls into which band - even though
the two implementations render different display strings for the top
band ("V.BRIGHT" on the tiny OLED vs "Very Bright" on the web page,
since the full word doesn't fit the OLED's canvas at any legible size).

This test proves the boundaries themselves are identical by asking both
real implementations (not a copy of their logic) to classify the same
set of representative lux values - including every exact boundary - and
comparing which BAND INDEX each one picked (0=Dark/DARK ...
4=Very Bright/V.BRIGHT), not the display text.

Run with: python3 tools/test_ambient_light_consistency.py
Requires: php (already a hard dependency of this whole project).
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import piratebox_glance as gl  # noqa: E402 - path insert must happen first

# Python's OLED-abbreviated labels, in band order.
PYTHON_LABELS_IN_ORDER = ["DARK", "DIM", "INDOOR", "BRIGHT", "V.BRIGHT"]
# PHP's full-word web labels, in the SAME band order.
PHP_LABELS_IN_ORDER = ["Dark", "Dim", "Indoor", "Bright", "Very Bright"]

# Representative values: well inside each band, plus every exact
# boundary from both sides (just below and exactly at each transition) -
# the set most likely to catch an off-by-one/wrong-operator drift
# between the two implementations.
TEST_LUX_VALUES = [0.0, 5.0, 9.9, 10.0, 25.0, 49.9, 50.0, 150.0, 249.9, 250.0, 500.0, 999.9, 1000.0, 5000.0, 100000.0]


def _php_classify(lux: float) -> str:
    php_code = (
        "require '" + str(REPO_ROOT / "var/www/html/includes/sensors.php") + "';"
        f"echo piratebox_classify_ambient_light({lux!r})['label'];"
    )
    result = subprocess.run(["php", "-r", php_code], capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        raise RuntimeError(f"php -r failed for lux={lux}: {result.stderr}")
    return result.stdout.strip()


class CrossLanguageConsistencyTests(unittest.TestCase):
    def test_php_is_reachable_and_returns_a_known_label(self):
        # Sanity check the harness itself before trusting the real
        # comparison below - a silently-broken php invocation must fail
        # loudly here, not manifest as a confusing mismatch elsewhere.
        label = _php_classify(50.0)
        self.assertIn(label, PHP_LABELS_IN_ORDER)

    def test_every_representative_lux_value_lands_in_the_same_band(self):
        for lux in TEST_LUX_VALUES:
            with self.subTest(lux=lux):
                python_label = gl._classify_ambient_light_label(lux)
                php_label = _php_classify(lux)
                self.assertIn(python_label, PYTHON_LABELS_IN_ORDER, f"unrecognized Python label {python_label!r}")
                self.assertIn(php_label, PHP_LABELS_IN_ORDER, f"unrecognized PHP label {php_label!r}")
                python_band = PYTHON_LABELS_IN_ORDER.index(python_label)
                php_band = PHP_LABELS_IN_ORDER.index(php_label)
                self.assertEqual(
                    python_band, php_band,
                    f"lux={lux}: Python classified as {python_label!r} (band {python_band}) "
                    f"but PHP classified as {php_label!r} (band {php_band}) - the two "
                    "implementations' boundaries have drifted apart",
                )


if __name__ == "__main__":
    unittest.main()
