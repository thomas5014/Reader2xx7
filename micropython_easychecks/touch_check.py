import time
from machine import SoftI2C, Pin
from cst3240 import CST3240

# 1. Define I2C & Control Pins (Modify these to match your board schematic)
SDA_PIN = 30
SCL_PIN = 31
RST_PIN = 33
IRQ_PIN = 32

# 2. Setup Pins
rst = Pin(RST_PIN, Pin.OUT, value=1)
irq = Pin(IRQ_PIN, Pin.IN, Pin.PULL_UP)

# 3. Setup I2C Bus (Standard 400kHz recommended for touch controllers)
i2c = SoftI2C(sda=SDA_PIN, scl=SCL_PIN, freq=100000)

global_time = time.ticks_ms()
def touch_isr(pin):
    # print("ISR: Touch event detected!",pin)
    global global_time
    current_time = time.ticks_ms()
    if time.ticks_diff(current_time, global_time) > 50:  # Debounce for 50ms
        # print("IRQ: Touch event detected!")
        global_time = current_time
    else:
        pass
        # print("IRQ: Ignored bounce event")

irq.irq(trigger=Pin.IRQ_FALLING, handler=touch_isr)

# 4. Instantiate Touch Driver
touch = CST3240(i2c, rst_pin=rst, irq_pin=irq)

print("CST3240 Driver Initialized. Touch the screen to see coordinates...")

# 5. Polling Loop
while True:
    points = touch.read_touch()
    if points:
        print(f"Touch Detected! Points: {points}")
    # if irq.value() == 0:  # Active low IRQ indicates touch event
    #     print("Touch detected! Reading coordinates...")
        # points = touch.read_touch()
        # print(f"Touch Points: {points}")
    time.sleep_ms(50)  # Polling interval matching ~20Hz updates
