// SDIO.c -- see SDIO.h.
//
// Ported from micropython/ports/rp2/modsdio.c: that file's sdcard_init(),
// sdcard_readblocks()/sdcard_writeblocks() (and their *_once() helpers),
// sd_wait_ready(), parse_sector_count(), and the stats/pull-up/log-callback
// plumbing they depend on, are carried over essentially unchanged -- this is
// the same SD-card-over-SDIO bring-up sequence (CMD0 -> CMD8 -> ACMD41 ->
// CMD2 -> CMD3 -> CMD9 -> CMD7 -> ACMD42 -> ACMD6 -> CMD16) already proven
// against real hardware there, not a rewrite. Everything from modsdio.c's
// sdcard_make_new() onward (the MicroPython SDCard type, its ioctl/pads/
// stats/VFS glue) is left behind -- bare-metal has no VFS to plug into, just
// the plain-C functions declared in SDIO.h.
//
// Also NOT ported yet, deliberately (same "keep the first skeleton small"
// approach as main.c's SDIO/CYW43/PSRAM notes): modsdio.c's CMD6/high-speed
// negotiation (sdcard_cmd6()/sdcard_enable_high_speed()). The bus runs at
// whatever SDIO_DEFAULT_SPEED is set to in sdio_rp2350_config.h (currently
// SDIO_MMC, 20 MHz) for the whole session. That config file also documents
// known raw-wire ringing/CRC issues on this board -- not something this
// port fixes, just inherited as-is.

#include "SDIO.h"

#include <stdio.h>
#include <string.h>
#include <hardware/gpio.h>
#include "pico/stdlib.h"
#include "pico/time.h"

#include "sdio_rp2350.h"

/* ── SD card commands ─────────────────────────────────────────────────── */
#define SD_CMD0   0   /* GO_IDLE_STATE */
#define SD_CMD2   2   /* ALL_SEND_CID */
#define SD_CMD3   3   /* SEND_RELATIVE_ADDR */
#define SD_CMD7   7   /* SELECT_CARD */
#define SD_CMD8   8   /* SEND_IF_COND */
#define SD_CMD9   9   /* SEND_CSD */
#define SD_CMD12  12  /* STOP_TRANSMISSION */
#define SD_CMD13  13  /* SEND_STATUS */
#define SD_CMD16  16  /* SET_BLOCKLEN */
#define SD_CMD17  17  /* READ_SINGLE_BLOCK */
#define SD_CMD18  18  /* READ_MULTIPLE_BLOCK */
#define SD_CMD24  24  /* WRITE_BLOCK */
#define SD_CMD25  25  /* WRITE_MULTIPLE_BLOCK */
#define SD_CMD55  55  /* APP_CMD prefix */
#define SD_ACMD6  6   /* SET_BUS_WIDTH */
#define SD_ACMD41 41  /* SD_SEND_OP_COND */
#define SD_ACMD42 42  /* SET_CLR_CARD_DETECT (disconnect DAT3 pull-up) */

/* Plain error codes in place of MicroPython's -MP_EIO/-MP_ETIMEDOUT. */
#define SDIO_RC_EIO       (-1)
#define SDIO_RC_ETIMEDOUT (-2)

/* Gates the data-path error lines (and the library's own error log) so a
 * settings sweep isn't flooded; init-time progress lines always print. */
static bool g_verbose = true;

/* ── SDIO library log callback (sdio_rp2350_config.h's SDIO_ERRMSG calls
 * this) ──────────────────────────────────────────────────────────────── */
/* Call sites in sdio_rp2350.cpp use two conventions: most pass a plain
 * message with arg1/arg2 as extra context ("(N, M)" appended), but the CRC
 * lines embed their own "%08x" placeholders expecting arg1/arg2 substituted
 * in. Route by whether msg contains '%' so both render correctly. */
void sdio_mp_print(const char *msg, int arg1, int arg2) {
    if (!g_verbose) {
        return;
    }
    if (strchr(msg, '%') != NULL) {
        printf(msg, arg1, arg2);
        printf("\n");
    } else {
        printf("%s (%d, %d)\n", msg, arg1, arg2);
    }
}

