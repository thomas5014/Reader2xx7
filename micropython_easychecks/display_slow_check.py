# display_slow_check.py -- deliberately slow, minimal-dependency pixel
# writer for scope/logic-analyzer probing.
#
# This bypasses the viper/asm_thumb fast bus path in display_check1.py
# entirely: every GPIO here is a plain machine.Pin, toggled one at a
# time with generous delays. The point is to remove all doubt about
# whether a bug in the fast-path code (we've already found and fixed a
# couple) is responsible for what you see -- this is the simplest
# possible correct implementation of the 8080 16-bit parallel write
# cycle, slow enough to capture cleanly on essentially any scope or
# logic analyzer.
#
# It also skips the full power/gamma tuning from init_extra() -- that's
# about picture *quality*, not about whether a write electrically lands
# on the panel at all, which is the only thing this script is checking.
# If a pixel actually shows up, that's a bonus; the scope trace is the
# real test.

import machine
import time
print(machine.freq(50_000_000))

WR_PIN, CS_PIN, DC_PIN, RST_PIN, RD_PIN = 17, 19, 18, 16, 32
DATA_PINS = list(range(0, 16))  # D0=GPIO4 .. D15=GPIO19

STEP_MS = 20  # per phase -- trivially capturable on any scope/LA

wr = machine.Pin(WR_PIN, machine.Pin.OUT, value=1)
cs = machine.Pin(CS_PIN, machine.Pin.OUT, value=1)
dc = machine.Pin(DC_PIN, machine.Pin.OUT, value=1)
rst = machine.Pin(RST_PIN, machine.Pin.OUT, value=1)
# RD also has a 10k pull-up to 3V3 on the board, so it's safe (stays
# high) even before this Pin object takes over -- GPIO32 just lets us
# actively pulse it low for a read cycle.
rd = machine.Pin(RD_PIN, machine.Pin.OUT, value=1)
data = [machine.Pin(15-i, machine.Pin.OUT, value=0) for i in DATA_PINS]


def _set_bus(value):
    for i, pin in enumerate(data):
        pin.value((value >> i) & 1)


def _write16(value, is_data):
    dc.value(1 if is_data else 0)
    _set_bus(value)
    time.sleep_ms(STEP_MS)
    wr.value(0)
    time.sleep_ms(STEP_MS)
    wr.value(1)
    time.sleep_ms(STEP_MS)


def cmd(c):
    _write16(c, is_data=False)


def data_word(d):
    _write16(d, is_data=True)


def reset():
    rst.value(1); time.sleep_ms(50)
    rst.value(0); time.sleep_ms(100)
    rst.value(1); time.sleep_ms(50)


def _bus_input():
    for pin in data:
        pin.init(machine.Pin.IN)


def _bus_output():
    for pin in data:
        pin.init(machine.Pin.OUT, value=0)


def _read_bus():
    value = 0
    for i, pin in enumerate(data):
        value |= pin.value() << i
    return value


def read_reg(command, n_bytes=1, delay_ms=STEP_MS):
    # 8080 read cycle -- EXPERIMENTAL, not verified against vendor docs
    # (the ER-TFT043-9 demo source we've used everywhere else is
    # write-only, no read example). Assumptions being made here, in case
    # the result looks like garbage and we need to know what to
    # question first:
    #   - DC=1 during the read-data phase, same convention as writes.
    #   - The response is clocked out MSB-of-transaction-first, one
    #     byte per RD pulse, sampled while RD is held low.
    #   - No CMD2 page-select needed to read this register (unlike many
    #     of the write-side registers, which live behind the 0xF000-04
    #     page unlock).
    # Timing is absurdly generous (20ms/phase) relative to any real
    # NT35510 read-cycle spec, which will be nanoseconds-to-low-hundreds
    # of-ns, so speed is not a concern here -- only whether the sequence
    # itself is correct.
    cmd(command)
    dc.value(1)
    _bus_input()
    time.sleep_ms(delay_ms)

    values = []
    for _ in range(n_bytes):
        rd.value(0)
        time.sleep_ms(delay_ms)
        values.append(_read_bus())
        rd.value(1)
        time.sleep_ms(delay_ms)

    _bus_output()
    return values


def run_read_test():
    print("CS low")
    cs.value(0)
    time.sleep_ms(STEP_MS)

    print("hardware reset")
    reset()

    print("sleep out")
    cmd(0x1100)
    time.sleep_ms(150)

    print("display on")
    cmd(0x2900)
    time.sleep_ms(60)

    print("reading Display Power Mode (cmd 0x0A00), 3 read cycles")
    print("  (some MIPI-style displays return a dummy first byte -- reading")
    print("   a few in a row so we can see if that's happening here)")
    for i, v in enumerate(read_reg(0x0A00, n_bytes=3)):
        print("  read #{}: 0x{:04x}  (low 0x{:02x}, high 0x{:02x})".format(
            i, v, v & 0xFF, (v >> 8) & 0xFF
        ))

    print("reading Display ID (cmd 0x0400), 4 read cycles")
    for i, v in enumerate(read_reg(0x0400, n_bytes=4)):
        print("  read #{}: 0x{:04x}".format(i, v))

    print("done")


