#include <Arduino.h>
#include <Ethernet.h>

static constexpr uint16_t MODBUS_PORT = 502;
static constexpr uint16_t FIRMWARE_VERSION = 2;
static constexpr unsigned long COMMAND_TIMEOUT_MS = 120000;

// KMP ProDino MKR Zero Ethernet V1 pinout.
// We use the pins directly because the upstream PlatformIO package currently
// pulls unrelated legacy KMP libraries into the build.
static constexpr uint8_t RELAY_PINS[4] = {21, 20, 19, 18};
static constexpr uint8_t OPTO_INPUT_PINS[4] = {16, 7, 0, 1};
static constexpr uint8_t STATUS_LED_PIN = 6;
static constexpr uint8_t W5500_RESET_PIN = 5;
static constexpr uint8_t W5500_CS_PIN = 4;

// Aktuelle UniFi/DHCP-MAC des WIZnet-Moduls beibehalten.
static byte mac[] = {0x00, 0x08, 0xDC, 0x53, 0x09, 0x73};
static EthernetServer server(MODBUS_PORT);

static bool relayState[4] = {false, false, false, false};
static unsigned long lastCommandMs = 0;
static unsigned long lastStatusMs = 0;

static void setRelay(uint8_t index, bool enabled) {
  if (index >= 4 || relayState[index] == enabled) {
    return;
  }
  relayState[index] = enabled;
  digitalWrite(RELAY_PINS[index], enabled ? HIGH : LOW);
  Serial.print(F("Relay "));
  Serial.print(index + 1);
  Serial.print(F(" = "));
  Serial.println(enabled ? F("ON") : F("OFF"));
}

static void allRelaysOff() {
  for (uint8_t i = 0; i < 4; i++) {
    setRelay(i, false);
  }
}

static uint16_t relayMask() {
  uint16_t mask = 0;
  for (uint8_t i = 0; i < 4; i++) {
    if (relayState[i]) {
      mask |= (1U << i);
    }
  }
  return mask;
}

static uint16_t inputMask() {
  uint16_t mask = 0;
  for (uint8_t i = 0; i < 4; i++) {
    if (digitalRead(OPTO_INPUT_PINS[i]) == HIGH) {
      mask |= (1U << i);
    }
  }
  return mask;
}

static void put16(uint8_t *buffer, size_t offset, uint16_t value) {
  buffer[offset] = static_cast<uint8_t>(value >> 8);
  buffer[offset + 1] = static_cast<uint8_t>(value & 0xFF);
}

static uint16_t get16(const uint8_t *buffer, size_t offset) {
  return (static_cast<uint16_t>(buffer[offset]) << 8) | buffer[offset + 1];
}

static void sendMbap(EthernetClient &client, const uint8_t *request, uint16_t pduLength) {
  uint8_t header[7];
  header[0] = request[0];
  header[1] = request[1];
  header[2] = 0;
  header[3] = 0;
  put16(header, 4, pduLength + 1);
  header[6] = request[6];
  client.write(header, sizeof(header));
}

static void sendException(EthernetClient &client, const uint8_t *request, uint8_t function, uint8_t code) {
  uint8_t pdu[2] = {static_cast<uint8_t>(function | 0x80), code};
  sendMbap(client, request, sizeof(pdu));
  client.write(pdu, sizeof(pdu));
}

static bool addressInRange(uint16_t address, uint16_t count) {
  return count >= 1 && address < 4 && (address + count) <= 4;
}

static void sendBits(EthernetClient &client, const uint8_t *request, uint8_t function, uint16_t mask, uint16_t address, uint16_t count) {
  if (!addressInRange(address, count)) {
    sendException(client, request, function, 2);
    return;
  }
  uint8_t byteCount = static_cast<uint8_t>((count + 7) / 8);
  uint8_t pdu[4] = {function, byteCount, 0, 0};
  for (uint16_t i = 0; i < count; i++) {
    if (mask & (1U << (address + i))) {
      pdu[2 + (i / 8)] |= (1U << (i % 8));
    }
  }
  sendMbap(client, request, 2 + byteCount);
  client.write(pdu, 2 + byteCount);
}

static void sendHoldingRegisters(EthernetClient &client, const uint8_t *request, uint8_t function, uint16_t address, uint16_t count) {
  if (count < 1 || address + count > 5) {
    sendException(client, request, function, 2);
    return;
  }
  uint16_t regs[5];
  uint32_t uptime = millis() / 1000UL;
  regs[0] = static_cast<uint16_t>(uptime & 0xFFFF);
  regs[1] = static_cast<uint16_t>((uptime >> 16) & 0xFFFF);
  regs[2] = relayMask();
  regs[3] = inputMask();
  regs[4] = FIRMWARE_VERSION;

  uint8_t byteCount = static_cast<uint8_t>(count * 2);
  uint8_t pdu[2 + 10] = {function, byteCount};
  for (uint16_t i = 0; i < count; i++) {
    put16(pdu, 2 + i * 2, regs[address + i]);
  }
  sendMbap(client, request, 2 + byteCount);
  client.write(pdu, 2 + byteCount);
}

