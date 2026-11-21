# Three-way comparison, one run, so the difference is unambiguous.
# Each box is 140x300, every row: 4px GREEN | 132px RED | 4px WHITE.
#   x=10   : C  bit-bang   draw_buf           (reference, known good)
#   x=170  : Python PIO/DMA driver draw_buf   (your nt35510.py on the board)
#   x=330  : C  PIO/DMA    draw_buf_dma
# Correct = green band on the left edge, white on the right.
# Shifted = a 1px WHITE sliver before the green band.
# Needs nt35510.py (your Python driver) on the device filesystem.
import machine, time
machine.freq(252_000_000)
from machine import PWM, Pin
import nt35510c
from nt35510 import NT35510

d = NT35510()          # Python driver resets/initialises the panel and pins
bl = PWM(Pin(20)); bl.freq(50_000); bl.duty_u16(65535)
d.fill(0)

W, H = 140, 300
GREEN, RED, WHITE = 0x07E0, 0xF800, 0xFFFF
buf = bytearray(W * H * 2)
for y in range(H):
    for x in range(W):
        c = GREEN if x < 4 else (WHITE if x >= W - 4 else RED)
        i = (y * W + x) * 2
        buf[i] = c & 0xFF
        buf[i + 1] = c >> 8

Y = 250
nt35510c.draw_buf(10, Y, W, H, buf)
d.draw_buf(170, Y, W, H, buf)
t0 = time.ticks_us()
nt35510c.draw_buf_dma(330, Y, W, H, buf)
t1 = time.ticks_us()
print("C DMA box: %d us" % time.ticks_diff(t1, t0))
print("left=C bit-bang  middle=Python DMA  right=C DMA")
print("Which boxes show a white sliver on the LEFT edge?")
