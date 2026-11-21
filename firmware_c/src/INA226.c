// INA226.c -- see INA226.h. Ported from micropython_easychecks/ina_check.py.
#include "INA226.h"

#include "hardware/i2c.h"
#include "hardware/gpio.h"

#define I2C_PORT i2c0
#define SDA_PIN  28
#define SCL_PIN  29
#define ADDR     0x40

#define REG_CONFIG       0x00
#define REG_SHUNTVOLTAGE 0x01
#define REG_BUSVOLTAGE   0x02

// --- Step 3: low-level I2C helpers ---------------------------------------
// Same shape as cst3240.c's read_reg16/write_reg16, but 8-bit register
// addresses (this chip doesn't use CST3240's 16-bit addressing) --
// equivalent to the Python driver's i2c.readfrom_mem().

static bool read_reg(uint8_t reg, uint8_t *data, size_t len) {
    if (i2c_write_blocking(I2C_PORT, ADDR, &reg, 1, true) != 1) {  // true = no stop, repeated start
        return false;
    }
    return i2c_read_blocking(I2C_PORT, ADDR, data, len, false) == (int)len;
}

int16_t read_reg16(uint8_t reg) {
    uint8_t value[2];
    read_reg(reg, value, 2);
    int16_t voltage;
    voltage = (value[0] << 8) | value[1];
    return voltage;
}

// --- Public API -----------------------------------------------------------

void ina226_init(void) {
    i2c_init(I2C_PORT, 400 * 1000);  // 100kHz, matching the Python driver's freq=100000
    gpio_set_function(SDA_PIN, GPIO_FUNC_I2C);
    gpio_set_function(SCL_PIN, GPIO_FUNC_I2C);
    gpio_pull_up(SDA_PIN);
    gpio_pull_up(SCL_PIN);
}

float ina226_bus_voltage(void) {
    return read_reg16(REG_BUSVOLTAGE) * 0.00125;
}

float ina226_shunt_voltage(void) {
    int16_t raw;
    raw = read_reg16(REG_SHUNTVOLTAGE);
    if (raw & 0x8000) {
        raw -= 0x10000;
    }
    return raw * 0.0025;
}