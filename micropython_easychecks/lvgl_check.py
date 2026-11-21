import machine
machine.freq(252_000_000)
print("freq set done")
import lvport
print("lvport import done")
lvport.init_display()
print("lvport display init done")
lvport.init_touch()
print("lvport touch init done")
lvport.init()
print("lvport init done")
import time

time.sleep(1)
lvport.demo()
print("lvport demo done")

# while True:
#     lvport.handler()
#     time.sleep_ms(5)
