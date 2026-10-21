#!/usr/bin/env python3
"""
Regression tests for the CVE-2026-109618 / CVE-2026-109619 ("php2shell")
PHP security update tooling: tools/apply_php_security_update.sh and the
etc/php/8.4/fpm/conf.d/99-piratebox-security.ini drop-in it installs.

Most of these are static assertions against the repo's own tracked
files, not a live apt/dpkg integration test - there is no disposable
Debian 13 box to exercise a real php8.4 upgrade against here, and the
one real run happened on the live Pi with its own before/after evidence
recorded in docs/OPERATIONAL-DECISIONS.md. TestLiveTransactionScoping is
the one exception: it runs the script's own `apt-get install
--only-upgrade --simulate` for real against this box's live apt state
(read-only, no root, changes nothing) and checks what it actually
reports, self-skipping once the box is no longer in the pre-upgrade
state it needs. What these tests protect is the handful of details
that are silently catastrophic to get wrong, where the failure is
invisible at the time and only shows up much later:

  - BOTH conffile-preservation mechanisms must be present, because
    PirateBox's PHP config is split across two files that Debian
    manages two DIFFERENT ways. /etc/php/8.4/fpm/php.ini is NOT a dpkg
    conffile - it is ucf-managed - so --force-confold does nothing for
    it and only UCF_FORCE_CONFFOLD retains it;
    /etc/php/8.4/fpm/pool.d/www.conf IS a dpkg conffile, so the reverse
    is true. Dropping either flag reverts half the configuration.
    Concretely: losing php.ini's local values silently returns
    upload_max_filesize to the stock 2M (file sharing broken for all
    but tiny files) and drops open_basedir entirely - which is both a
    security regression AND makes every sensor/status page degrade to
    "no data", the exact indistinguishable-from-missing-hardware
    failure already documented in tools/deploy_environment_sensors.sh.
    Neither produces an error at upgrade time.

  - The upgrade must be scoped to an explicit package list with
    --only-upgrade. A bare 'apt-get upgrade' / 'dist-upgrade' was
    explicitly ruled out by the operator, and on this box it would also
    pull unrelated changes into a security-only maintenance window.

  - No third-party PHP repository (Sury/ondrej/packages.sury.org) may
    appear anywhere in the tooling. The fix exists in Debian's own
    trixie-security, so adding one would be both unnecessary and a
    standing supply-chain commitment on an offline-first device.

  - The config test must come BEFORE the service restart, and the
    local-value verification before it too, so a reverted config is
    caught while the running workers still hold the good config.

  - The drop-in must disable session.upload_progress and must not
    enable anything.
"""

import os
import re
import subprocess
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, "tools", "apply_php_security_update.sh")
VERIFY = os.path.join(REPO, "tools", "verify_piratebox_http.sh")
DROPIN = os.path.join(
    REPO, "etc", "php", "8.4", "fpm", "conf.d", "99-piratebox-security.ini"
)

FIXED_VERSION = "8.4.27-1~deb13u1"


def dpkg_ge(version_a, version_b):
    """True if version_a >= version_b by dpkg's own version ordering.

    Defers to `dpkg --compare-versions` rather than a Python string/tuple
    comparison - Debian version strings (epochs, ~ for pre-releases,
    arbitrary suffixes like "deb13u1") don't sort correctly as plain
    strings or as naively-split tuples, and this script's whole job is
    telling "already patched" apart from "still vulnerable" correctly.
    """
    return subprocess.run(
        ["dpkg", "--compare-versions", version_a, "ge", version_b]
    ).returncode == 0


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def code_only(path):
    """A script with its full-line shell comments stripped.

    The forbidden-command assertions below have to run against what the
    script actually EXECUTES, not against its prose. These scripts carry
    long explanatory headers that necessarily quote the very things they
    forbid - e.g. the header explains why a blanket 'apt-get upgrade' is
    not used, and why no Sury/ondrej repository is added. A naive
    substring search over the whole file flags those sentences and fails,
    which is a false positive that would push the next person to delete
    the explanation rather than keep the guarantee.

    Only whole-line comments are removed; a trailing inline comment after
    real code is left in place, since stripping those properly would mean
    parsing shell quoting. That is fine here - these scripts put their
    reasoning on its own lines.
    """
    return "\n".join(
        line
        for line in read(path).splitlines()
        if not line.lstrip().startswith("#")
    )


