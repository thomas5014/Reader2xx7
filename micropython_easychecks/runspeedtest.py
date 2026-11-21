import time

@micropython.viper
def color565(r:int,g:int,b:int) -> int:
    return ((r & 0xF8)<<8) | ((g & 0xFC)<<3) | (b>>3)

@micropython.asm_thumb
def color565_asm(r0,r1,r2) -> int:
    mov(r3,0xF8)
    and_(r0,r3) # r &= 0xF8
    mov(r3,0xFC)
    and_(r1,r3) # g &= 0xFC
    mov(r3,0x08)
    lsl(r0,r3) # r <<= 8
    mov(r3,0x03)
    lsl(r1,r3) # g <<= 3
    lsr(r2,r3) # b >>= 3
    orr(r0,r1)
    orr(r0,r2)

@micropython.asm_thumb
def color565_asm2(r0, r1, r2) -> int:
    # 1. Process Red: Shift right 3 to clear lower bits, then left 11 (Net: lsl 8)
    lsr(r0, r0, 3)
    lsl(r0, r0, 27)

    # 2. Process Green: Shift right 2 to clear lower bits, then left 5 (Net: lsl 3)
    lsr(r1, r1, 2)
    lsl(r1, r1, 21)

    # 3. Process Blue: Shift right 3
    lsl(r2, r2, 13)

    # 4. Combine into r0 and return
    orr(r0, r1)
    orr(r0, r2)

    lsr(r0,r0,16)


def blank():
    pass

@micropython.asm_thumb
def asm_blank():
    pass

@micropython.viper
def viper_blank():
    pass

@micropython.viper
def run_speedtest():
    i:int = 0
    t0 = time.ticks_us()
    while i < 1_000_000:
        # viper_blank()
        color565_asm2(255, 128, 64)
        i += 1
    t1 = time.ticks_us()
    return t1 - t0

diff = run_speedtest()
print(f"Speed test completed in {diff:,} us, times per call: {diff/1_000:.6f} ns")
# Speed test completed in 50,389 us, times per call: 50.389000 ns      -- passive
# Speed test completed in 1,577,532 us, times per call: 1577.532000 ns -- viper
# Speed test completed in 1,205,438 us, times per call: 1205.438000 ns -- asm
# Speed test completed in 1,197,687 us, times per call: 1197.687000 ns -- asm2
# Speed test completed in 3,116,741 us, times per call: 3116.741000 ns -- blank
# Speed test completed in 891,483 us, times per call: 891.483000 ns    -- asm blank
# Speed test completed in 910,857 us, times per call: 910.857000 ns    -- viper blank

c = 255,23,170
print(bin(color565_asm2(*c)))
print(bin(color565(*c)))