# color_control.py -- palette helpers for font_blit_check.py.
#
# Rebuilt fresh rather than reusing ~/nt35510/bak/*/color_control.py:
# those predate this board's actual pin mapping, and more importantly
# their own color565() uses a different, non-standard RGB565 bit-packing
# than display_check1.color565() -- the one used everywhere else (fills,
# MyFrameBuffer's framebuf.RGB565 format, DMA writes). Mixing the two
# would make text render in the wrong colors even though solid fills
# looked correct, since the palette's bytes get written straight into
# the framebuffer with no channel reordering. This uses the standard
# color565 throughout instead.

from display_check1 import MyFrameBuffer, color565


def _scale(c, brightness):
    # brightness 0-100, blend RGB565 color c toward black.
    if brightness >= 100:
        return c
    if brightness <= 0:
        return 0
    r = (c >> 11) & 0x1F
    g = (c >> 5) & 0x3F
    b = c & 0x1F
    r = r * brightness // 100
    g = g * brightness // 100
    b = b * brightness // 100
    return (r << 11) | (g << 5) | b


def _rgb565_bytes(c):
    return bytes((c & 0xFF, c >> 8))


def make_palette(r, g, b, tones=(0, 33, 67, 100)):
    # 4-entry palette (2 bytes/entry) for GS2 (2-bit) glyphs: index 0 is
    # conventionally the transparent/background level -- _blit_gs2_row's
    # `key` skips writing that index entirely, so its actual color
    # rarely matters -- and indices 1-3 ramp from dim to full brightness.
    full = color565(r, g, b)
    data = b"".join(_rgb565_bytes(_scale(full, t)) for t in tones)
    return MyFrameBuffer(4, 1, bytearray(data))


PALETTE_WHITE = make_palette(0xFF, 0xFF, 0xFF)