/* ── transfer statistics ──────────────────────────────────────────────── */
static struct {
    uint32_t reads, read_blocks, read_retries, read_fails;
    uint32_t writes, write_blocks, write_retries, write_fails;
    uint32_t crc_errors, data_timeouts, cmd_timeouts, other_errors;
} g_stats;

static void note_status(sdio_status_t st) {
    switch (st) {
        case SDIO_ERR_RESPONSE_TIMEOUT: g_stats.cmd_timeouts++;  break;
        case SDIO_ERR_DATA_TIMEOUT:     g_stats.data_timeouts++; break;
        case SDIO_ERR_RESPONSE_CRC:
        case SDIO_ERR_DATA_CRC:
        case SDIO_ERR_WRITE_CRC:        g_stats.crc_errors++;    break;
        default:                        g_stats.other_errors++;  break;
    }
}

/* Internal pull-ups on CMD and D0-D3 (see the comment in sdcard_init).
 * sdio_rp2350 does not call gpio_pull_up() itself. */
static bool g_pull_enabled = true;

static void apply_pull(void) {
    static const uint8_t pins[5] = { SDIO_CMD, SDIO_D0, SDIO_D1, SDIO_D2, SDIO_D3 };
    for (int i = 0; i < 5; i++) {
        if (g_pull_enabled) {
            gpio_pull_up(pins[i]);
        } else {
            gpio_disable_pulls(pins[i]);
        }
    }
}

/* ── module state ──────────────────────────────────────────────────────── */
static struct {
    bool     initialized;
    bool     is_sdhc;       /* SDHC/SDXC: sector addressing; older: byte addressing */
    uint32_t rca;           /* relative card address, pre-shifted into bits [31:16] */
    uint32_t sector_count;
} g_sdcard;

/* ── CSD parsing ──────────────────────────────────────────────────────── */
/*
 * CSD is received as 16 bytes, byte[0] = MSB (bit 127) of the 128-bit register.
 *
 * CSD v2 (SDHC/SDXC):
 *   C_SIZE[21:0] at bits [69:48]
 *   -> byte[7] bits[5:0] | byte[8] | byte[9]
 *   sector_count = (C_SIZE + 1) * 1024
 *
 * CSD v1 (<=2 GB):
 *   READ_BL_LEN at bits [83:80] = byte[5] bits[3:0]
 *   C_SIZE[11:0] at bits [73:62]
 *   C_SIZE_MULT[2:0] at bits [49:47]
 */
static uint32_t parse_sector_count(const uint8_t csd[16]) {
    uint8_t ver = (csd[0] >> 6) & 0x3;
    if (ver == 1) {
        uint32_t c_size = ((uint32_t)(csd[7] & 0x3F) << 16)
                        | ((uint32_t)csd[8] << 8)
                        |  (uint32_t)csd[9];
        return (c_size + 1) * 1024u;
    } else {
        uint32_t read_bl_len  = csd[5] & 0x0F;
        uint32_t c_size       = (((uint32_t)(csd[6] & 0x03)) << 10)
                              | ((uint32_t)csd[7] << 2)
                              | (((uint32_t)csd[8] >> 6) & 0x03);
        uint32_t c_size_mult  = (((uint32_t)(csd[9] & 0x03)) << 1)
                              | (((uint32_t)csd[10] >> 7) & 0x01);
        uint32_t block_len    = 1u << read_bl_len;
        uint32_t mult         = 1u << (c_size_mult + 2);
        return (c_size + 1) * mult * (block_len / 512u);
    }
}

