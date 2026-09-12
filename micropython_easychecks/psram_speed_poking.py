import gc, time, uctypes
import fast_ops as fo

gc.collect()
buf = bytearray(65536)
addr = uctypes.addressof(buf)
print(hex(addr))
assert 0x20000000 <= addr < 0x20082000, "not in internal SRAM range -- retry on a fresher boot"

word_count = len(buf) // 4
t0 = time.ticks_us()
fo.asm_fill32(addr, 0x11111111, word_count)
t1 = time.ticks_us()
bad = fo.asm_verify32(addr, 0x11111111, word_count)
t2 = time.ticks_us()

print("SRAM write: {:.2f} MB/s".format(len(buf) / time.ticks_diff(t1, t0)))
print("SRAM read:  {:.2f} MB/s".format(len(buf) / time.ticks_diff(t2, t1)))
print("bad =", bad)

# result:
# 0x20017b70
# SRAM write: 168.04 MB/s
# SRAM read:  124.36 MB/s
# bad = -1

import sys
sys.exit(0)

import machine
print("psram_check.py: machine.freq() =", machine.freq())

QMI_M1_TIMING = 0x400d0020  # XIP_QMI_BASE (0x400d0000) + M1_TIMING offset (0x20)

val = machine.mem32[QMI_M1_TIMING]
print(hex(val))  # inspect what psram_init() actually programmed

# CLKDIV = bits[7:0], RXDELAY = bits[10:8]
clkdiv = val & 0xff
rxdelay = (val >> 8) & 0x7
print("clkdiv", clkdiv, "rxdelay", rxdelay)

# force divisor=1 -> PSRAM clock == clk_sys (266MHz here, 2x the rated 133MHz)
new_val = (val & ~0x7ff) | (1 << 0) | (rxdelay << 8)
machine.mem32[QMI_M1_TIMING] = new_val
