// PirateBox Pi<->ESP32 supervisor protocol - shared constants and
// message builders. See docs/ESP32-SUPERVISOR-DESIGN.md ("Protocol")
// for the full wire-format spec; this header is the firmware's own
// implementation of that spec, kept deliberately close to the doc's
// wording so the two never drift apart silently.
//
// WIRE FORMAT: newline-delimited JSON (NDJSON), one object per line,
// UTF-8, terminated by a single '\n'. Chosen over a binary framing
// specifically so the link stays inspectable with nothing more than a
// terminal - `screen /dev/ttyACM0 115200` (or any serial monitor)
// shows readable text, and a malformed line can never desync framing
// for more than one line (the next '\n' always resynchronizes both
// sides - see PirateBoxLineReader below).
//
// EVERY message, both directions, carries:
//   "v" (int)    - protocol version. PIRATEBOX_PROTOCOL_VERSION today.
//   "t" (string) - message type.
// A receiver on either side that sees an unrecognized "t" must reply
// (if it's the ESP32) with an "err" message and otherwise continue
// running completely normally - never resets, never stops, never
// treats an unrecognized-but-well-formed message as fatal. This is
// the extensibility contract: a newer Pi talking to older firmware
// (or vice versa) degrades gracefully instead of breaking.
#pragma once

#include <Arduino.h>
#include <ArduinoJson.h>
#include "ds18b20.h"  // for the Ds18b20Probe type used in pb_build_sensors()

#ifndef PIRATEBOX_FW_VERSION
#define PIRATEBOX_FW_VERSION "0.0.0-dev"
#endif
#ifndef PIRATEBOX_PROTOCOL_VERSION
#define PIRATEBOX_PROTOCOL_VERSION 1
#endif

// Board identity string - deliberately a plain constant, not read from
// any efuse/flash field, since the commissioning round already proved
// this exact unit's identity out-of-band (docs/OPERATIONAL-DECISIONS.md,
// 2026-09-07: ESP32-S3 QFN56 rev v0.2, 16MB GigaDevice flash, 8MB
// embedded PSRAM). A future maintainer building for different hardware
// changes this one string.
#define PIRATEBOX_BOARD_ID "esp32s3-n16r8"

// Capability identifiers this firmware can ever report. A capability
// only appears in a live "hello" message's "caps" array if the
// corresponding sensor actually initialized successfully at boot -
// see sensors.cpp. Pi-side software must treat any capability id it
// doesn't recognize as an opaque, ignorable string (forward
// compatibility for future sensors added here without a Pi-side
// update being required first).
#define CAP_TEMP_INTERNAL "temp_internal"
#define CAP_BH1750 "bh1750"
// DS18B20 is deliberately NOT reported as "detected only once a real
// device answers" the way temp_internal/bh1750 are - it is a genuinely
// multi-instance bus, so "0 probes currently found" is itself a valid,
// meaningful state (not the same as "this firmware build doesn't
// support DS18B20 at all"). This capability appears once the bus has
// ever found at least one probe (see pb_ds18b20_ever_found_a_probe())
// - per-probe identity/count/health always lives in the "sensors"
// message's "ds18b20" block instead, which can legitimately be
// "0 probes" without the capability itself being absent. See
// docs/ESP32-SUPERVISOR-DESIGN.md for the full reasoning.
#define CAP_DS18B20 "ds18b20"

// Bounds how large a single incoming line may grow before it is
// discarded - protects a memory-constrained MCU from an unbounded
// buffer if the host (or a noisy/disconnected line) never sends '\n'.
// Generously larger than any command this protocol defines today.
#define PIRATEBOX_MAX_LINE_LEN 512

// StaticJsonDocument sizing: generous but bounded headroom for the
// richest message this firmware builds. As of the DS18B20 phase
// (2026-09-07) that's "sensors" with up to DS18B20_MAX_PROBES (8)
// probe entries plus temp_internal/bh1750 - roughly 60 bytes/probe of
// JSON (ROM hex key + ok/value/unit) comfortably fits with headroom to
// spare. See docs/ESP32-SUPERVISOR-DESIGN.md for the sizing rationale
// if this ever needs to grow further.
#define PIRATEBOX_JSON_DOC_SIZE 1536

// --- Outgoing message builders ------------------------------------
// Each returns the JSON line WITHOUT a trailing newline - callers
// (main.cpp) append '\n' when writing to Serial, keeping the framing
// decision in exactly one place.

// `bh1750Available` reflects whether THIS BOOT's init probe found a
// real sensor responding - see bh1750.cpp's header for why this can
// legitimately be false (not yet physically wired) and why that's
// correct, not a fault. `ds18b20EverFound` uses the different,
// latching rule described at CAP_DS18B20 above.
String pb_build_hello(const String &mac, const String &resetReason, unsigned long uptimeMs,
                       bool bh1750Available, bool ds18b20EverFound);
String pb_build_heartbeat(unsigned long seq, unsigned long uptimeMs);
String pb_build_sensors(unsigned long seq, float internalTempC, bool tempOk,
                         bool bh1750Available, float bh1750Lux, bool bh1750Ok,
                         bool ds18b20EverFound, bool ds18b20BusOk,
                         int ds18b20ProbeCount, const Ds18b20Probe *ds18b20Probes);
String pb_build_pong(const String &nonce);
String pb_build_err(const String &reason);

// --- Incoming command handling -------------------------------------
// The only commands this firmware understands from the Pi. Deliberately
// NOT a generic command/eval interface - see docs/ESP32-SUPERVISOR-
// DESIGN.md ("Deliberately not a remote shell") for why that boundary
// is intentional, not an oversight.
enum class PbCommand {
    Unknown,
    Ping,
    GetInfo,
};

struct PbParsedCommand {
    PbCommand type = PbCommand::Unknown;
    String nonce;      // only meaningful for Ping
    bool parseError = false;   // true if the line was not valid JSON at all
};

// Parses one already-newline-stripped line. Never throws (ArduinoJson
// reports errors via its return code, not exceptions - this firmware
// is built without C++ exceptions per the Arduino-ESP32 default).
PbParsedCommand pb_parse_command(const String &line);
