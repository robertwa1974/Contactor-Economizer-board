// Contactor economizer - two channels, STM32G031K8 (STM32duino / PlatformIO)
// v3: rev B board (IMD interface). v2: general-purpose. Pick-up AND hold are current-regulated, so the peak coil
// current is the pick-up setting, not battery voltage / coil resistance.
// Per-channel profiles live in flash and are set over the USB serial port.
//
// Safety model (see design doc):
//  - The VCU command turns the high-side switch on/off in HARDWARE. Firmware can
//    never turn a high-side switch on; it can only force it off (KILL pin).
//  - If this MCU is dead or in reset, PWM pins are low, so no coil current can flow
//    and the contactors stay open.
//  - Release speed is set by hardware (TVS across the high-side switch), not firmware.
//  - Optional IMD (rev B): with "imd required", a close is refused unless IMD_OK has
//    been high for 2 s. Losing IMD_OK while closed is only a warning: the IMD never
//    forces an open; the VCU decides.
//  - Settings can only be changed or saved while both channels are OFF.
//  - Factory default is "unconfigured": a channel will not energize until a
//    profile is chosen and saved.

#include <Arduino.h>
#include <stddef.h>
#include <string.h>
#include <IWatchdog.h>
#include <EEPROM.h>   // pulls in the buffered flash-EEPROM helpers

// ---------------- Hardware limits (set by the PCB parts) ----------------
static const float HW_MAX_PICKUP_A = 5.0f;   // largest pick-up a profile may request
static const float HW_MAX_OC_A     = 6.5f;   // overcurrent trip ceiling
static const uint16_t HW_MAX_PICKUP_MS = 1000;

// ---------------- Control constants ----------------
static const float    KP              = 0.20f;  // duty per amp of error
static const float    KI              = 2.0f;   // duty per amp-second
static const float    INTEG_LIMIT     = 0.30f;  // integrator clamp (duty)
static const float    DUTY_MAX_REG    = 0.95f;  // cap while regulating
static const uint32_t OVERCURRENT_MS  = 2;      // trip must persist this long
static const float    PICKUP_OK_FRAC  = 0.60f;  // end of pick-up: I must be > frac*pickup
static const float    HOLD_LOW_FRAC   = 0.60f;  // hold: fault if I < frac*hold at max duty...
static const uint32_t HOLD_LOW_MS     = 200;    // ...for this long
static const float    HOLD_HIGH_MULT  = 2.5f;   // hold: fault if I > mult*hold...
static const uint32_t HOLD_HIGH_MS    = 500;    // ...for this long (Q1 stuck on?)
static const float    PASS_MIN_A      = 0.05f;  // pass-through: below this = open coil
static const uint32_t CMD_ON_DEBOUNCE_MS = 5;
// TPS1H100 ST: with DIAG_EN high it reports open load (<2-10 mA for 700 us).
// The VCU switches the high side on before our debounce ends and Q1 starts,
// so ST is legitimately low at the start of PICKUP. Ignore it for this long
// after entering an energised state, then require it to persist.
static const uint32_t HS_ST_BLANK_MS  = 20;
static const uint32_t HS_ST_PERSIST_MS = 10;
static const float    VBAT_MIN_FF     = 8.0f;
// IMD (insulation monitor) interface, rev B. IMD_OK must be high this long before
// it counts as OK, so a close during IMD start-up is refused rather than raced.
static const uint32_t IMD_QUALIFY_MS  = 2000;
static const uint32_t IMD_LOST_MS     = 20;     // IMD_OK low this long while closed = warning
// CONTx_CLOSED: coil energised in HOLD/PASS at >= this fraction of hold current.
static const float    CLOSED_FRAC     = 0.60f;
static const uint32_t CLOSED_DEBOUNCE_MS = 20;

// ---------------- Hardware scaling ----------------
static const float ADC_VREF   = 3.3f;
static const float ADC_COUNTS = 4095.0f;
// 30 mOhm shunt x INA240A1 gain 20 = 0.6 V/A, then 10k/20k divider = 0.4 V/A
static const float ISENSE_V_PER_A = 0.03f * 20.0f * (20.0f / 30.0f);
// 100k / 15k: full scale 25.3 V (covers jump-start; BAT54S clamps load dump).
static const float VBAT_V_PER_V   = 15.0f / 115.0f;