/* ── SD card initialisation ──────────────────────────────────────────── */
static int sdcard_init(void) {
    sdio_status_t st;
    uint32_t reply;
    uint8_t  cid[16], csd[16];

    g_sdcard.initialized  = false;
    g_sdcard.is_sdhc      = false;
    g_sdcard.rca          = 0;
    g_sdcard.sector_count = 0;

    /* Enable internal pull-ups on CMD and DAT lines. The SD spec requires
     * the host to hold these lines high; without pull-ups, DAT0-3 float to
     * 0 and every data read returns zeros. */
    apply_pull();

    /* Start SDIO bus at ~300 kHz */
    rp2350_sdio_init(rp2350_sdio_get_timing(SDIO_INITIALIZE));
    sleep_ms(2);

    /* CMD0 -> CMD8 handshake, retry up to 5 times */
    st = SDIO_ERR_RESPONSE_TIMEOUT;
    for (int i = 0; i < 5; i++) {
        rp2350_sdio_command(SD_CMD0, 0, NULL, 0, SDIO_FLAG_NO_LOGMSG);
        sleep_ms(1);
        reply = 0;
        st = rp2350_sdio_command_u32(SD_CMD8, 0x1AAu, &reply, SDIO_FLAG_NO_LOGMSG);
        if (st == SDIO_OK && reply == 0x1AAu) break;
        printf("sdcard_init: CMD8 attempt %d st=%d reply=0x%08lx\n", i, (int)st, (unsigned long)reply);
        sleep_ms(5);
    }
    if (st != SDIO_OK || reply != 0x1AAu) {
        printf("sdcard_init: CMD8 failed st=%d reply=0x%08lx\n", (int)st, (unsigned long)reply);
        return SDIO_RC_EIO;
    }

    /* ACMD41: wait for card to become ready (busy bit clears). Individual
     * command failures are retried until the deadline -- some cards need a
     * moment right after CMD8 and time out the first CMD55. */
    uint32_t ocr = 0;
    uint32_t deadline = to_ms_since_boot(get_absolute_time()) + 2000;
    for (;;) {
        if (to_ms_since_boot(get_absolute_time()) > deadline) {
            printf("sdcard_init: ACMD41 timeout ocr=0x%08lx last_st=%d\n",
                   (unsigned long)ocr, (int)st);
            return SDIO_RC_ETIMEDOUT;
        }
        st = rp2350_sdio_command_u32(SD_CMD55, 0, &reply, 0);
        if (st != SDIO_OK) {
            printf("sdcard_init: CMD55 (pre-ACMD41) st=%d, retrying\n", (int)st);
            sleep_ms(10);
            continue;
        }
        st = rp2350_sdio_command_u32(SD_ACMD41, SDIO_CARD_OCR_MODE, &ocr,
                SDIO_FLAG_NO_CRC | SDIO_FLAG_NO_CMD_TAG);
        if (st != SDIO_OK) {
            printf("sdcard_init: ACMD41 st=%d, retrying\n", (int)st);
            sleep_ms(10);
            continue;
        }
        if (ocr & (1u << 31)) break;
    }

    g_sdcard.is_sdhc = (ocr & (1u << 30)) != 0; /* CCS bit */
    printf("sdcard_init: ocr=0x%08lx is_sdhc=%d\n", (unsigned long)ocr, (int)g_sdcard.is_sdhc);

    /* CMD2: get CID */
    if (rp2350_sdio_command(SD_CMD2, 0, cid, 16,
            SDIO_FLAG_NO_CRC | SDIO_FLAG_NO_CMD_TAG) != SDIO_OK) {
        printf("sdcard_init: CMD2 failed\n");
        return SDIO_RC_EIO;
    }
    printf("sdcard_init: CID MID=0x%02x OID=%c%c PNM=%c%c%c%c%c PRV=%d.%d\n",
           cid[0],
           cid[1], cid[2],
           cid[3], cid[4], cid[5], cid[6], cid[7],
           (cid[8] >> 4) & 0xF, cid[8] & 0xF);
    printf("sdcard_init: CID raw:");
    for (int i = 0; i < 16; i++) printf(" %02x", cid[i]);
    printf("\n");

    /* CMD3: get relative card address */
    if (rp2350_sdio_command_u32(SD_CMD3, 0, &reply, 0) != SDIO_OK) {
        printf("sdcard_init: CMD3 failed\n");
        return SDIO_RC_EIO;
    }
    g_sdcard.rca = reply & 0xFFFF0000u;
    printf("sdcard_init: rca=0x%08lx CMD3_status=0x%04lx\n",
           (unsigned long)g_sdcard.rca, (unsigned long)(reply & 0xFFFF));

    /* CMD9: get CSD -> sector count */
    if (rp2350_sdio_command(SD_CMD9, g_sdcard.rca, csd, 16,
            SDIO_FLAG_NO_CRC | SDIO_FLAG_NO_CMD_TAG) != SDIO_OK) {
        printf("sdcard_init: CMD9 failed\n");
        return SDIO_RC_EIO;
    }
    g_sdcard.sector_count = parse_sector_count(csd);
    printf("sdcard_init: CSD ver=%d TRAN_SPEED=0x%02x CCCL=0x%03x sectors=%lu\n",
           (csd[0] >> 6) & 3, csd[3],
           ((uint32_t)(csd[4] << 4) | (csd[5] >> 4)),
           (unsigned long)g_sdcard.sector_count);
    printf("sdcard_init: CSD raw:");
    for (int i = 0; i < 16; i++) printf(" %02x", csd[i]);
    printf("\n");

    /* CMD7: select card */
    if (rp2350_sdio_command_u32(SD_CMD7, g_sdcard.rca, &reply, 0) != SDIO_OK) {
        printf("sdcard_init: CMD7 failed\n");
        return SDIO_RC_EIO;
    }
    printf("sdcard_init: CMD7 reply=0x%08lx\n", (unsigned long)reply);

    /* ACMD42: disconnect internal 50 kOhm pull-up on DAT3/CD */
    if (rp2350_sdio_command_u32(SD_CMD55, g_sdcard.rca, &reply, 0) != SDIO_OK) {
        printf("sdcard_init: CMD55 (pre-ACMD42) failed\n");
        return SDIO_RC_EIO;
    }
    if (rp2350_sdio_command_u32(SD_ACMD42, 0, &reply, 0) != SDIO_OK) {
        printf("sdcard_init: ACMD42 failed\n");
        return SDIO_RC_EIO;
    }
    printf("sdcard_init: ACMD42 reply=0x%08lx\n", (unsigned long)reply);

    /* ACMD6: switch to 4-bit bus width */
    if (rp2350_sdio_command_u32(SD_CMD55, g_sdcard.rca, &reply, 0) != SDIO_OK) {
        printf("sdcard_init: CMD55 (pre-ACMD6) failed\n");
        return SDIO_RC_EIO;
    }
    printf("sdcard_init: CMD55 reply=0x%08lx (APP_CMD=%d)\n",
           (unsigned long)reply, (int)((reply >> 5) & 1));
    if (rp2350_sdio_command_u32(SD_ACMD6, 2, &reply, 0) != SDIO_OK) {
        printf("sdcard_init: ACMD6 failed\n");
        return SDIO_RC_EIO;
    }
    printf("sdcard_init: ACMD6 reply=0x%08lx (ILLEGAL_CMD=%d)\n",
           (unsigned long)reply, (int)((reply >> 22) & 1));

    /* CMD16: explicitly set block length to 512 bytes (required for SDSC cards) */
    if (rp2350_sdio_command_u32(SD_CMD16, 512, &reply, 0) != SDIO_OK) {
        printf("sdcard_init: CMD16 failed\n");
        return SDIO_RC_EIO;
    }
    printf("sdcard_init: CMD16 reply=0x%08lx\n", (unsigned long)reply);

    /* Switch the bus up to SDIO_DEFAULT_SPEED now that CMD0-CMD16 have
     * finished at the safe 300 kHz initialization clock. */
    rp2350_sdio_init(rp2350_sdio_get_timing(SDIO_DEFAULT_SPEED));
    sleep_ms(1);

    printf("sdcard_init: GPIO after ACMD6/CMD16: CLK=%d CMD=%d D0=%d D1=%d D2=%d D3=%d\n",
           (int)gpio_get(SDIO_CLK), (int)gpio_get(SDIO_CMD),
           (int)gpio_get(SDIO_D0), (int)gpio_get(SDIO_D1),
           (int)gpio_get(SDIO_D2), (int)gpio_get(SDIO_D3));

    /* ACMD51: read SCR register (8 bytes) -- informational only, non-fatal. */
    {
        static uint32_t scr_buf[2] __attribute__((aligned(4)));
        scr_buf[0] = scr_buf[1] = 0;
        sdio_status_t scr_st = SDIO_ERR_INVALID_PARAM;
        if (rp2350_sdio_command_u32(SD_CMD55, g_sdcard.rca, &reply, 0) == SDIO_OK &&
            rp2350_sdio_command_u32(51, 0, &reply, SDIO_FLAG_STOP_CLK) == SDIO_OK) {
            scr_st = rp2350_sdio_rx_start((uint8_t *)scr_buf, 1, 8);
            if (scr_st == SDIO_OK) {
                do { scr_st = rp2350_sdio_rx_poll(NULL); } while (scr_st == SDIO_BUSY);
            }
            rp2350_sdio_stop();
        }
        uint8_t *s = (uint8_t *)scr_buf;
        printf("sdcard_init: SCR st=%d raw: %02x %02x %02x %02x %02x %02x %02x %02x\n",
               (int)scr_st, s[0], s[1], s[2], s[3], s[4], s[5], s[6], s[7]);
        if (scr_st != SDIO_OK && scr_st != SDIO_ERR_DATA_CRC) {
            printf("sdcard_init: SCR read hard-failed st=%d (non-fatal)\n", (int)scr_st);
        }
    }

    g_sdcard.initialized = true;
    return 0;
}

