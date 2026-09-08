#include "protocol.h"

String pb_build_hello(const String &mac, const String &resetReason, unsigned long uptimeMs,
                       bool bh1750Available, bool ds18b20EverFound) {
    StaticJsonDocument<PIRATEBOX_JSON_DOC_SIZE> doc;
    doc["v"] = PIRATEBOX_PROTOCOL_VERSION;
    doc["t"] = "hello";
    doc["fw"] = PIRATEBOX_FW_VERSION;
    doc["board"] = PIRATEBOX_BOARD_ID;
    doc["mac"] = mac;
    doc["reset_reason"] = resetReason;
    doc["uptime_ms"] = uptimeMs;
    JsonArray caps = doc.createNestedArray("caps");
    // Only capabilities actually confirmed at boot belong here - see
    // sensors.cpp/bh1750.cpp's own init functions. temp_internal is
    // every ESP32-S3's own on-die sensor (no wiring required), so it's
    // always listed. bh1750 is listed only if THIS boot's real I2C
    // probe found a sensor actually responding - see bh1750.cpp's
    // header for why "not listed" is the correct, expected state until
    // the operator physically wires one.
    caps.add(CAP_TEMP_INTERNAL);
    if (bh1750Available) {
        caps.add(CAP_BH1750);
    }
    // ds18b20 uses the different, latching "ever found" rule - see
    // CAP_DS18B20's own comment in protocol.h.
    if (ds18b20EverFound) {
        caps.add(CAP_DS18B20);
    }

    String out;
    serializeJson(doc, out);
    return out;
}

String pb_build_heartbeat(unsigned long seq, unsigned long uptimeMs) {
    StaticJsonDocument<192> doc;
    doc["v"] = PIRATEBOX_PROTOCOL_VERSION;
    doc["t"] = "hb";
    doc["seq"] = seq;
    doc["uptime_ms"] = uptimeMs;
    String out;
    serializeJson(doc, out);
    return out;
}

String pb_build_sensors(unsigned long seq, float internalTempC, bool tempOk,
                         bool bh1750Available, float bh1750Lux, bool bh1750Ok,
                         bool ds18b20EverFound, bool ds18b20BusOk,
                         int ds18b20ProbeCount, const Ds18b20Probe *ds18b20Probes) {
    StaticJsonDocument<PIRATEBOX_JSON_DOC_SIZE> doc;
    doc["v"] = PIRATEBOX_PROTOCOL_VERSION;
    doc["t"] = "sensors";
    doc["seq"] = seq;
    JsonObject readings = doc.createNestedObject("readings");
    JsonObject temp = readings.createNestedObject(CAP_TEMP_INTERNAL);
    temp["ok"] = tempOk;
    if (tempOk) {
        temp["value"] = internalTempC;
        temp["unit"] = "C";
    } else {
        temp["err"] = "read_failed";
    }
    // Only reported at all if this boot's init found a sensor - a
    // never-wired board must never appear to have a failing sensor,
    // just no entry at all (mirrors CAP_BH1750's own hello behavior).
    if (bh1750Available) {
        JsonObject bh1750 = readings.createNestedObject(CAP_BH1750);
        bh1750["ok"] = bh1750Ok;
        if (bh1750Ok) {
            bh1750["value"] = bh1750Lux;
            bh1750["unit"] = "lux";
        } else {
            bh1750["err"] = "read_failed";
        }
    }
    // Only reported at all once the bus has EVER found a probe - see
    // CAP_DS18B20's own comment. Unlike temp_internal/bh1750, "0
    // probes currently found" is a real, valid state represented
    // inside this block (an empty "probes" object), not by omitting
    // the block entirely - that omission is reserved for "this
    // firmware build's bus has never found anything, ever."
    if (ds18b20EverFound) {
        JsonObject ds18b20 = readings.createNestedObject(CAP_DS18B20);
        ds18b20["bus_ok"] = ds18b20BusOk;
        JsonObject probesObj = ds18b20.createNestedObject("probes");
        for (int i = 0; i < ds18b20ProbeCount; i++) {
            const Ds18b20Probe &p = ds18b20Probes[i];
            JsonObject probe = probesObj.createNestedObject(p.romHex);
            probe["ok"] = p.ok;
            if (p.ok) {
                probe["value"] = p.value;
                probe["unit"] = "C";
            } else {
                probe["err"] = p.err;
            }
        }
    }
    String out;
    serializeJson(doc, out);
    return out;
}

String pb_build_pong(const String &nonce) {
    StaticJsonDocument<192> doc;
    doc["v"] = PIRATEBOX_PROTOCOL_VERSION;
    doc["t"] = "pong";
    doc["nonce"] = nonce;
    String out;
    serializeJson(doc, out);
    return out;
}

String pb_build_err(const String &reason) {
    StaticJsonDocument<192> doc;
    doc["v"] = PIRATEBOX_PROTOCOL_VERSION;
    doc["t"] = "err";
    doc["reason"] = reason;
    String out;
    serializeJson(doc, out);
    return out;
}

PbParsedCommand pb_parse_command(const String &line) {
    PbParsedCommand result;

    if (line.length() == 0 || line.length() > PIRATEBOX_MAX_LINE_LEN) {
        result.parseError = true;
        return result;
    }

    StaticJsonDocument<PIRATEBOX_JSON_DOC_SIZE> doc;
    DeserializationError err = deserializeJson(doc, line);
    if (err) {
        result.parseError = true;
        return result;
    }

    // Malformed-but-valid-JSON shapes (missing "t", wrong type, etc.)
    // degrade to Unknown rather than a second error class - the caller
    // replies with the same "err" either way. No structural difference
    // to the Pi between "not JSON" and "JSON but not a real command".
    const char *t = doc["t"];
    if (t == nullptr) {
        result.type = PbCommand::Unknown;
        return result;
    }

    if (strcmp(t, "ping") == 0) {
        result.type = PbCommand::Ping;
        const char *nonce = doc["nonce"];
        if (nonce != nullptr) {
            result.nonce = String(nonce);
        }
        return result;
    }
    if (strcmp(t, "get_info") == 0) {
        result.type = PbCommand::GetInfo;
        return result;
    }

    // Any other "t" (including a genuinely future/unknown one from a
    // newer Pi) is Unknown, not an error - see the header's
    // extensibility contract.
    result.type = PbCommand::Unknown;
    return result;
}
