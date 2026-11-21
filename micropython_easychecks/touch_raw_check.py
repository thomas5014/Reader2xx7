# Instrument cst3240c.read_raw() to see exactly what the touch controller
# reports, poll by poll, across press+release cycles -- aimed at the
# "sometimes misses touches" / "button gets stuck pressed in LVGL" symptoms,
# which are probably the same underlying thing: cst3240_read()'s state==0
# check not reliably catching a real release.
#
# Prints only on change (not every poll) to avoid flooding/losing output in
# a tight loop -- but every change is printed, so a release that flickers
# or never arrives should be visible as a gap or a wrong-looking sequence.
#
# Tap and hold, then release, a few times. Also try a slow drag off the
# edge of a button vs a clean tap+lift, since those may behave differently.
# Ctrl-C to stop and see the summary.
import cst3240c, time

cst3240c.init()
print("polling -- tap/hold/release a few times, Ctrl-C when done")

n = 0
last = None
transitions = 0
t0 = time.ticks_ms()

try:
    while True:
        r = cst3240c.read_raw()
        n += 1
        if r is None:
            if last != "I2C_FAIL":
                t = time.ticks_diff(time.ticks_ms(), t0)
                print("n=%6d t=%7d ms  I2C READ FAILED" % (n, t))
                last = "I2C_FAIL"
                transitions += 1
            continue

        state = r[0] & 0x0F
        x = (r[1] << 4) | (r[3] >> 4)
        y = (r[2] << 4) | (r[3] & 0x0F)
        # Key on the whole raw tuple, not just state, so a state==0 sample
        # with leftover nonzero x/y/other bytes (stale-but-"released") also
        # counts as a distinct, printed event.
        if r != last:
            t = time.ticks_diff(time.ticks_ms(), t0)
            tag = "RELEASED" if state == 0 else "pressed "
            print("n=%6d t=%7d ms  %s  state=%d x=%4d y=%4d  raw=%s" % (
                n, t, tag, state, x, y, bytes(r).hex()))
            last = r
            transitions += 1
except KeyboardInterrupt:
    dt = time.ticks_diff(time.ticks_ms(), t0)
    print("\nstopped: %d polls in %d ms (%.0f polls/s), %d distinct states seen" % (
        n, dt, n / (dt / 1000), transitions))
