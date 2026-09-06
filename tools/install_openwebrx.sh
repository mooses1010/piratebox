#!/bin/bash
#
# Installs OpenWebRX+ as PirateBox's optional Radio (RTL-SDR) capability.
#
# Run once, as root (sudo bash tools/install_openwebrx.sh), from a
# checkout of this repo. Idempotent where practical (re-running after a
# partial failure skips already-completed steps rather than erroring),
# but this is a real system-modifying installer, not a dry-run tool -
# read this header before running it.
#
# WHY A MANUAL/SOURCE INSTALL, NOT A PACKAGE: upstream's own
# openwebrx-plus apt repository (https://luarvique.github.io/ppa/) is
# x64-only as of this writing and does not cover Debian Trixie or
# arm64 - not usable on this Pi. This script instead follows upstream's
# own documented manual-installation method (the "Manual Package
# installation" path from jketterl/openwebrx's wiki), adapted three
# evidence-backed ways:
#
#   1. Python components (pycsdr, OpenWebRX+ itself) install into a
#      dedicated venv (/opt/openwebrx/venv) rather than system-wide via
#      `sudo python3 setup.py install`, because modern Debian (PEP 668,
#      "externally managed environment") blocks unqualified system-wide
#      pip installs by default - a venv is the standard, current-
#      Debian-compatible equivalent, not an improvised workaround.
#   2. The SDR/profile configuration is seeded via OpenWebRX+'s own
#      documented `openwebrx config migrate` command reading a
#      classic-format config file (etc/openwebrx/sdrs_seed.py), rather
#      than hand-writing the modern JSON config store OpenWebRX+ itself
#      says is "not intended to be edited manually."
#   3. ALL FOUR of csdr/pycsdr/owrx_connector/openwebrx are cloned from
#      **luarvique's own GitHub account**, not jketterl's original
#      repositories, and each is pinned to a specific tested commit
#      rather than tracked at a moving "master" - see the 2026-09-05
#      incident note below the pinned SHAs for exactly why.
#
# WHAT THIS INSTALLS (exactly, for reproducibility/rollback - see
# docs/RADIO-SDR-ARCHITECTURE-DESIGN.md's OpenWebRX+ section for the
# full narrative):
#   - apt packages: build-essential cmake libfftw3-dev python3-venv
#     python3-dev netcat-openbsd libsndfile-dev librtlsdr-dev
#     automake autoconf libtool pkg-config libsamplerate-dev git
#     (rtl-sdr/librtlsdr0 are assumed already installed - see the
#     2026-09-05 "rtl-sdr/librtlsdr package-install gate" entry)
#   - a dedicated system user/group "openwebrx" (no login shell, no
#     home directory beyond /var/lib/openwebrx, member of the "plugdev"
#     group for RTL-SDR USB access via the existing rtl-sdr udev rule)
#   - csdr and owrx_connector: built from source (upstream C/C++
#     projects), installed system-wide via `make install`
#     (/usr/local/{bin,lib}) - standard for these two, no packaging
#     alternative exists
#   - pycsdr and OpenWebRX+ itself: built/installed into
#     /opt/openwebrx/venv (a Python venv), source checked out to
#     /opt/openwebrx/src/{pycsdr,openwebrx}
#   - /etc/openwebrx/openwebrx.conf, /var/lib/openwebrx/ (data dir)
#   - /etc/systemd/system/openwebrx.service (enabled, not started by
#     this script - see the end of this file)
#   - /etc/nginx/openwebrx-location.conf + the small include line
#     already staged in etc/nginx/sites-available/default
#
# WHAT THIS DOES NOT DO: install anything from OpenWebRX+'s own
# "Recommends:" pile (digiham, wsjt-x, direwolf, js8call, dump1090,
# etc. - digital-voice/data decoders, deliberately out of scope for
# "establish a clean basic receiver first"); touch hostapd, dnsmasq,
# nftables, or any core PirateBox PHP/data; change the RTL-SDR's EEPROM
# or firmware; enable transmit of any kind (OpenWebRX+ itself has no
# transmit capability - this is a receiver).
#
# ROLLBACK: see docs/RADIO-SDR-ARCHITECTURE-DESIGN.md's OpenWebRX+
# section, "Removal/rollback" - in short: `systemctl disable --now
# openwebrx`, remove the nginx include line, `rm -rf /opt/openwebrx
# /var/lib/openwebrx /etc/openwebrx /etc/systemd/system/openwebrx.service
# /etc/nginx/openwebrx-location.conf`, `userdel openwebrx`, `ldconfig`
# after removing the /usr/local csdr/owrx_connector installs if desired.
# Core PirateBox is never touched by any of this, in either direction.

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "This must be run as root (sudo bash tools/install_openwebrx.sh) - it installs system packages, creates a system user, and writes systemd/nginx config." >&2
    exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="/opt/openwebrx/src"
