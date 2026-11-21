from machine import I2C, Pin
import time
import micropython
micropython.alloc_emergency_exception_buf(100)   # real ISR tracebacks

tpI2c = I2C(1, scl=31, sda=30, freq=400_000)
print(tpI2c.scan())

addr = 0x5A
rst  = Pin(33, Pin.OUT, Pin.PULL_UP)
tpcb = Pin(32, Pin.IN, Pin.PULL_UP)
irq  = Pin(tpcb, Pin.IN, Pin.PULL_UP)

time.sleep_ms(20)

rst.value(0)
time.sleep_ms(50)
rst.value(1)
time.sleep_ms(100)

# tpI2c.writeto(addr, bytes([0xD1, 0x01]))      # enter debug info mode
# time.sleep_ms(10)

# buf = tpI2c.readfrom_mem(addr, 0xD1F8, 4, addrsize=16)
# tp_resx = buf[0] | (buf[1] << 8)
# tp_resy = buf[2] | (buf[3] << 8)
# print("TP_RESX =", tp_resx, " TP_RESY =", tp_resy)

# tpI2c.writeto(addr, bytes([0xD1, 0x09]))      # back to Normal Mode — required, or coordinates go bad
# time.sleep_ms(10)

touched = False
try:
    tpI2c.writeto_mem(addr, 0xD000, b'\x00', addrsize=16)
    tpI2c.writeto(addr, bytes([0xD1, 0x09]))   # force Normal Mode
    # r = tpI2c.readfrom_mem(addr, 0x06, 6)
    time.sleep_ms(10)
    # print("Touch controller initialized successfully. Register 0x06:", r)
except OSError as e:
    print(e)
    pass

def callback(pin):
    global touched
    touched = True
    
irq.irq(trigger=Pin.IRQ_FALLING, handler=callback)

from time import sleep
while True:
    if touched:
        r = tpI2c.readfrom_mem(addr, 0xD000, 7, addrsize=16)
        tpI2c.writeto_mem(addr, 0xD000, b'\xAB', addrsize=16)
        # print("Touch detected. Data:", r)
        id, state = r[0] >> 4, r[0] & 0x0F
        x = (r[1] << 4) | (r[3] >> 4)
        y = (r[2] << 4) | (r[3] & 0x0F)
        area = r[4]
        pointnum = r[5] & 0x0F
        checksum = r[6]
        print("Touch info: ID =", id, ", State =", state, ", X =", x, ", Y =", y, ", Area =", area, ", Finger# =", pointnum, ", Checksum =", checksum)
        touched = False
    sleep(.01)


"""Touch info: ID = 0 , State = 6 , X = 368 , Y = 747 , Area = 181 , Finger# = 1 , Checksum = 171
Touch info: ID = 0 , State = 6 , X = 368 , Y = 747 , Area = 203 , Finger# = 1 , Checksum = 171
Touch info: ID = 0 , State = 6 , X = 368 , Y = 747 , Area = 206 , Finger# = 1 , Checksum = 171
Touch info: ID = 0 , State = 6 , X = 368 , Y = 747 , Area = 161 , Finger# = 2 , Checksum = 171
Touch info: ID = 0 , State = 6 , X = 368 , Y = 747 , Area = 161 , Finger# = 2 , Checksum = 171
Touch info: ID = 0 , State = 6 , X = 368 , Y = 747 , Area = 162 , Finger# = 2 , Checksum = 171
Touch info: ID = 0 , State = 6 , X = 368 , Y = 747 , Area = 164 , Finger# = 3 , Checksum = 171
Touch info: ID = 0 , State = 6 , X = 368 , Y = 747 , Area = 164 , Finger# = 3 , Checksum = 171
Touch info: ID = 0 , State = 6 , X = 368 , Y = 747 , Area = 165 , Finger# = 3 , Checksum = 171
Touch info: ID = 0 , State = 6 , X = 368 , Y = 747 , Area = 167 , Finger# = 4 , Checksum = 171
Touch info: ID = 0 , State = 6 , X = 368 , Y = 747 , Area = 168 , Finger# = 4 , Checksum = 171
Touch info: ID = 0 , State = 6 , X = 368 , Y = 747 , Area = 169 , Finger# = 4 , Checksum = 171
Touch info: ID = 0 , State = 6 , X = 368 , Y = 747 , Area = 168 , Finger# = 4 , Checksum = 171
Touch info: ID = 0 , State = 6 , X = 368 , Y = 747 , Area = 170 , Finger# = 5 , Checksum = 171
Touch info: ID = 0 , State = 6 , X = 368 , Y = 747 , Area = 171 , Finger# = 5 , Checksum = 171
Touch info: ID = 0 , State = 6 , X = 368 , Y = 747 , Area = 171 , Finger# = 5 , Checksum = 171
Touch info: ID = 0 , State = 6 , X = 368 , Y = 747 , Area = 172 , Finger# = 5 , Checksum = 171
Touch info: ID = 0 , State = 6 , X = 368 , Y = 747 , Area = 163 , Finger# = 5 , Checksum = 171
Touch info: ID = 1 , State = 6 , X = 353 , Y = 649 , Area = 233 , Finger# = 4 , Checksum = 171
Touch info: ID = 1 , State = 6 , X = 353 , Y = 649 , Area = 235 , Finger# = 4 , Checksum = 171
Touch info: ID = 2 , State = 6 , X = 205 , Y = 476 , Area = 223 , Finger# = 3 , Checksum = 171
Touch info: ID = 2 , State = 6 , X = 205 , Y = 476 , Area = 226 , Finger# = 3 , Checksum = 171
Touch info: ID = 2 , State = 6 , X = 205 , Y = 476 , Area = 223 , Finger# = 3 , Checksum = 171
Touch info: ID = 2 , State = 6 , X = 205 , Y = 476 , Area = 157 , Finger# = 3 , Checksum = 171
Touch info: ID = 3 , State = 6 , X = 191 , Y = 316 , Area = 195 , Finger# = 2 , Checksum = 171
Touch info: ID = 3 , State = 6 , X = 191 , Y = 316 , Area = 191 , Finger# = 2 , Checksum = 171
Touch info: ID = 3 , State = 6 , X = 191 , Y = 316 , Area = 111 , Finger# = 2 , Checksum = 171
Touch info: ID = 4 , State = 6 , X = 251 , Y = 138 , Area = 151 , Finger# = 1 , Checksum = 171
Touch info: ID = 4 , State = 6 , X = 250 , Y = 135 , Area = 150 , Finger# = 1 , Checksum = 171
Touch info: ID = 4 , State = 6 , X = 249 , Y = 133 , Area = 145 , Finger# = 1 , Checksum = 171"""