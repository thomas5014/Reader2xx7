from machine import Pin
import time

cs = Pin(19, Pin.OUT)

for _ in range(1000):
    cs.value(0)
    time.sleep_ms(100)
    cs.value(1)
    time.sleep_ms(100)  

