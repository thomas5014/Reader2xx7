# First LVGL screen, driven entirely by C glue (modlvport.c): display flush via
# the PIO/DMA path, touch via cst3240c, LVGL tick from mp_hal_ticks_ms.
#
# lvport.init() is watchdog-guarded (5s) with progress "marks" written to a
# watchdog scratch register -- no printf inside the guarded section, since a
# live print there previously locked the board up solid. If init hangs, the
# watchdog resets the board on its own after 5s (no manual power cycle
# needed) and the mark survives that reset. This script checks for that
# FIRST, before doing anything else, so a crash from the previous run
# self-reports on the very next boot.
import lvport

was_wdt, stage = 0,0 #lvport.last_crash()
STAGE_NAMES = {
    0: "(no mark set -- crashed/reset before lvport.init() ran at all, or this is a power-on reset)",
    1: "MARK_START (watchdog just armed, about to call nt35510_init)",
    2: "MARK_NT35510_INIT_DONE (crashed in/after cst3240_init)",
    3: "MARK_CST3240_INIT_DONE (crashed in lv_init)",
    4: "MARK_LV_INIT_DONE (crashed in lv_display_create/lv_display_set_buffers)",
    5: "MARK_DISPLAY_CREATE_DONE (crashed in lv_indev_create)",
    6: "MARK_INDEV_CREATE_DONE (crashed disarming the watchdog -- shouldn't be reachable)",
    7: "MARK_INIT_DONE (full success last time; this reset is something else)",
}
print("watchdog caused the last reset:", was_wdt)
print("last stage mark:", stage, "--", STAGE_NAMES.get(stage, "(unknown)"))
if was_wdt and stage < 2:
    print(">>> HUNG INSIDE nt35510_init() (mark 1 set, mark 2 never written)")
elif was_wdt and stage == 2:
    print(">>> HUNG INSIDE cst3240_init() (mark 2 set, mark 3 never written)")
elif was_wdt and 2 < stage < 7:
    print(">>> HUNG INSIDE an LVGL call, not the hardware drivers")

import machine, time
machine.freq(252_000_000)
from machine import PWM, Pin

print("calling lvport.init() now...")
lvport.init()
print("lvport.init() returned -- no hang this time")

bl = PWM(Pin(20)); bl.freq(50_000); bl.duty_u16(65535)
lvport.demo()

frames = 0
t0 = time.ticks_ms()
try:
    while True:
        lvport.handler()
        frames += 1
        time.sleep_ms(5)
except KeyboardInterrupt:
    dt = time.ticks_diff(time.ticks_ms(), t0)
    print("handler calls: %d in %d ms" % (frames, dt))
