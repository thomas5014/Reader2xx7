import machine

import neopixel



np = neopixel.NeoPixel(machine.Pin(44), 1)  # Initialize NeoPixel on pin 4 with 8 LEDs
np[0] = (255, 0, 0)  # Set the first LED to red
np.write()  # Update the NeoPixel to show the color

import machine
import neopixel
import time
import math

time.sleep(1)

# Configure the number of pixels and the data pin (GPIO 0)
NUM_PIXELS = 1
PIN_NUM = 44

pin = machine.Pin(PIN_NUM, machine.Pin.OUT)
pixels = neopixel.NeoPixel(pin, NUM_PIXELS)

def hsv_to_rgb(hue):
    # Convert a hue angle from 0-360 degrees to RGB values (0-255)
    h = float(hue)
    s = 1.0
    v = 1.0
    h60 = h / 60.0
    h60f = math.floor(h60)
    f = h60 - h60f
    p = int(255 * v * (1 - s))
    q = int(255 * v * (1 - s * f))
    t = int(255 * v * (1 - s * (1 - f)))
    v_val = int(255 * v)
    
    if h60f == 0:
        return (v_val, t, p)
    elif h60f == 1:
        return (q, v_val, p)
    elif h60f == 2:
        return (p, v_val, t)
    elif h60f == 3:
        return (p, q, v_val)
    elif h60f == 4:
        return (t, p, v_val)
    else:
        return (v_val, p, q)

# Continuously loop through the rainbow spectrum
while True:
    for hue in range(0, 360):
        color = hsv_to_rgb(hue)
        pixels.fill(color)
        pixels.write()
        time.sleep(0.02)
