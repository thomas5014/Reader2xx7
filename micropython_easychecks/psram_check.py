# psram_check.py — PSRAM tester for the reader2350 board.
#
# Hardware: APS6404L-3SQR-ZR, 64 Mbit (8 MB) QSPI PSRAM on the RP2350's
# QMI chip-select 1 (see boards/reader2350.h: READER_PSRAM_CS1_GPIO = 47).
# On RP2350, QMI CS1 is memory-mapped at physical address 0x11000000 —
# ordinary Cortex-M load/store instructions read and write it directly,
# there's no command protocol involved (unlike the NOR flash, PSRAM has
# no separate program/erase step). That's what makes it a good fit for
# viper/asm_thumb: the "driver" is just fast pointer arithmetic.
#
# IMPORTANT — heap interaction: if your MicroPython build for this board
# extends the gc heap into PSRAM (the usual way RP2350+PSRAM ports work,
# and consistent with the ~8.6 MB free heap seen in memory_check.py's
# recorded output), then 0x11000000 is *also* live Python heap. Poking
# raw addresses there directly, while other objects may be allocated in
# the same range, will corrupt the interpreter.
#
# So the default test below never touches the raw address directly.
# Instead it does exactly what memory_check.py already does: allocate a
# bytearray and let the normal allocator hand you real memory (which
# will be PSRAM once the ~520 KB of on-chip SRAM ahead of it in the heap
# is spoken for). That's still a completely genuine PSRAM test — the
# cells being written are physically in the PSRAM chip — it's just
# addressed as a Python object instead of a raw pointer, which is what
# keeps it safe to run from the REPL on real hardware.
#
# A raw-address mode is included at the bottom for anyone who has
# reserved a genuinely-unmanaged tail of PSRAM in their own firmware
# (e.g. shrunk the gc heap on purpose). It is NOT run by default.
from machine import freq
freq(266_000_000)
import gc
import time
import uctypes

import fast_ops as fo

# --- config -----------------------------------------------------------

# Leave this much heap alone (stack/other allocations need headroom;
# also avoids an allocation-of-almost-everything edge case in the GC).
RESERVE_BYTES = 96 * 1024

# Small window used for the per-bit walking pattern (bus/short test).
# Kept small deliberately: full-capacity coverage is already provided by
# the LFSR and address-pattern tests below; this one is about isolating
# individual stuck/shorted data lines, which doesn't need scale.
WALK_WORDS = 256

SEED = fo.DEFAULT_SEED

# Physical base of the QMI CS1 (PSRAM) memory-mapped window on RP2350.
# Only used by the optional raw-address test at the bottom of this file.
PSRAM_BASE = 0x11000000
PSRAM_SIZE = 8 * 1024 * 1024  # APS6404L-3SQR-ZR, 64 Mbit

# --- helpers ------------------------------------------------------------


def _mb_per_s(nbytes, elapsed_us):
    if elapsed_us <= 0:
        return float("inf")
    return nbytes / elapsed_us  # bytes/us == MB/s