def run_gram_readback_test():
    # The Power Mode read confirmed the panel receives/executes our
    # commands correctly. This test goes one step further: write a
    # known color into GRAM via the normal set_window + Write Memory
    # Start (0x2C00) path, then re-select the same window and read it
    # back via Read Memory Start (0x2E00). If the color round-trips,
    # the pixel-write path is proven correct end-to-end at the digital
    # level, and any remaining "nothing visible" issue has to be
    # analog (LC-cell bias/drive), not a data/command bug.
    print("CS low")
    cs.value(0)
    time.sleep_ms(STEP_MS)

    print("hardware reset")
    reset()

    print("sleep out")
    cmd(0x1100)
    time.sleep_ms(150)

    print("pixel format 16bpp")
    cmd(0x3A00); data_word(0x55)

    print("display on")
    cmd(0x2900)
    time.sleep_ms(60)

    color = 0xF800  # red
    print("writing 1 pixel at (0,0), color 0x{:04x}".format(color))
    set_pixel(0, 0, color)

    print("re-selecting (0,0) and reading Memory Start (cmd 0x2E00), 4 read cycles")
    print("  (Read Memory Start often returns a dummy first word -- reading")
    print("   a few in a row so we can see which one, if any, is our color)")
    cmd(0x2A00); data_word(0x00)
    cmd(0x2A01); data_word(0x00)
    cmd(0x2A02); data_word(0x00)
    cmd(0x2A03); data_word(0x00)
    cmd(0x2B00); data_word(0x00)
    cmd(0x2B01); data_word(0x00)
    cmd(0x2B02); data_word(0x00)
    cmd(0x2B03); data_word(0x00)
    for i, v in enumerate(read_reg(0x2E00, n_bytes=4)):
        match = "  <-- MATCHES the color we wrote!" if v == color else ""
        print("  read #{}: 0x{:04x}{}".format(i, v, match))

    print("done")


def fill_rect(x0, y0, x1, y1, color, wr_delay_ms=1):
    # DC and the color bus are held constant for the whole fill -- only
    # WR toggles per pixel, matching how a real solid fill works (same
    # shape as the fast asm_thumb path in display_check1.py, just plain
    # Pin toggles). wr_delay_ms is deliberately much shorter than
    # STEP_MS here: this test is about visibility, not scope capture.
    cmd(0x3600); data_word(0x00)  # MADCTL -- portrait, matches vendor demo
    cmd(0x2A00); data_word(x0 >> 8)
    cmd(0x2A01); data_word(x0 & 0xFF)
    cmd(0x2A02); data_word(x1 >> 8)
    cmd(0x2A03); data_word(x1 & 0xFF)
    cmd(0x2B00); data_word(y0 >> 8)
    cmd(0x2B01); data_word(y0 & 0xFF)
    cmd(0x2B02); data_word(y1 >> 8)
    cmd(0x2B03); data_word(y1 & 0xFF)
    cmd(0x2C00)

    dc.value(1)
    _set_bus(color)
    count = (x1 - x0 + 1) * (y1 - y0 + 1)
    for _ in range(count):
        wr.value(0)
        time.sleep_ms(wr_delay_ms)
        wr.value(1)
        time.sleep_ms(wr_delay_ms)


def run_visible_rect_test():
    print("CS low")
    cs.value(0)
    time.sleep_ms(STEP_MS)

    print("hardware reset")
    reset()

    print("sleep out")
    cmd(0x1100)
    time.sleep_ms(150)

    print("pixel format 16bpp")
    cmd(0x3A00); data_word(0x55)

    print("display on")
    cmd(0x2900)
    time.sleep_ms(60)

    print("filling a 60x60 blue square at (0,0) -- blue chosen to be")
    print("unambiguous regardless of red-green color vision")
    fill_rect(0, 0, 59, 59, 0x001F)

    print("done -- look at the top-left corner of the panel")


def set_pixel(x, y, color):
    cmd(0x2A00); data_word(x >> 8)
    cmd(0x2A01); data_word(x & 0xFF)
    cmd(0x2A02); data_word(x >> 8)
    cmd(0x2A03); data_word(x & 0xFF)
    cmd(0x2B00); data_word(y >> 8)
    cmd(0x2B01); data_word(y & 0xFF)
    cmd(0x2B02); data_word(y >> 8)
    cmd(0x2B03); data_word(y & 0xFF)
    cmd(0x2C00)
    data_word(color)


def run():
    print("CS low")
    cs.value(0)
    time.sleep_ms(STEP_MS)

    print("hardware reset")
    reset()

    print("sleep out")
    cmd(0x1100)
    time.sleep_ms(150)

    print("pixel format 16bpp")
    cmd(0x3A00); data_word(0x55)

    print("display on")
    cmd(0x2900)
    time.sleep_ms(60)

    print("pixel 1: (0,0) red 0xF800")
    set_pixel(0, 0, 0xF800)

    print("pixel 2: (1,0) green 0x07E0")
    set_pixel(1, 0, 0x07E0)

    print("done -- probe WR (GPIO2) / DC (GPIO1) / CS (GPIO0) / D0-D15 (GPIO4-19)")


if __name__ == "__main__":
    run_visible_rect_test()
    # run()
    # run_read_test()