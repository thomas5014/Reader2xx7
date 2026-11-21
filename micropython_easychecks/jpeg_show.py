from machine import SoftSPI, Pin                                                                                                                                                           
import os, sdio                                                                                                                                                                          
# csP = 27; mosiP = 22; clkP = 23; misoP = 24                                                    
# spi = SoftSPI(baudrate=12_00_000, sck=Pin(clkP), mosi=Pin(mosiP), miso=Pin(misoP))
# cs  = Pin(csP, Pin.OUT, value=1)
# Pull-ups: MISO must not float (Samsung tri-states it between responses,
# SanDisk tends to drive it high — hence "SanDisk works, Samsung doesn't").
# DAT1/DAT2 are unused in SPI mode but shouldn't float either.
# Pin(misoP, Pin.IN, Pin.PULL_UP)   # MISO / DAT0
# Pin(25, Pin.IN, Pin.PULL_UP)   # DAT1 (unused in SPI mode)
# Pin(26, Pin.IN, Pin.PULL_UP)   # DAT2 (unused in SPI mode)
# print(dir(spi))
# try:
#     cs(0)
#     print(spi.read(32,450))
# finally:
#     cs(1)
# print("spi set")
# sd = sd.SDCard(spi, cs)
sd = sdio.SDCard()
# os.mount(sd, '/sd')    
# print(os.listdir("/sd"))

import stbjpeg, jpeg, nt35510, time
from machine import freq
freq(266_000_000)
nt = nt35510.NT35510()
off = 4000
def blit_cb(x, y, w, h, buf):
    pass
    y = y - off
    if y < 0:
        pass
    nt.draw_buf(x, y, w, h, buf)

file = 'Tsuihou Sareru Tabi ni Skill o Te ni Ireta Ore ga, 100 no Isekai de 2-shuume Musou_c027.2_001.jpg'
file = "1-04.jpg"
file = "100-125.jpg"
# file = "/sd/image1-2.jpg"
# file = "image1-2.jpg"
file = "/Leviathen_decode_sample.jpg"

buf = bytearray(1*1024*1024) # 1MB
t0 = time.ticks_us()
with open(file, 'rb') as f:
    # No scale= here -- stb_image doesn't support TJpgDec-style built-in
    # descaling, so this decodes at full resolution and just clips to the
    # panel with max_w/max_h. Expect it to be slower and use more RAM than
    # jpeg.decode(scale=1, ...) for that reason, decoding the whole image
    # into memory at once rather than streaming MCU blocks -- the point
    # here is comparing correctness (does the corruption reproduce with a
    # completely different decoder?), not speed.
    # end = f.readinto(buf)
    # print(dir(f),end)
    # stbjpeg.decode(f, blit_cb, max_w=480, max_h=800)
    pass
    jpeg.decode(f, blit_cb, scale=0, max_w=480, max_h=800+off)
    
t1 = time.ticks_us()
print(f"Time taken: {t1 - t0:,} us")

# buf = bytearray(1*1024*1024) # 1MB
# t0 = time.ticks_us()

# try:
#     os.remove("/sd/image1.jpeg")
#     with open("/sd/image1.jpeg", 'w') as f:
#         print(dir(f))
#         f.write(buf[:end])
# except Exception as e:
#     print(e)
# t1 = time.ticks_us()


from machine import PWM, Pin
backlight = PWM(Pin(20))
backlight.freq(50_000)
backlight.duty_u16(65535)
print(f"Time taken: {t1 - t0:,} us")
