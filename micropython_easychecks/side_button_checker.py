import machine
from time import sleep
import time

t = time.ticks_ms()

b = machine.Pin(34, machine.Pin.IN, machine.Pin.PULL_UP)
def side_callback(val):
    global t
    if time.ticks_diff(time.ticks_ms(), t) < 200:
        print("turning off")
        machine.Pin(40, machine.Pin.OUT).value(0)
    t = time.ticks_ms()
    print("pressed!",val)
machine.Pin(34, machine.Pin.IN, machine.Pin.PULL_UP)
b.irq(trigger=machine.Pin.IRQ_FALLING, handler=side_callback)

while True:
    # if b.value() == 0:
    #     print("Button pressed")
    # else:
    #     print("Button released")
    sleep(.1)