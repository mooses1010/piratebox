#!/bin/bash
#
# Applies the OLED daemon and its imported modules (piratebox_
# progression.py, piratebox_oled_daemon.py, piratebox_bh1750.py) to the
# live install and restarts piratebox-oled.service. Run as root:
#   sudo bash tools/update_progression.sh
#
# WHY THIS IS NEEDED (2026-09-06, Captain's Log achievement-description
# round): these files are imported/run in-process, once, at
# piratebox-oled.service startup - there is no hot-reload path, so a
# source change only takes effect after the file is replaced on disk
# AND the service is restarted. The live copies are root-owned
# (-rwxr-xr-x root:root) under /usr/local/bin/ - this repo's own copies
# change nothing live until this script (or the equivalent manual
# steps) runs, exactly the same "repo vs. deployed" split this
# project's other optional capabilities (OpenWebRX+, etc.) already have
# their own update scripts for. Kept under its original name (this was
# the first such script for the OLED subsystem) even though its scope
# has grown alongside the subsystem it deploys - a repeatable, narrowly-
# scoped script beats asking the operator to re-derive several copy
# commands from memory each round.
#
# 2026-09-07 (BH1750 ambient light sensor commissioning): extended to
# also deploy piratebox_oled_daemon.py (gained a startup-time
# registration of the new sensor into Progression's HARDWARE_SIGNALS
# registry - see that file's own comment right after Progression loads)
# and the new piratebox_bh1750.py module itself (all direct I2C access
# to the sensor - see its own header). Both copies are skipped
# harmlessly if the sensor is never wired on a given install -
# piratebox_oled_daemon.py's registration is already wrapped in its own
# try/except, degrading to "signal stays unregistered" exactly like a
# missing Progression subsystem already does.
#
# 2026-09-07, later still (ambient light At-a-Glance page): extended
# again to also deploy piratebox_glance.py - gained a new "ambient"
# GLANCE_PAGES entry consuming the same bh1750_module reference
# piratebox_oled_daemon.py already keeps (no new I2C reader, no second
# poller - see that file's own build_glance_metrics() comment). Same
# graceful-absence behavior: on an install with no BH1750, the page is
# simply never eligible (ambient_lux stays None), never a broken-
# looking placeholder.
#
# SAFE BY CONSTRUCTION: this script touches only these files and
# restarts exactly one already-optional, already-isolated service
# (piratebox-oled.service has no Requires=/BindsTo= on any core
# PirateBox service in either direction - see that unit file's own
# header). A bad copy or a restart failure here cannot affect
# hostapd/dnsmasq/nginx/php-fpm or any core PirateBox function - worst
# case, Silly Mode/the OLED face stops updating until fixed.
#
# Durable state is untouched by this script: /var/lib/piratebox-oled/
# progression.json (XP, levels, achievements already unlocked, history)
# is never written, moved, or reset here - only the CODE that reads and
# renders it changes. An achievement a device already discovered before
# this update keeps its exact unlock timestamp and XP; it simply gains
# a description the next time the daemon builds its public summary.

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "This must be run as root (sudo bash tools/update_progression.sh)." >&2
    exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

for f in piratebox_progression.py piratebox_oled_daemon.py piratebox_bh1750.py piratebox_glance.py; do
    cp "$REPO_ROOT/$f" "/usr/local/bin/$f"
    chown root:root "/usr/local/bin/$f"
    chmod 755 "/usr/local/bin/$f"
    echo "Copied $f -> /usr/local/bin/$f"
done

systemctl restart piratebox-oled
sleep 3
systemctl status piratebox-oled --no-pager -l || true
echo
echo "Recent journal:"
journalctl -u piratebox-oled --no-pager -n 20 || true
