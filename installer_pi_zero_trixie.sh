#!/bin/bash

# PirateBox Installer Script
# Run this script as root: sudo ./installer.sh

set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "Error: This script must be run as root."
    echo "Usage: sudo ./installer.sh"
    exit 1
fi

while true; do
    read -p "Did you run: sudo raspi-config and set all of the Localisation Options? Be sure to do this before running this installer. (y/n) " yn
    case $yn in
        [Yy]* ) break;;
        [Nn]* ) echo "Please run sudo raspi-config first."; exit;;
        * ) echo "Please answer yes or no.";;
    esac
done

echo "========================================"
echo "   PirateBox Installer Started"
echo "   Experimental - Tested on Raspberry Pi Zero 2 W"
echo "========================================"

# Time Sync Fix (Crucial for apt update)
echo "[+] Configuring Time Sync (NTP)..."
if ! grep -q "NTP=time.cloudflare.com" /etc/systemd/timesyncd.conf; then
    sed -i 's/#NTP=/NTP=time.cloudflare.com/' /etc/systemd/timesyncd.conf
    sed -i 's/NTP=/NTP=time.cloudflare.com/' /etc/systemd/timesyncd.conf
    systemctl restart systemd-timesyncd
    echo "    Waiting 5 seconds for time sync..."
    sleep 5
fi

# Install Dependencies
echo "[+] Updating system and installing dependencies..."
apt-get update
apt-get install -y hostapd dnsmasq dhcpcd5 nginx php-fpm php-mbstring qrencode
# NOTE (Phase 2 decision, 2026-08-31): this installer deliberately does NOT
# run `rpi-update`. Modern Raspberry Pi OS should not be moved onto
# bleeding-edge/untested firmware and kernel builds as part of a PirateBox
# install. See docs/OPERATIONAL-DECISIONS.md before reintroducing it.

# Network Configuration
echo "[+] Configuring Network..."

# dhcpcd
if ! grep -q "interface wlan0" /etc/dhcpcd.conf; then
    echo "    Configuring static IP for wlan0 in /etc/dhcpcd.conf..."
    # denyinterfaces eth0 + nohook resolv.conf (2026-09-03 Host/Management
    # DNS Isolation Fix - see docs/OPERATIONAL-DECISIONS.md "Host/
    # Management DNS Isolation Fix"): eth0 is this Pi's management/WAN
    # interface, meant to be owned entirely by NetworkManager (see the
    # conf.d install below) so it gets real upstream DNS. Without
    # `denyinterfaces eth0`, dhcpcd would also try to manage eth0 and
    # fight NetworkManager for it. Without `nohook resolv.conf`, dhcpcd's
    # global (not per-interface) resolv.conf hook rebuilds
    # /etc/resolv.conf from whatever DNS info dhcpcd itself has on EVERY
    # dhcpcd event, even for interfaces it isn't managing DNS for -
    # which on this box is nothing, so it silently overwrites
    # NetworkManager's real eth0 nameservers with an empty file. Both
    # lines must come before any `interface` stanza to apply globally.
    cat <<EOF >> /etc/dhcpcd.conf

denyinterfaces eth0
nohook resolv.conf

interface wlan0
static ip_address=10.0.0.1/24
nohook wpa_supplicant
EOF
    systemctl enable dhcpcd
    systemctl restart dhcpcd
fi

# NetworkManager: exclude the PirateBox AP radio(s) from NM management,
# and make NM's /etc/resolv.conf ownership explicit/deterministic for
# the interfaces it does manage (eth0). See etc/NetworkManager/conf.d/
# in the repo for the full rationale of each file; installed here so a
# fresh install can never end up in the un-isolated state that caused
# the 2026-09-03 incident (NetworkManager fighting hostapd for wlan0,
# or silently taking over /etc/resolv.conf ownership in a way a second
# manager - dhcpcd - could still race against).
echo "    Installing NetworkManager conf.d (AP exclusion + DNS ownership)..."
mkdir -p /etc/NetworkManager/conf.d
if [ -f "etc/NetworkManager/conf.d/99-piratebox.conf" ]; then
    cp "etc/NetworkManager/conf.d/99-piratebox.conf" /etc/NetworkManager/conf.d/99-piratebox.conf
else
    echo "    WARNING: etc/NetworkManager/conf.d/99-piratebox.conf not found in repo. Skipping."
