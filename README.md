# PirateBox - Offline File Share

This project transforms a Raspberry Pi (or similar Debian-based system) into an offline, anonymous file-sharing network. Users connect to the "PirateBox" Wi-Fi hotspot and are automatically redirected to a browser-based interface for uploading and downloading files.

Inspired by the discontinued [PirateBox](https://en.wikipedia.org/wiki/PirateBox) project, this lightweight implementation uses Nginx, PHP, dnsmasq, and hostapd without requiring a database. It functions as a "captive portal" similar to public Wi-Fi login pages found in hotels or libraries, but instead of requesting credentials, it immediately serves the file-sharing page.

This configuration has been tested on a Raspberry Pi Zero 2 W running Raspberry Pi OS Lite (Trixie).

<div dir="auto">
<a target="_blank" rel="noopener noreferrer" href="https://github.com/teklynk/piratebox/blob/main/pizero_piratebox.jpg?raw=true"><img src="https://github.com/teklynk/piratebox/raw/main/pizero_piratebox.jpg?raw=true" style="max-width: 100%;"></a>
<br>
<a target="_blank" rel="noopener noreferrer" href="https://github.com/teklynk/piratebox/blob/main/Screenshot%20from%202026-01-11%2001-00-39.png?raw=true"><img src="https://github.com/teklynk/piratebox/blob/main/Screenshot%20from%202026-01-11%2001-00-39.png?raw=true" style="max-width: 100%;"></a>
<br>
<a target="_blank" rel="noopener noreferrer" href="https://github.com/teklynk/piratebox/blob/main/Screenshot%20from%202026-01-1 01-02-06.png?raw=true"><img src="https://github.com/teklynk/piratebox/blob/main/Screenshot%20from%202026-01-11%2001-02-06.png?raw=true" style="max-width: 100%;"></a>
<br>
<a target="_blank" rel="noopener noreferrer" href="https://github.com/teklynk/piratebox/blob/main/Screenshot%20from%202026-01-11%2001-03-28.png?raw=true"><img src="https://github.com/teklynk/piratebox/blob/main/Screenshot%20from%202026-01-11%2001-03-28.png?raw=true" style="max-width: 100%;"></a>
</div>

## WiFi QR Code
**SSID: PirateBox**

!['PirateBox WiFi QR Code'](https://github.com/teklynk/piratebox/blob/main/PirateBox-wifi-qrcode.png?raw=true)

The device itself also serves this same Wi-Fi QR code, plus a second one
for the direct URL, on its own Help page (`http://10.0.0.1/help.php`) -
generated locally at install time, no external QR service involved. See
[docs/OPERATIONAL-DECISIONS.md](docs/OPERATIONAL-DECISIONS.md) (Phase 5).

## Features
- **Offline Network**: Creates its own Wi-Fi hotspot (SSID: PirateBox).
- **Captive Portal**: DNS redirection resolves all requests to the local server.
- **File Sharing**: Simple web interface to upload and download files, with sortable listing and human-readable sizes.
- **Messages (Guestbook)**: Leave a message that stays for later visitors to read.
- **Live Chat**: Have a conversation with others connected to the PirateBox.
- **Help page**: `help.php` - connect instructions (including a note for Android/Samsung devices that show "Internet may not be available"), platform guidance, and a short About section. Linked from every page's navigation.
- **Admin/status page**: see "Admin/Status Page" below.
- **Offline Utility Library** (`/utility/`, in progress): a growing offline reference/utility section - radio reference, emergency/outage reference, first aid, maps &amp; local info, a document library, and cross-section search - all working without any Internet access, same as the rest of the site. Linked from the main navigation. Radio, Emergency, First Aid, Maps, and Local Information are built out (Stages 2-6); Library/Search remain placeholders. See docs/OPERATIONAL-DECISIONS.md for the staged plan and progress.
  - **Radio Reference** (`/utility/radio/`): a fast, searchable, offline lookup for a wideband receiver - amateur bands, NOAA Weather Radio, AM/FM/shortwave broadcast, CB/FRS/GMRS/MURS, Marine VHF, Airband, Railroad, a modulation-type glossary, and practical guides (propagation, antennas, receiver tips). Data-driven from JSON files under `data/utility/radio/`, each record carrying a source, retrieval date, and confidence rating. Clearly distinguishes receive from transmit/license information throughout.
  - **Emergency / Outage Reference** (`/utility/emergency/`): calm, skimmable, searchable guidance for power outages, severe weather, water/food/sanitation, and planning/communication - sourced from Ready.gov/FEMA, CDC, NOAA/NWS, and NFPA. Data-driven from `data/utility/emergency/`, same provenance/confidence model as Radio.
  - **First Aid Reference** (`/utility/firstaid/`): conservative, overview-level first-aid guidance sourced from the American Red Cross and CDC - not a substitute for training or professional care, clearly stated on the page. Data-driven from `data/utility/firstaid/`.
  - **Maps &amp; Location Reference** (`/utility/maps/`): coordinate/GPS/navigation basics (USGS/NOAA-sourced) plus an empty, ready-to-use map catalog framework - add a real map by dropping a file in `public/utility/maps/files/` and one entry in `data/utility/maps/catalog.json`, no PHP editing needed. No map data ships by default.
  - **Local Information** (`/utility/local/`): one editable reference sheet (`data/utility/local/info.json`) for this PirateBox's current location - emergency management contact, NWS office, hospitals, shelters, emergency numbers, amateur repeaters, and other local resources. Ships nearly empty by design (only universal 911/Poison Control numbers pre-filled) - edit that one file when the box moves, no code changes needed.
- **Emergency Mode** (software foundation only - no physical switch yet): the site can present itself two ways from the same underlying content - normal PirateBox operation, or an emergency/utility-first landing page for outage/disaster deployment. Selected today via `set_piratebox_mode.sh` (a manual stand-in for the not-yet-installed physical toggle switch); always falls back safely to Normal if its state can't be read. See docs/OPERATIONAL-DECISIONS.md for the design and what's still deferred (GPIO, SSID switching, OLED status display).
- **Auto-Cleanup**: Script included to purge uploads and messages (optional via scheduled cron job - off by default, see "Maintenance" below).
- **Fully offline-rendered**: no CDNs, no Google Fonts, no external JS/CSS/images/APIs anywhere in the app - everything required to render and use every page ships with the device. See docs/OPERATIONAL-DECISIONS.md for the Phase 5 audit.

## Prerequisites
- Raspberry Pi with Wi-Fi capability.
- OS: Raspbian / Debian.
- Root/Sudo access.

## Installation

### 1. Install Dependencies
**Tip:** On the Raspberry Pi Zero 2 W, I used a usb hub that also has ethernet. This allowed me to SSH into the Pi while configuring hostapd.
- Run: `sudo raspi-config` and set all of the localization settings, WIFI region, TimeZone, Keyboard layout, set hostname and enabled SSH.

**Note:** The time server is not set by default. This can break `apt update` and produce errors on screen. The issue is that the date/time of the repos do not match the date/time of the Raspberry Pi. They are out of sync. These steps should sync your date/time and you can then run apt update. Ignore all online suggestions about downloading certs. It's just a time sync issue. 

```bash
sudo nano /etc/systemd/timesyncd.conf
```

Set the NTP server:
`NTP=time.cloudflare.com`

```bash
sudo systemctl restart systemd-timesyncd
```

```bash
timedatectl
```

Update your system and install the required packages:
```bash
sudo apt update
```
```bash
sudo apt install -y hostapd dnsmasq dhcpcd5 nginx php-fpm git
```

**A note on `rpi-update`:** on a Pi Zero 2 W running an older OS image, running `sudo rpi-update` to get the latest firmware/kernel fixed real iOS-disconnect/kernel-crash issues for the original author. `installer_pi_zero_trixie.sh` deliberately does **not** run it by default on Trixie - see [docs/OPERATIONAL-DECISIONS.md](docs/OPERATIONAL-DECISIONS.md) before reintroducing it. If you hit Wi-Fi stability issues, check `dmesg`/`journalctl -k` for `hwmon` undervoltage warnings first.

### 2. Network Configuration

#### Static IP (dhcpcd)
Edit `/etc/dhcpcd.conf` to set a static IP for the wireless interface:
```bash
interface wlan0
static ip_address=10.0.0.1/24
nohook wpa_supplicant
```
Enable and restart the service:
```bash
sudo systemctl enable dhcpcd
sudo systemctl restart dhcpcd
```

#### Access Point (hostapd)
Create `/etc/hostapd/hostapd.conf`:
```ini
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
```
Edit: `/etc/default/hostapd`
Point the daemon to this config in `/etc/default/hostapd`:
```bash
DAEMON_CONF="/etc/hostapd/hostapd.conf"
DAEMON_OPTS=""
```
Unmask and start hostapd:
```bash
sudo systemctl unmask hostapd
sudo systemctl enable hostapd
sudo systemctl start hostapd
```

Install the systemd override that unblocks Wi-Fi via `rfkill` before start
and enables automatic recovery on any exit (see
[docs/OPERATIONAL-DECISIONS.md](docs/OPERATIONAL-DECISIONS.md)):
```bash
sudo mkdir -p /etc/systemd/system/hostapd.service.d
sudo cp etc/systemd/system/hostapd.service.d/override.conf /etc/systemd/system/hostapd.service.d/override.conf
sudo systemctl daemon-reload
```

#### DNS & DHCP (dnsmasq)
Configure `/etc/dnsmasq.conf` to handle IP leasing, redirect all DNS queries to the PirateBox, and advertise the RFC 8910 Captive Portal API URL via DHCP option 114:
```ini
interface=wlan0
dhcp-range=10.0.0.10,10.0.0.250,12h
address=/#/10.0.0.1
dhcp-option=114,"http://10.0.0.1/.well-known/captive-portal"
```
Restart dnsmasq:
```bash
sudo systemctl restart dnsmasq
```

### 3. Web Server Configuration

#### Nginx
The default Nginx site configuration handles captive portal detection/redirection and large file uploads. See [Captive Portal Detection](#captive-portal-detection) below for how each platform is handled.

Copy the provided configuration from `etc/nginx/sites-available/default` to `/etc/nginx/sites-available/default`.

**Note:** The setting `client_max_body_size 150M;` is included in this site configuration. You do not need to add it to `/etc/nginx/nginx.conf` globally unless you prefer a global setting.

#### PHP-FPM
Edit `/etc/php/8.4/fpm/php.ini` to secure the installation and allow larger uploads:
```ini
disable_functions = exec,passthru,shell_exec,system,proc_open,popen,curl_exec,curl_multi_exec,parse_ini_file,show_source
upload_max_filesize = 120M
post_max_size = 130M
max_execution_time = 300
display_errors = Off
log_errors = On
```

**Note:** You may also need to set these values in the pool config (`/etc/php/8.4/fpm/pool.d/www.conf`) if `php.ini` changes don't take effect:
```ini
php_value[upload_max_filesize] = 120M
php_value[post_max_size] = 130M
```

### 4. Application Deployment
Copy the source files (`index.php`, `upload.php`, `styles.css`, images) to `/var/www/html/`.

Create the uploads directory and set permissions:
```bash
sudo mkdir -p /var/www/html/public/uploads
sudo mkdir -p /var/www/html/data
sudo chown -R www-data:www-data /var/www/html
sudo chmod 0755 /var/www/html/public/uploads
sudo chmod 0755 /var/www/html/data
```

### 5. Maintenance (manual purge - not scheduled by default)

**Default policy: automatic deletion of user content is OFF.** Uploads, chat
history, and guestbook messages persist indefinitely by default - this
installer does not add a cron job to delete them. See
[docs/OPERATIONAL-DECISIONS.md](docs/OPERATIONAL-DECISIONS.md) for the
reasoning.

A script `purge_uploads.sh` is installed to `/usr/local/bin/purge_uploads.sh`
as a **manual** utility if you ever want to wipe everything (all uploads +
all chat/guestbook history) yourself:
```bash
sudo /usr/local/bin/purge_uploads.sh
```
This is immediate and irreversible - there is no undo. If you want it
scheduled on your own install, you can add it back with `sudo crontab -e`:
```bash
0 0 * * * /usr/local/bin/purge_uploads.sh > /var/log/purge_uploads.log 2>&1
```

**Storage-exhaustion guard:** uploads are also protected from filling the
disk completely - `var/www/html/includes/config.php` defines a minimum
free-space reserve (1 GiB by default) that an upload may never cross;
uploads that would violate it are rejected with a clear message and never
written to disk. No existing files are ever deleted to make room. The main
page also shows current free space, with a warning once it's within 2x
that reserve.

**Narrower maintenance actions are also available from the admin page**
(see below) for clearing just chat, just the guestbook, or just uploads,
each independently and each behind a confirmation checkbox -
`purge_uploads.sh` remains available for the original "wipe everything at
once" behavior.

### 6. Admin/Status Page (Phase 4)

A lightweight, local-only admin page at `http://10.0.0.1/admin/` shows
storage/RAM/CPU/uptime, Wi-Fi client count, per-service health (hostapd/
dnsmasq/nginx/PHP-FPM), and power/undervoltage status, plus three narrow
maintenance actions (clear chat, clear guestbook, purge uploads - each
independent, each requiring an explicit confirmation checkbox).

**It is locked out by default** - the installer creates an *empty*
password file for it, so nobody (including you) can log in until you set
a password:
```bash
sudo /usr/local/bin/setup_admin_password.sh
```
This prompts for a username/password, hashes it, and writes
`/etc/nginx/.piratebox_admin_htpasswd` (mode 0640, root:www-data - never
committed to git, never has a default value). Re-run it any time to
change the password. The admin page itself is protected by nginx HTTP
Basic Auth on the `/admin/` path only - the rest of the site stays
account-free, matching PirateBox's normal design.

There is no reboot or service-restart button - see "Known Issues and
troubleshooting" below for the SSH commands. See
[docs/OPERATIONAL-DECISIONS.md](docs/OPERATIONAL-DECISIONS.md) for the
full design rationale and security boundaries.

### Disable Unnecessary Services

```bash
sudo systemctl disable bluetooth.service
sudo systemctl stop wpa_supplicant.service
sudo systemctl disable wpa_supplicant.service
sudo systemctl mask wpa_supplicant.service
```

You may also want to disable SSH. This will however mean that you will no longer be able to SSH into the device. 

```bash
sudo systemctl disable --now ssh
sudo systemctl mask ssh
sudo systemctl status ssh
```

### Captive Portal Detection

PirateBox is intentionally offline - it never has real Internet access, and
this project does not intercept or MITM HTTPS/TLS in any way (HTTPS sites
simply fail while connected, which is expected). Getting a client's OS to
recognize the network as a captive portal and present the PirateBox page
therefore relies entirely on plain-HTTP detection mechanisms:

- **Legacy HTTP-probe redirects** (nginx, all platforms): dnsmasq's
  wildcard DNS (`address=/#/10.0.0.1`) sends every hostname a client's OS
  probes - `connectivitycheck.gstatic.com`, `captive.apple.com`,
  `msftconnecttest.com`, etc. - to 10.0.0.1. nginx matches the well-known
  probe paths (`/generate_204`, `/gen_204`, `/hotspot-detect.html`,
  `/library/test/success.html`, `/success.html`, `/connecttest.txt`,
  `/ncsi.txt`) and 302-redirects them to `http://10.0.0.1/`, which the
  OS's captive-portal browser then loads. This is what Firefox/Linux,
  Windows NCSI, and Apple devices rely on.
- **RFC 8910/8908 Captive Portal API** (dnsmasq DHCP option 114 + nginx
  `/.well-known/captive-portal`): Android 11+ (confirmed on a Samsung
  device running Android 16) requests DHCP option 114 directly as part of
  its normal DHCP handshake and uses it as a first-class captive-portal
  signal, bypassing the DNS-hijack heuristic entirely. The endpoint always
  returns `{"captive":true,"user-portal-url":"http://10.0.0.1/"}` - see
  `docs/OPERATIONAL-DECISIONS.md` for why this was needed and how it was
  confirmed working.

Both mechanisms are active at once and don't conflict; a client that
doesn't support Capport simply falls back to the legacy probes.

### Known Issues and troubleshooting

hostapd is configured (via `etc/systemd/system/hostapd.service.d/override.conf`)
to unblock Wi-Fi with `rfkill` before starting, and to restart automatically
on any exit (`Restart=always`), not just on-failure - this recovers hostapd
even from the case where a wlan0 carrier hiccup makes it exit cleanly. A
`restart_hostapd.sh` script remains at `/usr/local/bin/restart_hostapd.sh`
for manual use (e.g. after hand-editing `hostapd.conf`), but is **not**
scheduled by cron - an unconditional hourly restart was found to disconnect
every connected client once an hour for no diagnosed benefit. See
[docs/OPERATIONAL-DECISIONS.md](docs/OPERATIONAL-DECISIONS.md) for the full
history, including live crash-test results.

If you're seeing genuine Wi-Fi instability (not just the old hourly cron),
check `dmesg` / `journalctl -k` for `hwmon: Undervoltage detected!` first -
that's a power supply/cable problem, not a software one, and is a more
likely cause on a Pi 3B+ than anything `rpi-update` would fix. (The admin
page also surfaces this - see `vcgencmd get_throttled` under Power below.)

**Service restarts / reboot (SSH only - Phase 4 deliberately does not
expose these as web buttons; see docs/OPERATIONAL-DECISIONS.md):**
```bash
sudo systemctl restart nginx
sudo systemctl restart php8.4-fpm
sudo systemctl restart dnsmasq
sudo /usr/local/bin/restart_hostapd.sh   # or: sudo systemctl restart hostapd
sudo reboot
```