# nor_flash_check.py — NOR flash tester for the reader2350 board.
#
# Hardware: W25Q128JVPIQ, 128 Mbit (16 MB) QSPI NOR flash. Unlike the
# PSRAM tester's chip, this *is* the boot/XIP flash — the same chip that
# holds this firmware and the filesystem you're reading this script
# from. Two consequences drove the design here:
#
#   1. There's no separate machine.SPI bus to it. The W25Q128's QSPI
#      lines are dedicated bootrom/QMI pins, not routed through a
#      general-purpose SPI peripheral, so the usual "bit-bang 0x9F and
#      read the JEDEC ID" approach used for an *external* SPI flash chip
#      simply isn't available here. The one safe, always-available way
#      to prove the chip is alive and talking is machine.unique_id() —
#      on the rp2 port this reads the flash's 64-bit unique serial
#      number via the bootrom's RUID command (the same mechanism
#      pico_get_unique_id() uses in C), executed safely from RAM with
#      interrupts disabled.
#
#   2. Raw sector erase/program against arbitrary flash offsets is
#      genuinely dangerous on this chip: whatever isn't firmware is very
#      likely already claimed by the filesystem (a 16 MB chip commonly
#      shows ~14-15 MB already partitioned to the VFS, leaving no
#      confirmed-free raw region at the Python level). So the default
#      test here goes through the filesystem — write/read/verify/delete
#      a scratch file — which cannot corrupt anything else because the
#      flash driver's own wear-levelling/erase logic is doing the actual
#      sector management underneath, exactly as it would for any file
#      you save. It's still real flash program/erase cycles, just
#      addressed through open()/write() instead of raw block numbers.
#
# A raw rp2.Flash() block-device mode is included at the bottom for
# anyone who has an actual reserved/unpartitioned region to point it at.
# It is NOT run by default, and its offset must be supplied explicitly —
# there is no offset this script could guess that's safe on every build.

import gc
import os
import time
import uctypes
import machine

import fast_ops as fo

# --- config -------------------------------------------------------------

TEST_FILE = "/nor_flash_test.tmp"
CHUNK_SIZE = 4096  # matches the flash's erase-sector size
TEST_SIZE = 1 * 1024 * 1024  # 1 MB default; bump this up for more coverage
SEED = fo.DEFAULT_SEED

# Real NOR sector erase/program is slow (tens to hundreds of ms per 4 KB
# sector on the W25Q128, and RP2 stalls XIP — so nothing else runs either
# — while it happens). With no output during a 256-chunk loop, a working
# test and a genuinely hung one look identical from the REPL. Print
# progress this often instead.
PROGRESS_EVERY = 16  # chunks

CRC_INIT = 0xFFFFFFFF  # standard CRC-32 (IEEE 802.3) seed/final-xor
CRC_XOROUT = 0xFFFFFFFF


def _mb_per_s(nbytes, elapsed_us):
    if elapsed_us <= 0:
        return float("inf")
    return nbytes / elapsed_us  # bytes/us == MB/s


