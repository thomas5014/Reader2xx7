// DRV2605L.h -- C port of micropython_easychecks/haptic_check.py
#pragma once

#include <stdint.h>
#include "stdbool.h"

void drv2605l_init(void);

void haptic_buzz(void);

bool drv2605l_raw(uint8_t);