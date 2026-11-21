import array, time
from machine import Pin
import rp2

# Configure LED count, GPIO pin, and brightness
NUM_LEDS = 1
PIN_NUM = 44 - 16
brightness = 0.5

@rp2.asm_pio(
    sideset_init=rp2.PIO.OUT_LOW,
    out_shiftdir=rp2.PIO.SHIFT_LEFT,
    autopull=True,
    pull_thresh=24,
)
def ws2812():
    T1 = 2
    T2 = 5
    T3 = 3
    wrap_target()
    label("bitloop")
    out(x, 1)                        .side(0)[T3 - 1]
    jmp(not_x, "do_zero")            .side(1)[T1 - 1]
    jmp("bitloop")                   .side(1)[T2 - 1]
    label("do_zero")
    nop()                            .side(0)[T2 - 1]
    wrap()

# Initialize State Machine at 8 MHz
sm = rp2.StateMachine(0, ws2812, freq=8_000_000, out_base=Pin(16), sideset_base=Pin(PIN_NUM))
sm.active(1)

# Buffer for 24-bit RGB values per LED (GRB format)
ar = array.array("I", [0 for _ in range(NUM_LEDS)])


def set_color(i, r, g, b):
    # Scale by brightness and pack into GRB format
    r = int(r * brightness)
    g = int(g * brightness)
    b = int(b * brightness)
    ar[i] = (g << 16) | (r << 8) | b


def show():
    # Push color data to PIO state machine FIFO
    for color in ar:
        sm.put(color)
    time.sleep_ms(10)


# Example usage: Set first LED to red and show
set_color(0, 255, 255, 255)
show()