// ---------------- Pins ----------------
static const uint32_t PIN_VBAT = PA4;
static const uint32_t PWM_HZ   = 20000;
// IMD stacking socket (J4). PB6/PB7 are reserved for USART1 to the IMD (no code yet;
// left in their reset state).
static const uint32_t PIN_IMD_OK      = PA15;  // input, 100k pull-down: high = insulation OK
static const uint32_t PIN_IMD_INHIBIT = PB3;   // output, high = ask the IMD to pause measuring

struct ChannelPins {
  uint32_t isense, pwm, timCh, cmd, kill, hsStatus, status, closed;
};
static const ChannelPins PINS[2] = {
  // HS_ST on PB8/PB9 since rev B (polled; was PB6/PB7).
  { PA0, PA6, 1, PB0, PB4, PB8, PA11, PA8 },
  // PA7's first PinMap_TIM entry is TIM1_CH1N; PA7_ALT1 selects TIM3_CH2 (AF1).
  { PA1, PA7_ALT1, 2, PB1, PB5, PB9, PA12, PC6 },
};

// ---------------- Profiles ----------------
enum Mode : uint8_t { MODE_DISABLED = 0, MODE_ECON = 1, MODE_PASS = 2 };

struct Profile {
  char     name[16];
  uint8_t  mode;
  float    pickupA;    // regulated pick-up current
  uint16_t pickupMs;   // pick-up duration
  float    holdA;      // regulated hold current
  float    coilOhms;   // nominal coil resistance (feed-forward only)
  float    ocA;        // overcurrent trip; 0 = automatic
};

// Built-in presets. Add new contactors here as they are measured.
static const Profile PRESETS[] = {
  // name           mode           pickA  ms   holdA  ohms  oc
  { "unconfigured", MODE_DISABLED, 0.0f,  0,   0.0f,  0.0f, 0.0f },
  // Gigavac GV200-005 from Mercedes B250e pack. Bench 2026-11-24:
  // 4.8 ohm cold, pick-up 0.8 A (re-checked 2026-11-25), drop-out 0.13 A.
  { "gv200-005",    MODE_ECON,     2.5f,  200, 0.30f, 5.0f, 0.0f },
  // LS Electric GER150 from Chevy Bolt. Datasheet: 23.5 ohm, 6.5 W at 12 V
  // (rated for continuous 12 V, economizing optional), pick-up max 9 V.
  // Bench 2026-11-25: 23 ohm, pick-up 0.30 A, drop-out 0.10 A.
  // Pick-up setting is capped by 12 V / 23.5 ohm.
  { "ger150",       MODE_ECON,     0.45f, 100, 0.25f, 23.5f, 0.0f },
  // Panasonic AEV14012 (BMW 330e S-box). Datasheet: 34 ohm, 4.2 W at 12 V,
  // pick-up max 9 V. Bench 2026-11-25: 25.9 ohm (BMW variant, not the 34 ohm
  // catalog coil: ~5.6 W at 12 V, so economizing is worthwhile), firm pick-up
  // 0.30 A (partial soft click at 0.20 A), drop-out 0.065 A.
  { "aev14012",     MODE_ECON,     0.44f, 100, 0.16f, 25.9f, 0.0f },
  // Contactors with their own internal economizer: just apply 12 V.
  { "passthrough",  MODE_PASS,     0.0f,  0,   0.0f,  0.0f, 4.0f },
};
static const uint8_t N_PRESETS = sizeof(PRESETS) / sizeof(PRESETS[0]);

struct Settings {
  uint32_t magic;
  uint16_t version;
  Profile  ch[2];
  uint8_t  imdRequired;   // 1 = refuse to close unless IMD_OK has been high for 2 s
  uint8_t  reserved[3];
  uint32_t crc;
};
static const uint32_t SETTINGS_MAGIC   = 0x45434F4E;  // "ECON"
static const uint16_t SETTINGS_VERSION = 3;          // v3: imdRequired added
static Settings cfg;

