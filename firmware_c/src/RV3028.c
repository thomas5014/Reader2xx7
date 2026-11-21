// RV3028.c -- see RV3028.h. Ported from micropython_easychecks/rtc_check.py.
#include "RV3028.h"

#include "hardware/i2c.h"
#include "hardware/gpio.h"
#include "pico/time.h"

#define I2C_PORT i2c0
#define SDA_PIN  28
#define SCL_PIN  29
#define ADDR     0x52

// --- Register map (from the Micro Crystal datasheet, same comment the
// Python version carried over) -------------------------------------------
#define REG_SEC            0x00  // burst-read start: SEC,MIN,HOUR,WEEKDAY,DATE,MONTH,YEAR
#define REG_STATUS         0x0E  // bit 7 = EEbusy
#define REG_CONTROL1       0x0F  // bit 3 = EERD (EEPROM auto-refresh disable)
#define REG_EECMD          0x27
#define REG_EEPROM_BACKUP  0x37

// --- Step 3: low-level I2C helpers ---------------------------------------
// Same shape as cst3240.c's read_reg16/write_reg16, but 8-bit register
// addresses (this chip doesn't use CST3240's 16-bit addressing) --
// equivalent to the Python driver's i2c.readfrom_mem()/writeto_mem().

static bool write_reg(uint8_t reg, const uint8_t *data, size_t len) {
    uint8_t buf[8];  // longest write here is the 7-byte time burst + 1 reg byte
    buf[0] = reg;
    for (size_t i = 0; i < len; i++) {
        buf[1 + i] = data[i];
    }
    return i2c_write_blocking(I2C_PORT, ADDR, buf, len + 1, false) == (int)(len + 1);
}

static bool write_reg8(uint8_t reg, uint8_t value) {
    return write_reg(reg, &value, 1);
}

static bool read_reg(uint8_t reg, uint8_t *data, size_t len) {
    if (i2c_write_blocking(I2C_PORT, ADDR, &reg, 1, true) != 1) {  // true = no stop, repeated start
        return false;
    }
    return i2c_read_blocking(I2C_PORT, ADDR, data, len, false) == (int)len;
}

static bool read_reg8(uint8_t reg, uint8_t *value) {
    return read_reg(reg, value, 1);
}

// --- Step 4a: BCD helpers -- direct port of _bcd_to_dec/_dec_to_bcd -------

static uint8_t bcd_to_dec(uint8_t bcd) {
    return ((bcd >> 4) * 10) + (bcd & 0x0F);
}

static uint8_t dec_to_bcd(uint8_t dec) {
    return (uint8_t)(((dec / 10) << 4) | (dec % 10));
}

// --- Step 4b: EEPROM backup-switchover, ported register-for-register from
// _enable_backup_switchover()/_wait_eebusy() -- this is config the chip
// needs once (to actually use its battery/supercap backup when main power
// drops) and the Python version works out the exact dance already: disable
// auto EEPROM refresh, write the new config bit into the RAM mirror, issue
// an "Update All" EEPROM command, wait for it to finish (t_UPDATE ~63ms, a
// real datasheet timing constant -- not a guess), then re-enable refresh.
static bool wait_eebusy(uint32_t timeout_ms) {
    absolute_time_t deadline = make_timeout_time_ms(timeout_ms);
    uint8_t status;
    while (true) {
        if (!read_reg8(REG_STATUS, &status)) return false;
        if (!(status & 0x80)) return true;  // EEbusy clear
        if (time_reached(deadline)) return false;
        sleep_ms(1);
    }
}

static void enable_backup_switchover(void) {
    uint8_t current;
    if (!read_reg8(REG_EEPROM_BACKUP, &current)) return;
    uint8_t updated = current | 0x0C;  // BSM = 11 (Level Switching Mode)
    if (current == updated) return;    // already committed, skip EEPROM wear

    uint8_t ctrl1;
    if (!read_reg8(REG_CONTROL1, &ctrl1)) return;

    write_reg8(REG_CONTROL1, ctrl1 | 0x08);     // 1. disable auto EEPROM->RAM refresh
    wait_eebusy(200);

    write_reg8(REG_EEPROM_BACKUP, updated);     // 2. update the RAM mirror

    write_reg8(REG_EECMD, 0x00);                // 3. commit RAM config (0x30-0x37) to EEPROM
    write_reg8(REG_EECMD, 0x11);                // "Update All"
    sleep_ms(63);                               // t_UPDATE
    wait_eebusy(200);

    write_reg8(REG_CONTROL1, ctrl1 & ~0x08);    // 4. re-enable auto refresh
}

// --- Public API -----------------------------------------------------------

void rv3028_init(void) {
    i2c_init(I2C_PORT, 400 * 1000);  // 100kHz, matching the Python driver's freq=100000
    gpio_set_function(SDA_PIN, GPIO_FUNC_I2C);
    gpio_set_function(SCL_PIN, GPIO_FUNC_I2C);
    gpio_pull_up(SDA_PIN);
    gpio_pull_up(SCL_PIN);

    enable_backup_switchover();
}

bool rv3028_read_time(rv3028_time_t *out) {
    uint8_t raw[7];
    if (!read_reg(REG_SEC, raw, sizeof(raw))) {
        return false;
    }
    out->second  = bcd_to_dec(raw[0] & 0x7F);
    out->minute  = bcd_to_dec(raw[1] & 0x7F);
    out->hour    = bcd_to_dec(raw[2] & 0x3F);
    out->weekday = bcd_to_dec(raw[3] & 0x07);
    out->date    = bcd_to_dec(raw[4] & 0x3F);
    out->month   = bcd_to_dec(raw[5] & 0x1F);
    out->year    = (uint16_t)bcd_to_dec(raw[6]) + 2000;
    return true;
}

void rv3028_set_time(const rv3028_time_t *t) {
    uint8_t data[7] = {
        dec_to_bcd(t->second),
        dec_to_bcd(t->minute),
        dec_to_bcd(t->hour),
        dec_to_bcd(t->weekday),
        dec_to_bcd(t->date),
        dec_to_bcd(t->month),
        dec_to_bcd((uint8_t)(t->year % 100)),
    };
    write_reg(REG_SEC, data, sizeof(data));  // burst write starting at REG_SEC
}
