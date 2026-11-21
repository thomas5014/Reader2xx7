# machine.freq() does NOT skip the retune when the target already matches
# the current frequency -- every call unconditionally switches clk_sys away
# to PLL_USB (~48MHz) and back while PLL_SYS is reconfigured, even when
# nothing actually needs to change. The clock doesn't reset on a soft
# reset (only a power cycle restores the default), so re-running this
# script was calling machine.freq(240MHz) while ALREADY at 240MHz on every
# run after the first -- a real, verified clock glitch, not a no-op. With
# MICROPY_GC_SPLIT_HEAP on, GC objects can live in PSRAM, and PSRAM's QMI
# timing is calibrated for a specific clk_sys rate -- anything touching
# PSRAM-backed memory during that momentary wrong-clock window is reading
# it with stale timing. Matches the symptom exactly: hangs immediately,
# before any display/touch/LVGL code has even run.
import machine
if machine.freq() != 240_000_000:
    print(machine.freq(240_000_000))
else:
    print("already at 240MHz, skipping redundant retune")
import nt35510c as nt
import lvport as lvp
import lvgl as lv
print(lv.is_initialized())
lvp.init_display()
lvp.init_touch()
print(lvp.has_display())
lvp.init_lvgl()
print(lvp.has_display())
print('inits done')

scr = lv.screen_active()
scr.set_style_bg_color(lv.color_hex(0x000000), 0)
print('screen_active + bg color done')
lst = lv.list(scr)
lst.set_style_align(lv.ALIGN.TOP_LEFT,0)
lst.set_size(240,100)
lst.add_text("Click Stuff")
lst.add_button(lv.SYMBOL.FILE, "File").add_event_cb(lambda e: print("File clicked"), lv.EVENT.CLICKED, None)
lst.add_button(lv.SYMBOL.SETTINGS, "Settings").add_event_cb(lambda e: print("Settings clicked"), lv.EVENT.CLICKED, None)
lst.add_button(lv.SYMBOL.EDIT, "Edit").add_event_cb(lambda e: print("Edit clicked"), lv.EVENT.CLICKED, None)
lst.add_button(lv.SYMBOL.CLOSE, "Close").add_event_cb(lambda e: print("Close clicked"), lv.EVENT.CLICKED, None)    
print('list widget done')


# 2. Create a barebones button on that screen
btn = lv.button(scr)
btn.align(lv.ALIGN.CENTER, 0, 0) # Center the button on screen

# 3. Create a label text child inside the button
label = lv.label(btn)
label.set_text("Click Me")
print('button + label done')

# 4. Define an event handler function
def event_handler(e):
    code = e.get_code()
    if code == lv.EVENT.CLICKED:
        print("Button clicked!")

# 5. Attach the event callback to your button
btn.add_event_cb(event_handler, lv.EVENT.ALL, None)
print('event cb attached')

# 6. Load the screen to make it visible
# lv.screen_load(scr)

# Backlight: nothing in lvp.init_display()/init_lvgl() turns this on --
# it's always been a separate step (see nt35510c_dma_check.py etc.). Without
# it the panel can be rendering a correct frame and still look like nothing
# is happening.
from machine import PWM, Pin
backlight = PWM(Pin(20))
backlight.freq(50_000)
backlight.duty_u16(30535)
print('backlight on')

# A single lvp.handler() call may not be enough to actually flush anything
# -- every script that's shown something on the panel so far loops this.
#
# This has to run forever, not a fixed count: a bounded loop stops polling
# touch the moment it ends, so if you're still touching (or just released)
# near the end of the window, nothing is left running to notice the release
# and re-render the button out of its pressed state -- it was never a
# release-detection bug, just that nobody was listening anymore. Ctrl-C to
# stop when you're done.
import time
try:
    while True:
        lvp.handler()
        time.sleep_ms(20)
except KeyboardInterrupt:
    # machine.freq(200_000_000) # slow down before exiting, to avoid the retune glitch on next run -maybe-
    print("stopped")