// Runs the ne2_uno firmware ELF on a simulated ATmega328P (simavr 1.6, libsimavr) with fixed
// analog inputs and comparator pulses, and logs what the host would see.
// Usage: ne2_sim FIRMWARE.elf OUT_DIR "CMD1\nCMD2..." STOP_AFTER_TICKS
// Writes OUT_DIR/uart.bin (raw serial bytes), dac.txt ("cycle level" on every OCR2B change),
// meta.txt (Timer1 start cycle, then one comparator-pulse cycle per line).
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <simavr/sim_avr.h>
#include <simavr/sim_elf.h>
#include <simavr/avr_uart.h>
#include <simavr/avr_adc.h>
#include <simavr/avr_acomp.h>

#define TCCR1B 0x81
#define OCR2B 0xB4
#define TICK 2000  // OCR1A + 1 used by the scenario (CONF,1999,...)

static avr_t *avr;
static FILE *uart, *dac, *meta;
static const char *cmds;
static size_t cmd_pos;
// pulse offsets in cycles from Timer1 start: mid-tick, just before and just after compare A
static const avr_cycle_count_t pulses[] = {
    10 * TICK + 700, 21 * TICK - 1, 33 * TICK, 47 * TICK + 1, 60 * TICK + 3, 75 * TICK + 1999};
#define NPULSE (sizeof pulses / sizeof pulses[0])

static void uart_out(struct avr_irq_t *irq, uint32_t v, void *p) { fputc(v, uart); }

static avr_cycle_count_t feed(avr_t *a, avr_cycle_count_t when, void *p) {  // one byte per 10 bits
  if (!cmds[cmd_pos]) return 0;
  avr_raise_irq(avr_io_getirq(a, AVR_IOCTL_UART_GETIRQ('0'), UART_IRQ_INPUT), cmds[cmd_pos++]);
  return when + 160;
}

// simavr 1.6 leaves ADC auto-trigger sources other than free running unimplemented, so the
// harness supplies the datasheet behaviour (Table 23-6): Timer1 compare B flag -> start conversion.
static void compb(struct avr_irq_t *irq, uint32_t v, void *p) {
  if (!v) return;
  avr_irq_t *trig = avr_io_getirq(avr, AVR_IOCTL_ADC_GETIRQ, ADC_IRQ_IN_TRIGGER);
  avr_raise_irq(trig, 0);  // either raise starts one conversion; a busy ADC ignores the other
  avr_raise_irq(trig, 1);
}

static avr_cycle_count_t pulse_end(avr_t *a, avr_cycle_count_t when, void *p) {
  avr_raise_irq(avr_io_getirq(a, AVR_IOCTL_ACOMP_GETIRQ, ACOMP_IRQ_AIN0), 0);
  return 0;
}

// simavr cancels a pending timer with the same (callback, param), so each pulse passes its index
static avr_cycle_count_t pulse(avr_t *a, avr_cycle_count_t when, void *p) {  // 10 us above AIN1
  avr_raise_irq(avr_io_getirq(a, AVR_IOCTL_ACOMP_GETIRQ, ACOMP_IRQ_AIN0), 4000);
  avr_cycle_timer_register(a, 160, pulse_end, NULL);
  return 0;
}

int main(int argc, char **argv) {
  if (argc != 5) { fprintf(stderr, "usage: ne2_sim FIRMWARE.elf OUT_DIR CMDS STOP_AFTER_TICKS\n"); return 2; }
  elf_firmware_t fw = {0};
  if (elf_read_firmware(argv[1], &fw)) return 1;
  avr = avr_make_mcu_by_name("atmega328p");
  avr_init(avr);
  avr->frequency = 16000000;
  avr->avcc = avr->aref = 5000;
  avr_load_firmware(avr, &fw);

  char path[512];
  snprintf(path, sizeof path, "%s/uart.bin", argv[2]); uart = fopen(path, "wb");
  snprintf(path, sizeof path, "%s/dac.txt", argv[2]); dac = fopen(path, "w");
  snprintf(path, sizeof path, "%s/meta.txt", argv[2]); meta = fopen(path, "w");
  cmds = argv[3];
  long stop_ticks = atol(argv[4]);

  uint32_t f = 0;  // binary stream: no console line printing
  avr_ioctl(avr, AVR_IOCTL_UART_SET_FLAGS('0'), &f);
  avr_irq_register_notify(avr_io_getirq(avr, AVR_IOCTL_UART_GETIRQ('0'), UART_IRQ_OUTPUT), uart_out, NULL);
  for (int i = 0; i < 4; i++)  // A0..A3 = 1, 2, 3, 4 V
    avr_raise_irq(avr_io_getirq(avr, AVR_IOCTL_ADC_GETIRQ, ADC_IRQ_ADC0 + i), 1000 * (i + 1));
  avr_raise_irq(avr_io_getirq(avr, AVR_IOCTL_ACOMP_GETIRQ, ACOMP_IRQ_AIN1), 2500);
  avr_raise_irq(avr_io_getirq(avr, AVR_IOCTL_ACOMP_GETIRQ, ACOMP_IRQ_AIN0), 0);
  avr_irq_register_notify(avr_get_interrupt_irq(avr, 12) + AVR_INT_IRQ_PENDING, compb, NULL);  // TIMER1_COMPB
  avr_cycle_timer_register_usec(avr, 100000, feed, NULL);  // after setup() has run

  avr_cycle_count_t start = 0, end = 0;
  uint8_t level = avr->data[OCR2B];
  const char *stop = "STOP\n";
  for (;;) {
    int st = avr_run(avr);
    if (st == cpu_Done || st == cpu_Crashed) { fprintf(stderr, "cpu state %d\n", st); return 1; }
    if (avr->data[OCR2B] != level) { level = avr->data[OCR2B]; fprintf(dac, "%llu %u\n", (unsigned long long)avr->cycle, level); }
    if (!start && avr->data[TCCR1B] == 0xC9) {  // START: ICNC1 ICES1 WGM12 CS10 (Arduino init() also sets TCCR1B)
      start = avr->cycle;
      fprintf(meta, "%llu\n", (unsigned long long)start);
      for (size_t i = 0; i < NPULSE; i++) {
        avr_cycle_timer_register(avr, pulses[i] - (avr->cycle - start), pulse, (void *)i);
        fprintf(meta, "%llu\n", (unsigned long long)(start + pulses[i]));
      }
    }
    if (start && !end && avr->cycle >= start + (avr_cycle_count_t)stop_ticks * TICK) {
      end = avr->cycle; cmds = stop; cmd_pos = 0;
      avr_cycle_timer_register(avr, 1, feed, NULL);
    }
    if (end && avr->cycle > end + 16000000 / 20) break;  // 50 ms to drain
  }
  fclose(uart); fclose(dac); fclose(meta);
  return 0;
}