VENV_DIR="/opt/openwebrx/venv"
DATA_DIR="/var/lib/openwebrx"

# 2026-09-05 incident #1 (reboot): a first install attempt (full
# `-j$(nproc)` = 4 concurrent GCC/G++ processes) progressed cleanly to
# ~90% of csdr's own build, then the Pi rebooted with no persistent
# journal surviving to explain why - undervoltage was logged early in
# the next boot (as it is on every boot of this chronically marginal-
# power Pi - not, by itself, proof of causation), but no prior stress
# in this whole investigation (RTL-SDR captures, USB operations)
# involved *sustained* full-core load for minutes at a time the way a
# parallel C++ build does. Capping build parallelism is a direct,
# reasoned mitigation for that newly-observed load profile - see
# docs/RADIO-SDR-ARCHITECTURE-DESIGN.md's OpenWebRX+ section for the
# full writeup. This project's sudoers config resets the environment on
# every sudo invocation, so an inline `BUILD_JOBS=N sudo ...` override
# would be silently ignored - edit the default below directly if a
# different value is ever wanted. The reduced-parallelism rebuild did
# NOT reproduce the reboot - useful evidence, not proof either way.
BUILD_JOBS=2

# 2026-09-05 incident #2 (wrong upstream fork): the FIRST successful
# (non-rebooting) build installed and started, then OpenWebRX+ crashed
# immediately: `ImportError: cannot import name 'NoiseFilter' from
# 'pycsdr.modules'`. Root cause, confirmed by inspecting the actual
# installed commits and upstream repositories (not assumed): this
# installer had been cloning csdr/pycsdr/owrx_connector from
# jketterl's ORIGINAL repositories, which stopped being updated years
# ago (jketterl/pycsdr's last-ever tag is 0.18.2, from October 2023) -
# while OpenWebRX+ (luarvique's fork, correctly used from the start)
# expects a much newer pycsdr (its own debian/control declares
# `python3-csdr (>= 0.18.40)`). luarvique maintains his OWN actively-
# developed forks of csdr, pycsdr, AND owrx_connector alongside his
# openwebrx fork specifically so all four stay mutually compatible -
# confirmed directly (NoiseFilter genuinely present in
# luarvique/pycsdr's source; luarvique/pycsdr's master matches tag
# 0.18.40 exactly, satisfying OpenWebRX+'s own declared minimum).
# luarvique/csdr has also been substantially restructured since the
# jketterl fork diverged (modern header-based C++, no more monolithic
# libcsdr.c/csdr.c) - the errhead()/NEON_OPTS bug this installer used
# to patch (incident in the previous commit) does not exist in this
# source at all, so that patch is no longer applied by this script.
#
# Fix: clone all four components from luarvique instead, each pinned
# to a specific commit tested together as a working set - not tracked
# at a moving "master", so a future run can't silently drift into a
# similar cross-repo incompatibility again. Update these together,
# deliberately, if a newer combination is ever wanted and tested.
OPENWEBRX_COMMIT="2d60e894d0889382d2eb0574a19f027f8504dcfa"
PYCSDR_COMMIT="42a5ab3ca48953e65441c4ed7fbd63f030f5afa8"
CSDR_COMMIT="8894bf904d380dc5ece13ca943d592a23f0070d7"
OWRX_CONNECTOR_COMMIT="5b014234cf0f1f49b01ec85f8b29d04c471d28ac"

