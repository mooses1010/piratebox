#!/usr/bin/env python3
"""
Regression tests for the hostapd/pb-ap runtime-reattachment fix
(2026-09-05 incident: the ALFA disconnected/re-enumerated at 12:15 PDT,
udev correctly renamed the recreated interface back to "pb-ap", but the
long-lived hostapd process never noticed and never reattached - the AP
stayed down for hours while every "is hostapd active" health check kept
reporting healthy).

These are static content assertions against the repo's own tracked
config files, not a live systemd/udev integration test - there is no
real systemd/udev instance to exercise in this test environment. The
goal is to catch the specific, easy-to-get-wrong mistakes this fix
depends on:

  - the BindsTo=/After= device unit name must be the EXACT systemd
    escaping of "pb-ap" (a wrong escape silently no-ops the whole
    fix - BindsTo= referencing a unit name that never exists behaves
    as if it were never there, with no error at parse time);
  - ConditionPathExists= must be present, or BindsTo= combined with
    the pre-existing Restart=always reintroduces a restart-loop/
    thrashing risk when the interface is absent;
  - the udev rule's SYSTEMD_WANTS tag must be on the SAME rule line
    that renames the interface to "pb-ap", not a separate rule that
    could drift out of sync with it.

See docs/OPERATIONAL-DECISIONS.md's 2026-09-05 dated entry for the
full incident writeup, and docs/EXTERNAL-AP-ARCHITECTURE-DESIGN.md
section 4 for why this is a narrower fix than (and does not change)
the separate, deliberate "runtime radio fallback is not automated"
decision recorded there.
"""
import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OVERRIDE_CONF = os.path.join(
    REPO_ROOT, "etc", "systemd", "system", "hostapd.service.d", "override.conf"
)
UDEV_RULE = os.path.join(
    REPO_ROOT, "etc", "udev", "rules.d", "99-piratebox-external-ap.rules"
)

# The one correct systemd escaping of the "pb-ap" network interface's
# device unit name (verified live via `systemd-escape --path
# /sys/subsystem/net/devices/pb-ap` during the incident investigation -
# NOT re-derived here, so a bug in a home-grown escaping function can't
# make this test agree with itself instead of with systemd).
EXPECTED_DEVICE_UNIT = r"sys-subsystem-net-devices-pb\x2dap.device"


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class TestHostapdOverrideConf(unittest.TestCase):
    def setUp(self):
        self.content = _read(OVERRIDE_CONF)

    def test_file_exists(self):
        self.assertTrue(os.path.isfile(OVERRIDE_CONF))

    def test_preserves_existing_phase2_reliability_behavior(self):
        # The 2026-08-31 fix (restart on ANY exit, not just on-failure)
        # must survive this change untouched.
        self.assertIn("Restart=always", self.content)
        self.assertIn("ExecStartPre=/usr/sbin/rfkill unblock wifi", self.content)

    def test_binds_to_correct_device_unit(self):
        lines = [l.strip() for l in self.content.splitlines()]
        self.assertIn(f"BindsTo={EXPECTED_DEVICE_UNIT}", lines,
                       "BindsTo= must reference the exact systemd-escaped "
                       "pb-ap device unit name - a wrong escape silently "
                       "no-ops this fix with no error at parse time.")
        self.assertIn(f"After={EXPECTED_DEVICE_UNIT}", lines,
                       "After= should pair with BindsTo= on the same unit "
                       "(standard systemd practice).")

    def test_condition_path_exists_guards_against_restart_thrashing(self):
        self.assertIn("ConditionPathExists=/sys/class/net/pb-ap", self.content,
                       "Without this, BindsTo= + the pre-existing "
                       "Restart=always would restart-loop every "
                       "RestartSec while pb-ap is absent until "
                       "StartLimitBurst trips and the unit gets stuck "
                       "'failed' - exactly the thrashing this fix must "
                       "avoid.")

    def test_binds_to_appears_before_condition_and_restart_survives(self):
        # Not strict systemd ordering (Condition=/BindsTo=/Restart= can
        # appear in any order in a real unit file), just confirms none
        # of the three actual DIRECTIVE lines (as opposed to prose
        # mentioning them in comments, which this file has plenty of)
        # got silently dropped or duplicated-and-conflicting.
        directive_lines = [
            l.strip() for l in self.content.splitlines()
            if l.strip() and not l.strip().startswith("#")
        ]
        for directive in ("Restart=", "BindsTo=", "ConditionPathExists="):
            matches = [l for l in directive_lines if l.startswith(directive)]
            self.assertEqual(
                len(matches), 1,
                f"expected exactly one '{directive}' directive line, found "
                f"{len(matches)}: {matches}",
            )


