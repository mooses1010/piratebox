#!/bin/bash
#
# PirateBox - Phase 4: set (or change) the admin/status page password.
#
# The admin page (/admin/) is protected by HTTP Basic Auth at the nginx
# level. This is deliberately NOT set up automatically with any default
# credential - the installer deploys an EMPTY htpasswd file, which means
# the admin page is completely inaccessible (fails every login) until you
# run this script. No password is ever committed to git.
#
# Run as root: sudo ./setup_admin_password.sh

set -euo pipefail

HTPASSWD_FILE="/etc/nginx/.piratebox_admin_htpasswd"

if [ "$(id -u)" -ne 0 ]; then
    echo "Error: this script must be run as root (sudo ./setup_admin_password.sh)." >&2
    exit 1
fi

if ! command -v openssl >/dev/null 2>&1; then
    echo "Error: openssl is required (used to hash the password) but was not found." >&2
    exit 1
fi

read -rp "Admin username [admin]: " ADMIN_USER
ADMIN_USER=${ADMIN_USER:-admin}

if [[ "$ADMIN_USER" == *:* ]]; then
    echo "Error: username cannot contain ':'." >&2
    exit 1
fi

read -rsp "Admin password: " ADMIN_PASS
echo
read -rsp "Confirm password: " ADMIN_PASS_CONFIRM
echo

if [ -z "$ADMIN_PASS" ]; then
    echo "Error: password cannot be empty (an empty password file locks the page out entirely, which is the current safe default - leave it that way if you're not ready to set one)." >&2
    exit 1
fi

if [ "$ADMIN_PASS" != "$ADMIN_PASS_CONFIRM" ]; then
    echo "Error: passwords did not match. Nothing was changed." >&2
    exit 1
fi

HASH=$(openssl passwd -apr1 "$ADMIN_PASS")
printf '%s:%s\n' "$ADMIN_USER" "$HASH" > "$HTPASSWD_FILE"
chown root:www-data "$HTPASSWD_FILE"
chmod 0640 "$HTPASSWD_FILE"

echo "Wrote $HTPASSWD_FILE for user '$ADMIN_USER'."

if command -v nginx >/dev/null 2>&1; then
    if nginx -t 2>&1; then
        systemctl reload nginx
        echo "nginx reloaded. Admin page is now available at http://10.0.0.1/admin/ with the credentials you just set."
    else
        echo "Warning: nginx -t failed - check your nginx config before reloading manually." >&2
        exit 1
    fi
fi
