import display_slow_check
import time
t0 = time.ticks_ms()
display_slow_check.run_visible_rect_test()
t1 = time.ticks_ms()

print("Function run time: {} ms".format(t1-t0))
