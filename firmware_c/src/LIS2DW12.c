// LIS2DW12.c -- see LIS2DW12.h. Ported from micropython_easychecks/accel_check.py.
#include "LIS2DW12.h"

#include "hardware/i2c.h"
#include "hardware/gpio.h"
#include "stdbool.h"
#include <stdio.h>
#include <stdint.h>

#define I2C_PORT i2c1
#define SDA_PIN   30
#define SCL_PIN   31
#define ADDR     0x18

#define REG_CTRL1    0x20
#define REG_CTRL2    0x21
#define REG_CTRL3    0x22
#define REG_OUT_X_L  0x28   //(X low byte; high byte is 0x29)
#define REG_OUT_Y_L  0x2A
#define REG_OUT_Z_L  0x2C
#define REG_OUT_T_L  0x0D

static bool write_reg(uint8_t reg, uint8_t val) {
    uint8_t buf[2] = { reg, val };
    return i2c_write_blocking(I2C_PORT, ADDR, buf, 2, false) == 2;
}

static int16_t read_axis(uint8_t reg_low) {
    uint8_t value[2];
    i2c_write_blocking(I2C_PORT, ADDR, &reg_low, 1, true);   // repeated start
    i2c_read_blocking(I2C_PORT, ADDR, value, 2, false);
    int16_t raw = (int16_t)((value[1] << 8) | value[0]);     // low byte first — reversed from INA226
    return raw >> 2;
}

float read_temperature(void) {
    uint8_t value[2];
    uint8_t reg = REG_OUT_T_L;
    i2c_write_blocking(I2C_PORT, ADDR, &reg, 1, true);   // repeated start
    i2c_read_blocking(I2C_PORT, ADDR, value, 2, false);
    int16_t raw = (int16_t)((value[1] << 8) | value[0]);     // low byte first — reversed from INA226
    return (float) raw / 256.0 + 25.0;
}

void lis2dw12_init(void) {
    i2c_init(I2C_PORT, 400 * 1000);
    gpio_set_function(SDA_PIN, GPIO_FUNC_I2C);
    gpio_set_function(SCL_PIN, GPIO_FUNC_I2C);
    gpio_pull_up(SDA_PIN);
    gpio_pull_up(SCL_PIN);
    
    bool ok = write_reg(REG_CTRL1, 0x51);
    ok = write_reg(REG_CTRL2, 0x0C) && ok;
    ok = write_reg(REG_CTRL3, 0x02) && ok;
    if (ok) printf("init writes done\n");
}

void lis2dw12_get(lis2dw12_data_t *data) {
    data->x = read_axis(REG_OUT_X_L);
    data->y = read_axis(REG_OUT_Y_L);
    data->z = read_axis(REG_OUT_Z_L);
}