// WS2818.c -- see WS2818.h
#include "WS2818.h"

#include <stdint.h>
#include "stdbool.h"
#include "hardware/pio.h"
#include "hardware/clocks.h"

#define LED_PIN 44

// State machine frequency: 8 MHz
#define PIO_FREQ_HZ 8000000u 

static PIO g_pio = NULL;
static int g_sm = -1;
static uint32_t g_off;

void init_sm(void) {
    // Config and nitiate state machine to LED_PIN
    pio_sm_config c = pio_get_default_sm_config();
    sm_config_set_wrap(&c, g_off, g_off + 3);
    sm_config_set_sideset_pins(&c, LED_PIN);
    sm_config_set_sideset(&c, 1, false, false);
    sm_config_set_out_shift(&c, false, true, 24);
    sm_config_set_clkdiv(&c, (float) clock_get_hz(clk_sys) / PIO_FREQ_HZ);
    pio_sm_init(g_pio, g_sm, g_off, &c);

    // Claiming LED_PIN for pio
    pio_gpio_init(g_pio, LED_PIN);
    pio_sm_set_consecutive_pindirs(g_pio, g_sm, LED_PIN, 1, true);
    pio_sm_set_enabled(g_pio, g_sm, true);
}

void ws2818_set_color(uint8_t r, uint8_t g, uint8_t b) {
    uint32_t word = ((uint32_t)g << 16) | ((uint32_t)r << 8) | b;
    word <<= 8;
    pio_sm_put_blocking(g_pio, g_sm, word);
}

static bool pio_check_claimed(PIO p) {
    for (int sm = 0; sm < 4; sm++) {
        if (pio_sm_is_claimed(p, sm)) return true;
    }
    return false;
}

bool ws2818_init(void) {
    uint16_t instr[4];

    instr[0] = pio_encode_out(pio_x, 1) | pio_encode_sideset(1, 0) | pio_encode_delay(2);
    instr[1] = pio_encode_jmp_not_x(3)  | pio_encode_sideset(1, 1) | pio_encode_delay(1);
    instr[2] = pio_encode_jmp(0)        | pio_encode_sideset(1, 1) | pio_encode_delay(4);
    instr[3] = pio_encode_nop()         | pio_encode_sideset(1, 0) | pio_encode_delay(4);

    pio_program_t prog = { .instructions = instr, .length = 4, .origin = -1};

    PIO cands[2] = { pio1, pio2 };
    for (int i =0; i < 2 && g_sm < 0; i++) {
        PIO p = cands[i];
        if (!pio_can_add_program(p,&prog)) continue;
        if (pio_check_claimed(p)) continue;
        int sm = pio_claim_unused_sm(p, false);
        if (sm < 0) continue;
        g_pio = p;
        g_sm = sm;
    }
    if (g_sm < 0) return false;
    pio_set_gpio_base(g_pio, 16);
    g_off = pio_add_program(g_pio, &prog);

    init_sm();
    return true;
}