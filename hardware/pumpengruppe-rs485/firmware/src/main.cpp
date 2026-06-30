#include <Arduino.h>
#include <ArduinoOTA.h>
#include <DNSServer.h>
#include <ESPmDNS.h>
#include <Preferences.h>
#include <Update.h>
#include <WebServer.h>
#include <WiFi.h>
#include <Adafruit_MAX31865.h>
#include <Adafruit_NeoPixel.h>

#ifndef FW_NAME
#define FW_NAME "pumpengruppe-rs485"
#endif

#ifndef FW_VERSION
#define FW_VERSION "0.1.0"
#endif

static constexpr uint16_t FW_VERSION_BCD = 0x0010;
static constexpr uint16_t DNS_PORT = 53;
static constexpr uint32_t POSITION_SAVE_INTERVAL_MS = 30000;
static constexpr uint32_t WIFI_CONNECT_TIMEOUT_MS = 15000;
static constexpr uint32_t MODBUS_SILENCE_US = 4000;
static constexpr uint32_t HARDWARE_POLL_INTERVAL_MS = 1000;
static constexpr float RTD_RREF_PT1000 = 4300.0f;
static constexpr float RTD_RREF_PT100 = 430.0f;
static constexpr float RTD_RNOMINAL_PT1000 = 1000.0f;
static constexpr float RTD_RNOMINAL_PT100 = 100.0f;

namespace HwPin {
static constexpr uint8_t RS485_RX = 16;
static constexpr uint8_t RS485_TX = 17;
static constexpr uint8_t RS485_DE = 4;
static constexpr uint8_t PUMP_DRV = 25;
static constexpr uint8_t MIX_ENABLE_DRV = 26;
static constexpr uint8_t MIX_DIR_DRV = 27;
static constexpr uint8_t RGB_DATA = 21;
static constexpr uint8_t RGB_COUNT = 24;
static constexpr uint8_t SPI_MOSI = 23;
static constexpr uint8_t SPI_MISO = 19;
static constexpr uint8_t SPI_SCK = 18;
static constexpr uint8_t RTD_VL_CS = 5;
static constexpr uint8_t RTD_RL_CS = 22;
}

enum Mode : uint16_t {
  MODE_AUTO = 0,
  MODE_HAND = 1,
  MODE_CAL_CLOSE = 2,
  MODE_CAL_OPEN = 3,
};

enum FaultCode : uint16_t {
  FAULT_OK = 0,
  FAULT_MODBUS_WATCHDOG = 1,
  FAULT_VL_SENSOR = 2,
  FAULT_RL_SENSOR = 3,
  FAULT_RELAY_CONFLICT = 4,
  FAULT_CALIBRATION_MISSING = 5,
  FAULT_RELAY_DIAG = 6,
};

enum ParityMode : uint8_t {
  PARITY_8N1 = 0,
  PARITY_8E1 = 1,
  PARITY_8O1 = 2,
};

enum RtdType : uint16_t {
  RTD_PT1000 = 0,
  RTD_PT100 = 1,
};

struct Config {
  char wifiSsid[33] = "";
  char wifiPass[65] = "";
  char hostname[33] = "pumpengruppe-rs485";
  char adminPass[33] = "admin";
  uint8_t slaveId = 30;
  uint32_t baud = 9600;
  ParityMode parity = PARITY_8N1;
  uint16_t watchdogTimeoutS = 60;
  uint16_t mixerRuntimeS = 120;
  uint16_t endstopOverrunS = 5;
  RtdType rtdType = RTD_PT1000;
  uint16_t failsafePump = 0;
  bool modbusTcpEnabled = true;
  uint16_t modbusTcpPort = 502;
};

struct RuntimeState {
  uint16_t commandSeq = 0;
  bool pumpRequested = false;
  bool pumpOn = false;
  int16_t targetPctX10 = 0;
  int16_t positionPctX10 = 0;
  Mode mode = MODE_AUTO;
  bool moving = false;
  int8_t moveDirection = 0;
  uint32_t moveStartMs = 0;
  uint32_t moveDurationMs = 0;
  int16_t moveStartPctX10 = 0;
  uint16_t lastCommandSeq = 0;
  FaultCode faultCode = FAULT_OK;
  int16_t vlTempX10 = 315;
  int16_t rlTempX10 = 285;
  uint32_t lastModbusMs = 0;
  uint32_t lastPositionSaveMs = 0;
  uint32_t txCount = 0;
  uint32_t rxCount = 0;
  uint32_t crcErrorCount = 0;
  bool wifiApMode = false;
  bool rtdVlOk = false;
  bool rtdRlOk = false;
  uint8_t rtdVlFault = 0;
  uint8_t rtdRlFault = 0;
  bool rgbConfigured = false;
  bool rs485Configured = false;
  bool relaysConfigured = false;
};

Config cfg;
RuntimeState st;
Preferences prefs;
WebServer server(80);
DNSServer dnsServer;
HardwareSerial rs485(2);
Adafruit_NeoPixel *pixels = nullptr;
Adafruit_MAX31865 rtdVl(HwPin::RTD_VL_CS, HwPin::SPI_MOSI, HwPin::SPI_MISO, HwPin::SPI_SCK);
Adafruit_MAX31865 rtdRl(HwPin::RTD_RL_CS, HwPin::SPI_MOSI, HwPin::SPI_MISO, HwPin::SPI_SCK);
WiFiServer *modbusTcpServer = nullptr;
WiFiClient modbusTcpClients[4];

static uint16_t holding[9] = {};
static uint16_t inputRegs[9] = {};
static uint8_t mbBuf[256] = {};
static size_t mbLen = 0;
static uint32_t lastMbByteUs = 0;
static uint32_t rebootAtMs = 0;

template <typename T>
static T clampValue(T value, T minValue, T maxValue) {
  if (value < minValue) return minValue;
  if (value > maxValue) return maxValue;
  return value;
}

static String htmlEscape(const String &in) {
  String out;
  out.reserve(in.length());
  for (char c : in) {
    switch (c) {
    case '&': out += F("&amp;"); break;
    case '<': out += F("&lt;"); break;
    case '>': out += F("&gt;"); break;
    case '"': out += F("&quot;"); break;
    default: out += c; break;
    }
  }
  return out;
}

static void copyString(char *dst, size_t len, const String &value) {
  String trimmed = value;
  trimmed.trim();
  strlcpy(dst, trimmed.c_str(), len);
}

static uint32_t serialConfig() {
  if (cfg.parity == PARITY_8E1) return SERIAL_8E1;
  if (cfg.parity == PARITY_8O1) return SERIAL_8O1;
  return SERIAL_8N1;
}

static const char *parityName(ParityMode parity) {
  switch (parity) {
  case PARITY_8E1: return "8E1";
  case PARITY_8O1: return "8O1";
  default: return "8N1";
  }
}

static String chipSuffix() {
  uint64_t mac = ESP.getEfuseMac();
  char buf[7];
  snprintf(buf, sizeof(buf), "%06X", static_cast<uint32_t>(mac & 0xFFFFFF));
  return String(buf);
}

