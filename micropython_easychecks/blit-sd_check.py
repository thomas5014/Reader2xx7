import sdio, os, time
sd = sdio.SDCard()
os.mount(sd,"/sd")

from nt35510 import NT35510
d = NT35510()


path = f"/sd/Novels/{os.listdir("/sd/Novels")[0]}/Images/"

buf = bytearray(480*700*2)

t0 = time.ticks_us()
with open("/sd/berto_480-700.raw","rb") as f:
    f.readinto(buf)
print("read done")
t1 = time.ticks_us()
print(t1-t0)

from machine import PWM, Pin
backlight = PWM(Pin(20))
backlight.freq(50_000)
backlight.duty_u16(65535)


# d.fill(0)
# with open("sample4_480-700.raw","rb") as f:
#     f.readinto(buf)
#     t0 = time.ticks_us()
#     t2 = time.ticks_us()
#     d.draw_buf(0, 0, 480, 700, buf)
#     t1 = time.ticks_us()
#     print(f"{t1-t2:,} us DMA from PSRAM, {t2-t0:,} us")
# d.fill(-1)


@micropython.viper
def switch_bytes(buf: object):
    p = ptr16(buf)
    n = int(len(buf)) & ~1
    tmp: int = 0
    i: int = 0
    _switch_bytes_asm(p,n)
    # while i < n:
    #     tmp = p[i]
    #     p[i] = p[i + 1]
    #     p[i + 1] = tmp
    #     i += 2

    return buf

# @micropython.asm_thumb
# def _switch_bytes_asm(r0,r1):
#     add(r1,r0,r1) # start from end
#     mov(r4,16) # half-wortd shift value
#     label(LOOP)
#     ldr(r2,[r1,0]) # load
#     mov(r3,r2)
#     lsl(r3,r4)
#     lsr(r2,r4)
#     orr(r2,r3)
#     str(r2,[r1,0])
#     sub(r1,r1,1)
#     cmp(r0,r1)
#     bne(LOOP)

# b = bytearray(2)
# b[0] = 0x0f
# print(b)
# print(switch_bytes(b))
t0 = time.ticks_us()
d.draw_buf(0,0,480,700,buf)#switch_bytes(buf))
t1 = time.ticks_us()
print(t1-t0," us")