static void handleModbusPdu(EthernetClient &client, const uint8_t *request, const uint8_t *pdu, uint16_t pduLength) {
  if (pduLength < 1) {
    return;
  }
  uint8_t function = pdu[0];
  switch (function) {
    case 1:
      if (pduLength < 5) {
        sendException(client, request, function, 3);
        return;
      }
      sendBits(client, request, function, relayMask(), get16(pdu, 1), get16(pdu, 3));
      return;

    case 2:
      if (pduLength < 5) {
        sendException(client, request, function, 3);
        return;
      }
      sendBits(client, request, function, inputMask(), get16(pdu, 1), get16(pdu, 3));
      return;

    case 3:
    case 4:
      if (pduLength < 5) {
        sendException(client, request, function, 3);
        return;
      }
      sendHoldingRegisters(client, request, function, get16(pdu, 1), get16(pdu, 3));
      return;

    case 5: {
      if (pduLength < 5) {
        sendException(client, request, function, 3);
        return;
      }
      uint16_t address = get16(pdu, 1);
      uint16_t value = get16(pdu, 3);
      if (address >= 4 || (value != 0xFF00 && value != 0x0000)) {
        sendException(client, request, function, 2);
        return;
      }
      setRelay(static_cast<uint8_t>(address), value == 0xFF00);
      lastCommandMs = millis();
      sendMbap(client, request, 5);
      client.write(pdu, 5);
      return;
    }

    case 15: {
      if (pduLength < 6) {
        sendException(client, request, function, 3);
        return;
      }
      uint16_t address = get16(pdu, 1);
      uint16_t count = get16(pdu, 3);
      uint8_t byteCount = pdu[5];
      if (!addressInRange(address, count) || pduLength < static_cast<uint16_t>(6 + byteCount)) {
        sendException(client, request, function, 2);
        return;
      }
      for (uint16_t i = 0; i < count; i++) {
        bool enabled = bool(pdu[6 + (i / 8)] & (1U << (i % 8)));
        setRelay(static_cast<uint8_t>(address + i), enabled);
      }
      lastCommandMs = millis();
      uint8_t response[5] = {function, pdu[1], pdu[2], pdu[3], pdu[4]};
      sendMbap(client, request, sizeof(response));
      client.write(response, sizeof(response));
      return;
    }

    default:
      sendException(client, request, function, 1);
      return;
  }
}

static void handleClient(EthernetClient &client) {
  if (!client.connected() || client.available() < 7) {
    return;
  }
  uint8_t header[7];
  if (client.read(header, sizeof(header)) != sizeof(header)) {
    return;
  }
  uint16_t protocol = get16(header, 2);
  uint16_t length = get16(header, 4);
  if (protocol != 0 || length < 2 || length > 260) {
    client.stop();
    return;
  }
  uint16_t pduLength = length - 1;
  uint8_t pdu[260];
  unsigned long deadline = millis() + 200;
  uint16_t pos = 0;
  while (pos < pduLength && millis() < deadline) {
    if (client.available()) {
      pdu[pos++] = client.read();
    }
  }
  if (pos != pduLength) {
    client.stop();
    return;
  }
  handleModbusPdu(client, header, pdu, pduLength);
}

static void startEthernet() {
  pinMode(W5500_RESET_PIN, OUTPUT);
  digitalWrite(W5500_RESET_PIN, LOW);
  delay(50);
  digitalWrite(W5500_RESET_PIN, HIGH);
  delay(250);
  Ethernet.init(W5500_CS_PIN);

  Serial.println(F("Ethernet DHCP start"));
  if (Ethernet.begin(mac) == 0) {
    Serial.println(F("DHCP failed, fallback 10.1.1.146"));
    IPAddress ip(10, 1, 1, 146);
    IPAddress dns(10, 1, 1, 1);
    IPAddress gateway(10, 1, 1, 1);
    IPAddress subnet(255, 255, 255, 0);
    Ethernet.begin(mac, ip, dns, gateway, subnet);
  }
  delay(1000);
  Serial.print(F("IP: "));
  Serial.println(Ethernet.localIP());
  server.begin();
  Serial.print(F("Modbus TCP listening on port "));
  Serial.println(MODBUS_PORT);
}

void setup() {
  Serial.begin(115200);
  delay(1500);
  Serial.println(F("Prodino Pool Modbus Controller boot"));
  for (uint8_t i = 0; i < 4; i++) {
    pinMode(RELAY_PINS[i], OUTPUT);
    digitalWrite(RELAY_PINS[i], LOW);
    pinMode(OPTO_INPUT_PINS[i], INPUT);
  }
  pinMode(STATUS_LED_PIN, OUTPUT);
  digitalWrite(STATUS_LED_PIN, HIGH);

  allRelaysOff();
  startEthernet();
  lastCommandMs = millis();
}

void loop() {
  EthernetClient client = server.available();
  if (client) {
    digitalWrite(STATUS_LED_PIN, HIGH);
    handleClient(client);
  }

  if (millis() - lastCommandMs > COMMAND_TIMEOUT_MS) {
    allRelaysOff();
  }

  if (millis() - lastStatusMs > 5000) {
    lastStatusMs = millis();
    digitalWrite(STATUS_LED_PIN, !digitalRead(STATUS_LED_PIN));
    Serial.print(F("IP "));
    Serial.print(Ethernet.localIP());
    Serial.print(F(" relays=0x"));
    Serial.print(relayMask(), HEX);
    Serial.print(F(" inputs=0x"));
    Serial.println(inputMask(), HEX);
  }

  Ethernet.maintain();
}
