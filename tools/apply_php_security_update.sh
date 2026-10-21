#!/bin/bash
#
# Applies Debian's official PHP security update for CVE-2026-109618 and
# CVE-2026-109619 ("php2shell"), 2026-10-21. Run as root:
#
#   sudo tools/apply_php_security_update.sh --dry-run   # preview, changes nothing
#   sudo tools/apply_php_security_update.sh             # apply
#
# Idempotent - safe to re-run. Re-running once already patched does the
# backup and verification passes and reports "already at or above the
# fixed version" without touching packages.
#
# WHAT THESE CVEs ARE: two critical unauthenticated-RCE flaws in PHP
# core, both rated CVSS v4.0 9.2 by PHP upstream, disclosed 2026-10-21.
#   CVE-2026-109619 - heap use-after-free in PHP's session
#     upload-progress handling. The handler runs on every multipart
#     POST *before* the request is initialised, so it can consume state
#     a previous request left behind on the same FPM worker.
#     session.upload_progress.enabled is ON by default, so stock
#     configuration is exploitable.
#   CVE-2026-109618 - RCE via out-of-memory corruption. OOM handling
#     can interrupt PHP while internal request data is only partially
#     initialised; request cleanup then treats the invalid data as
#     valid. Multipart parsing is one trigger.
# Fixed upstream in PHP 8.2.35 / 8.3.36 / 8.4.27 / 8.5.12. For Debian
# 13 (trixie) the fix is php8.4 8.4.27-1~deb13u1, shipped in
# DSA-6574-1, from the trixie-security suite this box already has
# configured. No third-party PHP repository (Sury/ondrej) is needed or
# used, and this is NOT a Debian release upgrade.
#
# WHY PIRATEBOX WAS EXPOSED: nginx routes every *.php request to
# php8.4-fpm with client_max_body_size 150M, so the vulnerable
# pre-request upload-progress path was reachable on every PHP endpoint
# on the site - not only public/upload.php - from any client associated
# to the visitor AP, with no authentication. memory_limit is a finite
# 256M, which is the condition CVE-2026-109618's OOM path needs.
#
# THE ONE REAL HAZARD THIS SCRIPT EXISTS TO HANDLE: upgrading php8.4
# can silently revert PirateBox's PHP configuration, and the damage
# would not be obvious. Two separate mechanisms, each needing a
# different flag:
#   /etc/php/8.4/fpm/php.ini is NOT a dpkg conffile - it is ucf-managed
#     (registered to php8.4-fpm in /var/lib/ucf/registry), and it is
#     locally modified: open_basedir (PirateBox's whole read-allowlist,
#     including every /run/piratebox* sensor export), memory_limit
#     256M, max_execution_time 300, post_max_size 130M,
#     upload_max_filesize 120M, max_file_uploads 10. ucf resolves this
#     with UCF_FORCE_CONFFOLD=1, which silently retains the installed
#     file.
#   /etc/php/8.4/fpm/pool.d/www.conf IS a dpkg conffile and IS locally
#     modified (dpkg --verify reports the md5 mismatch): the upload
#     sizing, the disk-backed upload_tmp_dir=/var/www/piratebox-tmp,
#     the www-data socket ownership and the pm.* sizing tuned for a
#     Pi 3B+. dpkg resolves this with --force-confold.
# Without both, a non-interactive upgrade could drop upload_max_
# filesize back to the stock 2M (file sharing silently broken for
# anything but tiny files) and drop open_basedir entirely (a security
# regression, and every sensor/status page silently degrading to "no
# data" - the exact failure mode already documented in
# tools/deploy_environment_sensors.sh). Step 6 therefore re-checks all
# six values after the upgrade and fails loudly if any reverted.
#
# SERVICES: restarts php8.4-fpm and nothing else. nginx, hostapd,
# dnsmasq, the pb-ap visitor AP, piratebox-oled, the ESP32 supervisor
# and the sensor stack are deliberately left alone - none of them need
# restarting for a PHP package change, and the AP/DHCP/DNS path must
# not be disturbed. The php8.4-fpm restart is a sub-second gap in PHP
# page serving only; nginx keeps listening throughout, so no client
# association and no captive-portal state is lost.

set -euo pipefail

