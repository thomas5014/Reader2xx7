# Compare the C driver's bit-banged draw_buf against the new PIO/DMA path.
# Firmware: reader2xx7-firmware branch (nt35510c.draw_buf_dma). Run from a
# power cycle at your normal boot clock (84 MHz PIO clock assumes ~252/258).
import nt35510c, time, machine
from machine import PWM, Pin
machine.freq(252_000_000)

nt35510c.init()
bl = PWM(Pin(20)); bl.freq(50_000); bl.duty_u16(65535)
print("sys clock:", machine.freq())

W, H = 480, 700
buf = bytearray(W * H * 2)
# vertical colour bars, native little-endian RGB565: red, green, blue, white
cols = (0xF800, 0x07E0, 0x001F, 0xFFFF)
for x in range(W):
    c = cols[x * 4 // W]
    lo, hi = c & 0xFF, c >> 8
    for y in range(H):
        i = (y * W + x) * 2
        buf[i] = lo
        buf[i + 1] = hi

nt35510c.fill(0)
t0 = time.ticks_us()
nt35510c.draw_buf(0, 0, W, H, buf)
t1 = time.ticks_us()
print(f"bit-bang draw_buf: {time.ticks_diff(t1, t0):,} us")
time.sleep(1)

nt35510c.fill(0)
t0 = time.ticks_us()
nt35510c.draw_buf_dma(0, 0, W, H, buf)
t1 = time.ticks_us()
print(f"PIO/DMA draw_buf_dma: {time.ticks_diff(t1, t0):,} us")
time.sleep(20)

# odd size + unaligned start: exercises the bit-banged head/tail pixels
nt35510c.fill(0)
mv = memoryview(buf)
nt35510c.fill_rect(10,10,101,51,-1)
nt35510c.draw_buf_dma(10, 10, 101, 51, mv[2:2 + 101 * 51 * 2])
print("odd-size + unaligned draw done (expect a clean 101x51 patch at 10,10)")
print(machine.freq())