static bool isAuthenticated() {
  return server.authenticate("admin", cfg.adminPass);
}

static bool requireAuth() {
  if (st.wifiApMode) return true;
  if (isAuthenticated()) return true;
  server.requestAuthentication();
  return false;
}

static void saveConfig() {
  prefs.begin("pumpgrp", false);
  prefs.putString("wifiSsid", cfg.wifiSsid);
  prefs.putString("wifiPass", cfg.wifiPass);
  prefs.putString("hostname", cfg.hostname);
  prefs.putString("adminPass", cfg.adminPass);
  prefs.putUChar("slaveId", cfg.slaveId);
  prefs.putUInt("baud", cfg.baud);
  prefs.putUChar("parity", cfg.parity);
  prefs.putUShort("wdS", cfg.watchdogTimeoutS);
  prefs.putUShort("runS", cfg.mixerRuntimeS);
  prefs.putUShort("overS", cfg.endstopOverrunS);
  prefs.putUShort("rtdType", cfg.rtdType);
  prefs.putUShort("failPump", cfg.failsafePump);
  prefs.putBool("mbTcpEn", cfg.modbusTcpEnabled);
  prefs.putUShort("mbTcpPort", cfg.modbusTcpPort);
  prefs.putShort("pos", st.positionPctX10);
  prefs.end();
}

static String prefStringOrDefault(const char *key, const char *fallback) {
  if (!prefs.isKey(key)) return String(fallback);
  return prefs.getString(key, fallback);
}

static void loadConfig() {
  prefs.begin("pumpgrp", true);
  copyString(cfg.wifiSsid, sizeof(cfg.wifiSsid), prefStringOrDefault("wifiSsid", cfg.wifiSsid));
  copyString(cfg.wifiPass, sizeof(cfg.wifiPass), prefStringOrDefault("wifiPass", cfg.wifiPass));
  copyString(cfg.hostname, sizeof(cfg.hostname), prefStringOrDefault("hostname", cfg.hostname));
  copyString(cfg.adminPass, sizeof(cfg.adminPass), prefStringOrDefault("adminPass", cfg.adminPass));
  cfg.slaveId = prefs.getUChar("slaveId", cfg.slaveId);
  cfg.baud = prefs.getUInt("baud", cfg.baud);
  cfg.parity = static_cast<ParityMode>(prefs.getUChar("parity", cfg.parity));
  cfg.watchdogTimeoutS = prefs.getUShort("wdS", cfg.watchdogTimeoutS);
  cfg.mixerRuntimeS = prefs.getUShort("runS", cfg.mixerRuntimeS);
  cfg.endstopOverrunS = prefs.getUShort("overS", cfg.endstopOverrunS);
  cfg.rtdType = static_cast<RtdType>(prefs.getUShort("rtdType", cfg.rtdType));
  cfg.failsafePump = prefs.getUShort("failPump", cfg.failsafePump);
  cfg.modbusTcpEnabled = prefs.getBool("mbTcpEn", cfg.modbusTcpEnabled);
  cfg.modbusTcpPort = prefs.getUShort("mbTcpPort", cfg.modbusTcpPort);
  st.positionPctX10 = prefs.getShort("pos", 0);
  prefs.end();
}

static void initHoldingFromConfig() {
  holding[0] = st.commandSeq;
  holding[1] = st.pumpRequested ? 1 : 0;
  holding[2] = static_cast<uint16_t>(st.targetPctX10);
  holding[3] = st.mode;
  holding[4] = cfg.watchdogTimeoutS;
  holding[5] = cfg.mixerRuntimeS;
  holding[6] = cfg.endstopOverrunS;
  holding[7] = cfg.rtdType;
  holding[8] = cfg.failsafePump;
}

static void applyOutputs() {
  digitalWrite(HwPin::PUMP_DRV, st.pumpOn ? HIGH : LOW);
  digitalWrite(HwPin::MIX_DIR_DRV, st.moveDirection > 0 ? HIGH : LOW);
  digitalWrite(HwPin::MIX_ENABLE_DRV, st.moving ? HIGH : LOW);
}

static void allOutputsOff() {
  st.pumpOn = false;
  st.moving = false;
  st.moveDirection = 0;
  applyOutputs();
}

static void updateInputRegisters() {
  uint16_t status = 0;
  status |= 1U << 0;
  if (st.faultCode != FAULT_OK) status |= 1U << 1;
  if (st.moving) status |= 1U << 2;
  if (st.pumpOn) status |= 1U << 3;
  if (st.moving && st.moveDirection > 0) status |= 1U << 4;
  if (st.moving && st.moveDirection < 0) status |= 1U << 5;
  inputRegs[0] = status;
  inputRegs[1] = static_cast<uint16_t>(st.positionPctX10);
  inputRegs[2] = static_cast<uint16_t>(st.vlTempX10);
  inputRegs[3] = static_cast<uint16_t>(st.rlTempX10);
  inputRegs[4] = st.lastCommandSeq;
  inputRegs[5] = st.faultCode;
  uint32_t uptime = millis() / 1000;
  inputRegs[6] = uptime & 0xFFFF;
  inputRegs[7] = uptime >> 16;
  inputRegs[8] = FW_VERSION_BCD;
}

static void configurePixels() {
  if (pixels) {
    delete pixels;
    pixels = nullptr;
  }
  pixels = new Adafruit_NeoPixel(HwPin::RGB_COUNT, HwPin::RGB_DATA, NEO_GRB + NEO_KHZ800);
  pixels->begin();
  pixels->clear();
  pixels->show();
  st.rgbConfigured = true;
}

static uint32_t rgb(uint8_t r, uint8_t g, uint8_t b) {
  return pixels ? pixels->Color(r, g, b) : 0;
}

static void updatePixels() {
  if (!pixels) return;
  pixels->clear();

  uint32_t wifiColor = WiFi.status() == WL_CONNECTED ? rgb(0, 32, 0) : rgb(32, 16, 0);
  uint32_t busColor = (millis() - st.lastModbusMs < 5000) ? rgb(0, 0, 32) : rgb(16, 16, 16);
  uint32_t faultColor = st.faultCode == FAULT_OK ? rgb(0, 12, 0) : rgb(48, 0, 0);
  uint32_t pumpColor = st.pumpOn ? rgb(0, 32, 0) : rgb(4, 4, 4);

  if (HwPin::RGB_COUNT > 0) pixels->setPixelColor(0, wifiColor);
  if (HwPin::RGB_COUNT > 1) pixels->setPixelColor(1, busColor);
  if (HwPin::RGB_COUNT > 2) pixels->setPixelColor(2, faultColor);
  if (HwPin::RGB_COUNT > 3) pixels->setPixelColor(3, pumpColor);

  int lit = map(clampValue<int16_t>(st.positionPctX10, 0, 1000), 0, 1000, 0, 20);
  for (int i = 0; i < 20 && (4 + i) < HwPin::RGB_COUNT; i++) {
    pixels->setPixelColor(4 + i, i < lit ? rgb(0, 0, 36) : rgb(2, 2, 2));
  }
  pixels->show();
}