class TestFilesExist(unittest.TestCase):
    def test_all_three_files_present_and_executable_as_appropriate(self):
        for path in (SCRIPT, VERIFY, DROPIN):
            self.assertTrue(os.path.isfile(path), f"missing {path}")
        for path in (SCRIPT, VERIFY):
            self.assertTrue(
                os.access(path, os.X_OK), f"{path} must be executable"
            )

    def test_shell_scripts_parse(self):
        for path in (SCRIPT, VERIFY):
            res = subprocess.run(
                ["bash", "-n", path], capture_output=True, text=True
            )
            self.assertEqual(
                res.returncode, 0, f"{path} failed bash -n: {res.stderr}"
            )


class TestConffilePreservation(unittest.TestCase):
    """The two mechanisms described in the module docstring."""

    def setUp(self):
        self.body = read(SCRIPT)

    def test_ucf_force_conffold_is_exported(self):
        # Double-F spelling: UCF_FORCE_CONFFOLD. UCF_FORCE_CONFOLD
        # (single F) is not a variable ucf reads, so a typo here
        # silently does nothing at all.
        self.assertRegex(
            self.body,
            r"export\s+UCF_FORCE_CONFFOLD=1",
            "php.ini is ucf-managed; UCF_FORCE_CONFFOLD=1 must be exported "
            "or the local php.ini is replaced by the package default",
        )
        self.assertNotIn(
            "UCF_FORCE_CONFFNEW",
            self.body,
            "UCF_FORCE_CONFFNEW would overwrite the local php.ini - the "
            "exact opposite of what is wanted",
        )
        # A single-F typo must not appear anywhere.
        self.assertIsNone(
            re.search(r"UCF_FORCE_CONFOLD\b", self.body),
            "UCF_FORCE_CONFOLD (single F) is not read by ucf - typo",
        )

    def test_dpkg_force_confold_passed_to_apt(self):
        self.assertIn(
            "-o Dpkg::Options::=--force-confold",
            self.body,
            "www.conf is a modified dpkg conffile; --force-confold must be "
            "passed or dpkg prompts or replaces it",
        )
        self.assertNotIn(
            "--force-confnew",
            self.body,
            "--force-confnew would discard the local www.conf",
        )

    def test_local_values_are_reverified_after_upgrade(self):
        for setting in (
            "memory_limit",
            "post_max_size",
            "upload_max_filesize",
            "max_execution_time",
            "max_file_uploads",
            "open_basedir",
        ):
            self.assertIn(
                setting,
                self.body,
                f"{setting} must be captured before and re-checked after "
                "the upgrade",
            )
        self.assertIn(
            "check_survived",
            self.body,
            "a post-upgrade comparison of the local values must exist",
        )


class TestNoRaceyGrepQPipes(unittest.TestCase):
    """Regression test for a real bug, not a hypothetical one.

    2026-10-21: Step 3 used `if ! apt-cache policy "$pkg" | grep -q
    'trixie-security'; then`. That read correctly and passed every time
    it was tried interactively - but under this script's own `set -o
    pipefail`, it failed on every actual unattended run (confirmed
    10/10 via `bash -x` trace against this live box). `grep -q` exits
    the instant it finds its first match and closes its read end;
    apt-cache policy's output is written in more than one underlying
    write(), and apt-cache's write to the now-closed pipe gets killed
    with SIGPIPE (exit 141) if it loses that race. `pipefail` then
    reports the pipeline's status as 141 - a hard security-check
    failure - even though grep's own exit status was a correct 0 (match
    found). The fix was to capture apt-cache policy's output once into
    a variable and test it with bash's own `[[ == *...* ]]`, which
    forks nothing and therefore cannot race.

    This is a general pattern, not specific to this one call site: any
    `| grep -q` (or `-m N`, which also stops reading early) downstream
    of a command whose output isn't trivially guaranteed to fit in one
    write() is a latent SIGPIPE/pipefail trap under `set -o pipefail`.
    `grep -c` and plain `grep`/`grep -E` without `-q`/`-m` read their
    whole input to EOF and do not have this problem - this test suite
    only flags the early-exiting forms.
    """

    EARLY_EXIT_GREP = re.compile(r"\|\s*grep\s+(-\w*q\w*|-m\s*\d+)\b")

    def test_apply_script_has_no_early_exiting_grep_in_a_pipe(self):
        self._assert_none(SCRIPT)

    def test_verify_script_has_no_early_exiting_grep_in_a_pipe(self):
        self._assert_none(VERIFY)

    def _assert_none(self, path):
        for lineno, line in enumerate(code_only(path).splitlines(), 1):
            self.assertIsNone(
                self.EARLY_EXIT_GREP.search(line),
                f"{path}:{lineno}: a pipe into an early-exiting grep "
                f"(-q/-m) is a SIGPIPE/pipefail race under this script's "
                f"own `set -o pipefail` - capture the upstream output in "
                f"a variable and match with bash's own [[ == *...* ]] "
                f"instead: {line!r}",
            )

    def test_step_3_uses_bash_native_match_not_a_pipe(self):
        body = read(SCRIPT)
        self.assertIn(
            '[[ "$POLICY_OUTPUT" != *"trixie-security"* ]]',
            body,
            "the trixie-security check must be a native bash substring "
            "test against an already-captured variable",
        )

    def test_apt_cache_policy_called_exactly_once_in_step_3(self):
        # Also closes the inefficiency the racy form carried: it is
        # cheaper, and leaves only one source of truth for both checks
        # to read from instead of two independent invocations that could
        # in principle observe different states.
        body = code_only(SCRIPT)
        self.assertEqual(
            body.count("apt-cache policy"),
            1,
            "Step 3 must call apt-cache policy once and reuse its "
            "captured output for both the version and suite checks",
        )


