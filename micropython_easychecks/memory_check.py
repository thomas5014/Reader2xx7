import os, gc, machine
import micropython
machine.freq(250_000_000)

stat = os.statvfs("/")
size = stat[1] * stat[2]
free = stat[0] * stat[3]
used = size - free

KB = 1024
MB = 1024 * 1024

print("Size : {:,} bytes, {:,} KB, {} MB".format(size, size / KB, size / MB))
print("Used : {:,} bytes, {:,} KB, {} MB".format(used, used / KB, used / MB))
print("Free : {:,} bytes, {:,} KB, {} MB".format(free, free / KB, free / MB))
micropython.mem_info(1)
print(f"Free memory: {gc.mem_free():,} Bytes")


# result:   ----- tldr good ---- 
# Size : 15,204,352 bytes, 14848 KB, 14.5 MB
# Used : 8,192 bytes, 8 KB, 0.0078125 MB
# Free : 15,196,160 bytes, 14840 KB, 14.4921868 MB
# stack: 500 out of 12032
# GC: total: 8641216, used: 6080, free: 8635136
#  No. of 1-blocks: 44, 2-blocks: 34, max blk sz: 64, max free sz: 512276
# GC memory layout; from 20012680:
# 00000000: h=MLhhhhB=DhhTTB=DB=B=B=DhTh===B=DTDB=B=Th=====B=B=B=TB=B=B=B=B=
# 00000400: B=B=B=B=TB=TB=B=B=B=B=h===========h===B=TB=Sh============h======
# 00000800: ==T==h==================h=======================================
# 00000c00: ========================h=======================================
# 00001000: ========================h=h=hFhB=Fh=hSSSh========h==SFFh==h=====
# 00001400: ===h===========hSSFFS..hSh===..h=======h========...........h===h
# 00001800: ==............h==...........Sh==.....................h=.........
#        (427 lines all free)
# 0006c800: ........................
# GC memory layout; from 1102eec0:
#        (8004 lines all free)
# 007d1000: ....................
# Free memory: 8,635,136 Bytes

import random, time
random.seed(42)
t0 = time.ticks_us()
buf = bytearray(2*1024*1024)
t3 = time.ticks_us()
@ micropython.viper
def fill_buf(buf: object,lenbuf:int):
    p = ptr8(buf)
    i: int = 0
    t1 = time.ticks_us()
    while i < lenbuf:
        p[i] = 1 # random.randint(0,2**8-1)
        i += 1
    t2 = time.ticks_us()
    return t1, t2

t1, t2 = fill_buf(buf, len(buf))

print("Buffer filled with random data.")
print(f"Time taken to fill buffer: {t2 - t1:,} us")
print(f"Total time taken: {t2 - t0:,} us, {(t2-t1)/(2*1024*1024):,.2f} us/byte")
print(f"Free memory after buffer allocation: {gc.mem_free():,} Bytes")
print(f"Buffer allocation time: {t3-t0:,} us, {(t3-t0)/(2*1024*1024):,.2f} us/byte")

# Buffer filled with random data.
# Time taken to fill buffer: 32,533,415 us
# Total time taken: 32,780,179 us, 15.51 us/byte
# Free memory after buffer allocation: 6,537,040 Bytes
# Buffer allocation time: 246,764 us, 0.12 us/byte

# Free memory: 8,634,448 Bytes
# Buffer filled with 00000001.
# Time taken to fill buffer: 14,922,892 us
# Total time taken: 15,169,664 us, 7.12 us/byte
# Free memory after buffer allocation: 6,537,040 Bytes
# Buffer allocation time: 246,772 us, 0.12 us/byte

# Viper!!
# Free memory: 8,634,160 Bytes
# Buffer filled with 00000001.
# Time taken to fill buffer: 525,927 us
# Total time taken: 772,954 us, 0.25 us/byte
# Free memory after buffer allocation: 6,536,704 Bytes
# Buffer allocation time: 247,027 us, 0.12 us/byte


# sys clock + 100mhz
# Size : 15,204,352 bytes, 14848 KB, 14.5 MB
# Used : 8,192 bytes, 8 KB, 0.0078125 MB
# Free : 15,196,160 bytes, 14840 KB, 14.4921868 MB
# stack: 500 out of 12032
# GC: total: 8641216, used: 7168, free: 8634048
#  No. of 1-blocks: 49, 2-blocks: 36, max blk sz: 64, max free sz: 512276
# GC memory layout; from 20012680:
# 00000000: h=MLhhhhB=DhhTTB=DB=B=B=DhTh===B=DTDB=B=Th=====B=B=B=TB=B=B=B=B=
# 00000400: B=B=B=B=TB=TB=B=B=B=B=h===========h===B=TB=Sh============h======
# 00000800: ==T==h==================h=======================================
# 00000c00: ========================h=======================================
# 00001000: ========================h=h=hhB=FFh=h=SSh========SFFhSh==h==hSSF
# 00001400: FS..hS...Sh==Sh===.................h=======h========............
# 00001800: ...h==............h==...........Sh==................Sh===h=.....
# 00001c00: ...S.....................h==================....................
# 00002000: ....................h=.........Sh==.............h==.....h======.
# 00002400: ...................h===....................h====================
# 00002800: ===h================............................................
#        (423 lines all free)
# 0006c800: ........................
# GC memory layout; from 1102eec0:
#        (8004 lines all free)
# 007d1000: ....................
# Free memory: 8,634,048 Bytes
# Buffer filled with random data.
# Time taken to fill buffer: 317,664 us
# Total time taken: 470,347 us, 0.15 us/byte
# Free memory after buffer allocation: 6,536,592 Bytes
# Buffer allocation time: 152,426 us, 0.07 us/byte