static void startMoveTo(int16_t targetPctX10) {
  targetPctX10 = clampValue<int16_t>(targetPctX10, 0, 1000);
  int16_t delta = targetPctX10 - st.positionPctX10;
  if (abs(delta) < 2) {
    st.targetPctX10 = targetPctX10;
    st.positionPctX10 = targetPctX10;
    st.moving = false;
    st.moveDirection = 0;
    applyOutputs();
    return;
  }

  st.targetPctX10 = targetPctX10;
  st.moveDirection = delta > 0 ? 1 : -1;
  st.moveStartPctX10 = st.positionPctX10;
  st.moveStartMs = millis();
  uint32_t baseMs = (static_cast<uint32_t>(abs(delta)) * cfg.mixerRuntimeS * 100UL) / 1000UL;
  if (targetPctX10 == 0 || targetPctX10 == 1000 || st.mode == MODE_CAL_CLOSE || st.mode == MODE_CAL_OPEN) {
    baseMs += static_cast<uint32_t>(cfg.endstopOverrunS) * 1000UL;
  }
  st.moveDurationMs = max<uint32_t>(baseMs, 200);
  st.moving = true;
  applyOutputs();
}

static void applyCommandRegisters() {
  cfg.watchdogTimeoutS = clampValue<uint16_t>(holding[4], 1, 600);
  cfg.mixerRuntimeS = clampValue<uint16_t>(holding[5], 5, 1000);
  cfg.endstopOverrunS = clampValue<uint16_t>(holding[6], 0, 120);
  cfg.rtdType = holding[7] == 1 ? RTD_PT100 : RTD_PT1000;
  cfg.failsafePump = holding[8] ? 1 : 0;

  st.pumpRequested = holding[1] != 0;
  st.mode = static_cast<Mode>(holding[3]);
  int16_t target = clampValue<int16_t>(static_cast<int16_t>(holding[2]), 0, 1000);

  if (st.mode == MODE_CAL_CLOSE) target = 0;
  if (st.mode == MODE_CAL_OPEN) target = 1000;

  if (holding[0] != st.lastCommandSeq || target != st.targetPctX10 || st.mode == MODE_CAL_CLOSE || st.mode == MODE_CAL_OPEN) {
    st.lastCommandSeq = holding[0];
    startMoveTo(target);
  }
}

static void updateMotion() {
  if (!st.moving) return;
  uint32_t elapsed = millis() - st.moveStartMs;
  if (elapsed >= st.moveDurationMs) {
    st.positionPctX10 = st.targetPctX10;
    if (st.mode == MODE_CAL_CLOSE) st.positionPctX10 = 0;
    if (st.mode == MODE_CAL_OPEN) st.positionPctX10 = 1000;
    st.moving = false;
    st.moveDirection = 0;
    applyOutputs();
    return;
  }
  int32_t travel = static_cast<int32_t>(elapsed) * 1000L / max<uint32_t>(1, cfg.mixerRuntimeS * 1000UL);
  st.positionPctX10 = clampValue<int16_t>(st.moveStartPctX10 + st.moveDirection * travel, 0, 1000);
}

static void updateTemperatures() {
  static uint32_t lastMs = 0;
  if (millis() - lastMs < 1000) return;
  lastMs = millis();
  float t = millis() / 1000.0f;
  st.vlTempX10 = 320 + static_cast<int16_t>(20.0f * sinf(t / 15.0f));
  st.rlTempX10 = 285 + static_cast<int16_t>(15.0f * sinf(t / 18.0f));
}

static void updateWatchdog() {
  bool watchdogExpired = st.lastModbusMs > 0 && (millis() - st.lastModbusMs > static_cast<uint32_t>(cfg.watchdogTimeoutS) * 1000UL);
  if (watchdogExpired) {
    st.faultCode = FAULT_MODBUS_WATCHDOG;
    st.pumpOn = cfg.failsafePump != 0;
    st.moving = false;
    st.moveDirection = 0;
  } else if (st.faultCode == FAULT_MODBUS_WATCHDOG) {
    st.faultCode = FAULT_OK;
  }
  if (!watchdogExpired) st.pumpOn = st.pumpRequested;
  applyOutputs();
}

static void maybeSavePosition() {
  if (millis() - st.lastPositionSaveMs < POSITION_SAVE_INTERVAL_MS) return;
  st.lastPositionSaveMs = millis();
  prefs.begin("pumpgrp", false);
  prefs.putShort("pos", st.positionPctX10);
  prefs.end();
}

static uint16_t modbusCrc(const uint8_t *data, size_t len) {
  uint16_t crc = 0xFFFF;
  for (size_t i = 0; i < len; i++) {
    crc ^= data[i];
    for (uint8_t bit = 0; bit < 8; bit++) {
      crc = (crc & 1) ? (crc >> 1) ^ 0xA001 : crc >> 1;
    }
  }
  return crc;
}

static void rs485Send(const uint8_t *data, size_t len) {
  digitalWrite(HwPin::RS485_DE, HIGH);
  delayMicroseconds(50);
  rs485.write(data, len);
  rs485.flush();
  delayMicroseconds(100);
  digitalWrite(HwPin::RS485_DE, LOW);
  st.txCount++;
}

static void sendException(uint8_t id, uint8_t fn, uint8_t code) {
  uint8_t frame[5] = {id, static_cast<uint8_t>(fn | 0x80), code, 0, 0};
  uint16_t crc = modbusCrc(frame, 3);
  frame[3] = crc & 0xFF;
  frame[4] = crc >> 8;
  rs485Send(frame, sizeof(frame));
}

static void handleReadRegs(uint8_t id, uint8_t fn, const uint8_t *req, const uint16_t *regs, uint16_t regCount) {
  uint16_t start = (req[2] << 8) | req[3];
  uint16_t qty = (req[4] << 8) | req[5];
  if (qty < 1 || qty > 60 || start + qty > regCount) {
    sendException(id, fn, 0x02);
    return;
  }
  uint8_t resp[128] = {};
  resp[0] = id;
  resp[1] = fn;
  resp[2] = qty * 2;
  for (uint16_t i = 0; i < qty; i++) {
    uint16_t v = regs[start + i];
    resp[3 + i * 2] = v >> 8;
    resp[4 + i * 2] = v & 0xFF;
  }
  uint16_t len = 3 + qty * 2;
  uint16_t crc = modbusCrc(resp, len);
  resp[len++] = crc & 0xFF;
  resp[len++] = crc >> 8;
  rs485Send(resp, len);
}

static void handleWriteSingle(uint8_t id, const uint8_t *req) {
  uint16_t addr = (req[2] << 8) | req[3];
  uint16_t value = (req[4] << 8) | req[5];
  if (addr >= 9) {
    sendException(id, 0x06, 0x02);
    return;
  }
  holding[addr] = value;
  applyCommandRegisters();
  rs485Send(req, 8);
}