// ---------------- Runtime state ----------------
enum State : uint8_t { ST_OFF, ST_PICKUP, ST_HOLD, ST_PASS, ST_FAULT };
enum Fault : uint8_t {
  F_NONE = 0, F_PICKUP_LOW = 1, F_OVERCURRENT = 2, F_HOLD_LOW = 4,
  F_HOLD_HIGH = 8, F_HS_SWITCH = 16, F_NOT_CONFIGURED = 32,
  F_IMD_INHIBIT = 64    // close refused: IMD required and IMD_OK not qualified
};

struct Channel {
  State    state = ST_OFF;
  uint8_t  faults = F_NONE;
  uint32_t tState = 0, tCmdOn = 0;
  bool     cmdSeen = false;
  float    integ = 0.0f, duty = 0.0f, amps = 0.0f;
  uint32_t tOverStart = 0, tLowStart = 0, tHighStart = 0, tStStart = 0, tEnergised = 0;
  bool     overActive = false, lowActive = false, highActive = false, stActive = false;
  // Warning (not a fault): IMD_OK dropped while this channel was energised. Cleared at OFF.
  bool     imdWarn = false, imdLostActive = false;
  uint32_t tImdLostStart = 0;
  // Debounced CONTx_CLOSED output.
  bool     closed = false;
  uint32_t tClosedChange = 0;
};

static Channel ch[2];
static HardwareTimer *pwmTim = nullptr;
static uint32_t pwmTicks = 0;
static float vbat = 12.0f;
static bool logOn = true;
static bool imdOkRaw = false;          // IMD_OK pin level this cycle
static bool imdOkQualified = false;    // high continuously for IMD_QUALIFY_MS
static uint32_t tImdHigh = 0;

// ---------------- Settings storage ----------------
static uint32_t crc32(const uint8_t *p, size_t n) {
  uint32_t c = 0xFFFFFFFFu;
  while (n--) {
    c ^= *p++;
    for (uint8_t k = 0; k < 8; k++) c = (c >> 1) ^ (0xEDB88320u & (0u - (c & 1u)));
  }
  return ~c;
}

static uint32_t settingsCrc(const Settings &s) {
  return crc32((const uint8_t *)&s, offsetof(Settings, crc));
}

static void loadDefaults() {
  memset(&cfg, 0, sizeof(cfg));
  cfg.magic = SETTINGS_MAGIC;
  cfg.version = SETTINGS_VERSION;
  cfg.ch[0] = PRESETS[0];
  cfg.ch[1] = PRESETS[0];
  cfg.imdRequired = 0;     // stand-alone builds (no IMD) must not be blocked by the pull-down
  cfg.crc = settingsCrc(cfg);
}

static void loadSettings() {
  eeprom_buffer_fill();
  uint8_t *p = (uint8_t *)&cfg;
  for (size_t i = 0; i < sizeof(cfg); i++) p[i] = eeprom_buffered_read_byte(i);
  if (cfg.magic != SETTINGS_MAGIC || cfg.version != SETTINGS_VERSION ||
      cfg.crc != settingsCrc(cfg)) {
    loadDefaults();
    Serial.println(F("No valid settings in flash: both channels unconfigured."));
  }
}

static void saveSettings() {
  cfg.crc = settingsCrc(cfg);
  const uint8_t *p = (const uint8_t *)&cfg;
  for (size_t i = 0; i < sizeof(cfg); i++) eeprom_buffered_write_byte(i, p[i]);
  IWatchdog.reload();
  eeprom_buffer_flush();   // page erase + write, tens of ms
  IWatchdog.reload();
}

static float ocLimit(const Profile &pr) {
  float oc = pr.ocA;
  if (oc <= 0.0f) {
    oc = pr.pickupA * 1.5f;
    if (oc < pr.holdA * 3.0f) oc = pr.holdA * 3.0f;
    oc += 0.5f;
  }
  return (oc > HW_MAX_OC_A) ? HW_MAX_OC_A : oc;
}

