// SDIO.h -- see SDIO.c. Ported from micropython_easychecks-adjacent
// ports/rp2/modsdio.c: the proven SD-card-over-SDIO bring-up/read/write
// sequence, with the MicroPython VFS/mp_obj wrapper layer stripped out.
#pragma once

#include <stdint.h>
#include <stdbool.h>

// Call once at startup, before any other sdio_sdcard_* function. Brings the
// SD card up through CMD0..CMD16 (see SDIO.c for the full sequence) and
// leaves the bus running at SDIO_DEFAULT_SPEED (sdio_rp2350_config.h).
// Returns true on success.
bool sdio_sdcard_init(void);

// Read/write `count` consecutive 512-byte blocks starting at `sector`.
// `buf` must be word-aligned and at least count*512 bytes. Both retry
// transiently-failed transfers internally (matching the proven driver's
// SD_READ_ATTEMPTS/SD_WRITE_ATTEMPTS behavior) and return 0 on success,
// a negative value on failure.
int sdio_sdcard_read_blocks(uint32_t sector, uint8_t *buf, uint32_t count);
int sdio_sdcard_write_blocks(uint32_t sector, const uint8_t *buf, uint32_t count);

// Total card capacity in 512-byte sectors, valid after sdio_sdcard_init()
// succeeds.
uint32_t sdio_sdcard_sector_count(void);