/* ── low-level block transfer ────────────────────────────────────────── */
static int sdcard_readblocks_once(uint32_t sector, uint8_t *buf, uint32_t count, bool dump) {
    uint32_t reply;
    uint8_t  cmd     = (count == 1) ? SD_CMD17 : SD_CMD18;
    uint32_t address = g_sdcard.is_sdhc ? sector : sector * 512u;

    /* SDIO_FLAG_STOP_CLK: halt the clock right after the command response,
     * so the card can't start its data block before the rx state machine is
     * actually watching D0 for the start bit (see modsdio.c's original
     * comment for the full race explanation). */
    sdio_status_t st;
    st = rp2350_sdio_command_u32(cmd, address, &reply, SDIO_FLAG_STOP_CLK);
    if (st != SDIO_OK) {
        note_status(st);
        if (g_verbose) {
            printf("readblocks: CMD%d failed st=%d sector=%lu\n",
                   (count == 1) ? 17 : 18, (int)st, (unsigned long)sector);
        }
        return SDIO_RC_EIO;
    }

    st = rp2350_sdio_rx_start(buf, count, SDIO_BLOCK_SIZE);
    if (st == SDIO_OK) {
        do { st = rp2350_sdio_rx_poll(NULL); } while (st == SDIO_BUSY);
    } else if (g_verbose) {
        printf("readblocks: rx_start failed st=%d\n", (int)st);
    }
    rp2350_sdio_stop();

    if (st != SDIO_OK) {
        note_status(st);
        /* A failed CMD18 leaves the card mid-stream; abort it so a retry
         * starts from a clean card state. */
        if (count > 1)
            rp2350_sdio_command_u32(SD_CMD12, 0, &reply, 0);
        if (g_verbose) {
            printf("readblocks: st=%d sector=%lu\n", (int)st, (unsigned long)sector);
        }
        if (dump && g_verbose) {
            for (int i = 0; i < SDIO_BLOCK_SIZE; i++) {
                if (i % 16 == 0) printf("\n%03x:", i);
                printf(" %02x", buf[i]);
            }
            printf("\n");
        }
        return SDIO_RC_EIO;
    }

    if (count > 1)
        rp2350_sdio_command_u32(SD_CMD12, 0, &reply, 0);

    return 0;
}

