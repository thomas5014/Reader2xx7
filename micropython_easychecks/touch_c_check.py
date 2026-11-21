# Exercise the C touch driver (cst3240c). Needs firmware built from the
# reader2xx7-firmware branch. Touch the panel; prints (x, y) on each poll
# while a finger is down and a "released" line when it lifts. Ctrl-C to stop.
import cst3240c, time

cst3240c.init()
print("touch init ok -- touch the screen (corners should read ~0/479 x, 0/799 y)")

down = False
prev = 0
while True:
    p = cst3240c.read()
    if p is not None:
        if p != prev:
            print(p)
        down = True
    elif down:
        print("released")
        down = False
    prev = p
    time.sleep_ms(20)
