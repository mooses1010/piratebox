#!/usr/bin/env python3
"""
Regression test for a live openwebrx.service outage (2026-09-06,
docs/RADIO-SDR-ARCHITECTURE-DESIGN.md section 16): after the operator
ran tools/update_openwebrx_config.sh, the service crash-looped with

    ValueError: Configuration version is too high (current: 8, found: 9)

Root cause, confirmed by reading the installed source directly, not
guessed: OpenWebRX+'s owrx/config/classic.py loads
etc/openwebrx/sdrs_seed.py as a plain Python module
(ClassicConfig._loadPythonFile), then calls Migrator.migrate(pm)
(owrx/config/migration.py), which reads this file's own top-level
"version" integer and raises exactly this error the instant it exceeds
Migrator.currentVersion - a constant HARD-CODED in the installed
package (currentVersion = 8 for this project's pinned OpenWebRX+
v1.2.123 / commit 2d60e894...). Two earlier commits
(209a82d, then e499b44) had each bumped this file's "version" field
while adding unrelated settings (magic_key/max_clients, then
tuning_step) as if it were a "content changed" revision counter - the
first bump (7->8) happened to land exactly on the installed ceiling and
was harmless by coincidence; the second (8->9) exceeded it and broke
the live service the moment it was actually deployed.

This test exists so that mistake - bumping "version" for any reason
other than a genuine, verified change to the installed OpenWebRX+'s own
migration ceiling - can never again reach a live deploy unnoticed.

Two layers of protection, mirroring tools/test_hostapd_recovery_config.py's
own "static assertion + real-class verification" pattern from this
project's history:

  1. A static assertion against the known-correct ceiling for the
     exact OPENWEBRX_COMMIT this project currently pins (update
     EXPECTED_VERSION deliberately, alongside re-verifying it against
     the newly-installed owrx/config/migration.py, if that commit is
     ever bumped - never bump it just because this seed file's content
     changed).
  2. A best-effort DYNAMIC check, skipped gracefully if the real
     OpenWebRX+ venv isn't present in this test environment (e.g. CI
     without the Pi's install): imports the actual installed
     owrx.config.classic.ClassicConfig and owrx.config.migration.Migrator
     classes and replicates the exact real load path
     (_loadPythonFile -> Migrator.migrate) against this repo's own
     sdrs_seed.py - the same technique used to verify this exact fix
     before asking the operator to redeploy it. This is strictly
     stronger than the static check: it fails the same way the live
     service actually failed, using the real installed code, not a
     hardcoded assumption about what that code does.
"""
import importlib.util
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SDRS_SEED = REPO_ROOT / "etc" / "openwebrx" / "sdrs_seed.py"
INSTALL_SCRIPT = REPO_ROOT / "tools" / "install_openwebrx.sh"

# The Migrator.currentVersion this project's pinned OPENWEBRX_COMMIT is
# known (by reading its installed owrx/config/migration.py directly on
# the live Pi) to expect. Update this ONLY alongside a deliberate
# OPENWEBRX_COMMIT bump and a fresh read of the new commit's own
# migration.py - never to "fix" a test failure without doing that.
EXPECTED_VERSION = 8

OWRX_VENV_SITE_PACKAGES = "/opt/openwebrx/venv/lib/python3.13/site-packages"


def _load_pm(path):
    """Mirrors owrx/config/classic.py's ClassicConfig._loadPythonFile,
    without needing the real class (used as a fallback when the real
    venv isn't importable, so the static test below still parses the
    file the same way OpenWebRX+ itself does: exec as a module, collect
    top-level names)."""
    spec = importlib.util.spec_from_file_location("config_webrx_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {k: v for k, v in vars(module).items() if not k.startswith("__")}


class TestConfigVersionStatic(unittest.TestCase):
    def test_declared_version_matches_known_good_ceiling(self):
        config = _load_pm(str(SDRS_SEED))
        self.assertIn("version", config, "sdrs_seed.py has no top-level 'version' field")
        self.assertEqual(
            config["version"],
            EXPECTED_VERSION,
            "etc/openwebrx/sdrs_seed.py declares version={} but this project's "
            "pinned OpenWebRX+ (OPENWEBRX_COMMIT in tools/install_openwebrx.sh) "
            "expects exactly {} (owrx/config/migration.py's Migrator."
            "currentVersion) - deploying this WILL crash-loop openwebrx.service "
            "with 'Configuration version is too high', exactly as it did on "
            "2026-09-06. This field is a schema-migration marker tied to the "
            "installed package, not a content-revision counter - do not bump "
            "it when only adding/changing plain settings.".format(
                config["version"], EXPECTED_VERSION
            ),
        )

    def test_pinned_commit_unchanged_since_this_ceiling_was_verified(self):
        text = INSTALL_SCRIPT.read_text()
        match = re.search(r'OPENWEBRX_COMMIT="([0-9a-f]{40})"', text)
        self.assertIsNotNone(match, "could not find OPENWEBRX_COMMIT pin in install script")
        # This is the exact commit EXPECTED_VERSION above was verified
        # against (docs/RADIO-SDR-ARCHITECTURE-DESIGN.md section 16). If
        # this fails, OPENWEBRX_COMMIT has been bumped without
        # re-verifying/re-deriving EXPECTED_VERSION from the new
        # commit's own migration.py - fix EXPECTED_VERSION deliberately,
        # don't just update this constant to silence the test.
        self.assertEqual(
            match.group(1),
            "2d60e894d0889382d2eb0574a19f027f8504dcfa",
            "OPENWEBRX_COMMIT changed - re-verify EXPECTED_VERSION above against "
            "the new commit's own owrx/config/migration.py before updating this "
            "test, don't assume it's still 8",
        )


@unittest.skipUnless(
    Path(OWRX_VENV_SITE_PACKAGES).is_dir(),
    "real OpenWebRX+ venv not present in this environment - static check above still applies",
)
class TestConfigVersionAgainstRealInstalledMigrator(unittest.TestCase):
    """Strongest available check: replicates the exact real code path
    that crashed the live service, using the actual installed classes,
    against this repo's own sdrs_seed.py - not a hardcoded assumption."""

    def setUp(self):
        if OWRX_VENV_SITE_PACKAGES not in sys.path:
            sys.path.insert(0, OWRX_VENV_SITE_PACKAGES)

    def test_real_migrator_accepts_repo_config_without_raising(self):
        from owrx.config.classic import ClassicConfig
        from owrx.config.migration import Migrator

        pm = ClassicConfig._loadPythonFile(str(SDRS_SEED))
        # This is the literal call that crash-looped the live service on
        # 2026-09-06 - if it raises here, the fix has regressed.
        try:
            Migrator.migrate(pm)
        except ValueError as e:
            self.fail(
                f"Migrator.migrate() raised against the repo's own sdrs_seed.py: {e} "
                "- this is the exact failure that took openwebrx.service down live; "
                "do not deploy this file."
            )

    def test_real_installed_ceiling_matches_static_expectation(self):
        from owrx.config.migration import Migrator

        self.assertEqual(
            Migrator.currentVersion,
            EXPECTED_VERSION,
            f"the REAL installed Migrator.currentVersion is {Migrator.currentVersion}, "
            f"but this test file's EXPECTED_VERSION constant says {EXPECTED_VERSION} - "
            "the installed OpenWebRX+ was upgraded/changed independently of "
            "OPENWEBRX_COMMIT; reconcile both before trusting either.",
        )


if __name__ == "__main__":
    unittest.main()
