# rd_bus_check.py -- is anything actually driving D0-D15 during a read?
# Reads the bus with RD low, once with pull-ups and once with pull-downs.
# If the two readings differ, nothing external is driving the bus.

import machine
import time

CS_PIN, DC_PIN, WR_PIN, RST_PIN, RD_PIN = 0, 1, 2, 3, 32
DATA_PINS = list(range(4, 20))  # D0=GPIO4 .. D15=GPIO19

cs = machine.Pin(CS_PIN, machine.Pin.OUT, value=1)
dc = machine.Pin(DC_PIN, machine.Pin.OUT, value=1)
wr = machine.Pin(WR_PIN, machine.Pin.OUT, value=1)
rst = machine.Pin(RST_PIN, machine.Pin.OUT, value=1)
rd = machine.Pin(RD_PIN, machine.Pin.OUT, value=1)


def sample(pull, rd_low=True):
    pins = [machine.Pin(p, machine.Pin.IN, pull) for p in DATA_PINS]
    time.sleep_ms(20)
    rd.value(0 if rd_low else 1)
    time.sleep_ms(20)
    v = sum(pin.value() << i for i, pin in enumerate(pins))
    rd.value(1)
    return v


cs.value(0)
print("RD pin reads back:", rd.value())
for name, pull in (("pull-up  ", machine.Pin.PULL_UP), ("pull-down", machine.Pin.PULL_DOWN)):
    for rd_low in (True, False):
        print(name, "RD", "low " if rd_low else "high", "{:016b}".format(sample(pull, rd_low)))
print("pattern identical with RD high and low -> bus held by something other than the panel's RD-gated output")
print("pattern only with RD low -> panel is driving, but not with real register data")
