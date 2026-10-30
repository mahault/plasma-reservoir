// NE-2 reservoir acquisition for the Arduino UNO (ATmega328P, 16 MHz).
// Host side and frame layout: plasma_rc/acquisition/serial_io.py and protocol.py.
// Registers per Microchip ATmega328P datasheet (Atmel-7810D): Timer1 CTC mode 4, ADC auto
// trigger on Timer1 compare match B (Table 23-6), comparator -> Timer1 input capture (ACIC,
// §22.3.2), Timer2 fast PWM on OC2B (D3) as the held-step / sine DAC (D-28).
#include "sine_table.h"

#define FW "ne2-uno-1"
const uint16_t MIN_OCR1A = 1999;  // >= 125 us per tick: one 10-bit conversion is 13 ADC clocks at 125 kHz
const uint16_t RING = 384;        // sample ring (2 bytes each), ~48 ms at 8 kHz
const uint8_t EV = 16;            // flash-event ring
const uint8_t SAMPLE = 1, EVENT = 2, BATCH = 32;

volatile uint16_t ring[RING];
volatile uint16_t head = 0, tail = 0;
volatile uint32_t tick = 0, last_tick = 0, first_tick = 0, dropped = 0;
volatile bool have_first = false;
volatile uint32_t ev_tick[EV];
volatile uint16_t ev_sub[EV];
volatile uint8_t ev_head = 0, ev_tail = 0;
volatile uint32_t ev_dropped = 0;

uint8_t order[5], nch = 0, ch_idx = 0;
uint16_t ocr1a = 0, seq = 0;
uint32_t sent = 0;
bool running = false;

// stimulus: 0 none, 1 steps (xorshift32, Marsaglia 2003), 2 sine (DDS)
volatile uint8_t stim = 0;
volatile uint32_t xs_p, xs_c, n_p, n_c, tps, step_tick, phase, phase_inc;
volatile uint8_t amp;

uint8_t xorshift_level(volatile uint32_t &x) {
  x ^= x << 13; x ^= x >> 17; x ^= x << 5;
  return x >> 24;
}

uint8_t next_step_level() {
  if (n_p) { n_p--; return xorshift_level(xs_p); }
  if (n_c) { n_c--; return xorshift_level(xs_c); }
  return 128;  // drive finished: mid-scale
}

ISR(TIMER1_COMPA_vect) {  // start of a new tick
  tick++;
  if (stim == 1 && ++step_tick >= tps) { step_tick = 0; OCR2B = next_step_level(); }
  if (stim == 2) {
    phase += phase_inc;
    OCR2B = 128 + ((int16_t)(int8_t)pgm_read_byte(&SINE_TABLE[phase >> 24]) * amp) / 128;
  }
}

ISR(TIMER1_COMPB_vect) {}  // clears OCF1B so the next compare B can trigger the ADC

ISR(ADC_vect) {
  uint16_t v = ADC;
  if (++ch_idx == nch) ch_idx = 0;
  ADMUX = _BV(REFS0) | order[ch_idx];  // takes effect for the next conversion (§23.5)
  if (!have_first) { first_tick = tick; have_first = true; }
  else if (tick != last_tick + 1) dropped++;  // a trigger was missed
  last_tick = tick;
  uint16_t h = (head + 1) % RING;
  if (h == tail) { dropped++; return; }
  ring[head] = v; head = h;
}

