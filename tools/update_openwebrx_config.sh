#!/bin/bash
#
# Applies etc/openwebrx/sdrs_seed.py AND etc/openwebrx/upstream/bands.json
# to the live OpenWebRX+ install and restarts the service - for use AFTER
# tools/install_openwebrx.sh has already run once. Run as root:
# sudo bash tools/update_openwebrx_config.sh
#
# WHY THIS IS SAFE AND EFFECTIVE (confirmed by reading the actual
# installed source, not assumed): OpenWebRX+'s config is a layered
# stack - a "dynamic" JSON store (/var/lib/openwebrx/settings.json,
# written by OpenWebRX+'s own /settings admin web UI) takes priority
# over the "classic" /etc/openwebrx/config_webrx.py file, which is
# otherwise executed fresh on every service start
# (owrx/config/classic.py). On this Pi, as of 2026-09-05,
# settings.json does not exist at all - no admin account has ever used
# /settings - so nothing masks the classic file, and it is the actual
# live source of truth for every setting in it. Re-copying an updated
# etc/openwebrx/sdrs_seed.py over /etc/openwebrx/config_webrx.py and
# restarting the service is therefore a fully effective way to change
# live SDR/profile/general-setting configuration for as long as that
# remains true.
#
# IF AN ADMIN ACCOUNT IS EVER CREATED AND USED (`openwebrx admin
# adduser <name>`, then a real /settings edit): settings.json will
# start existing, and from that point on, whichever specific keys the
# admin has touched via the UI will take priority over this file - this
# script would then only affect keys the admin has NOT touched via the
# UI. Not a concern today (no admin account exists), but worth knowing
# before relying on this script indefinitely.

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "This must be run as root (sudo bash tools/update_openwebrx_config.sh)." >&2
    exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -f /var/lib/openwebrx/settings.json ]; then
    echo "WARNING: /var/lib/openwebrx/settings.json exists - an admin has used" >&2
    echo "the /settings web UI at some point. This script will still apply, but" >&2
    echo "any setting the admin has explicitly changed via that UI will continue" >&2
    echo "to take priority over this file - see this script's own header." >&2
fi

cp "$REPO_ROOT/etc/openwebrx/sdrs_seed.py" /etc/openwebrx/config_webrx.py
echo "Copied etc/openwebrx/sdrs_seed.py -> /etc/openwebrx/config_webrx.py"

# Band plan ribbon data (2026-09-06, docs/RADIO-SDR-ARCHITECTURE-
# DESIGN.md section 14.3/15) - vendored verbatim from OpenWebRX+ itself
# (see etc/openwebrx/upstream/README.md for provenance/licensing), not
# admin-UI-editable the way the SDR/profile config above is, so always
# safe to (re-)copy here too.
cp "$REPO_ROOT/etc/openwebrx/upstream/bands.json" /etc/openwebrx/bands.json
echo "Copied etc/openwebrx/upstream/bands.json -> /etc/openwebrx/bands.json"

systemctl restart openwebrx
sleep 3
systemctl status openwebrx --no-pager -l || true
echo
echo "Recent journal:"
journalctl -u openwebrx --no-pager -n 20 || true
