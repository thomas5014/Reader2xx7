#include <stdio.h>
#include "pico/stdlib.h"
#include "nt35510.h"

int main() {
    stdio_init_all();

    for (int i = 0; i < 50 && !stdio_usb_connected(); i++) {
        sleep_ms(100);
    }
    sleep_ms(200);

    printf("\n=== reader2350 boot ===\n");
    printf("PICO_BOARD: reader2350, RP2350B\n");

    printf("lcd_init()...\n");
    lcd_init();
    printf("lcd_init() done\n");

    uint16_t colors[] = {0xF800, 0x07E0, 0x001F}; // red, green, blue
    uint32_t idx = 0;
    while (true) {
        printf("fill: 0x%04X\n", colors[idx]);
        lcd_fill(colors[idx]);
        idx = (idx + 1) % 3;
        sleep_ms(1000);
    }
}
