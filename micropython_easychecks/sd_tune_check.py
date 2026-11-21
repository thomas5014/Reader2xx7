# Sweep SDIO clock x pad settings and report read AND write throughput plus the
# driver's own error counters for each combination.
# Uses the runtime tuning API: sd.pads(), sd.set_clock(), sd.stats(), sd.info().
#
# Above 25 MHz the card is still in default-speed mode (no CMD6 high-speed
# switch is implemented), which is out of spec: some cards cope, some don't.
# That is what the error counters and the data comparison are for.
#
# Write safety: raw writes can damage data if one is interrupted, so
#  * the test region is the last ~2 MB of the card, the part a FAT filesystem
#    is least likely to have used;
#  * it is read once at a safe 10 MHz (twice, compared) into `master`, and
#    every write puts back exactly that trusted copy -- never data that was
#    read at an aggressive clock;
#  * if a write still fails after the driver's own retries, that chunk may be
#    left torn, so it is rewritten at a safe speed before carrying on, and the
#    script stops loudly if even that fails.
import machine
machine.freq(258_000_000)   # set before SDCard(): the SD dividers are derived from the CPU clock

import gc, sys, time, sdio

sd = sdio.SDCard()
sd.verbose(False)           # per-error log lines would flood the table; the counters carry the same info

BLOCK = 512
CHUNK_BLOCKS = 8
CHUNK_BYTES = CHUNK_BLOCKS * BLOCK
TOTAL_BLOCKS = 4096         # 2 MB per phase

CLOCKS = (10_000_000, 20_000_000, 25_000_000, 30_000_000, 35_000_000, 40_000_000, 50_000_000)
PADS = (                    # (drive mA, slew)
    (2, "slow"),
    (4, "slow"),
    (8, "slow"),
    (4, "fast"),
)
SAFE_HZ = 10_000_000
SAFE_PADS = (4, "slow")

# master = trusted copy of the region, scratch = what each read phase gets back
while True:
    try:
        gc.collect()
        master = bytearray(TOTAL_BLOCKS * BLOCK)
        scratch = bytearray(TOTAL_BLOCKS * BLOCK)
        break
    except MemoryError:
        master = scratch = None
        TOTAL_BLOCKS //= 2
        print("MemoryError, trying", TOTAL_BLOCKS, "blocks per phase")
mm = memoryview(master)
ms = memoryview(scratch)
N_CHUNKS = TOTAL_BLOCKS // CHUNK_BLOCKS
START_BLOCK = sd.ioctl(4, 0) - TOTAL_BLOCKS - 2048
probe = bytearray(BLOCK)


def sl(mv: object, i: int):
    return mv[i * CHUNK_BYTES:(i + 1) * CHUNK_BYTES]


# mv[a:b] allocates a new memoryview object every call. read_phase/write_phase
# call sl() once per chunk (512 times for a 2 MB phase at CHUNK_BLOCKS=8) --
# inside the ticks_us()-timed loop, that's 512 allocations contributing to GC
# pressure during the very thing being measured. MicroPython's GC is
# stop-the-world, so a collection triggered mid-phase lands directly in the
# measured dt with no relation to the actual transfer speed -- this is very
# likely why measured throughput dropped well beyond what the clock change
# alone explains. Slicing once here, before any phase is timed, and reusing
# the same list of views for every phase across the whole sweep removes that
# variable from the numbers below.
mm_slices = [sl(mm, i) for i in range(N_CHUNKS)]
ms_slices = [sl(ms, i) for i in range(N_CHUNKS)]


def safe_mode():
    sd.pads(drive=SAFE_PADS[0], slew=SAFE_PADS[1])
    sd.set_clock(SAFE_HZ)


def revive():
    """After a failed phase at a too-fast clock the card can be left mid-command."""
    global sd
    safe_mode()
    try:
        sd.readblocks(START_BLOCK, probe)
    except OSError:
        sd = sdio.SDCard()      # full re-init
        sd.verbose(False)
        safe_mode()