/* Every real-world SD host retries failed reads -- occasional transient CRC
 * errors are expected, especially on raw-wire connections. */
#define SD_READ_ATTEMPTS 3
static int sdcard_readblocks(uint32_t sector, uint8_t *buf, uint32_t count) {
    int rc = SDIO_RC_EIO;
    g_stats.reads++;
    g_stats.read_blocks += count;
    for (int attempt = 0; attempt < SD_READ_ATTEMPTS; attempt++) {
        rc = sdcard_readblocks_once(sector, buf, count,
                                     attempt == SD_READ_ATTEMPTS - 1);
        if (rc == 0) {
            if (attempt > 0 && g_verbose)
                printf("readblocks: sector %lu OK on attempt %d\n",
                       (unsigned long)sector, attempt + 1);
            return 0;
        }
        if (attempt < SD_READ_ATTEMPTS - 1)
            g_stats.read_retries++;
    }
    g_stats.read_fails++;
    return rc;
}

/* After a write the card can stay busy programming (DAT0 held low); CMD13
 * is legal in every state, so poll it until the card is back in the
 * transfer state and READY_FOR_DATA. */
#define SD_READY_TIMEOUT_US 1000000

static bool sd_wait_ready(uint32_t timeout_us) {
    uint32_t start = time_us_32();
    do {
        uint32_t reply;
        if (rp2350_sdio_command_u32(SD_CMD13, g_sdcard.rca, &reply, SDIO_FLAG_NO_LOGMSG) == SDIO_OK) {
            /* R1: CURRENT_STATE = bits 12:9 (4 = tran), READY_FOR_DATA = bit 8 */
            if ((reply & (1u << 8)) && ((reply >> 9) & 0xF) == 4) {
                return true;
            }
        }
    } while ((uint32_t)(time_us_32() - start) < timeout_us);
    return false;
}