// Returns nullptr if the profile is usable, else a reason.
static const char *validate(const Profile &pr) {
  if (pr.mode == MODE_DISABLED) return nullptr;
  if (pr.ocA < 0.0f || pr.ocA > HW_MAX_OC_A) return "oc out of range (0 = auto, max 6.5)";
  if (pr.mode == MODE_PASS) return nullptr;
  if (pr.mode != MODE_ECON) return "unknown mode";
  if (pr.pickupA <= 0.0f || pr.pickupA > HW_MAX_PICKUP_A) return "pickup out of range (0-5 A)";
  if (pr.pickupMs < 20 || pr.pickupMs > HW_MAX_PICKUP_MS) return "pickup_ms out of range (20-1000)";
  if (pr.holdA <= 0.0f || pr.holdA >= pr.pickupA) return "hold must be >0 and < pickup";
  if (pr.coilOhms < 0.5f || pr.coilOhms > 100.0f) return "ohms out of range (0.5-100)";
  return nullptr;
}

// ---------------- Helpers ----------------
static float readVolts(uint32_t pin, uint8_t samples = 4) {
  uint32_t sum = 0;
  for (uint8_t i = 0; i < samples; i++) sum += analogRead(pin);
  return (sum / (float)samples) * ADC_VREF / ADC_COUNTS;
}

static void setDuty(uint8_t n, float d) {
  if (d < 0.0f) d = 0.0f;
  if (d > 1.0f) d = 1.0f;
  ch[n].duty = d;
  // CCR >= period holds the output high (100%); CCR = 0 holds it low.
  uint32_t ccr = (d >= 1.0f) ? pwmTicks : (uint32_t)(d * pwmTicks);
  pwmTim->setCaptureCompare(PINS[n].timCh, ccr, TICK_COMPARE_FORMAT);
}

static void enterState(uint8_t n, State s, uint32_t now) {
  Channel &c = ch[n];
  c.state = s;
  c.tState = now;
  c.overActive = c.lowActive = c.highActive = false;
  c.integ = 0.0f;
  switch (s) {
    case ST_OFF:
      setDuty(n, 0.0f);
      digitalWrite(PINS[n].kill, LOW);
      c.faults = F_NONE;            // command removed: clear latched faults
      c.imdWarn = false;
      c.imdLostActive = false;
      break;
    case ST_PICKUP:
    case ST_PASS:
      digitalWrite(PINS[n].kill, LOW);
      c.tEnergised = now;           // start of HS_ST blanking (HOLD keeps it)
      c.stActive = false;
      break;
    case ST_HOLD:
      break;
    case ST_FAULT:
      setDuty(n, 0.0f);
      break;
  }
}

static bool persisted(bool cond, bool &active, uint32_t &tStart, uint32_t now, uint32_t holdMs) {
  if (!cond) { active = false; return false; }
  if (!active) { active = true; tStart = now; }
  return (now - tStart) >= holdMs;
}

// One PI step toward target amps. Feed-forward from coil resistance and battery.
static float regulate(uint8_t n, float target, float ohms, float dt, float dutyMax = DUTY_MAX_REG) {
  Channel &c = ch[n];
  float v = (vbat < VBAT_MIN_FF) ? VBAT_MIN_FF : vbat;
  float ff = target * ohms / v;
  float err = target - c.amps;
  c.integ += KI * err * dt;
  if (c.integ >  INTEG_LIMIT) c.integ =  INTEG_LIMIT;
  if (c.integ < -INTEG_LIMIT) c.integ = -INTEG_LIMIT;
  float d = ff + KP * err + c.integ;
  if (d > dutyMax) d = dutyMax;
  if (d < 0.0f) d = 0.0f;
  setDuty(n, d);
  return d;
}

// CONTx_CLOSED to the IMD: coil energised (HOLD or PASS) at >= 60 % of hold current
// (pass-through: above the open-coil threshold), debounced both ways. This is
// "coil energised", not proof that the main contacts have closed.
static void updateClosed(uint8_t n, uint32_t now) {
  Channel &c = ch[n];
  const Profile &pr = cfg.ch[n];
  bool want = false;
  if (c.state == ST_HOLD) want = c.amps >= CLOSED_FRAC * pr.holdA;
  else if (c.state == ST_PASS) want = c.amps >= PASS_MIN_A;
  if (want == c.closed) { c.tClosedChange = now; }
  else if (now - c.tClosedChange >= CLOSED_DEBOUNCE_MS) { c.closed = want; c.tClosedChange = now; }
  digitalWrite(PINS[n].closed, c.closed ? HIGH : LOW);
}