def restore(i):
    """A write that failed after all the driver's retries may have left chunk i torn."""
    safe_mode()
    for _ in range(3):
        try:
            sd.writeblocks(START_BLOCK + i * CHUNK_BLOCKS, sl(mm, i))
            return True
        except OSError:
            pass
    return False


def read_phase():
    sd.stats(reset=True)
    done = 0
    gc.collect()             # force any pending collection before the timed region, not during it
    t0 = time.ticks_us()
    try:
        for i in range(N_CHUNKS):
            sd.readblocks(START_BLOCK + i * CHUNK_BLOCKS, ms_slices[i])
            done += 1
    except OSError:
        pass                    # exhausted the driver's retries on chunk `done`
    return done, time.ticks_diff(time.ticks_us(), t0), sd.stats()


def write_phase():
    sd.stats(reset=True)
    done = 0
    gc.collect()
    t0 = time.ticks_us()
    try:
        for i in range(N_CHUNKS):
            sd.writeblocks(START_BLOCK + i * CHUNK_BLOCKS, mm_slices[i])
            done += 1
    except OSError:
        pass
    return done, time.ticks_diff(time.ticks_us(), t0), sd.stats()


def errs(s):
    return s["crc_errors"] + s["data_timeouts"] + s["cmd_timeouts"] + s["other_errors"]


def mbps(done, dt):
    return "%6.2f" % (done * CHUNK_BYTES / dt) if done else "     -"


