#!/bin/bash
#
# Applies piratebox_progression.py to the live OLED daemon install and
# restarts piratebox-oled.service. Run as root:
#   sudo bash tools/update_progression.sh
#
# WHY THIS IS NEEDED (2026-09-06, Captain's Log achievement-description
# round): piratebox_progression.py is imported in-process, once, at
# piratebox-oled.service startup (piratebox_oled_daemon.py's own
# `import piratebox_progression`) - there is no hot-reload path, so a
# source change only takes effect after the file is replaced on disk
# AND the service is restarted. The live copy lives at
# /usr/local/bin/piratebox_progression.py, root-owned
# (-rwxr-xr-x root:root) - this repo's own copy changes nothing live
# until this script (or the equivalent manual steps) runs, exactly the
# same "repo vs. deployed" split this project's other optional
# capabilities (OpenWebRX+, etc.) already have their own update
# scripts for. This is the first such script for the OLED/Progression
# subsystem - previous rounds deployed it fully by hand (see
# docs/OPERATIONAL-DECISIONS.md's "PirateBox Progression" entry,
# 2026-09-04) - written now because this round needs a second real
# deploy of the same file and a repeatable, narrowly-scoped script beats
# asking the operator to re-derive the same two commands from memory.
#
# SAFE BY CONSTRUCTION: this script touches exactly one file
# (piratebox_progression.py) and restarts exactly one already-optional,
# already-isolated service (piratebox-oled.service has no Requires=/
# BindsTo= on any core PirateBox service in either direction - see that
# unit file's own header). A bad copy or a restart failure here cannot
# affect hostapd/dnsmasq/nginx/php-fpm or any core PirateBox function -
# worst case, Silly Mode/the OLED face stops updating until fixed.
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

cp "$REPO_ROOT/piratebox_progression.py" /usr/local/bin/piratebox_progression.py
chown root:root /usr/local/bin/piratebox_progression.py
chmod 755 /usr/local/bin/piratebox_progression.py
echo "Copied piratebox_progression.py -> /usr/local/bin/piratebox_progression.py"

systemctl restart piratebox-oled
sleep 3
systemctl status piratebox-oled --no-pager -l || true
echo
echo "Recent journal:"
journalctl -u piratebox-oled --no-pager -n 20 || true
