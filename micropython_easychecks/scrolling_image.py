from machine import PWM, Pin
from nt35510 import NT35510
import time

@micropython.viper
def switch_bytes(buf: object):
    p = ptr8(buf)
    n = int(len(buf)) & ~1
    tmp: int = 0
    i: int = 0
    while i < n:
        tmp = p[i]
        p[i] = p[i + 1]
        p[i + 1] = tmp
        i += 2

    return buf

backlight = PWM(Pin(20))
backlight.freq(50_000)
backlight.duty_u16(40_000)
d = NT35510()
# d.fill(-1)
d.fill(0)
buf = bytearray(d.width*700*2)
with open("sample4_480-700.raw","rb") as f:
    f.readinto(buf)
    t0 = time.ticks_us()
    # _reverse32_buf(buf, len(buf))
    t2 = time.ticks_us()
    d.draw_buf(0, 0, 480, 700, switch_bytes(buf))
    t1 = time.ticks_us()
    print(f"{t1-t2:,} us DMA from PSRAM, {t2-t0:,} us")


for i in range(0, 3000, 10):
    i = i % 800
    h = 700 if 700+i < 800 else 800-i
    d.draw_buf(0, i, 480, h, buf)