static void runChannel(uint8_t n, uint32_t now, float dt) {
  Channel &c = ch[n];
  const ChannelPins &p = PINS[n];
  const Profile &pr = cfg.ch[n];

  c.amps = readVolts(p.isense) / ISENSE_V_PER_A;
  bool cmdActive = (digitalRead(p.cmd) == LOW);

  if (!cmdActive) {
    c.cmdSeen = false;
    if (c.state != ST_OFF) enterState(n, ST_OFF, now);
    digitalWrite(p.status, LOW);
    updateClosed(n, now);
    return;
  }

  if (!c.cmdSeen) { c.cmdSeen = true; c.tCmdOn = now; }
  bool cmdStable = (now - c.tCmdOn) >= CMD_ON_DEBOUNCE_MS;

  if (c.state == ST_PICKUP || c.state == ST_HOLD || c.state == ST_PASS) {
    bool stLow = (now - c.tEnergised >= HS_ST_BLANK_MS) && (digitalRead(p.hsStatus) == LOW);
    if (persisted(stLow, c.stActive, c.tStStart, now, HS_ST_PERSIST_MS)) c.faults |= F_HS_SWITCH;
  }

  // Hard overcurrent trip in any energised state.
  if (c.state == ST_PICKUP || c.state == ST_HOLD || c.state == ST_PASS) {
    if (persisted(c.amps > ocLimit(pr), c.overActive, c.tOverStart, now, OVERCURRENT_MS)) {
      c.faults |= F_OVERCURRENT;
      digitalWrite(p.kill, HIGH);
      enterState(n, ST_FAULT, now);
    }
  }

  switch (c.state) {
    case ST_OFF:
      if (!cmdStable) break;
      if (cfg.imdRequired && !imdOkQualified) {
        // IMD blocks a CLOSE (never forces an open). Keep both switches off and
        // latch until the VCU drops the command: no late, unsequenced close.
        c.faults |= F_IMD_INHIBIT;
        digitalWrite(p.kill, HIGH);
        enterState(n, ST_FAULT, now);
      }
      else if (pr.mode == MODE_ECON && validate(pr) == nullptr) enterState(n, ST_PICKUP, now);
      else if (pr.mode == MODE_PASS)                            enterState(n, ST_PASS, now);
      else { c.faults |= F_NOT_CONFIGURED; enterState(n, ST_FAULT, now); }
      break;

    case ST_PICKUP:
      // Pick-up may use 100% duty: high-resistance coils (~25 ohm) can only
      // reach about 1.5x their firm pick-up current from 12 V.
      regulate(n, pr.pickupA, pr.coilOhms, dt, 1.0f);
      if (now - c.tState >= pr.pickupMs) {
        if (c.amps < PICKUP_OK_FRAC * pr.pickupA) {
          c.faults |= F_PICKUP_LOW;   // open coil, or battery too low to reach pick-up
          enterState(n, ST_FAULT, now);
        } else {
          enterState(n, ST_HOLD, now);
        }
      }
      break;

    case ST_HOLD: {
      float d = regulate(n, pr.holdA, pr.coilOhms, dt);
      bool low = (d >= DUTY_MAX_REG) && (c.amps < HOLD_LOW_FRAC * pr.holdA);
      if (persisted(low, c.lowActive, c.tLowStart, now, HOLD_LOW_MS)) c.faults |= F_HOLD_LOW;
      // Far above target (e.g. Q1 shorted): report, keep holding; VCU decides.
      bool high = c.amps > HOLD_HIGH_MULT * pr.holdA;
      if (persisted(high, c.highActive, c.tHighStart, now, HOLD_HIGH_MS)) c.faults |= F_HOLD_HIGH;
      break;
    }

    case ST_PASS:
      setDuty(n, 1.0f);
      if (now - c.tState > 200 && c.amps < PASS_MIN_A) c.faults |= F_PICKUP_LOW;
      break;

    case ST_FAULT:
      setDuty(n, 0.0f);   // latched until the VCU removes the command
      break;
  }

  // IMD_OK lost while energised: warn only. The VCU decides when to open.
  if (cfg.imdRequired && (c.state == ST_PICKUP || c.state == ST_HOLD || c.state == ST_PASS)) {
    if (persisted(!imdOkRaw, c.imdLostActive, c.tImdLostStart, now, IMD_LOST_MS)) c.imdWarn = true;
  }

  // STAT/LED: holding with no fault. Warnings (imdWarn) do not affect it; a refused
  // close (F_IMD_INHIBIT) is a FAULT, so STAT stays released and the LED stays off.
  bool ok = (c.state == ST_HOLD || c.state == ST_PASS) && (c.faults == F_NONE);
  digitalWrite(p.status, ok ? HIGH : LOW);
  updateClosed(n, now);
}

