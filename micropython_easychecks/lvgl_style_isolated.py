# Isolated repro attempt for the "crashes on scr.set_style_bg_color(...),
# second run in the same boot (soft reset, no power cycle)" bug found in
# lvgl_test1.py. Deliberately uses NONE of our drivers -- no nt35510c, no
# cst3240c, no lvport -- just plain `lvgl`, a dummy no-op flush_cb and a
# throwaway buffer, so a real panel/PIO/DMA/I2C touch bus is never touched
# at all. If this still crashes at the same place on a second run, the bug
# is purely in LVGL's own state handling across a soft reset (or in how
# MicroPython's GC/module-reinit interacts with it) -- nothing to do with
# our hardware drivers. If it DOESN'T crash, our drivers are somehow
# involved despite seeming unrelated to styles.
#
# Run once after a full power cycle (should work cleanly), then trigger a
# soft reset and run again (same script, same way) -- that's the case that
# broke in lvgl_test1.py.
import machine
if machine.freq() != 240_000_000:
    print(machine.freq(240_000_000))
else:
    print("already at 240MHz, skipping redundant retune")
import gc
gc.collect()

import lvgl as lv
print("import lvgl done, is_initialized:", lv.is_initialized())

# Tiny throwaway buffer -- 10 lines is plenty, nothing real ever reads it
# since flush_cb just immediately reports "done" without touching hardware.
buf = bytearray(480 * 10 * 2)


def flush_cb(disp, area, px_map):
    disp.flush_ready()


disp = lv.display_create(480, 800)
print("display_create done")
disp.set_color_format(lv.COLOR_FORMAT.RGB565)
disp.set_buffers(buf, None, len(buf), lv.DISPLAY_RENDER_MODE.PARTIAL)
disp.set_flush_cb(flush_cb)
print("display configured (no real hardware touched)")

scr = lv.screen_active()
print("screen_active done")
scr.set_style_bg_color(lv.color_hex(0x000000), 0)
print("set_style_bg_color done -- if you see this, it did NOT crash here")