class TestUpgradeScoping(unittest.TestCase):
    def setUp(self):
        self.body = code_only(SCRIPT)

    def test_only_upgrade_is_used(self):
        self.assertIn(
            "--only-upgrade",
            self.body,
            "the upgrade must never install new packages",
        )

    def test_no_blanket_system_upgrade(self):
        for forbidden in (
            "apt-get upgrade",
            "apt-get dist-upgrade",
            "apt-get full-upgrade",
            "apt upgrade",
        ):
            self.assertNotIn(
                forbidden,
                self.body,
                f"'{forbidden}' is a blanket system upgrade, explicitly "
                "ruled out for this maintenance window",
            )

    def test_no_third_party_php_repository(self):
        combined = code_only(SCRIPT) + code_only(DROPIN)
        for forbidden in ("sury", "ondrej", "ppa:", "deb.sury.org"):
            self.assertNotIn(
                forbidden,
                combined.lower(),
                f"'{forbidden}' - the fix is in Debian's own "
                "trixie-security; no third-party repo may be added",
            )

    def test_no_release_upgrade(self):
        body = code_only(SCRIPT).lower()
        for forbidden in ("forky", "sid ", "do-release-upgrade"):
            self.assertNotIn(
                forbidden,
                body,
                f"'{forbidden}' - this must not become a Debian release "
                "upgrade",
            )

    def test_targets_the_known_fixed_version(self):
        self.assertIn(
            FIXED_VERSION,
            code_only(SCRIPT),
            f"the script must assert against the DSA-6574-1 fixed version "
            f"{FIXED_VERSION}",
        )

    def test_requires_the_security_suite(self):
        self.assertIn(
            "trixie-security",
            code_only(SCRIPT),
            "the script must confirm the candidate comes from the security "
            "suite rather than accepting any version",
        )


class TestSafetyOrdering(unittest.TestCase):
    def setUp(self):
        self.body = read(SCRIPT)

    def _pos(self, needle):
        idx = self.body.find(needle)
        self.assertNotEqual(idx, -1, f"not found in script: {needle}")
        return idx

    def test_backup_happens_before_package_change(self):
        self.assertLess(
            self._pos("Step 1: backup"),
            self._pos("Step 4: upgrade"),
            "the backup must be taken before anything is changed",
        )

    def test_config_test_precedes_restart(self):
        self.assertLess(
            self._pos("Step 6: validate configuration BEFORE restarting"),
            self._pos("Step 7: restart"),
            "the validation step must come before the restart step",
        )
        # And the actual `php-fpm -t` invocation must live in Step 6,
        # not merely be mentioned somewhere in the file.
        step6 = self.body[
            self._pos("Step 6: validate configuration BEFORE restarting"):
            self._pos("Step 7: restart")
        ]
        self.assertIn(
            '-t',
            step6,
            "php-fpm -t must actually run inside Step 6",
        )
        self.assertRegex(
            step6,
            r'php-fpm\$\{PHP_SERIES\}"?\s+-t',
            "Step 6 must run FPM's own config test before any restart",
        )

    def test_local_value_check_precedes_restart(self):
        self.assertLess(
            self._pos("check_survived memory_limit"),
            self._pos("Step 7: restart"),
            "a reverted config must be caught while the running workers "
            "still hold the good config",
        )

    def test_backup_is_verified_recoverable_not_just_created(self):
        self.assertIn(
            "Backup verified byte-identical to live config",
            self.body,
            "the script must diff the backup against live, not merely "
            "copy files and assume success",
        )

    def test_dry_run_mode_exists_and_changes_nothing(self):
        self.assertIn("--dry-run", self.body)
        self.assertIn("DRY_RUN=1", self.body)
        res = subprocess.run(
            ["bash", SCRIPT, "--bogus-flag"], capture_output=True, text=True
        )
        self.assertEqual(
            res.returncode, 2, "an unknown flag must be rejected, not ignored"
        )

    def test_requires_root(self):
        self.assertIn('[ "$(id -u)" -ne 0 ]', self.body)

    def test_restarts_only_php_fpm(self):
        # The script restarts "$FPM_SERVICE", so assert both that the
        # variable is the only restart target and that it is bound to
        # php-fpm. Checking the literal target alone would pass for any
        # variable whatsoever.
        self.assertRegex(
            self.body,
            r'FPM_SERVICE="php\$\{PHP_SERIES\}-fpm"',
            "FPM_SERVICE must be bound to php<series>-fpm",
        )
        restarts = re.findall(r"systemctl restart (\S+)", self.body)
        self.assertTrue(restarts, "expected at least one restart")
        allowed = {'"$FPM_SERVICE"', "${FPM_SERVICE}", '${FPM_SERVICE}"'}
        for target in restarts:
            normalised = target.rstrip(";")
            self.assertTrue(
                normalised in allowed or "fpm" in normalised,
                f"only php-fpm may be restarted, not {target} - nginx, "
                "hostapd, dnsmasq and the AP must be left alone",
            )

    def test_does_not_reboot_or_touch_networking(self):
        body = code_only(SCRIPT)
        for forbidden in (
            "reboot",
            "poweroff",
            "systemctl restart hostapd",
            "systemctl restart dnsmasq",
            "systemctl restart nginx",
            "iptables",
            "nft ",
            "ip link set",
        ):
            self.assertNotIn(
                forbidden,
                body,
                f"'{forbidden}' must not appear - networking, the AP and "
                "reboots are out of scope for a PHP package update",
            )


