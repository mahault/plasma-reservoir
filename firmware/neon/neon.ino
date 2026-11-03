// NE-2 reservoir acquisition for the Teensy 4.1 (i.MX RT1062, 600 MHz). Port of ../ne2_uno with the
// same commands and frames (host: plasma_rc/neon/serial_io.py, protocol.py). Differences:
//  - tick = (ocr1a + 1) CPU cycles, from an IntervalTimer; PONG reports the 600 MHz clock
//  - flash time stamps: ARM cycle counter at a RISING edge on FLASH_PIN from an external 3.3 V
//    comparator (the UNO's on-chip comparator path has no counterpart here); sub = cycles into the tick
//  - 12-bit ADC (PJRC: ~10 bits usable in practice), PWM-DAC at 8 bit / 585937.5 Hz (PJRC table)
// PJRC: pins accept 0-3.3 V and are NOT 5 V tolerant; every clamp on the board goes to 3.3 V.
#include <IntervalTimer.h>

#define FW "ne2-teensy41-1"
const uint8_t DAC_PIN = 2, FLASH_PIN = 3;
const uint8_t APIN[5] = {A0, A1, A2, A3, A4};
const uint32_t MIN_TICK = 6000;   // >= 10 us per tick for one blocking analogRead (E1 finds the real limit)
const uint16_t RING = 4096;
const uint8_t EV = 64;
const uint8_t SAMPLE = 1, EVENT = 2, BATCH = 32;

IntervalTimer tick_timer;
volatile uint16_t ring[RING];
volatile uint16_t head = 0, tail = 0;
volatile uint32_t tick = 0, tick_cyc = 0, first_tick = 0, dropped = 0;
volatile bool have_first = false;
volatile uint32_t ev_tick[EV], ev_sub[EV];
volatile uint8_t ev_head = 0, ev_tail = 0;
volatile uint32_t ev_dropped = 0;

uint8_t order[5], nch = 0;
volatile uint8_t ch_idx = 0;
uint32_t ocr1a = 0;
uint16_t seq = 0;
uint32_t sent = 0;
bool running = false;
int8_t sine[256];

// stimulus: 0 none, 1 steps (xorshift32, Marsaglia 2003), 2 sine (DDS); same sequence as the UNO
volatile uint8_t stim = 0;
volatile uint32_t xs_p, xs_c, n_p, n_c, tps, step_tick, phase, phase_inc;
volatile uint8_t amp;

uint8_t xorshift_level(volatile uint32_t &x) {
  uint32_t v = x;
  v ^= v << 13; v ^= v >> 17; v ^= v << 5;
  x = v;
  return v >> 24;
}

uint8_t next_step_level() {
  if (n_p) { n_p--; return xorshift_level(xs_p); }
  if (n_c) { n_c--; return xorshift_level(xs_c); }
  return 128;  // drive finished: mid-scale
}

void on_tick() {  // start of a new tick: stimulus, then one conversion (round robin)
  tick_cyc = ARM_DWT_CYCCNT;
  tick++;
  if (stim == 1 && ++step_tick >= tps) { step_tick = 0; analogWrite(DAC_PIN, next_step_level()); }
  if (stim == 2) { phase += phase_inc; analogWrite(DAC_PIN, 128 + (sine[phase >> 24] * amp) / 128); }
  uint16_t v = analogRead(APIN[order[ch_idx]]);
  if (++ch_idx == nch) ch_idx = 0;
  if (!have_first) { first_tick = tick; have_first = true; }
  uint16_t h = (head + 1) % RING;
  if (h == tail) { dropped++; return; }
  ring[head] = v; head = h;
}

void on_flash() {  // comparator edge = flash
  uint32_t c = ARM_DWT_CYCCNT, t = tick, s = c - tick_cyc;
  if (s > ocr1a) { t++; s -= ocr1a + 1; }  // the tick interrupt is pending, not yet serviced
  uint8_t h = (ev_head + 1) % EV;
  if (h == ev_tail) { ev_dropped++; return; }
  ev_tick[ev_head] = t; ev_sub[ev_head] = s; ev_head = h;
}

uint16_t crc_update(uint16_t crc, uint8_t b) {  // CRC-16/CCITT-FALSE, as protocol.py
  crc ^= (uint16_t)b << 8;
  for (uint8_t i = 0; i < 8; i++) crc = (crc & 0x8000) ? (crc << 1) ^ 0x1021 : crc << 1;
  return crc;
}

uint16_t put(uint16_t crc, uint8_t b) { Serial.write(b); return crc_update(crc, b); }

void send_frame(uint8_t kind, uint32_t tick0, const uint16_t *v, uint8_t n) {
  Serial.write(0xAA); Serial.write(0x55);
  uint16_t crc = 0xFFFF;
  crc = put(crc, kind);
  crc = put(crc, seq & 0xFF); crc = put(crc, seq >> 8);
  for (uint8_t i = 0; i < 4; i++) crc = put(crc, (tick0 >> (8 * i)) & 0xFF);
  crc = put(crc, n);
  for (uint8_t i = 0; i < n; i++) { crc = put(crc, v[i] & 0xFF); crc = put(crc, v[i] >> 8); }
  Serial.write(crc & 0xFF); Serial.write(crc >> 8);
  seq++;
}