fi
if [ -f "etc/NetworkManager/conf.d/98-piratebox-dns-ownership.conf" ]; then
    cp "etc/NetworkManager/conf.d/98-piratebox-dns-ownership.conf" /etc/NetworkManager/conf.d/98-piratebox-dns-ownership.conf
else
    echo "    WARNING: etc/NetworkManager/conf.d/98-piratebox-dns-ownership.conf not found in repo. Skipping."
fi
if command -v nmcli >/dev/null 2>&1 && systemctl is-active --quiet NetworkManager; then
    nmcli general reload conf || systemctl restart NetworkManager
fi

# hostapd
echo "    Creating /etc/hostapd/hostapd.conf..."
cat <<EOF > /etc/hostapd/hostapd.conf
interface=wlan0
driver=nl80211
ssid=PirateBox
hw_mode=g
channel=6
ieee80211n=1
wmm_enabled=1
auth_algs=1
wpa=0
country_code=US
EOF

# Point hostapd to config
sed -i 's|#DAEMON_CONF=""|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd
sed -i 's|DAEMON_CONF=""|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd
sed -i 's|#DAEMON_OPTS=""|DAEMON_OPTS=""|' /etc/default/hostapd
sed -i 's|DAEMON_OPTS=""|DAEMON_OPTS=""|' /etc/default/hostapd

systemctl unmask hostapd
systemctl enable hostapd

# hostapd systemd override: unblock Wi-Fi via rfkill before hostapd starts
# (fixes a boot-time race on some Pi models), and restart hostapd on ANY
# exit rather than only Restart=on-failure. Live testing (Phase 2,
# 2026-08-31) showed a hard hostapd failure can leave wlan0 in a state that
# briefly loses carrier, causing hostapd to exit CLEANLY (exit code 0) -
# which on-failure alone does not restart. Restart=always closes that gap;
# the base unit's StartLimitBurst=5/StartLimitIntervalUSec=10s (unchanged)
# still stops a genuine restart loop. See docs/OPERATIONAL-DECISIONS.md.
mkdir -p /etc/systemd/system/hostapd.service.d
cp etc/systemd/system/hostapd.service.d/override.conf /etc/systemd/system/hostapd.service.d/override.conf
systemctl daemon-reload

# dnsmasq
echo "    Configuring dnsmasq..."
[ -f /etc/dnsmasq.conf ] && cp /etc/dnsmasq.conf /etc/dnsmasq.conf.bak
cat <<EOF > /etc/dnsmasq.conf
interface=wlan0
dhcp-range=10.0.0.10,10.0.0.250,12h
address=/#/10.0.0.1

# Makes the wildcard above deterministic for every name, including this
# Pi's own hostname "piratebox" (which /etc/hosts would otherwise answer
# with 127.0.1.1 ahead of the wildcard) - see etc/dnsmasq.conf in the
# repo and docs/OPERATIONAL-DECISIONS.md for the full investigation.
no-hosts

# 2026-09-03 Host/Management DNS Isolation Fix (see
# docs/OPERATIONAL-DECISIONS.md): dnsmasq always answers queries
# arriving via loopback (127.0.0.1) regardless of `interface=` above -
# without this, the Pi's own host resolution can land on the captive
# wildcard above whenever /etc/resolv.conf has no nameserver lines
# (glibc's fallback resolver is 127.0.0.1). See etc/dnsmasq.conf in the
# repo for the full incident writeup.
except-interface=lo

# RFC 8910 / RFC 7710bis: DHCP option 114 advertises the Captive Portal API
# URL (RFC 8908) to clients that support it (Android 11+, some others).
# dnsmasq has no built-in name for option 114, so it's set numerically; the
# quoted value is sent as a raw ASCII URI string per RFC 8910 encoding.
# Endpoint is served by nginx at /.well-known/captive-portal. Legacy
# HTTP-probe-based detection (generate_204, hotspot-detect.html, ncsi.txt,
# etc.) is left in place unchanged for clients that don't support Capport.
dhcp-option=114,"http://10.0.0.1/.well-known/captive-portal"
EOF
systemctl restart dnsmasq

# Web Server Configuration
echo "[+] Configuring Web Server..."

# Nginx
if [ -f "etc/nginx/sites-available/default" ]; then
    echo "    Copying Nginx configuration..."
    cp "etc/nginx/sites-available/default" /etc/nginx/sites-available/default
else
    echo "    WARNING: etc/nginx/sites-available/default not found in repo. Skipping Nginx config copy."
fi

