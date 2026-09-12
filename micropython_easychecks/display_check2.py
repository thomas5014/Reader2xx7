import display_check1 as dc
import time
from machine import PWM
bl = PWM(35,freq=50_000)
bl.duty_u16(65355)
d = dc.NT35510()
print("init done")
time.sleep(0.5)
d.fill_rect(20, 20, 80, 80, 0xF800)  # small red box near top-left