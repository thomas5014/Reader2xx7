cmake_minimum_required(VERSION 3.13)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Point at the pico-sdk already vendored inside the MicroPython checkout,
# rather than the ~/pico/pico-sdk checkout or any environment variable --
# the C drivers this project reuses (nt35510_c/, cst3240_c/) were built and
# tested against this exact copy (including the CYW43_PIO_CLOCK_DIV_INT and
# PSRAM-related SDK investigation earlier this project), so pin to it
# explicitly instead of leaving it to whatever PICO_SDK_PATH happens to be
# set in the shell.
set(PICO_SDK_PATH "/Users/thomas/micropython/lib/pico-sdk")

# Board header: a copy of ports/rp2/boards/RPR480/rpr480.h (see
# rpr480_board.h for why it's a copy, not a shared file). PICO_BOARD must
# match the header's filename (minus .h) exactly -- the SDK looks for
# "<PICO_BOARD>.h" in PICO_BOARD_HEADER_DIRS.
list(APPEND PICO_BOARD_HEADER_DIRS ${CMAKE_CURRENT_LIST_DIR})
set(PICO_BOARD "rpr480_board")
set(PICO_PLATFORM "rp2350")
set(PICO_NUM_GPIOS 48)

include(pico_sdk_import.cmake)

project(rpr480_bare C CXX ASM)

pico_sdk_init()

# --- LVGL ---------------------------------------------------------------
# Compiled directly from source (file(GLOB_RECURSE ...)) rather than via
# LVGL's own CMakeLists.txt/env_support machinery: that machinery branches
# on ESP_PLATFORM/ZEPHYR_BASE/MICROPY_DIR/else-desktop, and the desktop
# branch pulls in things (Kconfig options, SDL-oriented defaults) meant for
# a hosted OS build, not bare-metal. Globbing the sources directly is the
# common pattern for bare pico-sdk + LVGL projects and keeps this simple.
#
# This uses the LVGL checkout already present in this workspace
# (Reader2xx7/lvgl/, one directory up) rather than the copy vendored inside
# lv_binding_micropython for the MicroPython build -- both are 9.3.0, so
# either works, but this one doesn't require reaching outside this project.
set(LVGL_DIR "${CMAKE_CURRENT_LIST_DIR}/../lvgl")
file(GLOB_RECURSE LVGL_SOURCES ${LVGL_DIR}/src/*.c)

# LV_CONF_PATH (an absolute path, as a compile definition) tells LVGL's own
# lv_conf_internal.h exactly which lv_conf.h to #include, instead of
# searching the include path for one named "lv_conf.h" -- must be visible
# to every translation unit that includes any lvgl header, LVGL's own
# sources and ours alike, since it controls struct layouts (LV_COLOR_DEPTH
# etc.) that both sides need to agree on.
add_compile_definitions(LV_CONF_PATH="${CMAKE_CURRENT_LIST_DIR}/lv_conf.h")

add_library(lvgl STATIC ${LVGL_SOURCES})
target_include_directories(lvgl PUBLIC
    # So `#include "lvgl/lvgl.h"` (used the same way modlvport.c used it)
    # resolves: this needs to be the *parent* of the lvgl/ directory, i.e.
    # Reader2xx7/ itself, since lvgl.h sits at LVGL_DIR's own root here
    # (${LVGL_DIR}/lvgl.h) rather than nested another level down the way
    # lv_binding_micropython's copy was.
    "${LVGL_DIR}/.."
)

# --- Drivers --------------------------------------------------------------
# Reused as-is from the MicroPython build (ports/rp2/nt35510_c,
# ports/rp2/cst3240_c, ports/rp2/sdio_rp2350) -- referenced in place rather
# than copied, so there's one copy of each driver and no risk of the two
# builds drifting apart. sdio_rp2350.cpp is the only C++ translation unit in
# this build (everything else is C) -- it's a plain pico-sdk PIO driver with
# extern "C" linkage, no MicroPython dependency, so it links in cleanly
# alongside src/SDIO.c (which ports modsdio.c's SD-card protocol layer, see
# that file's header comment).
set(MPY_RP2_DIR "/Users/thomas/micropython/ports/rp2")

add_executable(rpr480_bare
    src/main.c
    src/RV3028.c
    src/INA226.c
    src/WS2818.c
    src/LIS2DW12.c
    src/SDIO.c
    src/DRV2605L.c
    ${MPY_RP2_DIR}/nt35510_c/nt35510.c
    ${MPY_RP2_DIR}/cst3240_c/cst3240.c
    ${MPY_RP2_DIR}/sdio_rp2350/src/sdio_rp2350.cpp
)
target_include_directories(rpr480_bare PRIVATE
    ${MPY_RP2_DIR}
    ${MPY_RP2_DIR}/sdio_rp2350/include
)

target_link_libraries(rpr480_bare
    pico_stdlib
    hardware_gpio
    hardware_i2c
    hardware_pio
    hardware_dma
    hardware_clocks
    hardware_pwm
    lvgl
)

# USB CDC for stdio (printf), no UART -- matches how the board has actually
# been accessed all project (USB REPL in the MicroPython build).
pico_enable_stdio_usb(rpr480_bare 1)
pico_enable_stdio_uart(rpr480_bare 0)

pico_add_extra_outputs(rpr480_bare)