DRY_RUN=0
case "${1:-}" in
    --dry-run) DRY_RUN=1 ;;
    "") ;;
    *) echo "Usage: $0 [--dry-run]" >&2; exit 2 ;;
esac

if [ "$(id -u)" -ne 0 ]; then
    echo "This must be run as root (sudo tools/apply_php_security_update.sh)." >&2
    exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PHP_SERIES=8.4
FIXED_VERSION="8.4.27-1~deb13u1"
FPM_SERVICE="php${PHP_SERIES}-fpm"
FPM_INI="/etc/php/${PHP_SERIES}/fpm/php.ini"
FPM_POOL="/etc/php/${PHP_SERIES}/fpm/pool.d/www.conf"
DROPIN_NAME="99-piratebox-security.ini"
DROPIN_LIVE="/etc/php/${PHP_SERIES}/fpm/conf.d/${DROPIN_NAME}"
DROPIN_SRC="${REPO_ROOT}/etc/php/${PHP_SERIES}/fpm/conf.d/${DROPIN_NAME}"
BACKUP_ROOT="/home/moose/piratebox-backups"

run() { # echo + execute, or just echo under --dry-run
    if [ "$DRY_RUN" -eq 1 ]; then echo "  [dry-run] $*"; else echo "  + $*"; "$@"; fi
}

say() { echo; echo "=== $* ==="; }

if [ "$DRY_RUN" -eq 1 ]; then
    echo "### DRY RUN - no packages, config or services will be changed. ###"
    echo "### (apt-get update DOES run - it installs nothing; see Step 2.) ###"
fi

# ---------------------------------------------------------------------
say "Step 0: preflight"

. /etc/os-release
echo "OS: ${PRETTY_NAME} (VERSION_ID=${VERSION_ID})"
if [ "${VERSION_ID:-}" != "13" ]; then
    echo "FAIL: this script targets Debian 13 (trixie), where the fix is ${FIXED_VERSION}." >&2
    echo "      On a different release, re-check the Debian security tracker first." >&2
    exit 1
fi

# The exact set of php8.4 binary packages actually installed. Only these
# get upgraded - never a blanket 'apt-get upgrade', which the operator
# explicitly ruled out and which would drag in unrelated changes.
mapfile -t PHP_PKGS < <(dpkg-query -W -f='${binary:Package} ${db:Status-Status}\n' "php${PHP_SERIES}-*" 2>/dev/null \
    | awk '$2=="installed"{print $1}' | sort)
if [ "${#PHP_PKGS[@]}" -eq 0 ]; then
    echo "FAIL: no php${PHP_SERIES}-* packages appear installed." >&2; exit 1
fi
echo "Installed php${PHP_SERIES} packages (${#PHP_PKGS[@]}) and current versions:"
for p in "${PHP_PKGS[@]}"; do
    printf '  %-24s %s\n' "$p" "$(dpkg-query -W -f='${Version}' "$p")"
done

ORIG_CLI_VERSION="$(php -v 2>/dev/null | head -1)"
ORIG_FPM_VERSION="$(/usr/sbin/php-fpm${PHP_SERIES} -v 2>/dev/null | head -1)"
ORIG_PKG_VERSION="$(dpkg-query -W -f='${Version}' "php${PHP_SERIES}-fpm")"
echo "CLI: ${ORIG_CLI_VERSION}"
echo "FPM: ${ORIG_FPM_VERSION}"

# Record the six local php.ini/www.conf values that must survive.
read_ini_val() { grep -E "^[[:space:]]*$2[[:space:]]*=" "$1" | tail -1 | sed 's/.*=[[:space:]]*//'; }
ORIG_OPEN_BASEDIR="$(read_ini_val "$FPM_INI" open_basedir)"
ORIG_MEMORY_LIMIT="$(read_ini_val "$FPM_INI" memory_limit)"
ORIG_POST_MAX="$(read_ini_val "$FPM_INI" post_max_size)"
ORIG_UPLOAD_MAX="$(read_ini_val "$FPM_INI" upload_max_filesize)"
ORIG_MAX_EXEC="$(read_ini_val "$FPM_INI" max_execution_time)"
ORIG_MAX_FILES="$(read_ini_val "$FPM_INI" max_file_uploads)"
echo "Local php.ini values that must survive this upgrade:"
echo "  memory_limit=${ORIG_MEMORY_LIMIT} post_max_size=${ORIG_POST_MAX} upload_max_filesize=${ORIG_UPLOAD_MAX}"
echo "  max_execution_time=${ORIG_MAX_EXEC} max_file_uploads=${ORIG_MAX_FILES}"
echo "  open_basedir=${ORIG_OPEN_BASEDIR}"
if [ -z "$ORIG_OPEN_BASEDIR" ] || [ -z "$ORIG_UPLOAD_MAX" ]; then
    echo "FAIL: could not read the expected local php.ini values - refusing to proceed" >&2
    echo "      because Step 6 would have nothing to verify against." >&2
    exit 1
