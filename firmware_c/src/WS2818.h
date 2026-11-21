// WS2818.h -- C Basic led indicator driver for WS2818B LED
#pragma once 

#include <stdint.h>
#include "stdbool.h"

// Init
bool ws2818_init();

// Set color of lgb led
void ws2818_set_color(uint8_t r, uint8_t g, uint8_t b);