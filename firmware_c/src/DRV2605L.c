// DRV2605L.c -- see DRV2605L.h. Ported from micropython_easychecks/haptic_check.py.
#include "DRV2605L.h"

#include <stdio.h>
#include "stdbool.h"
#include "hardware/i2c.h"
#include "hardware/gpio.h"

#define I2C_PORT i2c0
#define SDA_PIN  28
#define SCL_PIN  29
#define EN_PIN   41
#define ADDR     0x5A

#define STATUS             0x00
#define MODE               0x01
#define LIBRARY_SELECTION  0x02
#define WAVEFORM_LIBRARY   0x03
#define WAVEFORM_SEQ_1     0x04
#define WAVEFORM_SEQ_2     0x05
#define WAVEFORM_SEQ_3     0x06
#define GO                 0x0C
#define RATED_VOLTAGE      0x16
#define OD_CLAMP           0x17
#define FEEDBACK_CONTROL   0x1A
#define CONTROL3           0x1D
#define OL_LRA_PERIOD      0x20

#define DEBUG 0


static bool write_reg(uint8_t reg, uint8_t val) {
    uint8_t buf[2] = { reg, val };
    return i2c_write_blocking(I2C_PORT, ADDR, buf, 2, false) == 2;
}

static bool read_reg(uint8_t reg, uint8_t *data) {
    if (i2c_write_blocking(I2C_PORT, ADDR, &reg, 1, true) != 1) {
        return false;
    }
    return i2c_read_blocking(I2C_PORT, ADDR, data, 1, false) == 1;
}

static bool check_done(void) {
    uint8_t data;
    bool go_cleared = false;

    for (int i = 0; i < 100; i++) {
        read_reg(GO, &data);
        if ((data & 1) == 0) {
            go_cleared = true;
            break;
        }
        sleep_ms(2);   
    }
    if (!go_cleared) {
        printf("WARNING: diagnostic GO bit never cleared\n");
        return false;
    }
    return true;
}

static bool run_debug(void) {
    // Diag mode
    write_reg(MODE, 0x06);
    // Start
    write_reg(GO, 0x01);

    if (!check_done()) return false;

    uint8_t diag_status;
    read_reg(STATUS, &diag_status);
    if (diag_status & 8) {
        printf("DIAG_RESULT=1: actuator NOT detected (open/shorted/no back-EMF)\n");
        return false;
    } else {
        printf("DIAG_RESULT=0: actuator responding normally -- LRA is present\n");
    }
    
    // Return to normal operating mode
    write_reg(MODE, 0x00);
    return true;
}

void drv2605l_init(void) {
    // Pulling up pin 41 to activate haptic driver
    gpio_init(EN_PIN);
    gpio_set_dir(EN_PIN, true);
    gpio_put(EN_PIN, true);

    // Initializing i2c to 400khz
    i2c_init(I2C_PORT,400*1000);
    gpio_set_function(SDA_PIN, GPIO_FUNC_I2C);
    gpio_set_function(SCL_PIN, GPIO_FUNC_I2C);
    gpio_pull_up(SDA_PIN);
    gpio_pull_up(SCL_PIN);

    // Chip reset
    write_reg(MODE, 0x80);
    sleep_ms(100);

    // Chip to standby
    write_reg(MODE, 0x00);
    sleep_ms(10);

    // Set for LRA 
    write_reg(FEEDBACK_CONTROL, 0x80);

    // Diagnostic things - optional
    if (DEBUG) run_debug();

    // Switching to open loop mode. Why? how the hell would i know!
    // Shhh... Shhh... everything is ok now, relax, the nightmare is over. remember 0x00 is the good one
    write_reg(CONTROL3, 0x00);

    // Manual LRAR freq set. still no clue why
    write_reg(OL_LRA_PERIOD, 0x33);

    // Setting specific voltages for Vybronucs - 2.0v Rated Spec
    write_reg(RATED_VOLTAGE, 0x53);
    write_reg(OD_CLAMP, 0x56);
}

void haptic_buzz(void) {
    // Setting up buzz stuff
    write_reg(WAVEFORM_LIBRARY, 0x06);   // LRA Library
    write_reg(LIBRARY_SELECTION, 0x00);  // Internal Trigger Mode
    write_reg(WAVEFORM_SEQ_1, 47);       // Effect 47 = Continuous Buzz 100%
    write_reg(WAVEFORM_SEQ_2, 47);       // Chain it again to make it longer
    write_reg(WAVEFORM_SEQ_3, 0); 

    // Buzz trigger
    write_reg(GO, 0x01);
}

// Play tone pattern from chip rom, 1-123: id
bool drv2605l_raw(uint8_t effect_id) {
    bool ok = write_reg(WAVEFORM_SEQ_1, effect_id);
    ok = write_reg(WAVEFORM_SEQ_2, 0) && ok;   // force-terminate right after slot 1
    ok = write_reg(GO, 0x01) && ok;
    return ok;
}
