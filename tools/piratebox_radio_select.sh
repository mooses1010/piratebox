#!/bin/bash
#
# STAGED - NOT INSTALLED, NOT ENABLED, NOT WIRED TO ANY SYSTEMD UNIT.
# Part of the External AP Architecture + Production Migration Readiness
# Round (2026-09-03) - see docs/EXTERNAL-AP-ARCHITECTURE-DESIGN.md
# "Boot fallback design" for the full reasoning. This script exists so a
# future migration has a concrete, reviewable boot-time decision step to
# adopt deliberately - it is not run by anything today, and running it
# today would have no effect on production (see "What this script does
# NOT do" below).
#
# PURPOSE: decide, once, at boot, before hostapd starts, which physical
# radio should serve as the PirateBox visitor AP - the external
# AWUS036ACM (stable name "pb-ap", see
# etc/udev/rules.d/99-piratebox-external-ap.rules) if it's present and
# healthy, otherwise the onboard wlan0 - and record that decision
# somewhere the rest of the system (status helper, admin/OLED, and a
# separate apply step) can read it.
#
# WHAT THIS SCRIPT DOES NOT DO:
#   - It does NOT edit /etc/hostapd/hostapd.conf, /etc/dnsmasq.conf, or
#     /etc/dhcpcd.conf. Deciding and applying are kept as two separate
#     steps on purpose (same preview-then-apply discipline as
#     piratebox_deploy.sh --dry-run) - a future "apply" step, reviewed
#     and gated separately, would read this script's decision and
#     template the actual hostapd/dnsmasq interface= lines from it. That
#     apply step does not exist yet either - see
#     docs/EXTERNAL-AP-ARCHITECTURE-DESIGN.md "Migration plan".
#   - It does NOT run continuously or watch for the adapter disappearing
#     at runtime. Boot-time selection only, per that same design doc's
#     "Runtime-failure behavior" section: automatic runtime fallback
#     (hot-swapping the active AP while PirateBox is running) is
#     substantially riskier - two DHCP/AP instances fighting over
#     10.0.0.1, or rapid flapping if a marginal USB connection resets
#     repeatedly - and is deliberately left undesigned/unimplemented
#     this round, not attempted half-heartedly here.
#   - It does NOT decide anything about 5GHz/regulatory domain, antenna
#     configuration, or NetworkManager ownership - those are separate,
#     already-staged/documented pieces (see the same design doc).
#
# OUTPUT: a small JSON record at /run/piratebox/radio-selection.json
# (tmpfs, gone every boot, recreated fresh every run - never a source of
# stale truth). Shape:
#   {"decision": "external"|"onboard", "interface": "pb-ap"|"wlan0",
#    "reason": "<human string>", "decided_at": <unix ts>}
#
# EXIT STATUS: always 0 (this script only observes and records - it
# should never fail a boot sequence just because the external adapter
# happens to be absent, which is an entirely expected, supported state,
# not an error).

set -u

OUT_DIR="/run/piratebox"
OUT_FILE="$OUT_DIR/radio-selection.json"
TMP_FILE="$(mktemp "${OUT_FILE}.XXXXXX" 2>/dev/null || echo "${OUT_FILE}.tmp")"

mkdir -p "$OUT_DIR" 2>/dev/null || true

decision="onboard"
interface="wlan0"
reason="default: no external AP adapter present"

# "Healthy" here deliberately means more than "the interface exists":
# it must be a real net device (not just a udev-renamed but half-bound
# leftover), and not soft/hard rfkilled - both are cheap, read-only
# checks appropriate for a boot-time gate. It does NOT attempt to bring
# the interface up or test association - that belongs to the (separate,
# not-yet-built) apply step, not this decision step.
if command -v ip >/dev/null 2>&1 && ip link show pb-ap >/dev/null 2>&1; then
    rfkill_blocked=false
    if command -v rfkill >/dev/null 2>&1; then
        # Match this adapter's rfkill line by the interface name rfkill
        # itself reports, not by list position (list order is not
        # guaranteed stable, for the same reason interface enumeration
        # order isn't - see docs/EXTERNAL-AP-ARCHITECTURE-DESIGN.md
        # "Stable ALFA identity").
        if rfkill list 2>/dev/null | grep -A2 "pb-ap" | grep -qi "Soft blocked: yes\|Hard blocked: yes"; then
            rfkill_blocked=true
        fi
    fi
    if [ "$rfkill_blocked" = "false" ]; then
        decision="external"
        interface="pb-ap"
        reason="pb-ap present and not rfkilled"
    else
        reason="pb-ap present but rfkilled - falling back to onboard"
    fi
fi

cat > "$TMP_FILE" <<EOF
{
  "decision": "$decision",
  "interface": "$interface",
  "reason": "$reason",
  "decided_at": $(date +%s)
}
EOF

chmod 0644 "$TMP_FILE" 2>/dev/null || true
mv -f "$TMP_FILE" "$OUT_FILE" 2>/dev/null || true

exit 0
