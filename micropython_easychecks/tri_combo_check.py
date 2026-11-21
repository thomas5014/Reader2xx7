# Brief smoke test: WiFi (CYW43) + SDIO + display, all claiming PIO/DMA
# resources in the same boot, in a realistic app init order. Each stage
# prints pass/fail independently so a hang or corruption in one is
# immediately attributable rather than showing up as a mystery in another.

#!!!!!!!!!! reminant display network conflict, deak with later
import time

print("--- 1. WiFi (CYW43) ---")
import network, machine; machine.freq(200_000_000)
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
time.sleep(0.5)
print("MAC:", ":".join("%02x" % b for b in wlan.config('mac')))
nets = wlan.scan()
print(f"scan ok, {len(nets)} networks found")

# print("--- 2. SDIO ---")
# import sdio, os
# sd = sdio.SDCard()
# os.mount(sd, "/sd")
# print("mounted, /sd:", os.listdir("/sd")[:5], "...")

print("--- 3. Display ---")
from nt35510 import NT35510
from machine import PWM, Pin
backlight = PWM(Pin(20))
backlight.freq(50_000)
backlight.duty_u16(65535)
d = NT35510()
d.fill(0)

buf = bytearray(480 * 700 * 2)
with open("sample4_480-700.raw", "rb") as f:
    f.readinto(buf)
t0 = time.ticks_us()
d.draw_buf(0, 0, 480, 700, buf)
# d.fill(0); d.fill(0xffff);d.fill(0); d.fill(0xffff);d.fill(0); d.fill(0xffff)
t1 = time.ticks_us()
print(f"draw_buf ok, {t1-t0:,} us")

print("--- 4. Re-check WiFi after display DMA activity ---")
nets2 = wlan.scan()
print(f"post-display scan ok, {len(nets2)} networks found")

print("--- 5. Re-check SD after display DMA activity ---")
buf2 = bytearray(512)
sd.readblocks(0, buf2)
print("post-display SD read ok")

print("ALL PASSED")


