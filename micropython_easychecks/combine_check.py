import time
from machine import I2C, Pin, PWM
from nt35510 import NT35510
from cst3240 import CST3240

# 1. Define I2C & Control Pins (Modify these to match your board schematic)
SDA_PIN = 30
SCL_PIN = 31
RST_PIN = 33
IRQ_PIN = 32

# 2. Setup Pins
rst = Pin(RST_PIN, Pin.OUT, value=1)
irq = Pin(IRQ_PIN, Pin.IN, Pin.PULL_UP)

# 3. Setup I2C Bus (Standard 400kHz recommended for touch controllers)
i2c = I2C(1, sda=SDA_PIN, scl=SCL_PIN, freq=100000)

global_time = time.ticks_ms()
def touch_isr(pin):
    global global_time
    current_time = time.ticks_ms()
    if time.ticks_diff(current_time, global_time) > 50:  # Debounce for 50ms
        global_time = current_time

irq.irq(trigger=Pin.IRQ_FALLING, handler=touch_isr)
touch = CST3240(i2c, rst_pin=rst, irq_pin=irq)


backlight = PWM(Pin(20))
backlight.freq(50_000)
backlight.duty_u16(10_000)
d = NT35510()
d.fill(-1)

prev = None
values = {}
last = 0
try:
    while True:
        points = None
        points = touch.read_touch()
        # raw = touch.read_raw()
        # print(raw)
        # if raw:
        #     ry = (raw[2] << 8) | raw[4]
        #     rx = (raw[1] << 8) | raw[3]
        #     x = rx * 480 // 7600
        #     y = ry * 800 // 12800
        #     d.pixel(x,y,0)
        #     t = time.ticks_ms()
        #     print(ry, time.ticks_diff(t, last)); last = t

        if points:
            # print(f"Touch Detected! Points: {points}")
            x,y = points[0]
            # d.fill_rect(x,y,10,10,0xf800)

            if prev and time.ticks_diff(time.ticks_ms(), prev[2]) < 100:
                # print(y, prev[1], time.ticks_diff(time.ticks_ms(), prev[2]))
                print(x,y)
                d.line(prev[0], prev[1], x, y, 0x00e0)
            prev = (x,y,time.ticks_ms())

            # if not y in values.keys():
            #     values[y] = [y, 1]
            #     print(f"Unique Y values: {len(values)}")
            # else:
            #     values[y][1] += 1

        time.sleep_ms(1)  # Polling interval matching ~20Hz updates
finally:
    print(f"Remaining values: {len(values)/8:.2f}%\n{values}")

# prev_y = None
# covered = set()          # every Y row the stroke passed through
# counts = {}              # raw reported Y -> hit count
# try:
#     while True:
#         points = touch.read_touch()
#         if points:
#             x, y = points[0]
            
#             counts[y] = counts.get(y, 0) + 1

#             if prev_y is not None and abs(y - prev_y) <= 40:   # same continuous stroke
#                 lo, hi = sorted((prev_y, y))
#                 covered.update(range(lo, hi + 1))
#             else:
#                 covered.add(y)
#             prev_y = y
#         else:
#             prev_y = None    # finger lifted -> don't bridge across strokes

#         time.sleep_ms(2)     # poll faster too
# finally:
#     missing = [y for y in range(800) if y not in covered]
#     print(f"Covered: {len(covered)/800*100:.2f}%  ({len(missing)} rows never crossed)")
#     print("Missing:", missing)
#     print("Reported-Y hit counts:", counts)