// ---------------- Serial command line ----------------
static const char *modeName(uint8_t m) {
  return m == MODE_ECON ? "econ" : m == MODE_PASS ? "pass" : "off";
}

static void printProfile(uint8_t n) {
  const Profile &pr = cfg.ch[n];
  Serial.print(F("ch")); Serial.print(n + 1);
  Serial.print(F(": ")); Serial.print(pr.name);
  Serial.print(F(" mode=")); Serial.print(modeName(pr.mode));
  Serial.print(F(" pickup=")); Serial.print(pr.pickupA, 2);
  Serial.print(F("A pickup_ms=")); Serial.print(pr.pickupMs);
  Serial.print(F(" hold=")); Serial.print(pr.holdA, 3);
  Serial.print(F("A ohms=")); Serial.print(pr.coilOhms, 2);
  Serial.print(F(" oc=")); Serial.print(ocLimit(pr), 2);
  Serial.print(pr.ocA <= 0.0f ? F("A(auto)") : F("A"));
  const char *why = validate(pr);
  if (why) { Serial.print(F("  INVALID: ")); Serial.print(why); }
  Serial.println();
}

static void printHelp() {
  Serial.println(F("Commands (settings change only while both channels are off):"));
  Serial.println(F("  show                       current profiles"));
  Serial.println(F("  presets                    list built-in profiles"));
  Serial.println(F("  preset <1|2> <name>        load a built-in profile"));
  Serial.println(F("  set <1|2> mode <off|econ|pass>"));
  Serial.println(F("  set <1|2> pickup <A>       regulated pick-up current, max 5"));
  Serial.println(F("  set <1|2> pickup_ms <ms>   pick-up time, 20-1000"));
  Serial.println(F("  set <1|2> hold <A>         regulated hold current"));
  Serial.println(F("  set <1|2> ohms <ohm>       coil resistance, measured"));
  Serial.println(F("  set <1|2> oc <A>           overcurrent trip, 0 = auto"));
  Serial.println(F("  save                       write profiles to flash"));
  Serial.println(F("  defaults                   reset both to unconfigured (not saved)"));
  Serial.println(F("  imd <required|optional>    refuse to close unless IMD_OK (default optional)"));
  Serial.println(F("  log <on|off>               500 ms status line"));
}

static void printImd() {
  Serial.print(F("imd: "));
  Serial.print(cfg.imdRequired ? F("required") : F("optional"));
  Serial.print(F(", IMD_OK="));
  Serial.println(imdOkQualified ? F("ok") : imdOkRaw ? F("qualifying") : F("low"));
}

static bool bothOff() { return ch[0].state == ST_OFF && ch[1].state == ST_OFF; }

// Minimal decimal parser ("0.30", "2.5", "-1"). Replaces strtof, which links
// newlib's full strtod (~4.5 KB) and would crowd the EEPROM flash page.
// Returns -1 on malformed input so validate() rejects it.
static float parseNum(const char *s) {
  if (!s || !*s) return -1.0f;
  bool neg = (*s == '-');
  if (neg) s++;
  float v = 0.0f, scale = 1.0f;
  bool dot = false, digits = false;
  for (; *s; s++) {
    if (*s >= '0' && *s <= '9') {
      digits = true;
      if (dot) { scale *= 0.1f; v += (*s - '0') * scale; }
      else     { v = v * 10.0f + (*s - '0'); }
    } else if (*s == '.' && !dot) {
      dot = true;
    } else {
      return -1.0f;
    }
  }
  if (!digits) return -1.0f;
  return neg ? -v : v;
}

