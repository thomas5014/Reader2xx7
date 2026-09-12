#ifndef _BOARDS_READER2350_H
#define _BOARDS_READER2350_H

pico_board_cmake_set(PICO_PLATFORM, rp2350)

// RP2350B (QFN-80): do NOT define PICO_RP2350A, or the SDK assumes the
// 30-GPIO 'A' variant and everything past GPIO29 stops existing.

// No UART wired to anything on this board — bring-up goes over USB CDC.
// (Deliberately not defining PICO_DEFAULT_UART: hardware/uart.h token-pastes
// it into "uart" ## N to build the uart_default instance, so -1 breaks the
// preprocessor. Leaving it undefined is the SDK's actual "no default UART".)

// W25Q128JVPIQ = 16 MB (128 Mbit). Same Winbond QSPI command set as the
// W25Q080 boot2 stage covers, just more capacity, so that boot2 is fine.
#define PICO_BOOT_STAGE2_CHOOSE_W25Q080 1

#ifndef PICO_FLASH_SPI_CLKDIV
#define PICO_FLASH_SPI_CLKDIV 2
#endif

pico_board_cmake_set_default(PICO_FLASH_SIZE_BYTES, (16 * 1024 * 1024))
#ifndef PICO_FLASH_SIZE_BYTES
#define PICO_FLASH_SIZE_BYTES (16 * 1024 * 1024)
#endif

pico_board_cmake_set_default(PICO_RP2350_A2_SUPPORTED, 1)
#ifndef PICO_RP2350_A2_SUPPORTED
#define PICO_RP2350_A2_SUPPORTED 1
#endif

// --- Display (NT35510, 16-bit 8080 parallel) ---
#define READER_LCD_PIN_CS   0
#define READER_LCD_PIN_DC   1
#define READER_LCD_PIN_WR   2
#define READER_LCD_PIN_RST  3
#define READER_LCD_PIN_D0   4   // data bus occupies D0..D0+15 = GPIO4-19
#define READER_LCD_BL_PWM_PIN 35

// --- Touch (CST3240, I2C1) ---
#define READER_TOUCH_I2C_INST i2c1
#define READER_TOUCH_PIN_SDA 23
#define READER_TOUCH_PIN_SCL 22
#define READER_TOUCH_ADDR    0x5A
// RST vs IRQ on GPIO30/31 not yet confirmed against silkscreen/hardware.

// --- I2C0: INA226, DRV2605, RV-3028-C7 RTC ---
#define READER_SENSOR_I2C_INST i2c0
#define READER_SENSOR_PIN_SDA 20
#define READER_SENSOR_PIN_SCL 21

// --- External PSRAM (APS6404L) on QMI CS1 ---
#define READER_PSRAM_CS1_GPIO 47

// --- CYW43439 (Wi-Fi/BT), wired like Pico 2 W's gspi bus ---
#define CYW43_PIN_WL_CLK   39
#define CYW43_PIN_WL_DATA  37   // shared half-duplex DI/DO/IRQ, see R8/R9
#define CYW43_PIN_WL_CS    38
#define CYW43_PIN_WL_REG_ON 36  // drives both WL_ON and BT_ON

#endif