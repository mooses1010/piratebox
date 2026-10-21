#!/bin/bash
#
# Read-only functional verification of the live PirateBox site and its
# supporting services. No sudo required, changes nothing, posts no
# content - every probe is a GET except one deliberately CSRF-less
# multipart POST (see below), so it can be run any time, including on a
# box with real visitors on it.
#
#   tools/verify_piratebox_http.sh
#
# Written for the CVE-2026-109618 / CVE-2026-109619 PHP security update
# (2026-10-21) as the before/after regression check - a PHP package
# upgrade plus an FPM restart touches every dynamic page on the site at
# once, so "nginx is still up" is not evidence that anything still
# works. Kept as a general-purpose smoke test: it is equally the right
# check after any deploy, any php.ini change, or any FPM restart.
#
# WHAT IT DELIBERATELY DOES NOT DO: it does not log in to /admin/ (it
# asserts the 401 instead - that the basic-auth gate is still closed is
# the security-relevant fact, and this way the script never needs a
# credential), and it does not post chat/bulletin content, so it can
# never pollute real community data.
#
# EXPECTED CODES WORTH KNOWING: public/upload.php answers a GET with
# 302 to / by design (upload.php:23 - it is POST-only, the form lives
# on index.php), and answers a multipart POST without a valid CSRF
# token with 302 as well. Both are correct behaviour, not failures. The
# multipart POST is included on purpose: it is the exact request shape
# that reaches the code path CVE-2026-109619 lives in, so a 502/500
# there is the first thing that would show a broken FPM.

set -uo pipefail

BASE="${PIRATEBOX_BASE_URL:-http://127.0.0.1}"
pass=0; fail=0

chk() { # name expected-code path [extra curl args...]
    local name="$1" expect="$2" path="$3"; shift 3
    local code
    code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 "$@" "${BASE}${path}" 2>/dev/null)"
    if [ "$code" = "$expect" ]; then
        printf '  OK   %-40s %s\n' "$name" "$code"; pass=$((pass+1))
    else
        printf '  FAIL %-40s got %s, want %s\n' "$name" "$code" "$expect"; fail=$((fail+1))
    fi
}

echo "PirateBox verification against ${BASE}"

echo
echo "--- captive portal detection (per-OS probe URLs) ---"
chk "apple hotspot-detect.html"  302 /hotspot-detect.html
chk "apple library test success" 302 /library/test/success.html
chk "apple success.html"         302 /success.html
chk "android generate_204"       302 /generate_204
chk "android gen_204"            302 /gen_204
chk "windows connecttest.txt"    302 /connecttest.txt
chk "windows ncsi.txt"           302 /ncsi.txt
chk "RFC 8908 captive-portal"    200 /.well-known/captive-portal

# The portal API's body matters as much as its status - a client that
# gets valid JSON with captive=true is what drives the sign-in prompt.
# Matched with bash's own [[ == *...* ]], not "| grep -q" - a
# grep-in-a-pipe check elsewhere in this project's PHP update tooling
# (tools/apply_php_security_update.sh Step 3) was confirmed to fail
# intermittently under `pipefail` via a grep -q/SIGPIPE race even when
# the match was genuinely present; this script sets the same `pipefail`
# (see the top of the file), so the same pattern is avoided here too
# rather than trusting that this particular body is "probably small
# enough" not to trigger it.
body="$(curl -sS --max-time 15 "${BASE}/.well-known/captive-portal" 2>/dev/null)"
if [[ "$body" == *'"captive":true'* ]]; then
    printf '  OK   %-40s %s\n' "captive-portal body" "$body"; pass=$((pass+1))
else
    printf '  FAIL %-40s %s\n' "captive-portal body" "$body"; fail=$((fail+1))
fi

echo
echo "--- core pages (each one rendered by PHP-FPM) ---"
chk "landing / (index.php)"       200 /
chk "chat.php"                    200 /chat.php
chk "bulletin.php"                200 /bulletin.php
chk "messages.php"                200 /messages.php
chk "help.php"                    200 /help.php
chk "whatcanidohere.php"          200 /whatcanidohere.php
chk "upload.php (POST-only, 302)" 302 /upload.php