void flush_samples(bool all) {
  uint16_t buf[BATCH];
  for (;;) {
    uint16_t h = head;
    uint16_t avail = (h + RING - tail) % RING;
    if (avail == 0 || (!all && avail < BATCH)) return;
    uint8_t n = avail < BATCH ? avail : BATCH;
    for (uint8_t i = 0; i < n; i++) buf[i] = ring[(tail + i) % RING];
    tail = (tail + n) % RING;
    send_frame(SAMPLE, first_tick + sent, buf, n);
    sent += n;
  }
}

void flush_events() {
  uint16_t buf[24];
  uint8_t n = 0;
  while (ev_tail != ev_head && n < 24) {
    uint32_t t = ev_tick[ev_tail];
    buf[n++] = t & 0xFFFF; buf[n++] = t >> 16; buf[n++] = ev_sub[ev_tail];
    ev_tail = (ev_tail + 1) % EV;
  }
  if (n) send_frame(EVENT, 0, buf, n);
}

void start_run(char *args) {
  stim = 0; step_tick = 0; phase = 0; analogWrite(DAC_PIN, 128);
  if (strncmp(args, "STEPS,", 6) == 0) {
    xs_p = strtoul(args + 6, &args, 10); n_p = strtoul(args + 1, &args, 10);
    xs_c = strtoul(args + 1, &args, 10); n_c = strtoul(args + 1, &args, 10);
    tps = strtoul(args + 1, &args, 10);
    if (!tps || (n_p && !xs_p) || (n_c && !xs_c)) { Serial.println("ERR,bad STEPS"); return; }
    stim = 1; analogWrite(DAC_PIN, next_step_level());
  } else if (strncmp(args, "SINE,", 5) == 0) {
    phase_inc = strtoul(args + 5, &args, 10); uint32_t a = strtoul(args + 1, &args, 10);
    if (!phase_inc || a > 127) { Serial.println("ERR,bad SINE"); return; }
    amp = a; stim = 2;
  } else if (strcmp(args, "NONE") != 0) { Serial.println("ERR,bad stimulus"); return; }
  head = tail = 0; ev_head = ev_tail = 0; tick = 0;
  dropped = ev_dropped = 0; have_first = false; seq = 0; sent = 0; ch_idx = 0;
  Serial.print("SYNC,"); Serial.println(micros());
  Serial.flush();
  running = true;
  tick_cyc = ARM_DWT_CYCCNT;
  tick_timer.begin(on_tick, (ocr1a + 1) / (F_CPU_ACTUAL / 1e6f));  // period in microseconds
  attachInterrupt(digitalPinToInterrupt(FLASH_PIN), on_flash, RISING);
}

void stop_run() {
  tick_timer.end();
  detachInterrupt(digitalPinToInterrupt(FLASH_PIN));
  running = false; analogWrite(DAC_PIN, 128);
  flush_samples(true); flush_events();
  Serial.print("STOPPED,"); Serial.print(dropped); Serial.print(','); Serial.println(ev_dropped);
}

void configure(char *args) {
  char *rest;
  uint32_t top = strtoul(args, &rest, 10);
  char *chans = rest + 1;
  uint8_t n = strlen(chans);
  if (top < MIN_TICK || top > 65535) { Serial.println("ERR,ocr1a out of range"); return; }  // sub fits u16
  if (n < 1 || n > 5) { Serial.println("ERR,1-5 channels"); return; }
  for (uint8_t i = 0; i < n; i++) {
    if (chans[i] < '0' || chans[i] > '4') { Serial.println("ERR,channels are 0-4"); return; }
    order[i] = chans[i] - '0';
  }
  nch = n; ocr1a = top;
  Serial.println("OK");
}

void handle(char *line) {
  if (strcmp(line, "PING") == 0) { Serial.print("PONG," FW ",12,"); Serial.println(F_CPU_ACTUAL); }
  else if (strncmp(line, "CONF,", 5) == 0 && !running) configure(line + 5);
  else if (strncmp(line, "START,", 6) == 0 && !running && nch) start_run(line + 6);
  else if (strcmp(line, "STOP") == 0 && running) stop_run();
  else Serial.println("ERR,unknown or out-of-order command");
}

void setup() {
  Serial.begin(115200);  // USB serial: the rate argument is ignored (480 Mbit/s link)
  ARM_DEMCR |= ARM_DEMCR_TRCENA;          // enable the cycle counter
  ARM_DWT_CTRL |= ARM_DWT_CTRL_CYCCNTENA;
  for (int i = 0; i < 256; i++) sine[i] = (int8_t)lroundf(127.0f * sinf(6.2831853f * i / 256));
  analogReadResolution(12);
  analogReadAveraging(1);
  analogWriteResolution(8);
  analogWriteFrequency(DAC_PIN, 585937.5);  // ideal 8-bit PWM rate at 600 MHz (PJRC)
  analogWrite(DAC_PIN, 128);
  pinMode(FLASH_PIN, INPUT);
}

void loop() {
  static char line[64];
  static uint8_t len = 0;
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') { line[len] = 0; handle(line); len = 0; }
    else if (c != '\r' && len < sizeof(line) - 1) line[len++] = c;
  }
  if (running) { flush_samples(false); flush_events(); }
}