# --- trusted master copy, read twice at a safe speed ---
print("test region: blocks %d..%d (%d KB per phase), master copy at %d Hz"
      % (START_BLOCK, START_BLOCK + TOTAL_BLOCKS - 1, TOTAL_BLOCKS * BLOCK // 1024, SAFE_HZ))
safe_mode()
for i in range(N_CHUNKS):
    sd.readblocks(START_BLOCK + i * CHUNK_BLOCKS, sl(mm, i))
for i in range(N_CHUNKS):
    sd.readblocks(START_BLOCK + i * CHUNK_BLOCKS, sl(ms, i))
if master != scratch:
    print("two reads at the safe speed disagree -- refusing to write to this card")
    sys.exit()

# --- preflight: which write sizes work at which clocks ---
# Each write puts back what is already there, so a success changes nothing. A
# failed multi-block write can leave part of it torn, so after any failure the
# blocks are put back one at a time at the safe speed (single-block writes are
# the most robust path). The driver's error log is on for the first failure
# only, which is enough to see what kind it was.
def heal(n):
    safe_mode()
    for b in range(n):
        sd.writeblocks(START_BLOCK + b, mm[b * BLOCK:(b + 1) * BLOCK])


shown = False
worked = {}
print("preflight: write size (blocks) x clock")
for hz in (SAFE_HZ, 20_000_000, 25_000_000):
    row = []
    for n in (1, 2, 3, 4, 8):
        sd.pads(drive=SAFE_PADS[0], slew=SAFE_PADS[1])
        sd.set_clock(hz)
        sd.stats(reset=True)
        sd.verbose(not shown)
        try:
            sd.writeblocks(START_BLOCK, mm[0:n * BLOCK])
            ok = True
        except OSError:
            ok = False
            shown = True
        sd.verbose(False)
        worked[(hz, n)] = ok
        row.append("%d:%s" % (n, "ok" if ok else "FAIL"))
        if not ok:
            try:
                heal(n)
            except OSError:
                print("!! could not put blocks %d..%d back -- check them"
                      % (START_BLOCK, START_BLOCK + n - 1))
                sys.exit()
    print("  %9d Hz   %s" % (hz, "  ".join(row)))

if not worked[(SAFE_HZ, CHUNK_BLOCKS)]:
    print("%d-block writes still fail at %d Hz -- stopping before the sweep" % (CHUNK_BLOCKS, SAFE_HZ))
    sys.exit()

print("target_hz  actual_hz  drive slew  |  R MB/s retry  err |  W MB/s retry  err | note")
seen = set()
for hz in CLOCKS:
    actual = sd.set_clock(hz)["data_hz"]
    if actual in seen:
        print("%9d  -> %d Hz, already covered" % (hz, actual))
        continue
    seen.add(actual)
    for drive, slew in PADS:
        sd.pads(drive=drive, slew=slew)
        sd.set_clock(hz)
        note = ""

        rd, rdt, rs = read_phase()
        r_mb, r_retry, r_err = mbps(rd, rdt), rs["read_retries"], errs(rs)
        w_mb, w_retry, w_err = "     -", 0, 0

        if rd != N_CHUNKS:
            note = "READ FAILED at chunk %d, write skipped" % rd
            revive()
        else:
            if scratch != master:
                note = "DATA MISMATCH on read (CRC passed!) "
            wd, wdt, ws = write_phase()
            w_mb, w_retry, w_err = mbps(wd, wdt), ws["write_retries"], errs(ws)
            if wd != N_CHUNKS:
                note += "WRITE FAILED at chunk %d" % wd
                revive()
                if not restore(wd):
                    print("!! could not restore blocks %d..%d -- that chunk may be damaged"
                          % (START_BLOCK + wd * CHUNK_BLOCKS, START_BLOCK + (wd + 1) * CHUNK_BLOCKS - 1))
                    sys.exit()

        print("%9d  %9d  %3dmA %-5s | %s %5d %4d | %s %5d %4d | %s" % (
            hz, actual, drive, slew, r_mb, r_retry, r_err, w_mb, w_retry, w_err, note))

# back to the firmware defaults
sd.pads(drive=4, slew="slow")
sd.set_clock(20_000_000)
sd.verbose(True)
print(sd.info())



# Result:
"""
sam evo 0
PSRAM ID: kgd=0x5d eid=0x53
sdcard_init: ocr=0xc0ff8000 is_sdhc=1
sdcard_init: CID MID=0x1b OID=SM PNM=EB1QT PRV=3.0
sdcard_init: CID raw: 1b 53 4d 45 42 31 51 54 30 98 dc 63 4c 01 52 a7
sdcard_init: rca=0x00010000 CMD3_status=0x0520
sdcard_init: CSD ver=1 TRAN_SPEED=0x32 CCCL=0x5b5 sectors=62521344
sdcard_init: CSD raw: 40 0e 00 32 5b 59 00 00 ee 7f 7f 80 0a 40 40 55
sdcard_init: CMD7 reply=0x00000700
sdcard_init: ACMD42 reply=0x00000920
sdcard_init: CMD55 reply=0x00000920 (APP_CMD=1)
sdcard_init: ACMD6 reply=0x00000920 (ILLEGAL_CMD=0)
sdcard_init: CMD16 reply=0x00000900
sdcard_init: GPIO after ACMD6/CMD16: CLK=1 CMD=1 D0=1 D1=1 D2=1 D3=1
sdcard_init: SCR st=0 raw: 02 85 84 82 00 00 00 00
test region: blocks 62515200..62519295 (2048 KB per phase), master copy at 10000000 Hz
preflight: write size (blocks) x clock
   10000000 Hz   1:ok  2:ok  3:ok  4:ok  8:ok
   20000000 Hz   1:ok  2:ok  3:ok  4:ok  8:ok
   25000000 Hz   1:ok  2:ok  3:ok  4:ok  8:ok
target_hz  actual_hz  drive slew  |  R MB/s retry  err |  W MB/s retry  err | note
 10000000    9923076    2mA slow  |   2.84     0    0 |   2.67     0    0 | 
 10000000    9923076    4mA slow  |   2.50     0    0 |   2.66     0    0 | 
 10000000    9923076    8mA slow  |   2.50     0    0 |   2.66     0    0 | 
 10000000    9923076    4mA fast  |   2.50     0    0 |   2.66     0    0 | 
 20000000   19846153    2mA slow  |   3.72     0    0 |   3.37     0    0 | 
 20000000   19846153    4mA slow  |   3.72     0    0 |   3.37     0    0 | 
 20000000   19846153    8mA slow  |   3.72     0    0 |   3.37     0    0 | 
 20000000   19846153    4mA fast  |   3.72     0    0 |   3.37     0    0 | 
 25000000   23454545    2mA slow  |   3.84     0    0 |   3.41     0    0 | 
 25000000   23454545    4mA slow  |   3.84     0    0 |   3.41     0    0 | 
 25000000   23454545    8mA slow  |   3.84     0    0 |   3.41     0    0 | 
 25000000   23454545    4mA fast  |   3.82     0    0 |   3.41     0    0 | 
 30000000   28666666    2mA slow  |   3.89     7    7 |   3.46     0    0 | 
 30000000   28666666    4mA slow  |   3.85    12   12 |   3.46     0    0 | 
 30000000   28666666    8mA slow  |   3.91     4    4 |   3.46     0    0 | 
 30000000   28666666    4mA fast  |   3.88     8    8 |   3.46     0    0 | 
 35000000   32250000    2mA slow  |   3.92     3    3 |   3.48     0    0 | 
 35000000   32250000    4mA slow  |   3.93     2    2 |   3.48     0    0 | 
 35000000   32250000    8mA slow  |   3.89     7    7 |   3.48     0    0 | 
 35000000   32250000    4mA fast  |   3.88     3    3 |   3.48     0    0 | 
 40000000   36857142    2mA slow  |   2.62   251  251 |   3.49     0    0 | 
 40000000   36857142    4mA slow  |   2.62   252  252 |   3.51     0    0 | 
 40000000   36857142    8mA slow  |   2.61   252  252 |   3.51     0    0 | 
 40000000   36857142    4mA fast  |   2.62   253  253 |   3.51     0    0 | 
 50000000   43000000    2mA slow  |   2.58   268  268 |   3.53     0    0 | 
 50000000   43000000    4mA slow  |   2.58   269  269 |   3.53     0    0 | 
 50000000   43000000    8mA slow  |   2.61   259  259 |   3.53     0    0 | 
 50000000   43000000    4mA fast  |   2.59   265  265 |   3.53     0    0 | 
{'data_div': 13, 'sys_hz': 258000000, 'target_hz': 20000000, 'cmd_hz': 19846153, 'data_hz': 19846153, 'cmd_div': 13, 'stale': False}

pny elite card:
PSRAM ID: kgd=0x5d eid=0x53
sdcard_init: ocr=0xc0ff8000 is_sdhc=1
sdcard_init: CID MID=0x27 OID=PH PNM=SD32G PRV=6.0
sdcard_init: CID raw: 27 50 48 53 44 33 32 47 60 27 07 0a cf 01 79 5b
sdcard_init: rca=0x00010000 CMD3_status=0x0520
sdcard_init: CSD ver=1 TRAN_SPEED=0x32 CCCL=0x5b5 sectors=60532736
sdcard_init: CSD raw: 40 0e 00 32 5b 59 00 00 e6 e9 7f 80 0a 40 00 b7
sdcard_init: CMD7 reply=0x00000700
sdcard_init: ACMD42 reply=0x00000920
sdcard_init: CMD55 reply=0x00000920 (APP_CMD=1)
sdcard_init: ACMD6 reply=0x00000920 (ILLEGAL_CMD=0)
sdcard_init: CMD16 reply=0x00000900
sdcard_init: GPIO after ACMD6/CMD16: CLK=1 CMD=1 D0=1 D1=1 D2=1 D3=1
sdcard_init: SCR st=0 raw: 02 85 80 83 00 00 00 00
test region: blocks 60526592..60530687 (2048 KB per phase), master copy at 10000000 Hz
preflight: write size (blocks) x clock
   10000000 Hz   1:ok  2:ok  3:ok  4:ok  8:ok
   20000000 Hz   1:ok  2:ok  3:ok  4:ok  8:ok
   25000000 Hz   1:ok  2:ok  3:ok  4:ok  8:ok
target_hz  actual_hz  drive slew  |  R MB/s retry  err |  W MB/s retry  err | note
 10000000    9923076    2mA slow  |   3.85     0    0 |   2.10     0    0 | 
 10000000    9923076    4mA slow  |   3.58     0    0 |   1.47     0    0 | 
 10000000    9923076    8mA slow  |   3.57     0    0 |   1.87     0    0 | 
 10000000    9923076    4mA fast  |   3.58     0    0 |   1.95     0    0 | 
 20000000   19846153    2mA slow  |   5.70     0    0 |   1.47     0    0 | 
 20000000   19846153    4mA slow  |   5.76     0    0 |   2.72     0    0 | 
 20000000   19846153    8mA slow  |   5.76     0    0 |   1.85     0    0 | 
 20000000   19846153    4mA fast  |   5.73     0    0 |   1.88     0    0 | 
 25000000   23454545    2mA slow  |   6.37     0    0 |   2.85     0    0 | 
 25000000   23454545    4mA slow  |   6.37     0    0 |   1.47     0    0 | 
 25000000   23454545    8mA slow  |   6.35     0    0 |   2.64     0    0 | 
 25000000   23454545    4mA fast  |   6.36     0    0 |   2.29     0    0 | 
 30000000   28666666    2mA slow  |   6.99     0    0 |   1.62     0    0 | 
 30000000   28666666    4mA slow  |   7.07     0    0 |   2.96     0    0 | 
 30000000   28666666    8mA slow  |   7.07     0    0 |   1.76     0    0 | 
 30000000   28666666    4mA fast  |   7.03     0    0 |   2.16     0    0 | 
 35000000   32250000    2mA slow  |   7.38     0    0 |   3.08     0    0 | 
 35000000   32250000    4mA slow  |   7.37     0    0 |   1.43     0    0 | 
 35000000   32250000    8mA slow  |   7.36     0    0 |   3.06     0    0 | 
 35000000   32250000    4mA fast  |   7.38     0    0 |   2.17     0    0 | 
 40000000   36857142    2mA slow  |   7.45     0    0 |   1.76     0    0 | 
 40000000   36857142    4mA slow  |   7.52     0    0 |   3.16     0    0 | 
 40000000   36857142    8mA slow  |   7.52     0    0 |   1.62     0    0 | 
 40000000   36857142    4mA fast  |   7.48     0    0 |   2.51     0    0 | 
 50000000   43000000    2mA slow  |   7.61     0    0 |   2.92     0    0 | 
 50000000   43000000    4mA slow  |   7.50     0    0 |   1.51     0    0 | 
 50000000   43000000    8mA slow  |   7.60     0    0 |   3.24     0    0 | 
 50000000   43000000    4mA fast  |   7.60     0    0 |   1.97     0    0 | 
{'data_div': 13, 'sys_hz': 258000000, 'target_hz': 20000000, 'cmd_hz': 19846153, 'data_hz': 19846153, 'cmd_div': 13, 'stale': False}
sand ultra hc1
PSRAM ID: kgd=0x5d eid=0x53
sdcard_init: ocr=0xc0ff8000 is_sdhc=1
sdcard_init: CID MID=0x03 OID=SD PNM=SL32G PRV=8.0
sdcard_init: CID raw: 03 53 44 53 4c 33 32 47 80 4b 03 aa d1 01 91 af
sdcard_init: rca=0xaaaa0000 CMD3_status=0x0520
sdcard_init: CSD ver=1 TRAN_SPEED=0x32 CCCL=0x5b5 sectors=62333952
sdcard_init: CSD raw: 40 0e 00 32 5b 59 00 00 ed c8 7f 80 0a 40 40 c3
sdcard_init: CMD7 reply=0x00000700
sdcard_init: ACMD42 reply=0x00000920
sdcard_init: CMD55 reply=0x00000920 (APP_CMD=1)
sdcard_init: ACMD6 reply=0x00000920 (ILLEGAL_CMD=0)
sdcard_init: CMD16 reply=0x00000900
sdcard_init: GPIO after ACMD6/CMD16: CLK=1 CMD=1 D0=1 D1=1 D2=1 D3=1
sdcard_init: SCR st=0 raw: 02 35 80 43 00 00 00 00
test region: blocks 62327808..62331903 (2048 KB per phase), master copy at 10000000 Hz
preflight: write size (blocks) x clock
   10000000 Hz   1:ok  2:ok  3:ok  4:ok  8:ok
   20000000 Hz   1:ok  2:ok  3:ok  4:ok  8:ok
   25000000 Hz   1:ok  2:ok  3:ok  4:ok  8:ok
target_hz  actual_hz  drive slew  |  R MB/s retry  err |  W MB/s retry  err | note
 10000000    9923076    2mA slow  |   3.41     0    0 |   2.09     0    0 | 
 10000000    9923076    4mA slow  |   3.40     0    0 |   2.18     0    0 | 
 10000000    9923076    8mA slow  |   3.36     0    0 |   2.22     0    0 | 
 10000000    9923076    4mA fast  |   3.40     0    0 |   2.24     0    0 | 
 20000000   19846153    2mA slow  |   5.31     0    0 |   2.90     0    0 | 
 20000000   19846153    4mA slow  |   5.31     0    0 |   2.78     0    0 | 
 20000000   19846153    8mA slow  |   5.30     0    0 |   3.02     0    0 | 
 20000000   19846153    4mA fast  |   5.31     0    0 |   2.92     0    0 | 
 25000000   23454545    2mA slow  |   5.77     0    0 |   2.92     0    0 | 
 25000000   23454545    4mA slow  |   5.53     0    0 |   3.11     0    0 | 
 25000000   23454545    8mA slow  |   5.76     0    0 |   3.17     0    0 | 
 25000000   23454545    4mA fast  |   5.76     0    0 |   3.04     0    0 | 
 30000000   28666666    2mA slow  |   6.12    16   16 |   2.89     0    0 | 
 30000000   28666666    4mA slow  |   6.08    15   15 |   3.28     5    5 | 
 30000000   28666666    8mA slow  |   6.13    14   14 |   3.29     0    0 | 
 30000000   28666666    4mA fast  |   6.20    10   10 |   3.19     0    0 | 
 35000000   32250000    2mA slow  |   6.54     8    8 |   2.79     0    0 | 
 35000000   32250000    4mA slow  |   6.51     9    9 |   3.41     0    0 | 
 35000000   32250000    8mA slow  |   6.56     6    6 |   3.28     0    0 | 
 35000000   32250000    4mA fast  |   6.56     6    6 |   2.80     0    0 | 
 40000000   36857142    2mA slow  |   3.45   496  496 |   3.46     0    0 | 
 40000000   36857142    4mA slow  |   3.64   493  493 |   3.51     0    0 | 
 40000000   36857142    8mA slow  |   3.63   497  497 |   3.35     0    0 | 
 40000000   36857142    4mA fast  |   3.63   497  497 |   3.21     0    0 | 
 50000000   43000000    2mA slow  |   3.66   532  532 |   2.96     0    0 | 
 50000000   43000000    4mA slow  |   3.70   522  522 |   3.70     0    0 | 
 50000000   43000000    8mA slow  |   3.70   524  524 |   3.54     0    0 | 
 50000000   43000000    4mA fast  |   3.38   526  526 |   4.09     0    0 | 
{'data_div': 13, 'sys_hz': 258000000, 'target_hz': 20000000, 'cmd_hz': 19846153, 'data_hz': 19846153, 'cmd_div': 13, 'stale': False}
"""