fi

# ---------------------------------------------------------------------
say "Step 1: backup of affected configuration"

TS="$(date +%Y%m%d-%H%M%S)"
BK="${BACKUP_ROOT}/php-cve-2026-109618-19-pre-${TS}"
run mkdir -p "$BK"
if [ "$DRY_RUN" -eq 0 ]; then
    cp -a "/etc/php/${PHP_SERIES}" "$BK/etc-php-${PHP_SERIES}"
    cp -aL /etc/nginx/sites-enabled/default "$BK/nginx-sites-enabled-default"
    dpkg -l | grep -E '^ii +php' > "$BK/installed-php-packages.txt"
    php -c "$FPM_INI" -i > "$BK/php-fpm-effective-ini.txt" 2>/dev/null || true
    md5sum "$FPM_INI" "$FPM_POOL" > "$BK/config-md5sums.txt"
    {
        echo "Pre-change backup ${TS}, before the CVE-2026-109618 / CVE-2026-109619"
        echo "(php2shell) security update. Original php${PHP_SERIES}-fpm: ${ORIG_PKG_VERSION}"
        echo
        echo "ROLLBACK (configuration only):"
        echo "  sudo cp -a $BK/etc-php-${PHP_SERIES}/fpm/php.ini         $FPM_INI"
        echo "  sudo cp -a $BK/etc-php-${PHP_SERIES}/fpm/pool.d/www.conf $FPM_POOL"
        echo "  sudo rm -f $DROPIN_LIVE"
        echo "  sudo php-fpm${PHP_SERIES} -t && sudo systemctl restart ${FPM_SERVICE}"
        echo
        echo "ROLLBACK (packages) reinstalls the VULNERABLE ${ORIG_PKG_VERSION}."
        echo "Last resort only, and re-patch promptly afterwards:"
        printf '  sudo apt-get install --only-upgrade --allow-downgrades'
        for p in "${PHP_PKGS[@]}"; do printf ' \\\n    %s=%s' "$p" "$ORIG_PKG_VERSION"; done
        echo
    } > "$BK/README.txt"
    # Verify the backup is actually recoverable, not just present.
    diff -q "$BK/etc-php-${PHP_SERIES}/fpm/php.ini" "$FPM_INI" >/dev/null \
        || { echo "FAIL: php.ini backup does not match live - aborting before any change." >&2; exit 1; }
    diff -q "$BK/etc-php-${PHP_SERIES}/fpm/pool.d/www.conf" "$FPM_POOL" >/dev/null \
        || { echo "FAIL: www.conf backup does not match live - aborting before any change." >&2; exit 1; }
    echo "  Backup verified byte-identical to live config: $BK"
else
    echo "  [dry-run] would back up /etc/php/${PHP_SERIES}, the nginx site, the package list"
    echo "  [dry-run] and the effective FPM ini into ${BACKUP_ROOT}/php-cve-...-pre-<ts>/"
fi

# ---------------------------------------------------------------------
say "Step 2: refresh package lists"

# Needed because the on-disk apt lists predate the advisory; without
# this, apt's candidate for php8.4-fpm is still the vulnerable version.
#
# This runs for real even under --dry-run, deliberately. It installs
# nothing and changes no package state - it only updates
# /var/lib/apt/lists - and without it a dry run would evaluate Step 3
# against a stale cache and report "the configured repositories do not
# offer the fix" on a box where the fix is in fact available. A dry run
# that can produce that false negative is worse than no dry run, since
# it would argue for exactly the wrong remedy (adding a repository).
# This is also why --dry-run still requires root.
apt-get update

# ---------------------------------------------------------------------
say "Step 3: verify the fix is available from Debian security"

