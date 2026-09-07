#include "protocol.h"

String pb_build_hello(const String &mac, const String &resetReason, unsigned long uptimeMs) {
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
    // sensors.cpp's own init. Today that's just the internal temp
    // sensor, which every ESP32-S3 has built in (no wiring required),
    // so it is always listed.
    caps.add(CAP_TEMP_INTERNAL);

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

String pb_build_sensors(unsigned long seq, float internalTempC, bool tempOk) {
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