# PHP
PHP_VER=$(ls /etc/php/ | sort -V | tail -n 1)
echo "    Detected PHP version: $PHP_VER"
PHP_INI="/etc/php/$PHP_VER/fpm/php.ini"

if [ -f "$PHP_INI" ]; then
    echo "    Updating php.ini settings..."
    sed -i 's/^upload_max_filesize.*/upload_max_filesize = 120M/' "$PHP_INI"
    sed -i 's/^post_max_size.*/post_max_size = 130M/' "$PHP_INI"
    sed -i 's/^max_execution_time.*/max_execution_time = 300/' "$PHP_INI"
    sed -i 's/^display_errors.*/display_errors = Off/' "$PHP_INI"
    sed -i 's/^log_errors.*/log_errors = On/' "$PHP_INI"
    sed -i 's/^disable_functions.*/disable_functions = exec,passthru,shell_exec,system,proc_open,popen,curl_exec,curl_multi_exec,parse_ini_file,show_source/' "$PHP_INI"
    # Phase 1 defense-in-depth restriction (previously live-only, not
    # reproduced by this installer - fixed in Phase 4). Phase 4 adds
    # /var/www/piratebox-tmp (the disk-backed upload_tmp_dir configured
    # below via pool.d/www.conf) plus the exact /proc, /sys, and /run
    # paths the admin status page reads.
    sed -i 's|^;\?open_basedir.*|open_basedir = /var/www/html:/var/lib/php/sessions:/tmp:/var/www/piratebox-tmp:/proc/uptime:/proc/meminfo:/sys/class/thermal/thermal_zone0/temp:/run/piratebox/status.json|' "$PHP_INI"
fi

# PHP-FPM pool config (upload_tmp_dir, upload_max_filesize/post_max_size
# per-pool overrides) - previously present in this repo but never actually
# deployed by this installer; fixed in Phase 4.
if [ -f "etc/php/8.4/fpm/pool.d/www.conf" ] && [ -d "/etc/php/$PHP_VER/fpm/pool.d" ]; then
    echo "    Copying PHP-FPM pool configuration..."
    cp "etc/php/8.4/fpm/pool.d/www.conf" "/etc/php/$PHP_VER/fpm/pool.d/www.conf"
fi

# Phase 4: disk-backed PHP upload temp directory (replaces the tmpfs-backed
# system default /tmp - see docs/OPERATIONAL-DECISIONS.md). Declared via
# tmpfiles.d so it's recreated with correct ownership on every boot and
# periodically cleaned of anything abandoned by a crashed PHP-FPM worker.
echo "    Configuring disk-backed PHP upload temp directory..."
mkdir -p /var/www/piratebox-tmp
chown www-data:www-data /var/www/piratebox-tmp
chmod 0700 /var/www/piratebox-tmp
if [ -f "etc/tmpfiles.d/piratebox-tmp.conf" ]; then
    cp "etc/tmpfiles.d/piratebox-tmp.conf" /etc/tmpfiles.d/piratebox-tmp.conf
    systemd-tmpfiles --create /etc/tmpfiles.d/piratebox-tmp.conf || true
fi

