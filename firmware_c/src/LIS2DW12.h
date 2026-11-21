// LIS2DW12.h -- see LIS2DW12.c. Ported from micropython_easychecks/accel_check.py.
#pragma once

#include <stdint.h>

typedef struct {
    int16_t x;
    int16_t y;
    int16_t z;
} lis2dw12_data_t;

// Call once at startup, before any other lis2dw12_* function.
void lis2dw12_init(void);

void lis2dw12_get(lis2dw12_data_t *data);
float read_temperature(void);