static int parseChannel(const char *s) {
  if (!s) return -1;
  int n = atoi(s);
  return (n == 1 || n == 2) ? n - 1 : -1;
}

static void handleLine(char *line) {
  char *cmd = strtok(line, " \t");
  if (!cmd) return;
  char *a1 = strtok(nullptr, " \t");
  char *a2 = strtok(nullptr, " \t");
  char *a3 = strtok(nullptr, " \t");

  if (!strcmp(cmd, "help") || !strcmp(cmd, "?")) { printHelp(); return; }
  if (!strcmp(cmd, "show")) { printProfile(0); printProfile(1); printImd(); return; }
  if (!strcmp(cmd, "presets")) {
    for (uint8_t i = 0; i < N_PRESETS; i++) { Serial.print(F("  ")); Serial.println(PRESETS[i].name); }
    return;
  }
  if (!strcmp(cmd, "log")) { logOn = a1 && !strcmp(a1, "on"); return; }

  // Everything below changes settings.
  if (!bothOff()) { Serial.println(F("Refused: remove both VCU commands first.")); return; }

  if (!strcmp(cmd, "defaults")) { loadDefaults(); Serial.println(F("Defaults loaded (not saved).")); return; }

  if (!strcmp(cmd, "save")) {
    for (uint8_t n = 0; n < 2; n++) {
      const char *why = validate(cfg.ch[n]);
      if (why) { Serial.print(F("Not saved, ch")); Serial.print(n + 1); Serial.print(F(": ")); Serial.println(why); return; }
    }
    saveSettings();
    Serial.println(F("Saved."));
    return;
  }

  if (!strcmp(cmd, "imd")) {
    if (a1 && !strcmp(a1, "required"))      cfg.imdRequired = 1;
    else if (a1 && !strcmp(a1, "optional")) cfg.imdRequired = 0;
    else { Serial.println(F("Usage: imd <required|optional>")); return; }
    printImd();
    return;
  }

  if (!strcmp(cmd, "preset")) {
    int n = parseChannel(a1);
    if (n < 0 || !a2) { Serial.println(F("Usage: preset <1|2> <name>")); return; }
    for (uint8_t i = 0; i < N_PRESETS; i++) {
      if (!strcmp(a2, PRESETS[i].name)) { cfg.ch[n] = PRESETS[i]; printProfile(n); return; }
    }
    Serial.println(F("Unknown preset. Type 'presets'."));
    return;
  }

  if (!strcmp(cmd, "set")) {
    int n = parseChannel(a1);
    if (n < 0 || !a2 || !a3) { Serial.println(F("Usage: set <1|2> <param> <value>")); return; }
    Profile &pr = cfg.ch[n];
    if (!strcmp(a2, "mode")) {
      if (!strcmp(a3, "off")) pr.mode = MODE_DISABLED;
      else if (!strcmp(a3, "econ")) pr.mode = MODE_ECON;
      else if (!strcmp(a3, "pass")) pr.mode = MODE_PASS;
      else { Serial.println(F("mode: off | econ | pass")); return; }
    }
    else if (!strcmp(a2, "pickup"))    pr.pickupA  = parseNum(a3);
    else if (!strcmp(a2, "pickup_ms")) { float v = parseNum(a3); pr.pickupMs = (v < 0.0f || v > 60000.0f) ? 0 : (uint16_t)v; }
    else if (!strcmp(a2, "hold"))      pr.holdA    = parseNum(a3);
    else if (!strcmp(a2, "ohms"))      pr.coilOhms = parseNum(a3);
    else if (!strcmp(a2, "oc"))        pr.ocA      = parseNum(a3);
    else { Serial.println(F("Unknown parameter. Type 'help'.")); return; }
    strncpy(pr.name, "custom", sizeof(pr.name));
    printProfile(n);
    return;
  }

  Serial.println(F("Unknown command. Type 'help'."));
}