# Ensures $2 is a clone of $1 checked out exactly at commit $3 - full
# clone (not --depth 1) so an arbitrary pinned SHA is always reachable
# regardless of how far the remote's own branches have since moved.
# If a directory already exists but points at the wrong remote or the
# wrong commit (exactly what incident #2 above needs to self-correct
# on a re-run, since jketterl-sourced checkouts are already on disk
# from the earlier attempt), it is removed and re-cloned rather than
# silently left in place - a plain "does this directory exist" check
# would never detect or fix that.
# Sets REPO_WAS_RECLONED=1 whenever the directory had to be created or
# replaced (wrong source, wrong commit, or simply absent) - callers use
# this to force a rebuild even if an old (wrong-source) build artifact
# is already present and would otherwise satisfy a naive "does the
# binary/library already exist" check. That exact gap is what let
# incident #2's wrong-fork libraries silently "pass" as already
# installed on a first, unfixed re-run attempt during diagnosis.
REPO_WAS_RECLONED=0
ensure_repo_at() {
    local url="$1" dir="$2" sha="$3"
    REPO_WAS_RECLONED=0
    if [ -d "$dir" ]; then
        local current_url current_sha
        current_url="$(git -C "$dir" remote get-url origin 2>/dev/null || echo "")"
        current_sha="$(git -C "$dir" rev-parse HEAD 2>/dev/null || echo "")"
        if [ "$current_url" != "$url" ] || [ "$current_sha" != "$sha" ]; then
            echo "  $dir exists but is $current_url @ $current_sha (expected $url @ $sha) - removing and re-cloning"
            rm -rf "$dir"
        fi
    fi
    if [ ! -d "$dir" ]; then
        git clone "$url" "$dir"
        git -C "$dir" checkout "$sha"
        REPO_WAS_RECLONED=1
    fi
}

echo "=== [1/8] apt dependencies ==="
apt-get update
apt-get install -y --no-install-recommends \
    build-essential cmake libfftw3-dev python3-venv python3-dev \
    netcat-openbsd libsndfile-dev librtlsdr-dev automake autoconf \
    libtool pkg-config libsamplerate-dev git

echo "=== [2/8] dedicated system user ==="
if ! id openwebrx >/dev/null 2>&1; then
    adduser --system --group --home "$DATA_DIR" --no-create-home openwebrx
fi
usermod -aG plugdev openwebrx
mkdir -p "$DATA_DIR"
chown openwebrx:openwebrx "$DATA_DIR"

mkdir -p "$BUILD_DIR"

echo "=== [3/8] csdr (C++ library, luarvique fork, system-wide via make install) ==="
ensure_repo_at "https://github.com/luarvique/csdr.git" "$BUILD_DIR/csdr" "$CSDR_COMMIT"
if [ "$REPO_WAS_RECLONED" = "1" ] || ! ldconfig -p | grep -q libcsdr.so; then
    cd "$BUILD_DIR/csdr"
    mkdir -p build && cd build
    cmake ..
    echo "csdr: starting make -j$BUILD_JOBS at $(date '+%H:%M:%S') - this is a long step; if this terminal ever goes silent for several minutes with no further output, that's a real interruption to investigate, not normal behavior"
    make -j"$BUILD_JOBS"
    echo "csdr: make finished at $(date '+%H:%M:%S'), running make install"
    make install
    ldconfig
else
    echo "csdr already installed, skipping"
fi

echo "=== [4/8] owrx_connector (C++ binaries, luarvique fork, system-wide via make install) ==="
ensure_repo_at "https://github.com/luarvique/owrx_connector.git" "$BUILD_DIR/owrx_connector" "$OWRX_CONNECTOR_COMMIT"
if [ "$REPO_WAS_RECLONED" = "1" ] || ! command -v rtl_connector >/dev/null 2>&1; then
    cd "$BUILD_DIR/owrx_connector"
    mkdir -p build && cd build
    cmake ..
    echo "owrx_connector: starting make -j$BUILD_JOBS at $(date '+%H:%M:%S')"
    make -j"$BUILD_JOBS"
    echo "owrx_connector: make finished at $(date '+%H:%M:%S'), running make install"
    make install
    ldconfig
else
    echo "owrx_connector already installed, skipping"
fi

echo "=== [5/8] Python venv + pycsdr (luarvique fork) ==="
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install --upgrade pip setuptools wheel

