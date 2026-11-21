# CMD6 high-speed mode: compare read+write throughput against the best
# in-spec default-speed result, then (separately, clearly labeled) try
# HIGHSPEED_OVERCLOCK.
#
# Write safety, same approach as sd_tune_check.py: the test region is read
# once at a safe clock (twice, compared) into a trusted master copy, and
# every write puts that same trusted copy back -- never data read at an
# aggressive clock. A write that fails after the driver's retries gets
# restored one block at a time at the safe clock before continuing.
import machine
machine.freq(258_000_000)

import sys, time, sdio

sd = sdio.SDCard()
sd.verbose(True)   # want to see exactly what enable_high_speed() reports

BLOCK = 512
CHUNK_BLOCKS = 8
CHUNK_BYTES = CHUNK_BLOCKS * BLOCK
TOTAL_BLOCKS = 4096
N_CHUNKS = TOTAL_BLOCKS // CHUNK_BLOCKS
START_BLOCK = sd.ioctl(4, 0) - TOTAL_BLOCKS - 2048
SAFE_HZ = 10_000_000

master = bytearray(TOTAL_BLOCKS * BLOCK)
scratch = bytearray(TOTAL_BLOCKS * BLOCK)
mm = memoryview(master)
ms = memoryview(scratch)
mm_slices = [mm[i * CHUNK_BYTES:(i + 1) * CHUNK_BYTES] for i in range(N_CHUNKS)]
ms_slices = [ms[i * CHUNK_BYTES:(i + 1) * CHUNK_BYTES] for i in range(N_CHUNKS)]


def safe_mode():
    sd.pads(drive=4, slew="slow")
    sd.set_clock(SAFE_HZ)


def revive():
    global sd
    safe_mode()
    try:
        sd.readblocks(START_BLOCK, bytearray(BLOCK))
    except OSError:
        sd = sdio.SDCard()
        sd.verbose(True)
        safe_mode()


def restore(i):
    safe_mode()
    for _ in range(3):
        try:
            sd.writeblocks(START_BLOCK + i * CHUNK_BLOCKS, mm_slices[i])
            return True
        except OSError:
            pass
    return False


def errs(s):
    return s["crc_errors"] + s["data_timeouts"] + s["cmd_timeouts"] + s["other_errors"]


def read_bench(label):
    sd.stats(reset=True)
    t0 = time.ticks_us()
    done = 0
    try:
        for i in range(N_CHUNKS):
            sd.readblocks(START_BLOCK + i * CHUNK_BLOCKS, ms_slices[i])
            done += 1
    except OSError:
        pass
    dt = time.ticks_diff(time.ticks_us(), t0)
    s = sd.stats()
    ok = done == N_CHUNKS
    match = ok and (scratch == master)
    print("%-24s read  %6.2f MB/s  retries=%-4d errors=%-3d %s  %s" % (
        label, (done * CHUNK_BYTES / dt) if done else 0, s["read_retries"], errs(s),
        "ok" if ok else "FAILED at chunk %d" % done,
        "" if not ok else ("match" if match else "DATA MISMATCH (CRC passed!)")))
    if not ok:
        revive()
    return ok and match


def write_bench(label):
    sd.stats(reset=True)
    t0 = time.ticks_us()
    done = 0
    try:
        for i in range(N_CHUNKS):
            sd.writeblocks(START_BLOCK + i * CHUNK_BLOCKS, mm_slices[i])
            done += 1
    except OSError:
        pass
    dt = time.ticks_diff(time.ticks_us(), t0)
    s = sd.stats()
    ok = done == N_CHUNKS
    print("%-24s write %6.2f MB/s  retries=%-4d errors=%-3d %s" % (
        label, (done * CHUNK_BYTES / dt) if done else 0, s["write_retries"], errs(s),
        "ok" if ok else "FAILED at chunk %d" % done))
    if not ok:
        revive()
        if not restore(done):
            print("!! could not restore blocks %d..%d -- check them"
                  % (START_BLOCK + done * CHUNK_BLOCKS, START_BLOCK + (done + 1) * CHUNK_BLOCKS - 1))
            sys.exit()
    return ok


def bench_pair(label):
    r_ok = read_bench(label)
    if r_ok:
        write_bench(label)
    else:
        print("  (write skipped, read wasn't trustworthy)")


# --- trusted master copy, read twice at a safe speed ---
print("test region: blocks %d..%d (%d KB), master copy at %d Hz"
      % (START_BLOCK, START_BLOCK + TOTAL_BLOCKS - 1, TOTAL_BLOCKS * BLOCK // 1024, SAFE_HZ))
safe_mode()
for i in range(N_CHUNKS):
    sd.readblocks(START_BLOCK + i * CHUNK_BLOCKS, mm_slices[i])
for i in range(N_CHUNKS):
    sd.readblocks(START_BLOCK + i * CHUNK_BLOCKS, ms_slices[i])
if master != scratch:
    print("two reads at the safe speed disagree -- refusing to write to this card")
    sys.exit()

# --- baseline: best in-spec default-speed result ---
sd.pads(drive=4, slew="slow")
sd.set_clock(25_000_000)
bench_pair("25MHz default-speed")

# --- CMD6 high-speed (50 MHz nominal) ---
ok = sd.enable_high_speed()
print("enable_high_speed():", ok)
if ok:
    bench_pair("CMD6 high-speed")
else:
    print("card/driver didn't switch to high-speed -- skipping")

# --- CMD6 + overclock preset: EXPERIMENTAL. Its PIO program uses a fixed
# /2 divider, not a tunable one, so at the current 258 MHz CPU clock this is
# ~129 MHz -- nothing like the "75 MHz" the mode is named for. That number
# only applies near a ~150 MHz CPU clock, which is tried second, below.
# enable_high_speed()'s own test-read still guards this: if it doesn't work,
# it reverts and reports False rather than leaving the bus in a bad state.
print("\n--- HIGHSPEED_OVERCLOCK experiments (may simply fail to switch) ---")
ok = sd.enable_high_speed(sdio.HIGHSPEED_OVERCLOCK)
print("enable_high_speed(OVERCLOCK) at 258MHz CPU clock (~129MHz data):", ok)
if ok:
    bench_pair("overclock @258MHz CPU")
else:
    print("  didn't switch/verify at ~129MHz -- expected, that's well past spec")

machine.freq(150_000_000)   # closer to the CPU clock the 75MHz nominal number assumes
safe_mode()
ok = sd.enable_high_speed(sdio.HIGHSPEED_OVERCLOCK)
print("enable_high_speed(OVERCLOCK) at 150MHz CPU clock (~75MHz data):", ok)
if ok:
    bench_pair("overclock @150MHz CPU")
else:
    print("  didn't switch/verify even near the intended 75MHz target")

# back to firmware defaults
machine.freq(258_000_000)
sd.pads(drive=4, slew="slow")
sd.set_clock(20_000_000)
print(sd.info())