static void handleWriteMultiple(uint8_t id, const uint8_t *req, size_t len) {
  uint16_t start = (req[2] << 8) | req[3];
  uint16_t qty = (req[4] << 8) | req[5];
  uint8_t byteCount = req[6];
  if (qty < 1 || qty > 9 || start + qty > 9 || byteCount != qty * 2 || len < static_cast<size_t>(9 + byteCount)) {
    sendException(id, 0x10, 0x02);
    return;
  }
  for (uint16_t i = 0; i < qty; i++) {
    holding[start + i] = (req[7 + i * 2] << 8) | req[8 + i * 2];
  }
  applyCommandRegisters();
  uint8_t resp[8] = {id, 0x10, req[2], req[3], req[4], req[5], 0, 0};
  uint16_t crc = modbusCrc(resp, 6);
  resp[6] = crc & 0xFF;
  resp[7] = crc >> 8;
  rs485Send(resp, sizeof(resp));
}

static size_t buildModbusPduResponse(uint8_t unitId, const uint8_t *pdu, size_t pduLen, uint8_t *out, size_t outMax) {
  if (pduLen < 1 || outMax < 2) return 0;
  uint8_t fn = pdu[0];
  auto exception = [&](uint8_t code) -> size_t {
    out[0] = fn | 0x80;
    out[1] = code;
    return 2;
  };

  if (fn == 0x03 || fn == 0x04) {
    if (pduLen < 5) return exception(0x03);
    uint16_t start = (pdu[1] << 8) | pdu[2];
    uint16_t qty = (pdu[3] << 8) | pdu[4];
    const uint16_t *regs = fn == 0x03 ? holding : inputRegs;
    uint16_t regCount = 9;
    if (qty < 1 || qty > 60 || start + qty > regCount || outMax < static_cast<size_t>(2 + qty * 2)) {
      return exception(0x02);
    }
    out[0] = fn;
    out[1] = qty * 2;
    for (uint16_t i = 0; i < qty; i++) {
      uint16_t v = regs[start + i];
      out[2 + i * 2] = v >> 8;
      out[3 + i * 2] = v & 0xFF;
    }
    return 2 + qty * 2;
  }

  if (fn == 0x06) {
    if (pduLen < 5 || outMax < 5) return exception(0x03);
    uint16_t addr = (pdu[1] << 8) | pdu[2];
    uint16_t value = (pdu[3] << 8) | pdu[4];
    if (addr >= 9) return exception(0x02);
    holding[addr] = value;
    applyCommandRegisters();
    memcpy(out, pdu, 5);
    return 5;
  }

  if (fn == 0x10) {
    if (pduLen < 6) return exception(0x03);
    uint16_t start = (pdu[1] << 8) | pdu[2];
    uint16_t qty = (pdu[3] << 8) | pdu[4];
    uint8_t byteCount = pdu[5];
    if (qty < 1 || qty > 9 || start + qty > 9 || byteCount != qty * 2 || pduLen < static_cast<size_t>(6 + byteCount)) {
      return exception(0x02);
    }
    for (uint16_t i = 0; i < qty; i++) {
      holding[start + i] = (pdu[6 + i * 2] << 8) | pdu[7 + i * 2];
    }
    applyCommandRegisters();
    if (outMax < 5) return 0;
    out[0] = fn;
    out[1] = pdu[1];
    out[2] = pdu[2];
    out[3] = pdu[3];
    out[4] = pdu[4];
    return 5;
  }

  return exception(0x01);
}

static void processModbusFrame(const uint8_t *frame, size_t len) {
  if (len < 4) return;
  uint8_t id = frame[0];
  if (id != cfg.slaveId && id != 0) return;
  uint16_t got = frame[len - 2] | (frame[len - 1] << 8);
  uint16_t want = modbusCrc(frame, len - 2);
  if (got != want) {
    st.crcErrorCount++;
    return;
  }
  st.rxCount++;
  st.lastModbusMs = millis();
  st.faultCode = FAULT_OK;
  if (id == 0) return;

  uint8_t fn = frame[1];
  if (fn == 0x03) handleReadRegs(id, fn, frame, holding, 9);
  else if (fn == 0x04) handleReadRegs(id, fn, frame, inputRegs, 9);
  else if (fn == 0x06 && len == 8) handleWriteSingle(id, frame);
  else if (fn == 0x10) handleWriteMultiple(id, frame, len);
  else sendException(id, fn, 0x01);
}

static void setupModbusTcp() {
  if (modbusTcpServer) {
    delete modbusTcpServer;
    modbusTcpServer = nullptr;
  }
  if (!cfg.modbusTcpEnabled) return;
  modbusTcpServer = new WiFiServer(cfg.modbusTcpPort);
  modbusTcpServer->begin();
  modbusTcpServer->setNoDelay(true);
  Serial.printf("Modbus TCP aktiv auf Port %u\n", cfg.modbusTcpPort);
}

static void handleModbusTcpClient(WiFiClient &client) {
  if (!client || !client.connected()) return;
  while (client.available() >= 7) {
    uint8_t header[7];
    size_t gotHeader = client.readBytes(header, sizeof(header));
    if (gotHeader < sizeof(header)) {
      client.stop();
      return;
    }

    uint16_t protocol = (header[2] << 8) | header[3];
    uint16_t length = (header[4] << 8) | header[5];
    if (protocol != 0 || length < 2 || length > 253) {
      client.stop();
      return;
    }
    uint8_t frame[260] = {};
    memcpy(frame, header, sizeof(header));
    size_t remaining = length - 1;
    if (remaining > 0) {
      size_t gotBody = client.readBytes(frame + 7, remaining);
      if (gotBody < remaining) {
        client.stop();
        return;
      }
    }
    uint8_t unitId = frame[6];
    if (unitId != cfg.slaveId && unitId != 0xFF && unitId != 0) {
      continue;
    }
    st.rxCount++;
    st.lastModbusMs = millis();
    st.faultCode = FAULT_OK;
    if (unitId == 0) continue;

    uint8_t pduResp[253] = {};
    size_t pduRespLen = buildModbusPduResponse(unitId, frame + 7, remaining, pduResp, sizeof(pduResp));
    if (pduRespLen == 0) continue;

    uint8_t resp[260] = {};
    resp[0] = frame[0];
    resp[1] = frame[1];
    resp[2] = 0;
    resp[3] = 0;
    uint16_t respLenField = pduRespLen + 1;
    resp[4] = respLenField >> 8;
    resp[5] = respLenField & 0xFF;
    resp[6] = unitId;
    memcpy(resp + 7, pduResp, pduRespLen);
    client.write(resp, 7 + pduRespLen);
    st.txCount++;
  }
}

static void pollModbusTcp() {
  if (!modbusTcpServer) return;
  WiFiClient incoming = modbusTcpServer->available();
  if (incoming) {
    bool assigned = false;
    for (auto &client : modbusTcpClients) {
      if (!client || !client.connected()) {
        client.stop();
        client = incoming;
        client.setNoDelay(true);
        assigned = true;
        break;
      }
    }
    if (!assigned) incoming.stop();
  }
  for (auto &client : modbusTcpClients) {
    if (client && client.connected()) handleModbusTcpClient(client);
    else client.stop();
  }
}