ensure_repo_at "https://github.com/luarvique/pycsdr.git" "$BUILD_DIR/pycsdr" "$PYCSDR_COMMIT"
if [ "$REPO_WAS_RECLONED" = "1" ] || ! "$VENV_DIR/bin/python3" -c "from pycsdr.modules import NoiseFilter" >/dev/null 2>&1; then
    cd "$BUILD_DIR/pycsdr"
    "$VENV_DIR/bin/python3" setup.py install install_headers
else
    echo "pycsdr already installed in venv with the expected NoiseFilter symbol, skipping"
fi

echo "=== [6/8] OpenWebRX+ itself (luarvique fork) ==="
ensure_repo_at "https://github.com/luarvique/openwebrx.git" "$BUILD_DIR/openwebrx" "$OPENWEBRX_COMMIT"
cd "$BUILD_DIR/openwebrx"
"$VENV_DIR/bin/pip" install --force-reinstall --no-deps .

echo "=== [7/8] configuration ==="
mkdir -p /etc/openwebrx
cp "$REPO_ROOT/etc/openwebrx/openwebrx.conf" /etc/openwebrx/openwebrx.conf

# Seed the SDR/profile configuration exactly once - re-running this
# script must not clobber any configuration the operator has since
# changed via OpenWebRX+'s own /settings web UI.
if [ ! -f "$DATA_DIR/settings.json" ] && [ ! -f "$DATA_DIR/sdrs.json" ]; then
    echo "No existing OpenWebRX+ config found - seeding from etc/openwebrx/sdrs_seed.py"
    cp "$REPO_ROOT/etc/openwebrx/sdrs_seed.py" /etc/openwebrx/config_webrx.py
    cd "$DATA_DIR"
    sudo -u openwebrx HOME="$DATA_DIR" "$VENV_DIR/bin/openwebrx" config migrate --source=/etc/openwebrx/config_webrx.py || \
        echo "WARNING: config migrate reported an error - check by hand before starting the service (see docs/RADIO-SDR-ARCHITECTURE-DESIGN.md)."
else
    echo "Existing OpenWebRX+ config found in $DATA_DIR - leaving it untouched (re-run is idempotent, not destructive)."
fi

# Record the exact upstream commits this install used, for reproducibility.
{
    echo "openwebrx=$OPENWEBRX_COMMIT"
    echo "pycsdr=$PYCSDR_COMMIT"
    echo "csdr=$CSDR_COMMIT"
    echo "owrx_connector=$OWRX_CONNECTOR_COMMIT"
} > /etc/openwebrx/INSTALLED_COMMIT

echo "=== [8/8] systemd + nginx ==="
cp "$REPO_ROOT/etc/systemd/system/openwebrx.service" /etc/systemd/system/openwebrx.service
systemctl daemon-reload
systemctl enable openwebrx

# nginx: copy the include target FIRST, then the updated site file that
# references it, then test before ever reloading - never leave a
# window where sites-enabled/default's include line points at a file
# that doesn't exist yet, which would fail nginx's config test and
# could take down the whole PirateBox site on the next reload/restart.
cp "$REPO_ROOT/etc/nginx/openwebrx-location.conf" /etc/nginx/openwebrx-location.conf
if [ ! -f /etc/nginx/sites-available/default.pre-openwebrx.bak ]; then
    cp /etc/nginx/sites-available/default /etc/nginx/sites-available/default.pre-openwebrx.bak
fi
cp "$REPO_ROOT/etc/nginx/sites-available/default" /etc/nginx/sites-available/default

if nginx -t; then
    systemctl reload nginx
    echo "nginx: config test passed, reloaded."
else
    echo "nginx: config test FAILED - rolling back sites-available/default to its pre-install version and NOT reloading." >&2
    cp /etc/nginx/sites-available/default.pre-openwebrx.bak /etc/nginx/sites-available/default
    exit 1
fi

echo "=== starting openwebrx.service ==="
systemctl restart openwebrx
sleep 3
systemctl status openwebrx --no-pager -l || true

echo
echo "=== Install complete ==="
echo "Pinned commits: openwebrx=$OPENWEBRX_COMMIT pycsdr=$PYCSDR_COMMIT csdr=$CSDR_COMMIT owrx_connector=$OWRX_CONNECTOR_COMMIT"
echo "Recent journal:"
journalctl -u openwebrx --no-pager -n 40 || true
