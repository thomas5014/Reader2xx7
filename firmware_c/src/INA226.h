// INA226.h -- C port of micropython_easychecks/ina_check.py's INA226 class
#pragma once

#include <stdint.h>

// Call once at startup, before any other ina226_* function.
void ina226_init(void);

// Starting simple with just returning the values, no i2c failure safeties
float ina226_bus_voltage(void);
float ina226_shunt_voltage(void);