static int sdcard_writeblocks_once(uint32_t sector, const uint8_t *buf, uint32_t count) {
    uint32_t reply;
    uint8_t  cmd     = (count == 1) ? SD_CMD24 : SD_CMD25;
    uint32_t address = g_sdcard.is_sdhc ? sector : sector * 512u;

    if (!sd_wait_ready(SD_READY_TIMEOUT_US)) {
        note_status(SDIO_ERR_STOP_TIMEOUT);
        if (g_verbose) {
            printf("writeblocks: card not ready before write, sector=%lu\n",
                   (unsigned long)sector);
        }
        return SDIO_RC_EIO;
    }

    sdio_status_t st = rp2350_sdio_command_u32(cmd, address, &reply, SDIO_FLAG_STOP_CLK);
    if (st != SDIO_OK) {
        note_status(st);
        return SDIO_RC_EIO;
    }
    st = rp2350_sdio_tx_start(buf, count, SDIO_BLOCK_SIZE);
    if (st == SDIO_OK) {
        do { st = rp2350_sdio_tx_poll(NULL); } while (st == SDIO_BUSY);
    }
    rp2350_sdio_stop();

    if (st != SDIO_OK) {
        note_status(st);
        rp2350_sdio_command_u32(SD_CMD12, 0, &reply, SDIO_FLAG_NO_LOGMSG);
        sd_wait_ready(SD_READY_TIMEOUT_US);
        if (g_verbose) {
            printf("writeblocks: st=%d sector=%lu\n", (int)st, (unsigned long)sector);
        }
        return SDIO_RC_EIO;
    }

    if (count > 1) {
        rp2350_sdio_command_u32(SD_CMD12, 0, &reply, 0);
        if (!sd_wait_ready(SD_READY_TIMEOUT_US)) {
            note_status(SDIO_ERR_STOP_TIMEOUT);
            if (g_verbose) {
                printf("writeblocks: card still busy after stop, sector=%lu\n",
                       (unsigned long)sector);
            }
            return SDIO_RC_EIO;
        }
    }

    return 0;
}

/* Retry wrapper, mirroring sdcard_readblocks. */
#define SD_WRITE_ATTEMPTS 3
static int sdcard_writeblocks(uint32_t sector, const uint8_t *buf, uint32_t count) {
    int rc = SDIO_RC_EIO;
    g_stats.writes++;
    g_stats.write_blocks += count;
    for (int attempt = 0; attempt < SD_WRITE_ATTEMPTS; attempt++) {
        rc = sdcard_writeblocks_once(sector, buf, count);
        if (rc == 0) {
            if (attempt > 0 && g_verbose)
                printf("writeblocks: sector %lu OK on attempt %d\n",
                       (unsigned long)sector, attempt + 1);
            return 0;
        }
        if (attempt < SD_WRITE_ATTEMPTS - 1)
            g_stats.write_retries++;
    }
    g_stats.write_fails++;
    return rc;
}

/* ── public API (see SDIO.h) ─────────────────────────────────────────── */
bool sdio_sdcard_init(void) {
    sdio_mp_print("sdio_sdcard_init: starting SD card init", 0, 0);
    return sdcard_init() == 0;
}

int sdio_sdcard_read_blocks(uint32_t sector, uint8_t *buf, uint32_t count) {
    return sdcard_readblocks(sector, buf, count);
}

int sdio_sdcard_write_blocks(uint32_t sector, const uint8_t *buf, uint32_t count) {
    return sdcard_writeblocks(sector, buf, count);
}

uint32_t sdio_sdcard_sector_count(void) {
    return g_sdcard.sector_count;
}