static void pollSerial() {
  static char buf[64];
  static uint8_t len = 0;
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\r' || c == '\n') {
      if (len) { buf[len] = 0; handleLine(buf); len = 0; }
    } else if (len < sizeof(buf) - 1) {
      buf[len++] = c;
    }
  }
}

// ---------------- Arduino entry points ----------------
void setup() {
  for (uint8_t n = 0; n < 2; n++) {
    pinMode(PINS[n].cmd, INPUT);
    pinMode(PINS[n].hsStatus, INPUT);
    pinMode(PINS[n].kill, OUTPUT);
    digitalWrite(PINS[n].kill, LOW);
    pinMode(PINS[n].status, OUTPUT);
    digitalWrite(PINS[n].status, LOW);
    pinMode(PINS[n].closed, OUTPUT);
    digitalWrite(PINS[n].closed, LOW);
  }
  pinMode(PIN_IMD_OK, INPUT);          // external 100k pull-down
  pinMode(PIN_IMD_INHIBIT, OUTPUT);
  digitalWrite(PIN_IMD_INHIBIT, LOW);  // reserved: IMD keeps measuring
  analogReadResolution(12);

  pwmTim = new HardwareTimer(TIM3);
  pwmTim->setOverflow(PWM_HZ, HERTZ_FORMAT);
  for (uint8_t n = 0; n < 2; n++) {
    pwmTim->setMode(PINS[n].timCh, TIMER_OUTPUT_COMPARE_PWM1, PINS[n].pwm);
    pwmTim->setCaptureCompare(PINS[n].timCh, 0, TICK_COMPARE_FORMAT);
  }
  pwmTim->resume();
  pwmTicks = pwmTim->getOverflow(TICK_FORMAT);

  Serial.begin(115200);
  Serial.println(F("Contactor economizer v3 (board rev B). Type 'help'."));
  loadSettings();
  printProfile(0);
  printProfile(1);
  printImd();

  IWatchdog.begin(100000);   // 100 ms
}

void loop() {
  static uint32_t lastUs = micros();
  static uint32_t lastLog = 0;

  pollSerial();

  uint32_t nowUs = micros();
  if (nowUs - lastUs < 1000) return;   // 1 kHz control loop
  float dt = (nowUs - lastUs) * 1e-6f;
  lastUs = nowUs;
  uint32_t now = millis();

  vbat = readVolts(PIN_VBAT) / VBAT_V_PER_V;
  bool imdNow = (digitalRead(PIN_IMD_OK) == HIGH);
  if (imdNow && !imdOkRaw) tImdHigh = now;
  imdOkRaw = imdNow;
  imdOkQualified = imdNow && (now - tImdHigh >= IMD_QUALIFY_MS);
  for (uint8_t n = 0; n < 2; n++) runChannel(n, now, dt);
  IWatchdog.reload();

  if (logOn && now - lastLog >= 500) {
    lastLog = now;
    static const char *names[] = { "OFF", "PICKUP", "HOLD", "PASS", "FAULT" };
    Serial.print(F("Vbat=")); Serial.print(vbat, 2);
    for (uint8_t n = 0; n < 2; n++) {
      Serial.print(F(" | ch")); Serial.print(n + 1);
      Serial.print(' '); Serial.print(names[ch[n].state]);
      Serial.print(F(" I=")); Serial.print(ch[n].amps, 3);
      Serial.print(F(" D=")); Serial.print(ch[n].duty * 100.0f, 1);
      Serial.print(F("% F=0x")); Serial.print(ch[n].faults, HEX);
      if (ch[n].closed)  Serial.print(F(" CLOSED"));
      if (ch[n].imdWarn) Serial.print(F(" W=IMD_LOST"));
    }
    Serial.print(F(" | IMD="));
    Serial.print(imdOkQualified ? F("ok") : imdOkRaw ? F("qual") : F("low"));
    Serial.print(cfg.imdRequired ? F(" req") : F(" opt"));
    Serial.println();
  }
}
