/*
 * Board definition for RPR480 -- a custom RP2350B board (Thomas's own design,
 * built around the same RP2350B + CYW43 module as the Waveshare
 * RP2350B-Plus-W, hence the shared CYW43 pin numbers below) with a
 * 4.3" 480x800 NT35510 display, CST3240 touch, LIS2DW12 accelerometer, RTC,
 * native SDIO SD card, DRV2605 haptics, INA226 current sense, a neopixel,
 * and a GPIO multiplexer. No settled product name yet -- "RPR480" is a
 * placeholder (480 for the display width), trivial to rename later: it's
 * just this directory name plus the string constants below.
 *
 * This is a COPY of ports/rp2/boards/RPR480/rpr480.h in the MicroPython
 * checkout, for the bare-metal (no MicroPython) build in this directory.
 * The pin/electrical facts described here don't depend on MicroPython at
 * all, so duplicating this one small file is simpler than making the two
 * builds share it across separate CMake projects -- if the pins/electrical
 * details ever change, update both copies.
 *
 * NOTE: THIS HEADER IS ALSO INCLUDED BY ASSEMBLER SO
 *       SHOULD ONLY CONSIST OF PREPROCESSOR DIRECTIVES
 */

// pico_cmake_set PICO_PLATFORM=rp2350
// pico_cmake_set PICO_CYW43_SUPPORTED=1

#ifndef _BOARDS_RPR480_H
#define _BOARDS_RPR480_H

// RP2350B: QFN-80 package, 48 GPIOs — do NOT set PICO_RP2350A so NUM_BANK0_GPIOS=48
#define PICO_RP2350A 0

// --- UART ---
#ifndef PICO_DEFAULT_UART
#define PICO_DEFAULT_UART 0
#endif
#ifndef PICO_DEFAULT_UART_TX_PIN
#define PICO_DEFAULT_UART_TX_PIN 0
#endif
#ifndef PICO_DEFAULT_UART_RX_PIN
#define PICO_DEFAULT_UART_RX_PIN 1
#endif

// --- LED --- (on CYW43, no direct GPIO LED)

// --- I2C ---
#ifndef PICO_DEFAULT_I2C
#define PICO_DEFAULT_I2C 0
#endif
#ifndef PICO_DEFAULT_I2C_SDA_PIN
#define PICO_DEFAULT_I2C_SDA_PIN 4
#endif
#ifndef PICO_DEFAULT_I2C_SCL_PIN
#define PICO_DEFAULT_I2C_SCL_PIN 5
#endif

// --- SPI ---
#ifndef PICO_DEFAULT_SPI
#define PICO_DEFAULT_SPI 0
#endif
#ifndef PICO_DEFAULT_SPI_SCK_PIN
#define PICO_DEFAULT_SPI_SCK_PIN 18
#endif
#ifndef PICO_DEFAULT_SPI_TX_PIN
#define PICO_DEFAULT_SPI_TX_PIN 19
#endif
#ifndef PICO_DEFAULT_SPI_RX_PIN
#define PICO_DEFAULT_SPI_RX_PIN 16
#endif
#ifndef PICO_DEFAULT_SPI_CSN_PIN
#define PICO_DEFAULT_SPI_CSN_PIN 17
#endif

// --- FLASH --- (16 MB on Plus variant)
#define PICO_BOOT_STAGE2_CHOOSE_W25Q080 1

#ifndef PICO_FLASH_SPI_CLKDIV
#define PICO_FLASH_SPI_CLKDIV 2
#endif

// pico_cmake_set_default PICO_FLASH_SIZE_BYTES = (16 * 1024 * 1024)
#ifndef PICO_FLASH_SIZE_BYTES
#define PICO_FLASH_SIZE_BYTES (16 * 1024 * 1024)
#endif

// pico_cmake_set_default PICO_RP2350_A2_SUPPORTED = 1
#ifndef PICO_RP2350_A2_SUPPORTED
#define PICO_RP2350_A2_SUPPORTED 1
#endif

// --- CYW43 (Waveshare RP2350B-Plus-W uses GPIO36-39, not the Pico 2 W's 23-25/29) ---
// Source: arduino-pico issue #3297 / PR #3301

#ifndef CYW43_WL_GPIO_COUNT
#define CYW43_WL_GPIO_COUNT 3
#endif

#ifndef CYW43_WL_GPIO_LED_PIN
#define CYW43_WL_GPIO_LED_PIN 0
#endif

#ifndef CYW43_WL_GPIO_SMPS_PIN
#define CYW43_WL_GPIO_SMPS_PIN 1
#endif

#ifndef CYW43_WL_GPIO_VBUS_PIN
#define CYW43_WL_GPIO_VBUS_PIN 2
#endif

#ifndef CYW43_PIN_WL_DYNAMIC
#define CYW43_PIN_WL_DYNAMIC 0
#endif

#ifndef CYW43_DEFAULT_PIN_WL_REG_ON
#define CYW43_DEFAULT_PIN_WL_REG_ON 36u
#endif

#ifndef CYW43_DEFAULT_PIN_WL_DATA_OUT
#define CYW43_DEFAULT_PIN_WL_DATA_OUT 37u
#endif

#ifndef CYW43_DEFAULT_PIN_WL_DATA_IN
#define CYW43_DEFAULT_PIN_WL_DATA_IN 37u
#endif

#ifndef CYW43_DEFAULT_PIN_WL_HOST_WAKE
#define CYW43_DEFAULT_PIN_WL_HOST_WAKE 37u
#endif

#ifndef CYW43_DEFAULT_PIN_WL_CLOCK
#define CYW43_DEFAULT_PIN_WL_CLOCK 39u
#endif

#ifndef CYW43_DEFAULT_PIN_WL_CS
#define CYW43_DEFAULT_PIN_WL_CS 38u
#endif

#endif // _BOARDS_RPR480_H