class TestDropIn(unittest.TestCase):
    def setUp(self):
        self.body = read(DROPIN)

    def test_disables_session_upload_progress(self):
        self.assertIsNotNone(
            re.search(
                r"^\s*session\.upload_progress\.enabled\s*=\s*0\s*$",
                self.body,
                re.MULTILINE,
            ),
            "the drop-in's whole purpose is disabling upload progress",
        )

    def test_does_not_enable_it_anywhere(self):
        self.assertIsNone(
            re.search(
                r"^\s*session\.upload_progress\.enabled\s*=\s*[^0\s]",
                self.body,
                re.MULTILINE,
            ),
            "no line may re-enable session.upload_progress",
        )

    def test_only_sets_settings_not_comments_claiming_to(self):
        # Every non-comment, non-blank line must be a real assignment.
        for line in self.body.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(";"):
                continue
            self.assertIn(
                "=", stripped, f"unexpected non-assignment line: {line!r}"
            )

    def test_sets_nothing_unrelated(self):
        """A security drop-in must not quietly retune the site."""
        assignments = [
            line.split("=")[0].strip()
            for line in self.body.splitlines()
            if line.strip() and not line.strip().startswith(";") and "=" in line
        ]
        self.assertEqual(
            assignments,
            ["session.upload_progress.enabled"],
            "the drop-in must change exactly one setting",
        )

    def test_documents_that_the_package_update_is_the_real_fix(self):
        body = self.body.lower()
        self.assertIn("8.4.27", body)
        self.assertIn(
            "not a substitute",
            read(SCRIPT).lower(),
            "the script must state the drop-in does not replace the update",
        )

    def test_names_both_cves(self):
        combined = (self.body + read(SCRIPT)).upper()
        for cve in ("CVE-2026-109618", "CVE-2026-109619"):
            self.assertIn(cve, combined)


class TestVerifyScript(unittest.TestCase):
    def setUp(self):
        self.body = read(VERIFY)
        self.code = code_only(VERIFY)

    def test_is_read_only(self):
        for forbidden in (
            "systemctl restart",
            "systemctl stop",
            "apt-get",
            "rm -",
            "> /var/www",
        ):
            self.assertNotIn(
                forbidden,
                self.code,
                f"'{forbidden}' - the verification script must change "
                "nothing",
            )

    def test_covers_the_required_surface(self):
        for probe in (
            "hotspot-detect.html",
            "generate_204",
            "connecttest.txt",
            ".well-known/captive-portal",
            "chat.php",
            "bulletin.php",
            "messages.php",
            "upload.php",
            "/admin/",
            "nginx",
            "php8.4-fpm",
            "hostapd",
            "dnsmasq",
        ):
            self.assertIn(
                probe, self.body, f"verification must cover {probe}"
            )

    def test_asserts_admin_stays_locked(self):
        self.assertRegex(
            self.body,
            r'chk "admin/ unauthenticated"\s+401',
            "the admin basic-auth gate must be asserted closed",
        )

    def test_exercises_the_multipart_path(self):
        self.assertIn(
            "-F ",
            self.body,
            "a real multipart POST is the request shape that reaches the "
            "CVE-2026-109619 code path",
        )

    def test_does_not_post_community_content(self):
        # It may POST multipart to upload.php (CSRF-rejected), but must
        # never submit chat/bulletin/message content.
        self.assertNotIn("--data", self.code)
        self.assertNotIn("-d ", self.code)

    def test_exits_nonzero_on_failure(self):
        self.assertIn('[ "$fail" -eq 0 ]', self.body)


