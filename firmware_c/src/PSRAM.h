// PSRAM.h -- see PSRAM.c. Ported from ports/rp2/rp2_psram.c: QMI-level
// PSRAM (XIP chip-select 1) detect + bring-up. The MicroPython GC-heap
// wiring (gc_init/gc_add onto the PSRAM range) is deliberately NOT
// ported -- there's no GC heap here to extend. What this gives you is
// just the chip brought up and memory-mapped; what you put there
// (ring buffer or otherwise) is a separate later step.
#pragma once

#include <stddef.h>

// Memory-mapped base address for PSRAM once psram_bringup() succeeds --
// same address ports/rp2/rp2_psram.h calls PSRAM_BASE (QMI chip-select
// 1's XIP window). Ordinary loads/stores to
// [PSRAM_BASE, PSRAM_BASE + psram_bringup()'s return value) just work
// once bring-up has run -- no separate read/write API needed.
#define PSRAM_BASE 0x11000000u

// Detect and configure the PSRAM chip on the given XIP chip-select pin
// (GPIO47 on RPR480 -- see rpr480_board.h / the MicroPython build's
// MICROPY_HW_PSRAM_CS_PIN). Returns the detected size in bytes, or 0 if
// no PSRAM chip was found. Call once, early -- see PSRAM.c's header
// comment for why "early" matters here more than for the other
// drivers.
size_t psram_bringup(unsigned int cs_pin);
