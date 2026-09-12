#ifndef NT35510_H
#define NT35510_H

#include <stdint.h>

#define NT35510_WIDTH  480
#define NT35510_HEIGHT 800

void lcd_init(void);
void lcd_fill_rect(uint16_t x, uint16_t y, uint16_t w, uint16_t h, uint16_t color);
void lcd_fill(uint16_t color);

#endif