echo
echo "--- utility sections ---"
for u in "" status download library fieldtools search maps radio outdoor \
         glossary computing materials mechanical manifest captains-log local; do
    chk "utility/${u:-index}" 200 "/utility/${u:+$u/}"
done

echo
echo "--- JSON API endpoints (status + payload validity) ---"
for e in "chat.php?fetch=1" "bulletin.php?fetch=1" "messages.php?fetch=1"; do
    code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 "${BASE}/${e}" 2>/dev/null)"
    body="$(curl -sS --max-time 15 "${BASE}/${e}" 2>/dev/null)"
    if [ "$code" = "200" ] && printf '%s' "$body" | php -r \
        'json_decode(stream_get_contents(STDIN)); exit(json_last_error()===JSON_ERROR_NONE?0:1);' 2>/dev/null
    then
        printf '  OK   %-40s %s, valid JSON (%s bytes)\n' "$e" "$code" "${#body}"; pass=$((pass+1))
    else
        printf '  FAIL %-40s %s, invalid/empty JSON\n' "$e" "$code"; fail=$((fail+1))
    fi
done

echo
echo "--- admin gate stays closed (no credential used) ---"
chk "admin/ unauthenticated"          401 /admin/
chk "admin/index.php unauthenticated" 401 /admin/index.php

echo
echo "--- security posture ---"
chk "hidden dotfile denied"  403 /.env
chk "missing .php is 404"    404 /does-not-exist.php

echo
echo "--- multipart POST path (where CVE-2026-109619 lived) ---"
# A real multipart/form-data POST, which is what triggers PHP's
# upload-progress handling. Without a CSRF token the app answers 302;
# what must never happen is 502/500/000, which would mean FPM crashed
# or died handling the request.
code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 \
        -F "probe=@/etc/hostname" "${BASE}/upload.php" 2>/dev/null)"
case "$code" in
    502|500|000|"")
        printf '  FAIL %-40s %s (FPM failed on multipart)\n' "multipart POST to upload.php" "$code"
        fail=$((fail+1)) ;;
    *)
        printf '  OK   %-40s %s (handled, no FPM fault)\n' "multipart POST to upload.php" "$code"
        pass=$((pass+1)) ;;
esac

echo
echo "--- required services ---"
for s in nginx php8.4-fpm hostapd dnsmasq; do
    st="$(systemctl is-active "$s" 2>/dev/null)"
    if [ "$st" = active ]; then printf '  OK   %-40s %s\n' "$s" "$st"; pass=$((pass+1))
    else printf '  FAIL %-40s %s\n' "$s" "$st"; fail=$((fail+1)); fi
done

echo
echo "--- supporting services (reported, not asserted) ---"
# Reported rather than asserted because these are legitimately optional
# or transient: piratebox-gpio only runs with the button wired up, and
# piratebox-status is a oneshot driven by its timer, so 'inactive' or
# 'activating' here is normal and not a regression.
for s in piratebox-oled piratebox-esp32-supervisor piratebox-gpio \
         piratebox-status piratebox-history piratebox-backup.timer; do
    st="$(systemctl is-active "$s" 2>/dev/null || true)"
    printf '  --   %-40s %s\n' "$s" "${st:-not-present}"
done

echo
echo "--- visitor AP radio state (must be undisturbed) ---"
if ip link show pb-ap >/dev/null 2>&1; then
    printf '  OK   %-40s %s\n' "pb-ap interface" \
        "$(ip -br link show pb-ap 2>/dev/null | awk '{print $2}')"; pass=$((pass+1))
    printf '  --   %-40s %s\n' "associated stations" \
        "$(iw dev pb-ap station dump 2>/dev/null | grep -c '^Station' || true)"
else
    printf '  --   %-40s %s\n' "pb-ap interface" "not present"
fi

echo
echo "RESULT: ${pass} passed, ${fail} failed"
[ "$fail" -eq 0 ]