# Application Deployment
echo "[+] Deploying Application files..."
mkdir -p /var/www/html/public/uploads
mkdir -p /var/www/html/data
cp -r var/www/html/* /var/www/html/
chown -R www-data:www-data /var/www/html
chmod 0755 /var/www/html/public/uploads
chmod 0755 /var/www/html/data

# Phase 5: QR codes for the Help page, generated fresh at deploy time
# with qrencode (a small, standard CLI tool - not a PHP/runtime
# dependency, and not committed to git since they're just a rendering of
# two static strings this installer already knows). SSID/security here
# match hostapd.conf's open "PirateBox" network - if you change the SSID
# or add a password, update the WIFI: string below to match.
#
# Two QR codes by design (2026-09-03, restored after a brief one-QR
# simplification round - see docs/OPERATIONAL-DECISIONS.md "Two-QR
# PirateBox Onboarding Restored"): a standards-compatible WIFI: join QR,
# plus a plain http://piratebox/ URL QR for opening the site once
# already connected. No nonstandard combined Wi-Fi+URL payload. The
# printed "OPEN > piratebox/" fallback text on the Help page (under the
# join QR) stays too - it's deliberate redundancy so the join QR alone
# is sufficient by itself, not a substitute for the second QR.
echo "    Generating QR codes..."
if command -v qrencode >/dev/null 2>&1; then
    qrencode -o /var/www/html/public/assets/qr-wifi.png -s 6 -m 2 "WIFI:T:nopass;S:PirateBox;;"
    qrencode -o /var/www/html/public/assets/qr-url.png -s 6 -m 2 "http://piratebox/"
    chown www-data:www-data /var/www/html/public/assets/qr-url.png /var/www/html/public/assets/qr-wifi.png
else
    echo "    WARNING: qrencode not found - QR images will be missing from the Help page."
fi

# Phase 4: record the deployed commit for the admin page's version display.
# Best-effort only - if this isn't a git checkout, the admin page just
# shows "unknown" rather than failing.
if command -v git >/dev/null 2>&1 && git rev-parse HEAD >/dev/null 2>&1; then
    git rev-parse HEAD > /var/www/html/includes/VERSION
    chown www-data:www-data /var/www/html/includes/VERSION
else
    rm -f /var/www/html/includes/VERSION
fi

# Phase 4: admin/status page (public/admin/, already copied above by the
# `cp -r var/www/html/*` step). Protected by nginx HTTP Basic Auth - see
# etc/nginx/sites-available/default. The htpasswd file is created EMPTY
# here (nobody can log in) rather than with any default credential; run
# setup_admin_password.sh afterwards to set a real password. No secret is
# ever committed to git or written by this installer.
echo "[+] Setting up admin page authentication (locked out until configured)..."
if [ ! -f /etc/nginx/.piratebox_admin_htpasswd ]; then
    touch /etc/nginx/.piratebox_admin_htpasswd
fi
chown root:www-data /etc/nginx/.piratebox_admin_htpasswd
chmod 0640 /etc/nginx/.piratebox_admin_htpasswd

# Phase 4: status helper timer (Wi-Fi client count, per-service health,
# undervoltage - see docs/OPERATIONAL-DECISIONS.md for why this needs to
# run as a separate root helper instead of from PHP).
echo "[+] Installing status helper timer..."
cp piratebox_status_helper.sh /usr/local/bin/
chmod +x /usr/local/bin/piratebox_status_helper.sh
cp etc/systemd/system/piratebox-status.service /etc/systemd/system/piratebox-status.service
cp etc/systemd/system/piratebox-status.timer /etc/systemd/system/piratebox-status.timer
systemctl daemon-reload
systemctl enable --now piratebox-status.timer

# Maintenance Scripts & Cron
echo "[+] Installing Maintenance Scripts..."
cp purge_uploads.sh /usr/local/bin/
chmod +x /usr/local/bin/purge_uploads.sh
cp restart_hostapd.sh /usr/local/bin/
chmod +x /usr/local/bin/restart_hostapd.sh
cp setup_admin_password.sh /usr/local/bin/
chmod +x /usr/local/bin/setup_admin_password.sh

echo "[+] Setting up Cron Jobs..."
# NOTE (Phase 2 decision, 2026-08-31): the nightly purge_uploads.sh cron and
# the hourly restart_hostapd.sh cron are deliberately NOT installed by
# default. purge_uploads.sh deletes ALL uploads/chat/messages irreversibly -
# this project's default data-retention policy is "automatic deletion of
# user content = OFF", so it is left available at /usr/local/bin only as a
# manual utility. restart_hostapd.sh unconditionally restarted hostapd every
# hour, disconnecting every connected Wi-Fi client for no diagnosed reason;
# real hostapd recovery is now handled by systemd (see the hostapd override
# above). Both scripts remain installed and safe to run by hand. See
# docs/OPERATIONAL-DECISIONS.md for the full rationale before re-adding
# either cron entry.
(crontab -l; echo "@daily sleep 10; reboot > /dev/null 2>&1") | awk '!x[$0]++' | crontab -

# Disable Services
echo "[+] Disabling unnecessary services..."
systemctl disable bluetooth.service 2>/dev/null || true
systemctl stop wpa_supplicant.service 2>/dev/null || true
systemctl disable wpa_supplicant.service 2>/dev/null || true
systemctl mask wpa_supplicant.service 2>/dev/null || true

echo "========================================"
echo "   Installation Complete!"
echo "   Please reboot your system: sudo reboot"
echo ""
echo "   The admin/status page at http://10.0.0.1/admin/ is LOCKED OUT"
echo "   by default (no credential was set). Run this to enable it:"
echo "       sudo /usr/local/bin/setup_admin_password.sh"
echo "========================================"