# Call apt-cache policy exactly ONCE and keep its full output in a
# variable - both for both checks below to read from, and specifically
# NOT to re-run it through "| grep -q" a second time. That second form
# ("apt-cache policy ... | grep -q 'trixie-security'") looked correct
# and matched interactively every time it was tried by hand, but under
# this script's own `set -o pipefail` it failed on every real
# unattended run (confirmed 10/10 in a bash -x trace against this
# exact live box, 2026-10-21) with the pipeline reporting exit 141 -
# SIGPIPE - even though grep DID find "trixie-security" and printed
# nothing wrong. `grep -q` exits the instant it finds its first match
# and closes its read end; apt-cache policy's output here is written
# in more than one underlying write() (observed, not assumed - it is
# NOT one single write small enough to always win the race), so when
# apt-cache is still mid-write to a pipe grep has already closed, the
# kernel kills it with SIGPIPE and it exits 141. `pipefail` then
# reports the pipeline's status as 141, not grep's real 0, which the
# `!` above turned into a false "not offered by trixie-security"
# failure on a box where the candidate demonstrably WAS 8.4.27-1~deb13u1
# from trixie-security the entire time. Matching the string against an
# already-captured variable with bash's own `[[ == *...* ]]` needs no
# pipe and no second process, so there is nothing left to race.
POLICY_OUTPUT="$(apt-cache policy "php${PHP_SERIES}-fpm")"
CANDIDATE="$(awk '/Candidate:/{print $2}' <<< "$POLICY_OUTPUT")"
echo "php${PHP_SERIES}-fpm installed=${ORIG_PKG_VERSION} candidate=${CANDIDATE} required>=${FIXED_VERSION}"

if dpkg --compare-versions "$ORIG_PKG_VERSION" ge "$FIXED_VERSION"; then
    echo "Already at or above the fixed version - no package change needed."
    SKIP_PACKAGES=1
else
    SKIP_PACKAGES=0
    if [ -z "$CANDIDATE" ] || ! dpkg --compare-versions "$CANDIDATE" ge "$FIXED_VERSION"; then
        echo "FAIL: the configured repositories do not offer ${FIXED_VERSION} or newer." >&2
        echo "      Candidate is '${CANDIDATE}'. Investigate repository reachability" >&2
        echo "      (trixie-security in /etc/apt/sources.list.d/debian.sources)." >&2
        echo "      Do NOT add a third-party PHP repository to work around this." >&2
        exit 1
    fi
    # The fix must come from the security suite, not an unexpected source.
    # Bash's own substring test - no pipe, no second process, no SIGPIPE
    # race; see the long comment above POLICY_OUTPUT for exactly why
    # that matters here and not just as a style preference.
    if [[ "$POLICY_OUTPUT" != *"trixie-security"* ]]; then
        echo "FAIL: ${CANDIDATE} is not being offered by trixie-security - refusing." >&2
        exit 1
    fi
    echo "Confirmed: ${CANDIDATE} is offered by trixie-security (DSA-6574-1)."
fi

# ---------------------------------------------------------------------
say "Step 4: upgrade only the installed php${PHP_SERIES} packages"

if [ "$SKIP_PACKAGES" -eq 1 ]; then
    echo "Skipped - already patched."
else
    # UCF_FORCE_CONFFOLD: silently retain the locally-modified,
    # ucf-managed php.ini. --force-confold: same for the www.conf dpkg
    # conffile. --only-upgrade with an explicit package list: never pull
    # in a new package, never touch anything outside php8.4.
    echo "  Keeping local config: UCF_FORCE_CONFFOLD=1 + Dpkg --force-confold"
    if [ "$DRY_RUN" -eq 1 ]; then
        echo "  [dry-run] simulating the exact install now:"
        DEBIAN_FRONTEND=noninteractive apt-get install --only-upgrade \
            --simulate "${PHP_PKGS[@]}"
    else
        export UCF_FORCE_CONFFOLD=1
        export DEBIAN_FRONTEND=noninteractive
        apt-get install --only-upgrade -y \
            -o Dpkg::Options::=--force-confold \
            -o Dpkg::Options::=--force-confdef \
            "${PHP_PKGS[@]}"
    fi
fi

# ---------------------------------------------------------------------
say "Step 5: install the PirateBox hardening drop-in"

