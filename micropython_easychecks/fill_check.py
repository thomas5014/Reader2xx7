from machine import PWM, Pin, freq;backlight = PWM(Pin(20),freq=50_000,duty_u16=65535); freq(258_000_000)
import nt35510c, time; nt35510c.init(); nt35510c.fill(0xF800)
t0 = time.ticks_us();  nt35510c.fill(0xf100); t1 = time.ticks_us(); print(t1-t0)

buf = bytearray(480*700*2)
with open("sample4_480-700.raw","rb") as f:
    f.readinto(buf)
    t0 = time.ticks_us()
    t2 = time.ticks_us()
    nt35510c.draw_buf(0, 0, 480, 700, buf)
    t1 = time.ticks_us()
    print(f"{t1-t2:,} us DMA from PSRAM, {t2-t0:,} us")