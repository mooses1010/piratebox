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

// Bounds how large a single incoming line may grow before it is
// discarded - protects a memory-constrained MCU from an unbounded
// buffer if the host (or a noisy/disconnected line) never sends '\n'.
// Generously larger than any command this protocol defines today.
#define PIRATEBOX_MAX_LINE_LEN 512

// StaticJsonDocument sizing: generous but bounded headroom for the
// richest message this firmware builds (currently "hello", with its
// caps array) plus safety margin for future fields - see
// docs/ESP32-SUPERVISOR-DESIGN.md for the sizing rationale if this
// ever needs to grow.
#define PIRATEBOX_JSON_DOC_SIZE 768

// --- Outgoing message builders ------------------------------------
// Each returns the JSON line WITHOUT a trailing newline - callers
// (main.cpp) append '\n' when writing to Serial, keeping the framing
// decision in exactly one place.

// `bh1750Available` reflects whether THIS BOOT's init probe found a
// real sensor responding - see bh1750.cpp's header for why this can
// legitimately be false (not yet physically wired) and why that's
// correct, not a fault.
String pb_build_hello(const String &mac, const String &resetReason, unsigned long uptimeMs, bool bh1750Available);
String pb_build_heartbeat(unsigned long seq, unsigned long uptimeMs);
String pb_build_sensors(unsigned long seq, float internalTempC, bool tempOk,
                         bool bh1750Available, float bh1750Lux, bool bh1750Ok);
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