# Defense in depth for CVE-2026-109619; see the file's own header for
# why this costs PirateBox no functionality. Not a substitute for
# Step 4 - PHP upstream says only the update is a complete fix.
if [ ! -f "$DROPIN_SRC" ]; then
    echo "FAIL: missing ${DROPIN_SRC}" >&2; exit 1
fi
if [ "$DRY_RUN" -eq 0 ] && cmp -s "$DROPIN_SRC" "$DROPIN_LIVE"; then
    echo "  Already installed and identical: $DROPIN_LIVE"
else
    run install -o root -g root -m 0644 "$DROPIN_SRC" "$DROPIN_LIVE"
fi

# ---------------------------------------------------------------------
say "Step 6: validate configuration BEFORE restarting anything"

if [ "$DRY_RUN" -eq 1 ]; then
    echo "  [dry-run] would run: php-fpm${PHP_SERIES} -t"
    echo "  [dry-run] would re-verify the six local php.ini values survived"
else
    # FPM's own config test. Must pass before the service is touched.
    "/usr/sbin/php-fpm${PHP_SERIES}" -t
    echo "  php-fpm${PHP_SERIES} -t: OK"

    # Did the upgrade silently revert PirateBox's config? This is the
    # check the whole conffile-flag dance above exists to make passable.
    fail=0
    check_survived() { # label original current
        if [ "$2" = "$3" ]; then
            printf '  OK   %-22s %s\n' "$1" "$3"
        else
            printf '  FAIL %-22s was %s, now %s\n' "$1" "$2" "$3"; fail=1
        fi
    }
    check_survived memory_limit        "$ORIG_MEMORY_LIMIT" "$(read_ini_val "$FPM_INI" memory_limit)"
    check_survived post_max_size       "$ORIG_POST_MAX"     "$(read_ini_val "$FPM_INI" post_max_size)"
    check_survived upload_max_filesize "$ORIG_UPLOAD_MAX"   "$(read_ini_val "$FPM_INI" upload_max_filesize)"
    check_survived max_execution_time  "$ORIG_MAX_EXEC"     "$(read_ini_val "$FPM_INI" max_execution_time)"
    check_survived max_file_uploads    "$ORIG_MAX_FILES"    "$(read_ini_val "$FPM_INI" max_file_uploads)"
    check_survived open_basedir        "$ORIG_OPEN_BASEDIR" "$(read_ini_val "$FPM_INI" open_basedir)"
    for v in upload_max_filesize post_max_size upload_tmp_dir; do
        grep -qE "^[[:space:]]*php_(admin_)?value\[$v\]" "$FPM_POOL" \
            && printf '  OK   %-22s present in www.conf\n' "$v" \
            || { printf '  FAIL %-22s missing from www.conf\n' "$v"; fail=1; }
    done
    if [ "$fail" -ne 0 ]; then
        echo >&2
        echo "FAIL: the upgrade reverted PirateBox PHP configuration." >&2
        echo "      php8.4-fpm has NOT been restarted, so the running workers still" >&2
        echo "      have the old (correct) config loaded. Restore and restart with:" >&2
        echo "        sudo cp -a $BK/etc-php-${PHP_SERIES}/fpm/php.ini         $FPM_INI" >&2
        echo "        sudo cp -a $BK/etc-php-${PHP_SERIES}/fpm/pool.d/www.conf $FPM_POOL" >&2
        echo "        sudo php-fpm${PHP_SERIES} -t && sudo systemctl restart ${FPM_SERVICE}" >&2
        exit 1
    fi
fi

# ---------------------------------------------------------------------
say "Step 7: restart php${PHP_SERIES}-fpm only"

if [ "$DRY_RUN" -eq 1 ]; then
    echo "  [dry-run] would run: systemctl restart ${FPM_SERVICE}"
    echo "  [dry-run] nginx / hostapd / dnsmasq / OLED / ESP32 left untouched"
