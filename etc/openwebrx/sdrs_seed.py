# PirateBox: one-time OpenWebRX+ SDR/profile seed file.
#
# This is a "classic" config_webrx.py-format file (the format OpenWebRX+
# itself still documents and supports migrating from - see that file's
# own DEPRECATION notice: "the new configuration storage is not intended
# to be edited manually" past the initial migration). It exists purely
# so tools/install_openwebrx.sh can produce a working, reproducible,
# non-interactive baseline via the project's own documented
# `openwebrx config migrate` command, rather than hand-writing the
# internal JSON store OpenWebRX+ explicitly warns against editing by
# hand. After migration, ongoing changes belong in OpenWebRX+'s own
# /settings web UI, not this file - it is not re-read after the first
# migration.
#
# Deliberately minimal, matching the "establish a clean basic receiver
# first" instruction: one device (the confirmed RTL2832U+R820T dongle,
# docs/RADIO-SDR-ARCHITECTURE-DESIGN.md section 3a/3b), two profiles,
# both plain analog demodulation (NFM/WFM) - no digital-voice decoders,
# no APRS, no ADS-B, nothing from OpenWebRX+'s own "Recommends:" pile.
#
# Gain: 8.7 dB, not "auto" - the RTL-SDR/librtlsdr characterization
# round (docs/RADIO-SDR-ARCHITECTURE-DESIGN.md section 3b.3) found
# automatic gain badly overloaded the ADC with the attached MLA-50+
# active loop antenna (51.7% of samples clipped at the rails at FM
# broadcast); manual 8.70 dB eliminated it completely (0% clipped).
# This is a receiver-chain/antenna-gain finding, not a defect - see
# that section before changing this value back to "auto".
#
# Sample rate: 2.048 Msps, the more conservative of the two rates
# validated stable in raw-capture testing (section 3b.4) - OpenWebRX+
# adds real DSP/FFT/waterfall/web-serving load on top of raw capture,
# which raw rtl_sdr testing never exercised, so starting at the lower
# validated rate (not the higher 3.2 Msps one) is the deliberately
# conservative choice per instruction. Increase only with fresh
# measurements to justify it.
#
# No receiver_gps is set: this project does not publish the operator's
# precise physical location to visitors or the wider internet, matching
# its existing no-PII-exposure posture elsewhere (e.g. visitor MAC
# addresses are never persisted - docs/DEVICE-MEMORY-DESIGN.md).

version = 7

receiver_name = "PirateBox Radio"
receiver_location = "PirateBox"
receiver_admin = "admin@piratebox.local"
receiver_gps = {"lat": 0, "lon": 0}
photo_title = ""
photo_desc = ""

max_clients = 2

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
                "name": "FM Broadcast",
                "center_freq": 98000000,
                "samp_rate": 2048000,
                "start_freq": 100100000,
                "start_mod": "wfm",
            },
        },
    },
}
