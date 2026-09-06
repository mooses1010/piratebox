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
# installation" path from jketterl/openwebrx's wiki, which luarvique's
# OpenWebRX+ fork shares - both build on the same csdr/pycsdr/
# owrx_connector foundation), adapted in two evidence-backed ways:
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

# 2026-09-05 incident: a first install attempt (full `-j$(nproc)` = 4
# concurrent GCC/G++ processes) progressed cleanly to ~90% of csdr's own
# build, then the Pi rebooted with no persistent journal surviving to
# explain why - undervoltage was logged early in the next boot (as it
# is on every boot of this chronically marginal-power Pi - not, by
# itself, proof of causation), but no prior stress in this whole
# investigation (RTL-SDR captures, USB operations) involved *sustained*
# full-core load for minutes at a time the way a parallel C++ build
# does. Capping build parallelism is a direct, reasoned mitigation for
# that newly-observed load profile, not a general slowdown for its own
# sake - see docs/RADIO-SDR-ARCHITECTURE-DESIGN.md's OpenWebRX+ section
# for the full incident writeup. This project's sudoers config resets
# the environment on every sudo invocation, so an inline
# `BUILD_JOBS=N sudo ...` override would be silently ignored - edit the
# default below directly if a different value is ever wanted.
BUILD_JOBS=2

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

echo "=== [3/8] csdr (C library, system-wide via make install) ==="
if [ ! -f /usr/local/lib/libcsdr.so ] && [ ! -f /usr/local/lib/libcsdr.so.1 ]; then
    cd "$BUILD_DIR"
    [ -d csdr ] || git clone -b master --depth 1 https://github.com/jketterl/csdr.git
    cd csdr

    # Upstream compatibility patch: aarch64 + GCC 14+ (Debian Trixie's
    # default) fails to build csdr's NEON-only debug-trace code with
    # "implicit declaration of function 'errhead'" - a real, confirmed-
    # unfixed upstream bug (https://github.com/jketterl/csdr/issues/13),
    # not a misconfiguration on this project's part. See the patch
    # file's own header comment for the full root-cause explanation.
    # Applied idempotently: a marker string in the patch itself lets a
    # re-run detect it's already in place rather than re-applying (which
    # `patch` would otherwise reject as already-applied noise, or - worse
    # - silently double-apply against a differently-edited tree).
    if ! grep -q "errhead() is defined ONLY in the separate csdr.c CLI\|Upstream bug (confirmed unfixed" src/libcsdr.c 2>/dev/null; then
        echo "Applying csdr-errhead-neon-aarch64.patch"
        patch -p1 < "$REPO_ROOT/etc/openwebrx/patches/csdr-errhead-neon-aarch64.patch"
    else
        echo "csdr-errhead-neon-aarch64.patch already applied, skipping"
    fi

    mkdir -p build && cd build
    cmake ..
    echo "csdr: starting make -j$BUILD_JOBS at $(date '+%H:%M:%S') - this is the long step; if this terminal ever goes silent for several minutes with no further output, that's a real interruption to investigate, not normal behavior"
    make -j"$BUILD_JOBS"
    echo "csdr: make finished at $(date '+%H:%M:%S'), running make install"
    make install
    ldconfig
else
    echo "csdr already installed, skipping"
fi

echo "=== [4/8] owrx_connector (C++ binaries, system-wide via make install) ==="
if ! command -v rtl_connector >/dev/null 2>&1; then
    cd "$BUILD_DIR"
    [ -d owrx_connector ] || git clone -b master --depth 1 https://github.com/jketterl/owrx_connector.git
    cd owrx_connector
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

echo "=== [5/8] Python venv + pycsdr ==="
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install --upgrade pip setuptools wheel

if ! "$VENV_DIR/bin/python3" -c "import pycsdr" >/dev/null 2>&1; then
    cd "$BUILD_DIR"
    [ -d pycsdr ] || git clone -b master --depth 1 https://github.com/jketterl/pycsdr.git
    cd pycsdr
    "$VENV_DIR/bin/python3" setup.py install install_headers
else
    echo "pycsdr already installed in venv, skipping"
fi

echo "=== [6/8] OpenWebRX+ itself ==="
cd "$BUILD_DIR"
if [ ! -d openwebrx ]; then
    git clone -b master --depth 1 https://github.com/luarvique/openwebrx.git
fi
cd openwebrx
OWRX_COMMIT="$(git rev-parse HEAD)"
echo "OpenWebRX+ commit: $OWRX_COMMIT"
"$VENV_DIR/bin/pip" install .

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

# Record the exact upstream commit this install used, for reproducibility.
echo "$OWRX_COMMIT" > /etc/openwebrx/INSTALLED_COMMIT

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
cp /etc/nginx/sites-available/default /etc/nginx/sites-available/default.pre-openwebrx.bak
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
echo "OpenWebRX+ commit: $OWRX_COMMIT"
echo "Recent journal:"
journalctl -u openwebrx --no-pager -n 40 || true