static void pollModbus() {
  while (rs485.available()) {
    int b = rs485.read();
    if (b < 0) break;
    if (mbLen < sizeof(mbBuf)) mbBuf[mbLen++] = static_cast<uint8_t>(b);
    lastMbByteUs = micros();
  }
  if (mbLen > 0 && micros() - lastMbByteUs > MODBUS_SILENCE_US) {
    processModbusFrame(mbBuf, mbLen);
    mbLen = 0;
  }
}

static String configJson() {
  String json = "{";
  json += "\"wifiSsid\":\"" + htmlEscape(cfg.wifiSsid) + "\",";
  json += "\"hostname\":\"" + htmlEscape(cfg.hostname) + "\",";
  json += "\"slaveId\":" + String(cfg.slaveId) + ",";
  json += "\"baud\":" + String(cfg.baud) + ",";
  json += "\"parity\":\"" + String(parityName(cfg.parity)) + "\",";
  json += "\"watchdogTimeoutS\":" + String(cfg.watchdogTimeoutS) + ",";
  json += "\"mixerRuntimeS\":" + String(cfg.mixerRuntimeS) + ",";
  json += "\"endstopOverrunS\":" + String(cfg.endstopOverrunS) + ",";
  json += "\"rtdType\":\"" + String(cfg.rtdType == RTD_PT100 ? "PT100" : "PT1000") + "\",";
  json += "\"failsafePump\":" + String(cfg.failsafePump) + ",";
  json += "\"modbusTcpEnabled\":" + String(cfg.modbusTcpEnabled ? 1 : 0) + ",";
  json += "\"modbusTcpPort\":" + String(cfg.modbusTcpPort);
  json += "}";
  return json;
}

static String stateJson() {
  updateInputRegisters();
  String json = "{";
  json += "\"fw\":\"" FW_VERSION "\",";
  json += "\"uptimeS\":" + String(millis() / 1000) + ",";
  json += "\"heap\":" + String(ESP.getFreeHeap()) + ",";
  json += "\"wifiMode\":\"" + String(st.wifiApMode ? "AP" : "STA") + "\",";
  json += "\"wifiConnected\":" + String(WiFi.status() == WL_CONNECTED ? "true" : "false") + ",";
  json += "\"ip\":\"" + (st.wifiApMode ? WiFi.softAPIP().toString() : WiFi.localIP().toString()) + "\",";
  json += "\"rssi\":" + String(WiFi.status() == WL_CONNECTED ? WiFi.RSSI() : 0) + ",";
  json += "\"pumpRequested\":" + String(st.pumpRequested ? "true" : "false") + ",";
  json += "\"pumpOn\":" + String(st.pumpOn ? "true" : "false") + ",";
  json += "\"moving\":" + String(st.moving ? "true" : "false") + ",";
  json += "\"direction\":\"" + String(st.moveDirection > 0 ? "AUF" : (st.moveDirection < 0 ? "ZU" : "STOP")) + "\",";
  json += "\"targetPct\":" + String(st.targetPctX10 / 10.0f, 1) + ",";
  json += "\"positionPct\":" + String(st.positionPctX10 / 10.0f, 1) + ",";
  json += "\"vlTempC\":" + String(st.vlTempX10 / 10.0f, 1) + ",";
  json += "\"rlTempC\":" + String(st.rlTempX10 / 10.0f, 1) + ",";
  json += "\"mode\":" + String(st.mode) + ",";
  json += "\"faultCode\":" + String(st.faultCode) + ",";
  json += "\"lastCommandSeq\":" + String(st.lastCommandSeq) + ",";
  json += "\"rxCount\":" + String(st.rxCount) + ",";
  json += "\"txCount\":" + String(st.txCount) + ",";
  json += "\"crcErrorCount\":" + String(st.crcErrorCount) + ",";
  json += "\"modbusTcpEnabled\":" + String(cfg.modbusTcpEnabled ? "true" : "false") + ",";
  json += "\"modbusTcpPort\":" + String(cfg.modbusTcpPort) + ",";
  json += "\"rtdVlOk\":" + String(st.rtdVlOk ? "true" : "false") + ",";
  json += "\"rtdRlOk\":" + String(st.rtdRlOk ? "true" : "false") + ",";
  json += "\"rtdVlFault\":" + String(st.rtdVlFault) + ",";
  json += "\"rtdRlFault\":" + String(st.rtdRlFault) + ",";
  json += "\"rgbConfigured\":" + String(st.rgbConfigured ? "true" : "false") + ",";
  json += "\"rs485Configured\":" + String(st.rs485Configured ? "true" : "false") + ",";
  json += "\"relaysConfigured\":" + String(st.relaysConfigured ? "true" : "false") + ",";
  json += "\"lastModbusAgeS\":" + String(st.lastModbusMs == 0 ? -1 : static_cast<int32_t>((millis() - st.lastModbusMs) / 1000));
  json += "}";
  return json;
}

static String wifiScanJson() {
  int count = WiFi.scanComplete();
  if (count == WIFI_SCAN_RUNNING) return "{\"running\":true,\"networks\":[]}";
  if (count < 0) {
    WiFi.scanNetworks(true, true);
    return "{\"running\":true,\"networks\":[]}";
  }

  String json = "{\"running\":false,\"networks\":[";
  for (int i = 0; i < count; i++) {
    if (i) json += ",";
    json += "{";
    json += "\"ssid\":\"" + htmlEscape(WiFi.SSID(i)) + "\",";
    json += "\"rssi\":" + String(WiFi.RSSI(i)) + ",";
    json += "\"secure\":" + String(WiFi.encryptionType(i) == WIFI_AUTH_OPEN ? "false" : "true");
    json += "}";
  }
  json += "]}";
  WiFi.scanDelete();
  WiFi.scanNetworks(true, true);
  return json;
}

static void sendNoCache() {
  server.sendHeader("Cache-Control", "no-store");
}

static bool isCaptivePortalRequest() {
  if (!st.wifiApMode) return false;
  String host = server.hostHeader();
  host.toLowerCase();
  if (host.length() == 0) return false;
  if (host == WiFi.softAPIP().toString()) return false;
  if (host == String(cfg.hostname) + ".local") return false;
  return true;
}

static void redirectToCaptivePortal() {
  server.sendHeader("Location", String("http://") + WiFi.softAPIP().toString() + "/", true);
  server.sendHeader("Cache-Control", "no-store");
  server.send(302, "text/plain; charset=utf-8", "Einrichtungsseite");
}

