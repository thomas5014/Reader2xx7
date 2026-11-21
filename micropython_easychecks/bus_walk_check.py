# bus_walk_check.py -- walking-ones/zeros test of D0-D15 (GPIO4-19).
# Panel is deselected (CS high, RD high, WR high) so it shouldn't drive
# the bus. Detects shorts between data lines and to GND/3V3 on the MCU
# side. It can NOT detect an open between a GPIO and the panel pin --
# use a meter, or rd_bus_check.py (undriven bit while RD low), for that.

import machine
import time

CS_PIN, DC_PIN, WR_PIN, RST_PIN, RD_PIN = 0, 1, 2, 3, 32
DATA_PINS = list(range(4, 20))  # D0=GPIO4 .. D15=GPIO19

machine.Pin(CS_PIN, machine.Pin.OUT, value=1)
machine.Pin(DC_PIN, machine.Pin.OUT, value=1)
machine.Pin(WR_PIN, machine.Pin.OUT, value=1)
machine.Pin(RST_PIN, machine.Pin.OUT, value=1)
machine.Pin(RD_PIN, machine.Pin.OUT, value=1)


def walk(drive, pull):
    # drive one line at `drive`, hold the rest as inputs with `pull`,
    # return the 16-bit readback
    bad = []
    for i, gpio in enumerate(DATA_PINS):
        pins = [machine.Pin(p, machine.Pin.IN, pull) for p in DATA_PINS]
        pins[i].init(machine.Pin.OUT, value=drive)
        time.sleep_ms(5)
        v = sum(p.value() << b for b, p in enumerate(pins))
        idle = 0xFFFF if pull == machine.Pin.PULL_UP else 0
        expect = (idle & ~(1 << i)) | (drive << i)
        if v != expect:
            diff = v ^ expect
            others = [b for b in range(16) if diff >> b & 1]
            bad.append((i, gpio, others))
        pins[i].init(machine.Pin.IN)
    return bad


fails = 0
for label, drive, pull in (
    ("walking 1 (others pulled down)", 1, machine.Pin.PULL_DOWN),
    ("walking 0 (others pulled up)", 0, machine.Pin.PULL_UP),
):
    print(label)
    for i, gpio, others in walk(drive, pull):
        fails += 1
        print("  D{} (GPIO{}) driven: unexpected bits D{}".format(
            i, gpio, ", D".join(str(b) for b in others)))
print("FAIL" if fails else "PASS: no shorts between data lines")