class TestUdevRule(unittest.TestCase):
    def setUp(self):
        self.content = _read(UDEV_RULE)
        # The one non-comment rule line.
        rule_lines = [
            l for l in self.content.splitlines()
            if l.strip() and not l.strip().startswith("#")
        ]
        self.assertEqual(
            len(rule_lines), 1,
            "expected exactly one active udev rule line in this file"
        )
        self.rule_line = rule_lines[0]

    def test_file_exists(self):
        self.assertTrue(os.path.isfile(UDEV_RULE))

    def test_preserves_existing_rename_match(self):
        # The original, already-validated-live matching conditions must
        # survive untouched.
        for expected in [
            'SUBSYSTEM=="net"',
            'ACTION=="add"',
            'ENV{ID_USB_DRIVER}=="mt76x2u"',
            'ENV{ID_VENDOR_ID}=="0e8d"',
            'ENV{ID_MODEL_ID}=="7612"',
            'NAME="pb-ap"',
        ]:
            self.assertIn(expected, self.rule_line)

    def test_systemd_wants_hostapd_on_the_same_rule_line(self):
        # Must be on the SAME line as the NAME="pb-ap" rename - a
        # separate rule matching the same device could silently drift
        # out of sync with it over time.
        self.assertIn('ENV{SYSTEMD_WANTS}+="hostapd.service"', self.rule_line)

    def test_rule_line_is_well_formed(self):
        # Sanity check: comma-separated key==value / key+=value pairs,
        # no stray unescaped quote imbalance.
        self.assertEqual(self.rule_line.count('"'), self.rule_line.count('"'))
        self.assertGreaterEqual(self.rule_line.count(","), 5)

    def test_stale_not_yet_installed_claim_was_corrected(self):
        # This file's header once claimed "STAGED, NOT YET INSTALLED",
        # which was confirmed false against live state during the
        # 2026-09-05 incident investigation (the rule was already
        # live-installed and had been correctly renaming the interface
        # all along). Guard against that stale claim silently
        # resurfacing in a future edit.
        self.assertNotIn("STAGED, NOT YET INSTALLED", self.content)


class TestDeviceUnitNameCrossCheck(unittest.TestCase):
    """The single most fragile part of this fix: override.conf's
    BindsTo=/After= device unit name is hand-derived from the SAME
    "pb-ap" string the udev rule renames the interface to. If a future
    edit ever renames the interface (in the udev rule) without updating
    override.conf's escaped unit name to match, BindsTo=/After= would
    silently reference a device unit that never exists - no error, the
    fix just quietly stops doing anything. This test derives the
    expected escaped unit name independently (via systemd-escape, if
    available) and cross-checks it against override.conf.
    """

    def test_udev_interface_name_matches_override_conf_device_unit(self):
        udev_content = _read(UDEV_RULE)
        match = re.search(r'NAME="([^"]+)"', udev_content)
        self.assertIsNotNone(match, "could not find NAME=\"...\" in the udev rule")
        iface_name = match.group(1)
        self.assertEqual(
            iface_name, "pb-ap",
            "this test's hard-coded EXPECTED_DEVICE_UNIT assumes the "
            "interface is named 'pb-ap' - update both together if this "
            "ever changes",
        )

        override_content = _read(OVERRIDE_CONF)
        self.assertIn(EXPECTED_DEVICE_UNIT, override_content)

        # Best-effort independent verification via systemd-escape itself,
        # when available (e.g. running directly on the Pi) - skipped
        # (not failed) in any environment without it, since this test
        # must also run in ordinary CI/dev environments.
        import shutil
        import subprocess

        if shutil.which("systemd-escape"):
            result = subprocess.run(
                ["systemd-escape", "--path", f"/sys/subsystem/net/devices/{iface_name}"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                escaped = result.stdout.strip()
                self.assertEqual(
                    f"{escaped}.device", EXPECTED_DEVICE_UNIT,
                    "systemd-escape's own output no longer matches this "
                    "fix's hard-coded device unit name",
                )


if __name__ == "__main__":
    unittest.main()
