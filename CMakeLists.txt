# == DO NOT EDIT THE FOLLOWING LINES for the Raspberry Pi Pico VS Code Extension to work ==
if(WIN32)
    set(USERHOME $ENV{USERPROFILE})
else()
    set(USERHOME $ENV{HOME})
endif()
set(sdkVersion 2.3.1)
set(toolchainVersion 15_2_Rel1)
set(picotoolVersion 2.3.1)
set(picoVscode ${USERHOME}/.pico-sdk/cmake/pico-vscode.cmake)
if (EXISTS ${picoVscode})
    include(${picoVscode})
endif()
# ====================================================================================
cmake_minimum_required(VERSION 3.13)

set(PICO_BOARD reader2350)
set(PICO_BOARD_HEADER_DIRS ${CMAKE_CURRENT_SOURCE_DIR}/boards)

include(${CMAKE_CURRENT_SOURCE_DIR}/pico_sdk_import.cmake)

project(reader_fw C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

pico_sdk_init()

file(GLOB_RECURSE LVGL_SOURCES ${CMAKE_CURRENT_SOURCE_DIR}/lvgl/src/*.c)
add_library(lvgl STATIC ${LVGL_SOURCES})
target_include_directories(lvgl PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/lvgl
)

add_executable(reader_fw
    main.c
    nt35510.c
)

target_link_libraries(reader_fw
    pico_stdlib
    hardware_gpio
    lvgl
)

pico_enable_stdio_usb(reader_fw 1)
pico_enable_stdio_uart(reader_fw 0)

pico_add_extra_outputs(reader_fw)