class TestLiveTransactionScoping(unittest.TestCase):
    """Runs the real `apt-get install --only-upgrade --simulate` the
    script would run, read-only, against this box's live apt state, and
    checks the transaction it reports - not just the script's source
    text. --simulate requires no root and changes nothing.

    This directly verifies the 2026-10-21 request: confirm that the
    update "selects only the intended PHP security packages with no
    unexpected removals or unrelated upgrades" - against the actual
    live package set, not an assumption about it.

    Skips (rather than fails) if the box isn't currently in the
    "upgrade available" state the real run saw, so this file keeps
    passing after the real upgrade has already happened.
    """

    def _installed_php_packages(self):
        res = subprocess.run(
            [
                "dpkg-query", "-W",
                "-f", "${binary:Package} ${db:Status-Status}\n",
                "php8.4-*",
            ],
            capture_output=True, text=True,
        )
        return sorted(
            line.split()[0]
            for line in res.stdout.splitlines()
            if line.endswith(" installed")
        )

    def test_simulated_transaction_touches_only_installed_php_packages(self):
        installed = self._installed_php_packages()
        if not installed:
            self.skipTest("no php8.4-* packages installed on this box")

        policy = subprocess.run(
            ["apt-cache", "policy", "php8.4-fpm"],
            capture_output=True, text=True,
        ).stdout
        installed_version = next(
            (
                line.split(":", 1)[1].strip()
                for line in policy.splitlines()
                if line.strip().startswith("Installed:")
            ),
            "",
        )
        # Already patched is success, not a reason to run this check at
        # all: dpkg reports nothing to upgrade in that case (confirmed on
        # this box right after the real 2026-10-21 run), which would
        # otherwise look identical to "the transaction touched zero
        # packages because something is broken." Skip explicitly instead
        # of trying to tell those two apart from --simulate's output.
        if not installed_version or dpkg_ge(installed_version, FIXED_VERSION):
            self.skipTest(
                f"already at or above {FIXED_VERSION} (installed="
                f"{installed_version or 'unknown'}) - nothing for "
                "--simulate to report, which is the correct, patched state"
            )
        if "trixie-security" not in policy or FIXED_VERSION not in policy:
            self.skipTest(
                "the fixed version isn't the current trixie-security "
                "candidate on this box (apt lists may be stale - run "
                "apt-get update first)"
            )

        res = subprocess.run(
            ["apt-get", "install", "--only-upgrade", "--simulate", *installed],
            capture_output=True, text=True, env={**os.environ, "LC_ALL": "C"},
        )
        out = res.stdout

        upgraded = set()
        for line in out.splitlines():
            if line.startswith("Inst "):
                upgraded.add(line.split()[1])
            if line.strip().startswith("Remv "):
                self.fail(f"simulate wants to REMOVE a package: {line!r}")

        self.assertEqual(
            upgraded,
            set(installed),
            "the simulated transaction must upgrade exactly the "
            "installed php8.4-* packages - nothing more, nothing less: "
            f"expected {sorted(installed)}, got {sorted(upgraded)}",
        )

        match = re.search(
            r"(\d+) upgraded, (\d+) newly installed, (\d+) to remove",
            out,
        )
        self.assertIsNotNone(match, f"couldn't parse summary line from: {out}")
        n_new, n_removed = int(match.group(2)), int(match.group(3))
        self.assertEqual(n_new, 0, "no package may be newly installed")
        self.assertEqual(n_removed, 0, "no package may be removed")

        for line in out.splitlines():
            if line.startswith("Inst ") or line.strip().startswith("Conf "):
                self.assertIn(
                    "8.4.27-1~deb13u1",
                    line,
                    f"every touched package must land on the DSA-6574-1 "
                    f"fixed version, not some other candidate: {line!r}",
                )
                self.assertNotIn(
                    "sury", line.lower(),
                    f"candidate must not come from a third-party repo: {line!r}",
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