def _report(name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    print("[{}] {}{}".format(status, name, "  " + detail if detail else ""))
    return ok


# --- identification -------------------------------------------------------


def check_identification():
    print("W25Q128JVPIQ, 16 MB QSPI NOR flash (boot/XIP flash)")
    uid = machine.unique_id()
    ok = len(uid) == 8
    hexid = "".join("{:02x}".format(b) for b in uid)
    _report(
        "flash responds (unique ID via bootrom RUID)",
        ok,
        "id=0x{} ({} bytes)".format(hexid, len(uid)),
    )
    return ok


# --- file-based data integrity + throughput -------------------------------


def _preflight_single_chunk(chunk_size=CHUNK_SIZE):
    # Write, read back, and verify exactly one sector before committing to
    # the full loop. This is the fast/cheap way to tell "the flash write
    # path works but is just slow" apart from "the very first write hangs"
    # — the latter points at the firmware's flash-safe-execute path
    # (interrupts/other core parked during the XIP stall), not this script.
    buf = bytearray(chunk_size)
    fo.lfsr_fill_buf(buf, SEED)
    t0 = time.ticks_us()
    with open(TEST_FILE, "wb") as f:
        f.write(buf)
    t1 = time.ticks_us()
    readback = bytearray(chunk_size)
    with open(TEST_FILE, "rb") as f:
        f.readinto(readback)
    t2 = time.ticks_us()
    try:
        os.remove(TEST_FILE)
    except OSError:
        pass

    ok = readback == buf
    print(
        "  preflight: 1 chunk ({} bytes) write {} ms, read {} ms -> {}".format(
            chunk_size,
            time.ticks_diff(t1, t0) // 1000,
            time.ticks_diff(t2, t1) // 1000,
            "OK" if ok else "MISMATCH",
        )
    )
    return ok


def check_file_roundtrip(test_size=TEST_SIZE, chunk_size=CHUNK_SIZE):
    assert test_size % chunk_size == 0, "test_size must be a multiple of chunk_size"
    n_chunks = test_size // chunk_size

    if not _preflight_single_chunk(chunk_size):
        print("[FAIL] preflight single-chunk write/read failed — not"
              " attempting the full round trip.")
        return False

    stat = os.statvfs("/")
    free_bytes = stat[0] * stat[3]
    print("Filesystem free space: {:,} bytes".format(free_bytes))
    if free_bytes < test_size * 2:
        print(
            "[FAIL] not enough free space for a {:,}-byte round trip"
            " with safety margin — reduce TEST_SIZE.".format(test_size)
        )
        return False

    buf = bytearray(chunk_size)
    addr = uctypes.addressof(buf)
    seeds = []  # per-chunk starting LFSR state, so verify can address
    # any chunk independently without needing to chain through a
    # streaming read the way the write side chains through a stream.

    print("Writing {:,} bytes ({} chunks of {})...".format(
        test_size, n_chunks, chunk_size
    ))
    state = SEED
    crc = CRC_INIT
    t0 = time.ticks_us()
    with open(TEST_FILE, "wb") as f:
        for i in range(n_chunks):
            seeds.append(state)
            state = fo.lfsr_fill_buf(buf, state)
            crc = fo.asm_crc32(addr, chunk_size, crc)
            f.write(buf)
            if (i + 1) % PROGRESS_EVERY == 0 or i + 1 == n_chunks:
                elapsed_ms = time.ticks_diff(time.ticks_us(), t0) // 1000
                print("  ...{}/{} chunks written ({} ms elapsed)".format(
                    i + 1, n_chunks, elapsed_ms
                ))
    t1 = time.ticks_us()
    write_crc = crc ^ CRC_XOROUT
    write_us = time.ticks_diff(t1, t0)
    print("  write: {:.2f} MB/s, checksum 0x{:08x}".format(
        _mb_per_s(test_size, write_us), write_crc
    ))

    print("Reading back and verifying...")
    bad_at = None
    crc = CRC_INIT
    t0 = time.ticks_us()
    with open(TEST_FILE, "rb") as f:
        for i in range(n_chunks):
            n = f.readinto(buf)
            if n != chunk_size:
                bad_at = ("short read", i * chunk_size)
                break
            crc = fo.asm_crc32(addr, chunk_size, crc)
            local_bad = fo.lfsr_verify_buf(buf, seeds[i])
            if local_bad != -1 and bad_at is None:
                bad_at = ("data mismatch", i * chunk_size + local_bad * 4)
            if (i + 1) % PROGRESS_EVERY == 0 or i + 1 == n_chunks:
                elapsed_ms = time.ticks_diff(time.ticks_us(), t0) // 1000
                print("  ...{}/{} chunks read ({} ms elapsed)".format(
                    i + 1, n_chunks, elapsed_ms
                ))
    t1 = time.ticks_us()
    read_crc = crc ^ CRC_XOROUT
    read_us = time.ticks_diff(t1, t0)
    print("  read:  {:.2f} MB/s, checksum 0x{:08x}".format(
        _mb_per_s(test_size, read_us), read_crc
    ))

    try:
        os.remove(TEST_FILE)
    except OSError:
        pass

    ok = bad_at is None
    detail = "{:,} bytes round-tripped".format(test_size)
    if not ok:
        detail = "{} at byte offset {:,}".format(bad_at[0], bad_at[1])
    checksum_ok = write_crc == read_crc
    _report("file round-trip integrity", ok and checksum_ok, detail)
    if ok and not checksum_ok:
        print(
            "[FAIL] word-level verify passed but CRC32 mismatch"
            " (0x{:08x} != 0x{:08x}) — investigate.".format(write_crc, read_crc)
        )
    print(
        "  (cross-check: binascii.crc32() over the same bytes should"
        " reproduce these checksums)"
    )
    return ok and checksum_ok


# --- main flow --------------------------------------------------------------


def run(test_size=TEST_SIZE):
    print("=== nor_flash_check ===")
    gc.collect()
    results = []
    results.append(check_identification())
    results.append(check_file_roundtrip(test_size))

    overall = all(results)
    print("=== {} ===".format("ALL TESTS PASSED" if overall else "FAILURES DETECTED"))
    return overall


# --- optional advanced mode: raw block device -------------------------------
#
# rp2.Flash() addresses the whole 16 MB chip as flash-sector-sized
# (4096-byte) blocks, going straight to the hardware erase/program calls
# instead of through a filesystem. There is no offset this script can
# pick safely on its own — firmware size and filesystem size vary by
# build. You must supply block_offset yourself, verified against your
# own partition layout (e.g. computed from PICO_FLASH_SIZE_BYTES minus
# whatever you've reserved for the VFS in your board port), and it must
# not overlap firmware or the mounted filesystem.
#
#   import nor_flash_check, rp2
#   nor_flash_check.run_raw_blocks(block_offset=3800, block_count=4)


def run_raw_blocks(block_offset, block_count=1, block_size=CHUNK_SIZE):
    import rp2

    print("=== nor_flash_check (RAW BLOCK MODE) ===")
    print(
        "Testing blocks [{}, {}) ({} bytes at flash offset 0x{:x}).".format(
            block_offset,
            block_offset + block_count,
            block_count * block_size,
            block_offset * block_size,
        )
    )
    print("Make sure this range is NOT firmware or the mounted filesystem.")

    flash = rp2.Flash()
    buf = bytearray(block_size)

    # Precompute each block's starting LFSR state up front so the write
    # and read passes can each address a given block independently,
    # instead of needing to stream through in lockstep.
    seeds = []
    state = SEED
    for _ in range(block_count):
        seeds.append(state)
        state = fo.lfsr_fill_buf(buf, state)

    ok = True
    for i, b in enumerate(range(block_offset, block_offset + block_count)):
        fo.lfsr_fill_buf(buf, seeds[i])
        flash.writeblocks(b, buf)  # erases + programs this block

    for i, b in enumerate(range(block_offset, block_offset + block_count)):
        flash.readblocks(b, buf)
        bad = fo.lfsr_verify_buf(buf, seeds[i])
        if bad != -1:
            print("[FAIL] block {} word #{}".format(b, bad))
            ok = False

    _report("raw block round-trip", ok, "{} block(s)".format(block_count))
    return ok


if __name__ == "__main__":
    run()

# Result:
# === nor_flash_check ===
# W25Q128JVPIQ, 16 MB QSPI NOR flash (boot/XIP flash)
# [PASS] flash responds (unique ID via bootrom RUID)  id=0x0aaea6cc952493c4 (8 bytes)
#   preflight: 1 chunk (4096 bytes) write 73 ms, read 1 ms -> OK
# Filesystem free space: 14,118,912 bytes
# Writing 1,048,576 bytes (256 chunks of 4096)...
#   ...16/256 chunks written (1040 ms elapsed)
#   ...32/256 chunks written (2031 ms elapsed)
#   ...48/256 chunks written (3031 ms elapsed)
#   ...64/256 chunks written (4019 ms elapsed)
#   ...80/256 chunks written (4992 ms elapsed)
#   ...96/256 chunks written (5971 ms elapsed)
#   ...112/256 chunks written (6945 ms elapsed)
#   ...128/256 chunks written (7920 ms elapsed)
#   ...144/256 chunks written (8900 ms elapsed)
#   ...160/256 chunks written (9868 ms elapsed)
#   ...176/256 chunks written (10850 ms elapsed)
#   ...192/256 chunks written (11829 ms elapsed)
#   ...208/256 chunks written (12811 ms elapsed)
#   ...224/256 chunks written (13797 ms elapsed)
#   ...240/256 chunks written (14785 ms elapsed)
#   ...256/256 chunks written (15788 ms elapsed)
#   write: 0.07 MB/s, checksum 0x314153da
# Reading back and verifying...
#   ...16/256 chunks read (78 ms elapsed)
#   ...32/256 chunks read (155 ms elapsed)
#   ...48/256 chunks read (233 ms elapsed)
#   ...64/256 chunks read (310 ms elapsed)
#   ...80/256 chunks read (388 ms elapsed)
#   ...96/256 chunks read (466 ms elapsed)
#   ...112/256 chunks read (543 ms elapsed)
#   ...128/256 chunks read (621 ms elapsed)
#   ...144/256 chunks read (698 ms elapsed)
#   ...160/256 chunks read (776 ms elapsed)
#   ...176/256 chunks read (853 ms elapsed)
#   ...192/256 chunks read (931 ms elapsed)
#   ...208/256 chunks read (1008 ms elapsed)
#   ...224/256 chunks read (1086 ms elapsed)
#   ...240/256 chunks read (1163 ms elapsed)
#   ...256/256 chunks read (1241 ms elapsed)
#   read:  0.84 MB/s, checksum 0x314153da
# [PASS] file round-trip integrity  1,048,576 bytes round-tripped
#   (cross-check: binascii.crc32() over the same bytes should reproduce these checksums)
# === ALL TESTS PASSED ===