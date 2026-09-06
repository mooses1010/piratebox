#!/usr/bin/env python3
"""
Regression tests for the OpenWebRX+ native band plan ribbon deployment
(2026-09-06, docs/RADIO-SDR-ARCHITECTURE-DESIGN.md section 14.3/15):
OpenWebRX+'s own owrx/bands.py feature was found fully wired up but
dataless on this install - its bands.json data file was never copied
from the OpenWebRX+ source tree into /etc/openwebrx/ during setup. The
fix vendors that exact upstream file into this repo
(etc/openwebrx/upstream/bands.json) and wires both
tools/install_openwebrx.sh (fresh installs) and
tools/update_openwebrx_config.sh (existing installs) to deploy it, so a
future install/update doesn't silently regress back to "no band
labels" the way the original install did.

These are static content/text assertions against the repo's own
tracked files - there is no live OpenWebRX+ service to exercise in this
test environment (see tools/test_hostapd_recovery_config.py for the
same style/rationale). The goal is to catch the specific mistakes that
would silently break this feature without any install-time error:

  - the vendored bands.json must still be present, valid JSON, and
    shaped the way owrx/bands.py's own Band class expects (a list of
    dicts, each with "name"/"lower_bound"/"upper_bound") - a malformed
    or truncated file fails silently server-side (owrx/bands.py logs
    and falls back to an empty band list, matching the exact "loaded
    but empty" pattern this fix was written to escape) rather than
    crashing anything, so nothing else would catch this;
  - it must not have been hand-edited into a different file than what
    it claims to vendor - checked via a content hash, not just
    "the file exists" (a good-faith edit here would quietly turn
    "vendored upstream data" into undocumented PirateBox-authored data,
    contradicted by etc/openwebrx/upstream/README.md's own provenance
    claim);
  - both installer scripts must actually copy it to the exact path
    owrx/bands.py's own _loadBands() checks first
    (/etc/openwebrx/bands.json, for bandplan_region=0) - a copy to the
    wrong path, or a copy that silently got removed in a later edit,
    would reproduce the original "wired up but dataless" bug on a
    fresh install with no error anywhere;
  - this project's privacy-motivated receiver_gps=(0,0) (see section
    14.2 - a real GPS coordinate would enable location-dependent
    repeater markers/Travel Mode leakage) must remain unchanged by this
    round's work, since the band plan feature itself has no such
    dependency and this fix must not quietly reopen that question.

See docs/RADIO-SDR-ARCHITECTURE-DESIGN.md section 14 (investigation)
and section 15 (this implementation) for the full writeup.
"""
import hashlib
import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BANDS_JSON = REPO_ROOT / "etc" / "openwebrx" / "upstream" / "bands.json"
UPSTREAM_README = REPO_ROOT / "etc" / "openwebrx" / "upstream" / "README.md"
INSTALL_SCRIPT = REPO_ROOT / "tools" / "install_openwebrx.sh"
UPDATE_SCRIPT = REPO_ROOT / "tools" / "update_openwebrx_config.sh"
SDRS_SEED = REPO_ROOT / "etc" / "openwebrx" / "sdrs_seed.py"

# sha256 of the exact upstream bands.json this round vendored, from
# luarvique/openwebrx commit 2d60e894d0889382d2eb0574a19f027f8504dcfa
# (matching OPENWEBRX_COMMIT in tools/install_openwebrx.sh at the time
# this file was vendored) - confirmed identical to
# /opt/openwebrx/src/openwebrx/bands.json on the live Pi via sha256sum.
# Update this alongside a deliberate re-sync (see the README's own
# "Keeping this in sync" section) - this constant exists to catch an
# ACCIDENTAL hand-edit, not to block an intentional upstream refresh.
EXPECTED_SHA256 = "acce2f7dd7e4bdae5f9012af284f57d211925a9f15321c5155e0c612bb3856c4"


class TestVendoredBandsJson(unittest.TestCase):
    def test_file_exists(self):
        self.assertTrue(BANDS_JSON.is_file(), f"missing {BANDS_JSON}")

    def test_matches_recorded_upstream_hash(self):
        digest = hashlib.sha256(BANDS_JSON.read_bytes()).hexdigest()
        self.assertEqual(
            digest,
            EXPECTED_SHA256,
            "etc/openwebrx/upstream/bands.json no longer matches the recorded "
            "upstream hash - either it was hand-edited (don't - see its "
            "README.md) or it was deliberately re-synced to a newer "
            "OpenWebRX+ commit (update EXPECTED_SHA256 above to match, "
            "alongside the README's provenance/commit notes)",
        )

    def test_valid_json_list_of_bands(self):
        data = json.loads(BANDS_JSON.read_text())
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        for band in data:
            self.assertIn("name", band)
            self.assertIn("lower_bound", band)
            self.assertIn("upper_bound", band)
            self.assertLess(band["lower_bound"], band["upper_bound"])

    def test_provenance_readme_present(self):
        self.assertTrue(UPSTREAM_README.is_file())
        text = UPSTREAM_README.read_text()
        # Must actually claim upstream provenance, not just exist.
        self.assertIn("luarvique/openwebrx", text)
        self.assertIn("not PirateBox-authored", text)


class TestInstallerScriptsDeployBandplan(unittest.TestCase):
    def test_install_script_copies_bands_json_to_expected_path(self):
        text = INSTALL_SCRIPT.read_text()
        self.assertIn(
            'etc/openwebrx/upstream/bands.json" /etc/openwebrx/bands.json',
            text,
            "tools/install_openwebrx.sh no longer deploys the vendored "
            "bands.json to /etc/openwebrx/bands.json - a fresh install "
            "would regress to the original 'wired up but dataless' bug",
        )

    def test_update_script_copies_bands_json_to_expected_path(self):
        text = UPDATE_SCRIPT.read_text()
        self.assertIn(
            'etc/openwebrx/upstream/bands.json" /etc/openwebrx/bands.json',
            text,
            "tools/update_openwebrx_config.sh no longer deploys the vendored "
            "bands.json - an existing install applying config updates "
            "would never pick up the band plan fix",
        )

    def test_pinned_commit_matches_vendored_readme(self):
        install_text = INSTALL_SCRIPT.read_text()
        match = re.search(r'OPENWEBRX_COMMIT="([0-9a-f]{40})"', install_text)
        self.assertIsNotNone(match, "could not find OPENWEBRX_COMMIT pin in install script")
        readme_text = UPSTREAM_README.read_text()
        self.assertIn(
            match.group(1),
            readme_text,
            "the pinned OPENWEBRX_COMMIT in tools/install_openwebrx.sh no "
            "longer matches the commit recorded in "
            "etc/openwebrx/upstream/README.md - the vendored bands.json "
            "may be stale relative to whatever OpenWebRX+ commit a fresh "
            "install would actually build (see the README's 'Keeping this "
            "in sync' section)",
        )


class TestReceiverGpsUnchanged(unittest.TestCase):
    """This round's own stop condition: do not enable location-dependent
    repeater functionality by exposing a real location. The band plan
    feature has no receiver_gps dependency at all - this guards against
    that boundary being blurred by a future edit to this same file."""

    def test_receiver_gps_still_zeroed(self):
        text = SDRS_SEED.read_text()
        match = re.search(r'receiver_gps\s*=\s*\{([^}]*)\}', text)
        self.assertIsNotNone(match, "could not find receiver_gps in sdrs_seed.py")
        body = match.group(1)
        self.assertIn('"lat": 0', body.replace("'", '"'))
        self.assertIn('"lon": 0', body.replace("'", '"'))


if __name__ == "__main__":
    unittest.main()