ISR(TIMER1_CAPT_vect) {  // comparator edge = flash (D6 above D7 reference)
  uint16_t icr = ICR1;
  uint32_t t = tick;
  if ((TIFR1 & _BV(OCF1A)) && icr < (ocr1a >> 1)) t++;  // wrapped, COMPA not yet serviced
  uint8_t h = (ev_head + 1) % EV;
  if (h == ev_tail) { ev_dropped++; return; }
  ev_tick[ev_head] = t; ev_sub[ev_head] = icr; ev_head = h;
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
    noInterrupts(); uint16_t h = head; interrupts();
    uint16_t avail = (h + RING - tail) % RING;
    if (avail == 0 || (!all && avail < BATCH)) return;
    uint8_t n = avail < BATCH ? avail : BATCH;
    for (uint8_t i = 0; i < n; i++) buf[i] = ring[(tail + i) % RING];
    noInterrupts(); tail = (tail + n) % RING; interrupts();  // 16-bit: the ADC ISR reads it
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
  stim = 0; step_tick = 0; phase = 0; OCR2B = 128;
  if (strncmp(args, "STEPS,", 6) == 0) {
    xs_p = strtoul(args + 6, &args, 10); n_p = strtoul(args + 1, &args, 10);
    xs_c = strtoul(args + 1, &args, 10); n_c = strtoul(args + 1, &args, 10);
    tps = strtoul(args + 1, &args, 10);
    if (!tps || (n_p && !xs_p) || (n_c && !xs_c)) { Serial.println("ERR,bad STEPS"); return; }
    stim = 1; OCR2B = next_step_level();
  } else if (strncmp(args, "SINE,", 5) == 0) {
    phase_inc = strtoul(args + 5, &args, 10); uint32_t a = strtoul(args + 1, &args, 10);
    if (!phase_inc || a > 127) { Serial.println("ERR,bad SINE"); return; }
    amp = a; stim = 2;
  } else if (strcmp(args, "NONE") != 0) { Serial.println("ERR,bad stimulus"); return; }
  head = tail = 0; ev_head = ev_tail = 0; tick = last_tick = 0;
  dropped = ev_dropped = 0; have_first = false; seq = 0; sent = 0; ch_idx = 0;
  ADMUX = _BV(REFS0) | order[0];
  Serial.print("SYNC,"); Serial.println(micros());
  Serial.flush();
  TCNT1 = 0; TIFR1 = 0xFF;
  TCCR1B = _BV(ICNC1) | _BV(ICES1) | _BV(WGM12) | _BV(CS10);  // CTC, prescaler 1, rising edge
  running = true;
}

void stop_run() {
  TCCR1B = 0;  // stop Timer1: no more ticks, conversions or captures
  running = false; OCR2B = 128;
  flush_samples(true); flush_events();
  Serial.print("STOPPED,"); Serial.print(dropped); Serial.print(','); Serial.println(ev_dropped);
}

void configure(char *args) {
  char *rest;
  uint32_t top = strtoul(args, &rest, 10);
  char *chans = rest + 1;
  uint8_t n = strlen(chans);
  if (top < MIN_OCR1A || top > 65535) { Serial.println("ERR,ocr1a out of range"); return; }
  if (n < 1 || n > 5) { Serial.println("ERR,1-5 channels"); return; }
  for (uint8_t i = 0; i < n; i++) {
    if (chans[i] < '0' || chans[i] > '4') { Serial.println("ERR,channels are 0-4"); return; }
    order[i] = chans[i] - '0';
    DIDR0 |= _BV(order[i]);  // disable the digital buffer on used analog pins
  }
  nch = n; ocr1a = top; OCR1A = top; OCR1B = 0;
  Serial.println("OK");
}

void handle(char *line) {
  if (strcmp(line, "PING") == 0) { Serial.print("PONG," FW ","); Serial.println(10); }
  else if (strncmp(line, "CONF,", 5) == 0 && !running) configure(line + 5);
  else if (strncmp(line, "START,", 6) == 0 && !running && nch) start_run(line + 6);
  else if (strcmp(line, "STOP") == 0 && running) stop_run();
  else Serial.println("ERR,unknown or out-of-order command");
}

void setup() {
  Serial.begin(1000000);  // exact at 16 MHz (datasheet Table 19-12)
  pinMode(3, OUTPUT);     // OC2B: PWM-DAC
  TCCR2A = _BV(COM2B1) | _BV(WGM21) | _BV(WGM20);  // fast PWM, non-inverting
  TCCR2B = _BV(CS20);                               // no prescaler: 62.5 kHz
  OCR2B = 128;
  pinMode(6, INPUT); pinMode(7, INPUT);  // AIN0/AIN1, pull-ups off (D-24)
  DIDR1 = _BV(AIN1D) | _BV(AIN0D);
  ADCSRB = _BV(ADTS2) | _BV(ADTS0);       // auto trigger: Timer1 compare match B; ACME = 0
  ACSR = _BV(ACIC);                       // comparator output -> Timer1 input capture
  ADCSRA = _BV(ADEN) | _BV(ADATE) | _BV(ADIE) | _BV(ADPS2) | _BV(ADPS1) | _BV(ADPS0);  // /128
  TCCR1A = 0; TCCR1B = 0;
  TIMSK1 = _BV(OCIE1A) | _BV(OCIE1B) | _BV(ICIE1);
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
