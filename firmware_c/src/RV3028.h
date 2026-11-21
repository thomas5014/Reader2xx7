// RV3028.h -- C port of micropython_easychecks/rtc_check.py's RV3028 class
// (Micro Crystal RV-3028-C7 RTC). Faithfully transcribed, not redesigned --
// in particular the EEPROM backup-switchover sequence in rv3028_init() is
// copied register-for-register from the Python version, including its
// timing (t_UPDATE ~63ms), since that's exactly the kind of "already
// debugged once, don't re-derive it" logic nt35510_c/cst3240_c were built
// the same way around.
#pragma once

#include <stdint.h>
#include <stdbool.h>

// Call once at startup, before any other rv3028_* function.
void rv3028_init(void);

// A plain C struct standing in for the Python version's returned dict --
// same seven fields, same meaning. year is the full 4-digit year (e.g.
// 2026), not the RTC's internal 0-99 offset-from-2000 byte.
typedef struct {
    uint16_t year;
    uint8_t month;    // 1-12
    uint8_t date;     // 1-31 (day of month)
    uint8_t weekday;  // 0=Sunday .. 6=Saturday
    uint8_t hour;     // 0-23
    uint8_t minute;
    uint8_t second;
} rv3028_time_t;

bool rv3028_read_time(rv3028_time_t *out);
void rv3028_set_time(const rv3028_time_t *t);
