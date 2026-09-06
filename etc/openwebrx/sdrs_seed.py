# PirateBox: OpenWebRX+ SDR/profile/general-settings seed file.
#
# This is a "classic" config_webrx.py-format file. tools/install_openwebrx.sh
# copies it to /etc/openwebrx/config_webrx.py, which OpenWebRX+ actually
# reads directly (via owrx/config/classic.py's ClassicConfig, which
# executes the file fresh on every service start - confirmed live,
# 2026-09-05: this exact Pi's /var/lib/openwebrx/settings.json, the
# higher-priority "dynamic" layer that OpenWebRX+'s own /settings web UI
# writes to, does not exist at all, meaning nothing is masking this
# classic file - it is the actual live source of truth for every
# setting below, not a one-time seed that stops mattering after a
# "config migrate" run. (OpenWebRX+'s own documentation still says the
# dynamic JSON store "is not intended to be edited manually" once an
# admin starts using /settings - if that ever happens on this Pi, the
# dynamic layer's own keys will start taking priority over this file's
# matching keys, and this comment's "actual live source of truth" claim
# will need revisiting for whichever keys the admin has touched.)
# Consequence for maintenance: updating a value in this file and
# re-copying it to /etc/openwebrx/config_webrx.py (then restarting the
# service) is a valid, safe way to change live configuration for as
# long as no admin account/settings-UI edits exist yet on this install -
# see tools/install_openwebrx.sh's separate "apply config update"
# guidance for exactly this.
#
# Deliberately minimal, matching the "establish a clean basic receiver
# first" instruction: one device (the confirmed RTL2832U+R820T dongle,
# docs/RADIO-SDR-ARCHITECTURE-DESIGN.md section 3a/3b), three profiles,
# all plain analog demodulation (NFM/WFM) - no digital-voice decoders,
# no APRS, no ADS-B, nothing from OpenWebRX+'s own "Recommends:" pile.
#
# Gain: 8.7 dB, not "auto" - the RTL-SDR/librtlsdr characterization
# round (docs/RADIO-SDR-ARCHITECTURE-DESIGN.md section 3b.3) found
# automatic gain badly overloaded the ADC with the attached MLA-50+
# active loop antenna (51.7% of samples clipped at the rails at FM
# broadcast); manual 8.70 dB eliminated it completely (0% clipped).
# This is a receiver-chain/antenna-gain finding, not a defect - see
# that section before changing this value back to "auto". Applies
# per-device, so all three profiles below share it.
#
# Sample rate: 2.048 Msps for every profile, the more conservative of
# the two rates validated stable in raw-capture testing (section
# 3b.4) - OpenWebRX+ adds real DSP/FFT/waterfall/web-serving load on
# top of raw capture, which raw rtl_sdr testing never exercised, so
# starting at the lower validated rate (not the higher 3.2 Msps one)
# is the deliberately conservative choice per instruction. Increase
# only with fresh measurements to justify it.
#
# allow_center_freq_changes: True - without this (OpenWebRX+'s own
# default is False), a connected client can only tune within whichever
# profile's own fixed ~2.048 MHz window is currently selected, with no
# way to move the window itself - confirmed live by a human browser
# test (2026-09-05): NOAA Weather Radio only showed ~161.5-163.5 MHz,
# FM Broadcast only ~97-99 MHz, with no way to reach any other part of
# the RTL2832U+R820T's actual tunable range. Enabling this lets any
# connected client (no admin login required - this is a general,
# visitor-facing setting, not gated behind OpenWebRX+'s own /settings
# admin auth) drag/retune the center frequency freely within whatever
# the R820T tuner itself will actually lock onto. Each profile/session
# still only ever shows ONE ~2.048 MHz-wide slice of spectrum centered
# on the current tuned frequency at a time, not the whole RF spectrum
# simultaneously - retuning moves that slice, it doesn't widen it.
#
# magic_key = "" (2026-09-05, second human browser test round): without
# this, allow_center_freq_changes above is NOT actually sufficient for a
# no-login visitor to retune - confirmed the hard way. OpenWebRX+'s own
# connection.py gates the "setfrequency" message on
# "magic == '' or key == magic" where magic = the configured magic_key,
# UNCONDITIONALLY (unlike profile selection, which only checks this when
# a profile is explicitly marked key_locked). OpenWebRX+'s own default
# (owrx/config/defaults.py) is magic_key="memagic", NOT an empty string -
# this seed file never set it, so every setfrequency request sent by
# var/www/html/public/utility/radio/live.php (which never included any
# "key" param, matching this project's own "no visitor secret" goal) was
# being silently dropped server-side: no exception, no error message, no
# config push - the shared receiver's center_freq simply never changed.
# Confirmed empirically (not just by reading source): the exact same
# setfrequency call that silently no-opped without a key produced an
# instant, correct config push (and a genuinely retuned, streaming
# receiver, re-verified across 27.185/100.1/162.475 MHz) the moment
# "key": "memagic" was added to it. Setting magic_key to an empty string
# here removes this gate entirely, matching allow_center_freq_changes'
# own intent (no admin login, no shared secret, for ordinary visitor
# retuning) - once applied, live.php needs no key at all, and neither
# would any future retune control OpenWebRX+'s own frontend might add.
# IMPORTANT CORRECTION to this document's own history: the "confirmed"
# multi-band retuning claim in docs/RADIO-SDR-ARCHITECTURE-DESIGN.md
# section 13.6 was itself a false positive caused by this exact bug -
# every setfrequency call in that test also omitted the key, so the
# receiver never actually left its starting frequency; the frame-count
# differences reported there reflect normal variation at one unchanging
# frequency, not genuine reception at three different bands. Section
# 13.8 documents the corrected re-verification.
#
# No receiver_gps is set: this project does not publish the operator's
# precise physical location to visitors or the wider internet, matching
# its existing no-PII-exposure posture elsewhere (e.g. visitor MAC
# addresses are never persisted - docs/DEVICE-MEMORY-DESIGN.md).

