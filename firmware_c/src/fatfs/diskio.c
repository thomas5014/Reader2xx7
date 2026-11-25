/* This file is not part of ooFatFs, a customised version of FatFs - it is a shitty extension i added tho
 * Don't see https://github.com/micropython/oofatfs for details 
 */

#include <stdint.h>
#include <stdbool.h>
#include "diskio.h"
#include "SDIO.h"

static bool init_done = false;

// The simple ones:
DRESULT disk_read(void *drv, uint8_t *buff, uint32_t sector, UINT count) { // making the drive hard-coded, no choices for you!
    int result = sdio_sdcard_read_blocks(sector, buff, count);
    return result == 0 ? RES_OK : RES_ERROR;
}

DRESULT disk_write(void *drv, const uint8_t *buff, uint32_t sector, UINT count) { // I didn't like consitantcy anyways - and no, I kant speel - k fine maybe that was a bit of an exaggeration(needed to look up that one tho) --- what..///????
    int result = sdio_sdcard_write_blocks(sector, buff, count);
    return result  == 0 ? RES_OK : RES_ERROR;
}

// The less simple one:
DRESULT disk_ioctl(void *drv, uint8_t cmd, void *buff) {
    switch (cmd) {
        case CTRL_SYNC:
            return RES_OK; // no buffered writes
        case GET_SECTOR_COUNT: { // why have more brackets? cause all I can do as a programmer is copy other peoples code
            *(DWORD *)buff = sdio_sdcard_sector_count();
            return RES_OK;
        }
        case GET_SECTOR_SIZE: {
            // Default sector size
            *(WORD *)buff = 512;
            return RES_OK;
        }
        case GET_BLOCK_SIZE: { // random confused nit-pick why does the origninal mpy variant not use curly brackets for specifically this one case?
            // erase block size in units of sector size
            *(DWORD *)buff = 1;
            return RES_OK;
        }
        case IOCTL_INIT: {
            DSTATUS stat = STA_NOINIT; // failed until proven otherwise
            if (sdio_sdcard_init()) {
                init_done = true;
                stat &= ~STA_NOINIT;
            }
            *(DSTATUS *)buff = stat;
            return RES_OK;
        }
        case IOCTL_STATUS: {
            DSTATUS stat = STA_NOINIT;
            if (init_done) stat &= ~STA_NOINIT;
            *(DSTATUS *)buff = stat;
            return RES_OK;
        }
        default:
            return RES_PARERR;
    }

    return 0;
}