else
    run systemctl restart "$FPM_SERVICE"
    # Wait for the socket to come back rather than assuming it has.
    for _ in $(seq 1 30); do
        [ -S "/run/php/php${PHP_SERIES}-fpm.sock" ] && systemctl is-active --quiet "$FPM_SERVICE" && break
        sleep 0.5
    done
    systemctl is-active --quiet "$FPM_SERVICE" \
        || { echo "FAIL: ${FPM_SERVICE} did not come back active." >&2
             systemctl status "$FPM_SERVICE" --no-pager -n 30 >&2; exit 1; }
    [ -S "/run/php/php${PHP_SERIES}-fpm.sock" ] \
        || { echo "FAIL: FPM socket /run/php/php${PHP_SERIES}-fpm.sock missing." >&2; exit 1; }
    echo "  ${FPM_SERVICE} active, socket present."
fi

# ---------------------------------------------------------------------
say "Step 8: confirm the patched version is what is actually running"

if [ "$DRY_RUN" -eq 1 ]; then
    echo "  [dry-run] would confirm the live FPM worker reports >= ${FIXED_VERSION}"
else
    NEW_PKG_VERSION="$(dpkg-query -W -f='${Version}' "php${PHP_SERIES}-fpm")"
    echo "php${PHP_SERIES}-fpm package: ${ORIG_PKG_VERSION}  ->  ${NEW_PKG_VERSION}"
    echo "CLI: $(php -v | head -1)"
    echo "FPM: $(/usr/sbin/php-fpm${PHP_SERIES} -v | head -1)"
    dpkg --compare-versions "$NEW_PKG_VERSION" ge "$FIXED_VERSION" \
        || { echo "FAIL: still below ${FIXED_VERSION} after the upgrade." >&2; exit 1; }
    # The decisive check: what the *running* FPM worker actually uses,
    # not the package DB and not a naive CLI re-check.
    #
    # `php -c "$FPM_INI" -r '...'` (the first form this used) is wrong
    # and was caught giving a false "still On" here on the real 2026-10-21
    # run: `-c <file>` only swaps which php.ini the CLI SAPI reads - the
    # *additional .ini scan directory* stays whatever the `php` CLI
    # binary was compiled with (/etc/php/8.4/cli/conf.d), so a CLI-based
    # check never sees anything FPM's own conf.d/ adds, including the
    # drop-in Step 5 just installed. `php --ini` confirms this directly
    # ("Scan for additional .ini files in: /etc/php/8.4/cli/conf.d" even
    # when -c points at the fpm php.ini).
    #
    # Fixed by making an actual HTTP request through the live
    # nginx -> FPM socket, so this checks the exact runtime the public
    # faces - not any reconstruction of what FPM's ini loading *should*
    # do. The probe file lives in the docroot for only as long as this
    # one curl takes, is removed unconditionally (trap, so even a FAIL
    # or a SIGINT cleans it up), and is excluded from the live site's
    # directory listings/search by its name alone (nothing links to it).
    # Deliberately NOT dot-prefixed: nginx's own "Block hidden
    # files" rule (location ~ /\.(?!well-known).*) would 403 it
    # before PHP ever ran, making the probe useless for exactly
    # the thing it is trying to verify.
    PROBE_NAME="piratebox-update-probe-$$.php"
    PROBE_PATH="/var/www/html/public/${PROBE_NAME}"
    cleanup_probe() { rm -f "$PROBE_PATH"; }
    trap cleanup_probe EXIT
    install -o www-data -g www-data -m 0644 /dev/stdin "$PROBE_PATH" <<'PHP_EOF'
<?php
header('Content-Type: text/plain');
echo ini_get('session.upload_progress.enabled') ? 'On' : 'Off';
PHP_EOF
    UP="$(curl -sS --max-time 10 "http://127.0.0.1/${PROBE_NAME}")"
    cleanup_probe
    trap - EXIT
    echo "session.upload_progress.enabled (live FPM worker, via real HTTP request): ${UP}"
    [ "$UP" = "Off" ] || { echo "FAIL: upload_progress still enabled on the live worker." >&2; exit 1; }
fi

# ---------------------------------------------------------------------
say "Step 9: functional verification"

if [ "$DRY_RUN" -eq 1 ]; then
    echo "  [dry-run] would run: tools/verify_piratebox_http.sh"
else
    bash "${REPO_ROOT}/tools/verify_piratebox_http.sh"
fi

echo
if [ "$DRY_RUN" -eq 1 ]; then
    echo "### DRY RUN complete - nothing was changed. ###"
else
    echo "=== Done. PirateBox is patched against CVE-2026-109618 / CVE-2026-109619. ==="
    echo "Backup: $BK"
fi