version = 8

receiver_name = "PirateBox Radio"
receiver_location = "PirateBox"
receiver_admin = "admin@piratebox.local"
receiver_gps = {"lat": 0, "lon": 0}
photo_title = ""
photo_desc = ""

# 4, not the previous 2 (2026-09-05): live.php's control-socket design
# needs two concurrent connections by itself (the embedded iframe's own
# session plus its own short-lived control socket) - a max_clients of 2
# left no headroom at all for a second visitor, or even a single
# visitor's browser holding a brief extra connection during a page
# reload. Kept modest, not unlimited - this Pi's own measured DSP/CPU
# load (docs/RADIO-SDR-ARCHITECTURE-DESIGN.md section 13.5) was for a
# single real demodulating client; this project has not measured cost
# under several concurrent ones.
max_clients = 4
allow_center_freq_changes = True
magic_key = ""

sdrs = {
    "rtlsdr": {
        "name": "RTL-SDR (RTL2832U + R820T)",
        "type": "rtl_sdr",
        "ppm": 0,
        "rf_gain": "8.7",
        "profiles": {
            "noaa-weather": {
                "name": "NOAA Weather Radio",
                "center_freq": 162475000,
                "samp_rate": 2048000,
                "start_freq": 162400000,
                "start_mod": "nfm",
            },
            "fm-broadcast": {
                # 2026-09-05, first live install: center_freq 98000000 with
                # start_freq 100100000 logged "start_freq for profile
                # 'fm-broadcast' is out of range" at startup - 100.1MHz sits
                # 2.1MHz from a 98MHz center, outside the ~1.024MHz half-
                # width a 2.048 Msps profile actually covers. Fixed by
                # centering on the same 100.1MHz already validated as a
                # real, working receive frequency in the RTL-SDR
                # characterization round (docs/RADIO-SDR-ARCHITECTURE-
                # DESIGN.md section 3b.3) rather than picking an arbitrary
                # new center - both fields now agree.
                "name": "FM Broadcast",
                "center_freq": 100100000,
                "samp_rate": 2048000,
                "start_freq": 100100000,
                "start_mod": "wfm",
            },
            "general-sdr": {
                # 2026-09-05: added per explicit operator request after the
                # human browser test confirmed real reception, but found
                # NOAA/FM's fixed ~2 MHz windows too restrictive. This
                # profile's own starting point is the same validated
                # 100.1 MHz FM signal (a known-good, already-confirmed-
                # audible starting point rather than an untested
                # frequency) - with allow_center_freq_changes (above)
                # enabled, a visitor can retune anywhere from here.
                #
                # No hard min/max tuning limit is enforced by OpenWebRX+
                # itself for a plain rtl_sdr connector device (confirmed
                # by reading the actual installed owrx/source/rtl_sdr.py -
                # it declares a valid *sample rate* range, 250 kHz-3.2
                # Msps, matching librtlsdr's own real limits, but no
                # frequency-range field at all) - a client can request
                # any numeric center frequency, forwarded directly to
                # rtl_connector/the R820T tuner. Real-world usable range
                # is therefore set by the tuner's own actual PLL lock
                # range, not by OpenWebRX+ or this config: roughly
                # 24 MHz-1766 MHz for the R820T/R820T2 family (community-
                # documented, not re-measured across that whole span in
                # this project's own testing - this unit has been
                # directly confirmed working at 27.185 MHz, 100.1 MHz,
                # and 162.475 MHz specifically, per docs/RADIO-SDR-
                # ARCHITECTURE-DESIGN.md sections 3b.3 and 13.5). Tuning
                # outside that range will not damage anything - the
                # tuner simply fails to produce a usable signal - but it
                # is not a supported/verified part of this unit's range.
                "name": "General SDR (Wide Tuning)",
                "center_freq": 100100000,
                "samp_rate": 2048000,
                "start_freq": 100100000,
                "start_mod": "wfm",
            },
        },
    },
}