static void handleRoot() {
  if (isCaptivePortalRequest()) {
    redirectToCaptivePortal();
    return;
  }
  if (!requireAuth()) return;
  sendNoCache();
  server.send(200, "text/html; charset=utf-8", R"HTML(
<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Pumpengruppe RS485</title>
  <style>
    :root{font-family:system-ui,-apple-system,Segoe UI,sans-serif;color:#17202a;background:#f4f7f6}
    body{margin:0}.bar{background:#193b3a;color:white;padding:14px 18px;display:flex;justify-content:space-between;gap:12px;align-items:center}
    main{max-width:1100px;margin:0 auto;padding:18px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}
    section{background:white;border:1px solid #d8e0de;border-radius:8px;padding:14px}h1{font-size:20px;margin:0}h2{font-size:16px;margin:0 0 12px}
    .kv{display:grid;grid-template-columns:1fr auto;gap:8px;font-size:14px}.kv div{padding:5px 0;border-bottom:1px solid #edf1f0}.v{font-weight:650}
    label{display:block;font-size:13px;margin:10px 0 4px;color:#31413f}input,select{width:100%;box-sizing:border-box;padding:8px;border:1px solid #b9c6c3;border-radius:6px;background:white}
    button,a.button{border:0;border-radius:6px;background:#136f63;color:white;padding:9px 12px;margin-top:12px;cursor:pointer;text-decoration:none;display:inline-block}
    button.secondary{background:#4a5b59}.row{display:grid;grid-template-columns:1fr 1fr;gap:10px}.ok{color:#087a44}.bad{color:#af2d2d}.muted{color:#667}
  </style>
</head>
<body>
  <div class="bar"><h1>Pumpengruppe RS485</h1><span id="fw">...</span></div>
  <main>
    <div class="grid">
      <section><h2>Status</h2><div class="kv" id="status"></div></section>
      <section><h2>Werte</h2><div class="kv" id="values"></div>
        <form id="control">
          <div class="row"><div><label>Zielposition %</label><input name="target" type="number" min="0" max="100" step="0.5" value="0"></div>
          <div><label>Pumpe</label><select name="pump"><option value="0">Aus</option><option value="1">An</option></select></div></div>
          <button>Testwerte setzen</button>
        </form>
      </section>
      <section><h2>WLAN</h2>
        <form id="wifi">
          <label>Gefundene WLANs</label>
          <div class="row"><select id="ssidList"><option value="">scan laeuft...</option></select><button type="button" class="secondary" onclick="scanWifi()">Scan</button></div>
          <label>SSID</label><input name="wifiSsid">
          <label>Passwort</label><input name="wifiPass" type="password" placeholder="leer lassen = unveraendert">
          <label>Hostname</label><input name="hostname">
          <label>Web-Passwort</label><input name="adminPass" type="password" placeholder="leer lassen = unveraendert">
          <button>Speichern</button>
        </form>
      </section>
      <section><h2>RS485 / Modbus</h2>
        <form id="rs485">
          <div class="row"><div><label>Slave-ID</label><input name="slaveId" type="number" min="1" max="247"></div>
          <div><label>Baudrate</label><input name="baud" type="number"></div></div>
          <label>Format</label><select name="parity"><option>8N1</option><option>8E1</option><option>8O1</option></select>
          <button>Speichern & Neustart</button>
        </form>
      </section>
      <section><h2>Hardware</h2><div class="kv" id="hardware"></div></section>
      <section><h2>Modbus TCP</h2>
        <form id="tcp">
          <label>Modbus TCP aktiv</label><select name="modbusTcpEnabled"><option value="1">Ein</option><option value="0">Aus</option></select>
          <label>TCP-Port</label><input name="modbusTcpPort" type="number" min="1" max="65535">
          <button>Speichern & Neustart</button>
        </form>
      </section>
      <section><h2>Mischer / Sensoren</h2>
        <form id="mixer">
          <div class="row"><div><label>Laufzeit 0-100 % (s)</label><input name="mixerRuntimeS" type="number"></div>
          <div><label>Endlagen-Ueberlauf (s)</label><input name="endstopOverrunS" type="number"></div></div>
          <label>Watchdog (s)</label><input name="watchdogTimeoutS" type="number">
          <label>RTD-Typ</label><select name="rtdType"><option>PT1000</option><option>PT100</option></select>
          <label>Pumpe bei Busausfall</label><select name="failsafePump"><option value="0">Aus</option><option value="1">An</option></select>
          <button>Speichern</button>
        </form>
      </section>
      <section><h2>Service</h2>
        <a class="button" href="/update">Firmware-Update</a>
        <button class="secondary" onclick="reboot()">Neustart</button>
        <p class="muted" id="msg"></p>
      </section>
    </div>
  </main>
<script>
const $=s=>document.querySelector(s);
function kv(el, rows){ el.innerHTML=rows.map(([k,v,c])=>`<div>${k}</div><div class="v ${c||''}">${v}</div>`).join(''); }
async function getJson(url){ const r=await fetch(url); return await r.json(); }
async function postForm(url, form){
 $('#msg').textContent='Speichere...';
 const body=new URLSearchParams(new FormData(form));
 const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body});
 const text=await r.text();
 $('#msg').textContent=text;
 if(!r.ok) return;
 if(text.toLowerCase().includes('neustart')){
   setTimeout(()=>{$('#msg').textContent='ESP startet neu. Wenn WLAN-Daten stimmen, erscheint er gleich im Ziel-WLAN; sonst kommt der Einrichtungs-AP wieder.'},800);
   return;
 }
 setTimeout(loadConfig,300);
}
async function loadConfig(){ const c=await getJson('/api/config'); for(const f of document.querySelectorAll('input,select')) if(c[f.name]!==undefined && f.name!=='wifiPass' && f.name!=='adminPass') f.value=c[f.name]; }
async function scanWifi(){
 const data=await getJson('/api/wifi-scan');
 const list=$('#ssidList');
 if(data.running){ list.innerHTML='<option value="">scan laeuft...</option>'; setTimeout(scanWifi,1500); return; }
 list.innerHTML='<option value="">SSID auswaehlen...</option>'+data.networks.map(n=>`<option value="${n.ssid}">${n.ssid} (${n.rssi} dBm${n.secure?', gesichert':', offen'})</option>`).join('');
}
async function tick(){ const s=await getJson('/api/state'); $('#fw').textContent=`FW ${s.fw} | ${s.ip}`; kv($('#status'),[
 ['WLAN', `${s.wifiMode} ${s.wifiConnected?'verbunden':'nicht verbunden'}`, s.wifiConnected?'ok':'bad'],
 ['RSSI', `${s.rssi} dBm`], ['Uptime', `${s.uptimeS}s`], ['Heap', s.heap],
 ['Modbus RX/TX', `${s.rxCount}/${s.txCount}`], ['CRC Fehler', s.crcErrorCount],
 ['Modbus TCP', s.modbusTcpEnabled?`Port ${s.modbusTcpPort}`:'Aus'],
 ['Letzter Bus', s.lastModbusAgeS<0?'nie':`${s.lastModbusAgeS}s`],
 ['Fehlercode', s.faultCode, s.faultCode===0?'ok':'bad']
 ]); kv($('#values'),[
 ['Pumpe', s.pumpOn?'An':'Aus', s.pumpOn?'ok':''], ['Mischer', `${s.positionPct.toFixed(1)} %`],
 ['Ziel', `${s.targetPct.toFixed(1)} %`], ['Fahrt', `${s.moving?s.direction:'STOP'}`],
 ['Vorlauf', `${s.vlTempC.toFixed(1)} °C`], ['Ruecklauf', `${s.rlTempC.toFixed(1)} °C`],
 ['Sequenz', s.lastCommandSeq]
 ]); kv($('#hardware'),[
 ['RS485-Transceiver', s.rs485Configured ? (s.lastModbusAgeS<0?'bereit, keine Telegramme':'Telegramme empfangen') : 'nicht initialisiert', s.rs485Configured?'ok':'bad'],
 ['Modbus TCP', s.modbusTcpEnabled ? `bereit auf Port ${s.modbusTcpPort}` : 'deaktiviert', s.modbusTcpEnabled?'ok':''],
 ['MAX31865 Vorlauf', s.rtdVlOk ? `OK, ${s.vlTempC.toFixed(1)} °C` : `nicht erreichbar / Fehler ${s.rtdVlFault}`, s.rtdVlOk?'ok':'bad'],
 ['MAX31865 Ruecklauf', s.rtdRlOk ? `OK, ${s.rlTempC.toFixed(1)} °C` : `nicht erreichbar / Fehler ${s.rtdRlFault}`, s.rtdRlOk?'ok':'bad'],
 ['RGB-LED-Kette', s.rgbConfigured ? 'angesteuert, nicht ruecklesbar' : 'nicht initialisiert', s.rgbConfigured?'ok':'bad'],
 ['Relaisausgaenge', s.relaysConfigured ? 'GPIO initialisiert, keine Rueckmeldung' : 'nicht initialisiert', s.relaysConfigured?'ok':'bad']
 ]); }
for (const id of ['wifi','rs485','tcp','mixer']) $(('#'+id)).addEventListener('submit',e=>{e.preventDefault();postForm('/api/config',e.target)});
$('#ssidList').addEventListener('change',e=>{ if(e.target.value) document.querySelector('input[name=wifiSsid]').value=e.target.value; });
$('#control').addEventListener('submit',e=>{e.preventDefault();postForm('/api/control',e.target)});
async function reboot(){ await fetch('/api/reboot',{method:'POST'}); $('#msg').textContent='Neustart angefordert'; }
loadConfig(); scanWifi(); tick(); setInterval(tick,1000);
</script>
</body>
</html>
)HTML");
}

static void handleConfigGet() {
  if (!requireAuth()) return;
  sendNoCache();
  server.send(200, "application/json", configJson());
}

static uint16_t argU16(const char *name, uint16_t oldValue, uint16_t minValue, uint16_t maxValue) {
  if (!server.hasArg(name) || server.arg(name).length() == 0) return oldValue;
  return clampValue<uint16_t>(server.arg(name).toInt(), minValue, maxValue);
}

static uint8_t argU8(const char *name, uint8_t oldValue, uint8_t minValue, uint8_t maxValue) {
  return static_cast<uint8_t>(argU16(name, oldValue, minValue, maxValue));
}

static void handleConfigPost() {
  if (!requireAuth()) return;
  bool rs485NeedsRestart = false;
  bool wifiNeedsRestart = false;
  bool tcpNeedsRestart = false;
  if (server.hasArg("wifiSsid")) {
    String old = cfg.wifiSsid;
    copyString(cfg.wifiSsid, sizeof(cfg.wifiSsid), server.arg("wifiSsid"));
    if (old != cfg.wifiSsid) wifiNeedsRestart = true;
  }
  if (server.hasArg("wifiPass") && server.arg("wifiPass").length() > 0) {
    copyString(cfg.wifiPass, sizeof(cfg.wifiPass), server.arg("wifiPass"));
    wifiNeedsRestart = true;
  }
  if (server.hasArg("hostname")) {
    String old = cfg.hostname;
    copyString(cfg.hostname, sizeof(cfg.hostname), server.arg("hostname"));
    if (old != cfg.hostname) wifiNeedsRestart = true;
  }
  if (server.hasArg("adminPass") && server.arg("adminPass").length() > 0) copyString(cfg.adminPass, sizeof(cfg.adminPass), server.arg("adminPass"));
  if (server.hasArg("slaveId")) cfg.slaveId = argU8("slaveId", cfg.slaveId, 1, 247);
  if (server.hasArg("baud")) { cfg.baud = clampValue<uint32_t>(server.arg("baud").toInt(), 1200, 921600); rs485NeedsRestart = true; }
  if (server.hasArg("parity")) {
    String p = server.arg("parity");
    cfg.parity = p == "8E1" ? PARITY_8E1 : (p == "8O1" ? PARITY_8O1 : PARITY_8N1);
    rs485NeedsRestart = true;
  }
  if (server.hasArg("pinRx")) { cfg.pinRx = argU8("pinRx", cfg.pinRx, 0, 39); rs485NeedsRestart = true; }
  if (server.hasArg("pinTx")) { cfg.pinTx = argU8("pinTx", cfg.pinTx, 0, 39); rs485NeedsRestart = true; }
  if (server.hasArg("pinDe")) { cfg.pinDe = argU8("pinDe", cfg.pinDe, 0, 39); rs485NeedsRestart = true; }
  if (server.hasArg("mixerRuntimeS")) cfg.mixerRuntimeS = argU16("mixerRuntimeS", cfg.mixerRuntimeS, 5, 1000);
  if (server.hasArg("endstopOverrunS")) cfg.endstopOverrunS = argU16("endstopOverrunS", cfg.endstopOverrunS, 0, 120);
  if (server.hasArg("watchdogTimeoutS")) cfg.watchdogTimeoutS = argU16("watchdogTimeoutS", cfg.watchdogTimeoutS, 1, 600);
  if (server.hasArg("rtdType")) cfg.rtdType = server.arg("rtdType") == "PT100" ? RTD_PT100 : RTD_PT1000;
  if (server.hasArg("failsafePump")) cfg.failsafePump = server.arg("failsafePump").toInt() ? 1 : 0;
  if (server.hasArg("modbusTcpEnabled")) {
    bool old = cfg.modbusTcpEnabled;
    cfg.modbusTcpEnabled = server.arg("modbusTcpEnabled").toInt() != 0;
    if (old != cfg.modbusTcpEnabled) tcpNeedsRestart = true;
  }
  if (server.hasArg("modbusTcpPort")) {
    uint16_t old = cfg.modbusTcpPort;
    cfg.modbusTcpPort = argU16("modbusTcpPort", cfg.modbusTcpPort, 1, 65535);
    if (old != cfg.modbusTcpPort) tcpNeedsRestart = true;
  }

  holding[4] = cfg.watchdogTimeoutS;
  holding[5] = cfg.mixerRuntimeS;
  holding[6] = cfg.endstopOverrunS;
  holding[7] = cfg.rtdType;
  holding[8] = cfg.failsafePump;
  saveConfig();
  if (wifiNeedsRestart || rs485NeedsRestart || tcpNeedsRestart) {
    rebootAtMs = millis() + 1200;
    server.send(200, "text/plain; charset=utf-8", "Gespeichert. Neustart wird ausgefuehrt...");
    return;
  }
  server.send(200, "text/plain; charset=utf-8", "Gespeichert.");
}

static void handleStateGet() {
  if (!requireAuth()) return;
  sendNoCache();
  server.send(200, "application/json", stateJson());
}

static void handleWifiScanGet() {
  if (!requireAuth()) return;
  sendNoCache();
  server.send(200, "application/json", wifiScanJson());
}

static void handleControlPost() {
  if (!requireAuth()) return;
  if (server.hasArg("pump")) {
    st.pumpRequested = server.arg("pump").toInt() != 0;
    holding[1] = st.pumpRequested ? 1 : 0;
  }
  if (server.hasArg("target")) {
    st.commandSeq++;
    holding[0] = st.commandSeq;
    holding[2] = clampValue<int>(roundf(server.arg("target").toFloat() * 10.0f), 0, 1000);
    holding[3] = MODE_HAND;
    applyCommandRegisters();
  }
  server.send(200, "text/plain; charset=utf-8", "Testwerte gesetzt.");
}

static void handleRebootPost() {
  if (!requireAuth()) return;
  server.send(200, "text/plain; charset=utf-8", "Neustart...");
  rebootAtMs = millis() + 500;
}

static void handleUpdatePage() {
  if (!requireAuth()) return;
  server.send(200, "text/html; charset=utf-8", R"HTML(
<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Update</title>
<style>body{font-family:system-ui;margin:30px;max-width:650px}input,button{padding:10px;margin:8px 0}button{background:#136f63;color:white;border:0;border-radius:6px}</style></head>
<body><h1>Firmware-Update</h1><form method="POST" action="/update" enctype="multipart/form-data"><input type="file" name="update" accept=".bin"><br><button>Upload starten</button></form><p><a href="/">zurueck</a></p></body></html>
)HTML");
}

static void handleUpdateUpload() {
  HTTPUpload &upload = server.upload();
  if (upload.status == UPLOAD_FILE_START) {
    allOutputsOff();
    Update.begin(UPDATE_SIZE_UNKNOWN);
  } else if (upload.status == UPLOAD_FILE_WRITE) {
    Update.write(upload.buf, upload.currentSize);
  } else if (upload.status == UPLOAD_FILE_END) {
    Update.end(true);
  }
}

static void handleUpdateDone() {
  if (!requireAuth()) return;
  bool ok = !Update.hasError();
  server.send(ok ? 200 : 500, "text/plain; charset=utf-8", ok ? "Update OK, Neustart..." : "Update fehlgeschlagen");
  if (ok) {
    delay(500);
    ESP.restart();
  }
}

static void setupWeb() {
  server.on("/", HTTP_GET, handleRoot);
  server.on("/generate_204", HTTP_GET, []() { redirectToCaptivePortal(); });
  server.on("/gen_204", HTTP_GET, []() { redirectToCaptivePortal(); });
  server.on("/hotspot-detect.html", HTTP_GET, []() { redirectToCaptivePortal(); });
  server.on("/connecttest.txt", HTTP_GET, []() { redirectToCaptivePortal(); });
  server.on("/ncsi.txt", HTTP_GET, []() { redirectToCaptivePortal(); });
  server.on("/fwlink", HTTP_GET, []() { redirectToCaptivePortal(); });
  server.on("/api/config", HTTP_GET, handleConfigGet);
  server.on("/api/config", HTTP_POST, handleConfigPost);
  server.on("/api/state", HTTP_GET, handleStateGet);
  server.on("/api/wifi-scan", HTTP_GET, handleWifiScanGet);
  server.on("/api/control", HTTP_POST, handleControlPost);
  server.on("/api/reboot", HTTP_POST, handleRebootPost);
  server.on("/update", HTTP_GET, handleUpdatePage);
  server.on("/update", HTTP_POST, handleUpdateDone, handleUpdateUpload);
  server.onNotFound([]() {
    if (st.wifiApMode) {
      redirectToCaptivePortal();
      return;
    }
    server.send(404, "text/plain; charset=utf-8", "Not found");
  });
  server.begin();
}

static void setupWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.setHostname(cfg.hostname);
  if (strlen(cfg.wifiSsid) > 0) {
    WiFi.begin(cfg.wifiSsid, cfg.wifiPass);
    uint32_t start = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - start < WIFI_CONNECT_TIMEOUT_MS) {
      delay(200);
    }
  }
  if (WiFi.status() != WL_CONNECTED) {
    st.wifiApMode = true;
    WiFi.mode(WIFI_AP_STA);
    String ssid = "Pumpengruppe-" + chipSuffix();
    WiFi.softAP(ssid.c_str());
    dnsServer.start(DNS_PORT, "*", WiFi.softAPIP());
    WiFi.scanNetworks(true, true);
    Serial.printf("Offener Einrichtungs-AP aktiv: %s, IP %s\n", ssid.c_str(), WiFi.softAPIP().toString().c_str());
  } else {
    st.wifiApMode = false;
    Serial.printf("WLAN verbunden: %s, IP %s\n", cfg.wifiSsid, WiFi.localIP().toString().c_str());
  }
  if (MDNS.begin(cfg.hostname)) {
    MDNS.addService("http", "tcp", 80);
  }
}

static void setupOta() {
  ArduinoOTA.setHostname(cfg.hostname);
  ArduinoOTA.setPassword(cfg.adminPass);
  ArduinoOTA.onStart([]() { allOutputsOff(); });
  ArduinoOTA.begin();
}

static void setupPins() {
  pinMode(cfg.pinPump, OUTPUT);
  pinMode(cfg.pinMixEnable, OUTPUT);
  pinMode(cfg.pinMixDir, OUTPUT);
  pinMode(cfg.pinDe, OUTPUT);
  digitalWrite(cfg.pinDe, LOW);
  allOutputsOff();
}

static void setupRs485() {
  rs485.end();
  rs485.begin(cfg.baud, serialConfig(), cfg.pinRx, cfg.pinTx);
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.printf("\n%s %s startet\n", FW_NAME, FW_VERSION);
  loadConfig();
  setupPins();
  configurePixels();
  initHoldingFromConfig();
  setupWifi();
  setupOta();
  setupWeb();
  setupRs485();
  setupModbusTcp();
  Serial.println("Weboberflaeche bereit.");
}

void loop() {
  server.handleClient();
  if (st.wifiApMode) dnsServer.processNextRequest();
  ArduinoOTA.handle();
  pollModbus();
  pollModbusTcp();
  updateTemperatures();
  applyCommandRegisters();
  updateMotion();
  updateWatchdog();
  updateInputRegisters();
  updatePixels();
  maybeSavePosition();
  if (rebootAtMs && millis() > rebootAtMs) {
    allOutputsOff();
    delay(50);
    ESP.restart();
  }
}