def _report(name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    print("[{}] {}{}".format(status, name, "  " + detail if detail else ""))
    return ok


# --- tests over an already-allocated bytearray --------------------------


def test_const_pattern(addr, word_count, pattern, name):
    t0 = time.ticks_us()
    fo.asm_fill32(addr, pattern, word_count)
    t1 = time.ticks_us()
    bad = fo.asm_verify32(addr, pattern, word_count)
    t2 = time.ticks_us()

    write_us = time.ticks_diff(t1, t0)
    read_us = time.ticks_diff(t2, t1)
    nbytes = word_count * 4
    ok = bad == -1
    detail = "write {:.2f} MB/s, read {:.2f} MB/s".format(
        _mb_per_s(nbytes, write_us), _mb_per_s(nbytes, read_us)
    )
    if not ok:
        detail += "  first bad word #{} (addr 0x{:08x})".format(
            bad, addr + bad * 4
        )
    _report(name, ok, detail)
    return ok


def test_walking_bits(addr, word_count):
    ok = True
    for bit in range(32):
        pattern = 1 << bit
        fo.asm_fill32(addr, pattern, word_count)
        bad = fo.asm_verify32(addr, pattern, word_count)
        if bad != -1:
            print(
                "[FAIL] walking-1 bit {}: word #{} addr 0x{:08x}".format(
                    bit, bad, addr + bad * 4
                )
            )
            ok = False

        inv = (~pattern) & 0xFFFFFFFF
        fo.asm_fill32(addr, inv, word_count)
        bad = fo.asm_verify32(addr, inv, word_count)
        if bad != -1:
            print(
                "[FAIL] walking-0 bit {}: word #{} addr 0x{:08x}".format(
                    bit, bad, addr + bad * 4
                )
            )
            ok = False
    _report("walking 1s/0s ({} words x 32 bits x2)".format(word_count), ok)
    return ok


def test_address_pattern(addr, word_count):
    t0 = time.ticks_us()
    fo.asm_addr_fill32(addr, word_count)
    t1 = time.ticks_us()
    bad = fo.asm_addr_verify32(addr, word_count)
    t2 = time.ticks_us()

    write_us = time.ticks_diff(t1, t0)
    read_us = time.ticks_diff(t2, t1)
    nbytes = word_count * 4
    ok = bad == -1
    detail = "write {:.2f} MB/s, read {:.2f} MB/s".format(
        _mb_per_s(nbytes, write_us), _mb_per_s(nbytes, read_us)
    )
    if not ok:
        detail += "  first bad word #{} (addr 0x{:08x})".format(
            bad, addr + bad * 4
        )
    _report("address-in-data pattern", ok, detail)
    return ok


def test_lfsr_pattern(buf):
    t0 = time.ticks_us()
    fo.lfsr_fill_buf(buf, SEED)
    t1 = time.ticks_us()
    bad = fo.lfsr_verify_buf(buf, SEED)
    t2 = time.ticks_us()

    write_us = time.ticks_diff(t1, t0)
    read_us = time.ticks_diff(t2, t1)
    nbytes = len(buf)
    ok = bad == -1
    detail = "write {:.2f} MB/s, read {:.2f} MB/s (viper)".format(
        _mb_per_s(nbytes, write_us), _mb_per_s(nbytes, read_us)
    )
    if not ok:
        detail += "  first bad word #{} (addr 0x{:08x})".format(
            bad, uctypes.addressof(buf) + bad * 4
        )
    _report("LFSR pseudo-random pattern", ok, detail)
    return ok


# --- main flow ------------------------------------------------------------


def run(test_bytes=None):
    gc.collect()
    free_before = gc.mem_free()
    print("=== psram_check ===")
    print("APS6404L-3SQR-ZR, 8 MB QSPI PSRAM on QMI CS1 (GPIO47)")
    print("Free heap before allocation: {:,} bytes".format(free_before))
    if free_before < 2 * 1024 * 1024:
        print(
            "  NOTE: free heap is well under 8 MB — PSRAM may not be"
            " mapped into the heap by this firmware build. Internal"
            " RP2350B SRAM alone is ~520 KB, so a healthy PSRAM-backed"
            " build should show several MB free here."
        )

    if test_bytes is None:
        test_bytes = free_before - RESERVE_BYTES
    test_bytes -= test_bytes % 4  # word align
    if test_bytes <= 0:
        print("Not enough free heap to run a test.")
        return False

    # gc.mem_free() is *total* free bytes, not the size of the largest
    # contiguous free run — a single bytearray() needs the latter. If the
    # heap is fragmented, or PSRAM is a separate non-contiguous gc region
    # from internal SRAM (common on these ports), the biggest single
    # allocation can be well under mem_free(). Back off and retry rather
    # than assuming the first request will fit.
    buf = None
    attempt = test_bytes
    while attempt >= RESERVE_BYTES:
        try:
            print("Allocating {:,} bytes ({:.2f} MB) for testing...".format(
                attempt, attempt / (1024 * 1024)
            ))
            buf = bytearray(attempt)
            break
        except MemoryError:
            gc.collect()
            attempt = (attempt * 3) // 4
            attempt -= attempt % 4
    if buf is None:
        print("Could not allocate a usable test buffer.")
        return False

    test_bytes = len(buf)
    addr = uctypes.addressof(buf)
    word_count = test_bytes // 4
    print("Buffer at 0x{:08x} ({:,} bytes)".format(addr, test_bytes))

    results = []
    results.append(test_const_pattern(addr, word_count, 0x00000000, "all-zeros"))
    results.append(test_const_pattern(addr, word_count, 0xFFFFFFFF, "all-ones"))
    results.append(test_walking_bits(addr, WALK_WORDS))
    results.append(test_address_pattern(addr, word_count))
    results.append(test_lfsr_pattern(buf))

    del buf
    gc.collect()

    overall = all(results)
    print("=== {} ===".format("ALL TESTS PASSED" if overall else "FAILURES DETECTED"))
    return overall


# --- optional advanced mode: raw memory-mapped address range -------------
#
# Only meaningful if you know for certain the [base, base+size) range
# below is NOT part of the live gc heap (or any other running code's
# memory) at the moment this runs — e.g. you've reserved a fixed tail of
# PSRAM in your own board port and never handed it to the allocator. Do
# not call this against 0x11000000 on a stock heap-extended build; it
# will corrupt the interpreter.
#
#   import psram_check
#   psram_check.run_raw(base=0x11780000, size_bytes=512*1024)


def run_raw(base, size_bytes):
    word_count = size_bytes // 4
    print("=== psram_check (RAW MODE) ===")
    print("Testing 0x{:08x}..0x{:08x} directly. Make sure this range is".format(
        base, base + size_bytes
    ))
    print("NOT part of the live gc heap before running this.")

    ok = True
    ok &= test_const_pattern(base, word_count, 0x00000000, "all-zeros")
    ok &= test_const_pattern(base, word_count, 0xFFFFFFFF, "all-ones")
    ok &= test_walking_bits(base, min(WALK_WORDS, word_count))
    ok &= test_address_pattern(base, word_count)

    state = SEED
    t0 = time.ticks_us()
    state = fo.lfsr_fill_addr(base, word_count, state)
    t1 = time.ticks_us()
    bad = fo.lfsr_verify_addr(base, word_count, SEED)
    t2 = time.ticks_us()
    nbytes = size_bytes
    detail = "write {:.2f} MB/s, read {:.2f} MB/s (viper)".format(
        _mb_per_s(nbytes, time.ticks_diff(t1, t0)),
        _mb_per_s(nbytes, time.ticks_diff(t2, t1)),
    )
    ok &= _report("LFSR pseudo-random pattern", bad == -1, detail)

    print("=== {} ===".format("ALL TESTS PASSED" if ok else "FAILURES DETECTED"))
    return ok


if __name__ == "__main__":
    run()


# Result:
# === psram_check ===
# APS6404L-3SQR-ZR, 8 MB QSPI PSRAM on QMI CS1 (GPIO47)
# Free heap before allocation: 8,629,056 bytes
# Allocating 8,530,752 bytes (8.14 MB) for testing...
# Allocating 6,398,064 bytes (6.10 MB) for testing...
# Buffer at 0x1102eec0 (6,398,064 bytes)
# [PASS] all-zeros  write 15.55 MB/s, read 40.84 MB/s
# [PASS] all-ones  write 15.56 MB/s, read 40.84 MB/s
# [PASS] walking 1s/0s (256 words x 32 bits x2)
# [PASS] address-in-data pattern  write 15.56 MB/s, read 42.66 MB/s
# [PASS] LFSR pseudo-random pattern  write 3.08 MB/s, read 3.26 MB/s (viper)
# === ALL TESTS PASSED ===