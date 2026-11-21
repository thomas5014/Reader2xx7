# Logs the 3.3V/5V rails continuously on core1 (no GIL -- keeps running even
# if core0 locks up) while core0 runs lvport.init() repeatedly on the main
# thread. If a crash correlates with a brownout, the live-printed trace
# should show voltage sagging in the samples right before the connection
# drops. One print per sample (not batched) since frequent small prints have
# survived crashes here better than anything printed right before one dies.
#
# Run this whole file (not piecemeal at the REPL) so the sampler thread is
# already running before the risky call starts.
import _thread, time
from machine import Pin, ADC

bat = ADC(Pin(45))  # 3.3V rail
sys_ = ADC(Pin(46))  # 5V rail

_stop = False


def sampler():
    n = 0
    t0 = time.ticks_us()
    while not _stop:
        raw_v3 = bat.read_u16()
        raw_v5 = sys_.read_u16()
        v3 = (raw_v3 / 65535) * 3.3 * 3
        v5 = (raw_v5 / 65535) * 3.3 * 3
        t = time.ticks_diff(time.ticks_us(), t0)
        print("RAIL %6d  t=%8d us  3V3=%.3f  5V=%.3f" % (n, t, v3, v5))
        n += 1
        time.sleep_ms(20)


_thread.start_new_thread(sampler, ())
time.sleep_ms(200)  # let a few baseline samples print before the risky part

import machine
machine.freq(150_000_000)
print(">>> about to call lvport.init() <<<")
import lvport
lvport.init()
print(">>> lvport.init() returned OK <<<")

time.sleep_ms(500)
_stop = True
