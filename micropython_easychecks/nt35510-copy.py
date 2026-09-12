from machine import Pin, PWM # type: ignore
import machine, micropython, framebuf, time
from micropython import const
from rp2 import PIO, StateMachine, asm_pio, DMA

PIO0_TXF1  = const(0x50200014)  # PIO0 SM1 TX FIFO
SM1_FREQ   =       100_000_000  
CLOCK      =      200_000_000
# Methods of Invertion
buf_inv    =      True
BSWAP      =      False
PIO_SDIR   =      PIO.SHIFT_RIGHT # or RIGHT
PTHRESH    = const(12) # or 32
DMASIZE    = const(1) # or 2 for full word
machine.freq(CLOCK)  # 250MHz for faster GPIO toggling


@micropython.viper
def color565(r:int,g:int,b:int) -> int:
    return ((r & 0xF8)<<8) | ((g & 0xFC)<<3) | (b>>3)

@micropython.viper
def cd_bright(color:int, brightness:int) -> int:
    if brightness == 0:
        return 0
    r = ((color >> 11) & 0x1F) * brightness // 100
    g = ((color >> 5)  & 0x3F) * brightness // 100
    b = (color & 0x1F) * brightness // 100
    return (r << 11) | (g << 5) | b

@micropython.viper
def cx_bright(color:int, brightness:int) -> int:
    if brightness == 0:
        return 0
    r = ((color >> 11) & 0x1F) * brightness // 255
    g = ((color >> 5)  & 0x3F) * brightness // 255
    b = (color & 0x1F) * brightness // 255
    return (r << 11) | (g << 5) | b

@micropython.asm_thumb
def _rev16(r0) -> int:
    rbit(r0,r0)
    mov(r1,16)
    lsr(r0,r1)

@micropython.asm_thumb
def _reverse16_buf(r0, r1): 
    # r0 = pointer to the start of the buffer (buf)
    # r1 = number of bytes in the buffer (len(buf))
    
    # Calculate the end address of the buffer
    add(r1, r0, r1)      # r1 now points to the byte JUST AFTER the buffer
    mov(r3, 16)
    
    label(LOOP)
    sub(r1, r1, 2)      # Move pointer back by 2 bytes to point to a valid halfword
    
    # Load using a 0 immediate offset
    ldrh(r2, [r1, 0])   
    
    # Reverse bits in place
    rbit(r2, r2)
    lsr(r2, r3)
    
    # Store back using a 0 immediate offset
    strh(r2, [r1, 0])

    # Check if we have processed back to the start of the buffer
    cmp(r1, r0)         
    bne(LOOP)           # Loop again if r1 != r0 (haven't reached the start)



SIO_BASE   = 0xD0000000  # alias for SIO (faster to access, same hardware)
GPIO_OUT   = SIO_BASE + 0x10
# NOTE: on RP2040 GPIO_OUT_SET sits at +0x14 right after GPIO_OUT, but
# RP2350 inserted GPIO_HI_OUT (for GPIO32-47) at +0x14 and pushed the
# real atomic-set register to +0x18 (confirmed against
# hardware/regs/sio.h: SIO_GPIO_OUT_SET_OFFSET=0x18). +0x14 on RP2350
# is a different register entirely (GPIO_HI_OUT, unrelated pins), so
# this was silently a no-op for DC (GPIO18) the whole time this path
# existed -- not something introduced by the pinout rewrite.
GPIO_SET   = SIO_BASE + 0x18
DATA_MASK  = const(0xFFFF)   # GPIO0-15 -- no shift, bits land directly
WR_MASK    = const(1 << 17)
DC_MASK    = const(1 << 18)
# IO_BANK0 atomic aliases for WR's CTRL register (GPIO17, base=0x40028000,
# offset = 0x04 + 17*8 = 0x8C). Atomic SET/CLR only modify the written
# bits — FUNCSEL is preserved after sm1.init().
GPIO_WR_CTRL_SET = 0x4002A08C  # IO_BANK0 base + 0x2000 (atomic SET) + 0x8C
GPIO_WR_CTRL_CLR = 0x4002B08C  # IO_BANK0 base + 0x3000 (atomic CLR) + 0x8C
OUTOVER_HIGH    = const(3 << 12)  # CTRL bits 13:12 = OUTOVER; value 3 = force output HIGH

@micropython.asm_thumb
def _strobe_bulk(r0, r1, r2, r3):
    # r0=addr, r1=low, r2=high, r3=count//16
    label(LOOP)
    str(r1, [r0, 0])
    str(r2, [r0, 0])
    str(r1, [r0, 0])
    str(r2, [r0, 0])
    str(r1, [r0, 0])
    str(r2, [r0, 0])
    str(r1, [r0, 0])
    str(r2, [r0, 0])
    str(r1, [r0, 0])
    str(r2, [r0, 0])
    str(r1, [r0, 0])
    str(r2, [r0, 0])
    str(r1, [r0, 0])
    str(r2, [r0, 0])
    str(r1, [r0, 0])
    str(r2, [r0, 0])
    str(r1, [r0, 0])
    str(r2, [r0, 0])
    str(r1, [r0, 0])
    str(r2, [r0, 0])
    str(r1, [r0, 0])
    str(r2, [r0, 0])
    str(r1, [r0, 0])
    str(r2, [r0, 0])
    str(r1, [r0, 0])
    str(r2, [r0, 0])
    str(r1, [r0, 0])
    str(r2, [r0, 0])
    str(r1, [r0, 0])
    str(r2, [r0, 0])
    str(r1, [r0, 0])
    str(r2, [r0, 0])
    sub(r3, 1)
    bne(LOOP)

@micropython.asm_thumb
def _strobe_rem(r0, r1, r2, r3):
    # r0=addr, r1=low, r2=high, r3=remainder
    label(LOOP)
    str(r1, [r0, 0])
    str(r2, [r0, 0])
    sub(r3, 1)
    bne(LOOP)

@micropython.asm_thumb
def _strobe_n(r0, r1, r2, r3):
    # r0=addr, r1=low, r2=high, r3=count
    # WR-low pulse width padding -- widened from 2 to 4 cycles since
    # "grainy" corruption persisted at 100MHz+2. No vendor AC-timing
    # table to compute an exact margin from, so this is empirical.
    label(LOOP)
    str(r1, [r0, 0])
    add(r3, 0)
    add(r3, 0)
    str(r2, [r0, 0])
    sub(r3, 1)
    bne(LOOP)

@asm_pio(
    out_init=(PIO.OUT_HIGH,)*16,
    # SHIFT_LEFT: the OSR's first-shifted-out bit is the value's MSB,
    # which lands on out_base (GPIO0) -- with DB0=GPIO15 down to
    # DB15=GPIO0, that's the bit-reversal DB0-DB15 needs, done for free
    # by the shift register (no software pass needed, see
    # _bus_write16_buf_dmapio). An earlier attempt at this direction
    # looked broken, but that was actually the unrelated GPIO_SET
    # address bug (fixed) masking whether this ever worked on its own
    # merits -- retested clean now.
    # pull_thresh=32 (not 16): with only one out(pins,16) per loop
    # iteration, threshold=16 would autopull a fresh 32-bit word on
    # *every* iteration, discarding the half that hadn't been shifted
    # out yet. threshold=32 lets two consecutive out(pins,16) calls
    # fully drain one pulled word (2 pixels) before the next pull.
    out_shiftdir=PIO_SDIR,
    autopull=True, pull_thresh=PTHRESH,
    sideset_init=PIO.OUT_HIGH,   # WR starts HIGH
)

def _pio_16wr_dma():
    out(pins, 16).side(1)        # pixel on D0-D15, WR=1 (1-cycle setup time)
    nop()        .side(0)        # WR=0 (write strobe low)
    nop()        .side(1)        # WR=1 (write complete)

sm1 = StateMachine(1, _pio_16wr_dma, freq=SM1_FREQ,
                   out_base=machine.Pin(0), sideset_base=machine.Pin(17))

_dma = DMA()
_dma_ctrl_le = _dma.pack_ctrl(
    # size=1 (16-bit, 1 pixel/transfer) -- matches pull_thresh=16 1:1,
    # no ambiguity about autopull preserving a leftover half-word.
    size=DMASIZE,
    inc_read=True,
    inc_write=False,
    treq_sel=1,
    # bswap=False: this is the *default* ctrl, for normal native
    # (little-endian) buffers -- fb.fill(), MyFrameBuffer, font glyph
    # rendering, anything not read straight from a big-endian raw file.
    # bswap=True was only ever correct for sample4_480-700.raw
    # specifically (confirmed big-endian earlier); leaving it on
    # globally corrupted every normal framebuf-sourced draw instead
    # (e.g. 0x07E0 green rendering as red). If a big-endian file needs
    # drawing again, that wants its own separate ctrl/call, mirroring
    # _bus_write16_buf vs _bus_write16_buf_be in the bit-banged path --
    # not a single global flag serving both cases.
    bswap=BSWAP,
    irq_quiet=True,
    enable=True,
)

class MyFrameBuffer(framebuf.FrameBuffer):
    def __init__(self, width, height, buf=None):
        self.buffer = memoryview(buf) if buf else memoryview(bytearray(width * height * 2))
        self.width = width
        self.height = height
        super().__init__(self.buffer, self.width, self.height, framebuf.RGB565)

class NT35510:
    def __init__(self, wr=17, cs=19, dc=18, rst=16, rd=32, width=480, height=800):
        # Data bus: must initialize so RP2350 clears pad isolation before viper writes
        # DB0-DB15 = GPIO15..GPIO0 (reversed, see _rev16) -- this loop
        # just needs to cover GPIO0-15, the isolation-clear itself
        # doesn't care about bit order.
        for i in range(0,16,1):
            Pin(i, Pin.OUT, value=0)
        self.wr  = Pin(wr, Pin.OUT, value=1)
        self.rd  = Pin(rd, Pin.OUT, value=1)
        self.cs  = Pin(cs, Pin.OUT, value=1)
        self.dc  = Pin(dc, Pin.OUT, value=1)
        self.rst = Pin(rst, Pin.OUT, value=1)
        # self.bl  = Pin(bl, Pin.OUT, value=0)  # or PWM later
        
        self.width = width
        self.height = height

        self.init_display()
        self.MyFrameBuffer = MyFrameBuffer

        self.sm1_freq = SM1_FREQ

    def init_display(self):
        # Just send sleep-out and fill small area red
        #_bl.off()
        # self.bl.on()
        # self.rd.high()
        self.cs.low()
        self.hw_reset()
        self.init_extra()
        self._cmd(0x3a00); self._data(0x55)               # set pixel format
        self._cmd(0x1100); time.sleep_ms(120)        # exit sleep booster on
        self._cmd(0x2900); time.sleep_ms(50)          # display on

    @micropython.viper
    def _bus_write16_too_fast(self, v: int, count: int):
        pout = ptr32(GPIO_OUT)
        v = pout[0] & ~DATA_MASK | int(_rev16(v)) | DC_MASK
        low:int  = v & ~WR_MASK
        high:int = v | WR_MASK
        bulk:int = count >> 4
        rem:int  = count & 15
        if bulk:
            _strobe_bulk(GPIO_OUT, low, high, bulk)
        if rem:
            _strobe_rem(GPIO_OUT, low, high, rem)

    @micropython.viper
    def _bus_write16_fast(self, value: int, count: int):
        if count <= 0:
            return

        pout = ptr32(GPIO_OUT)
        out: int = (
            (pout[0] & ~DATA_MASK)
            | DC_MASK
            | int(_rev16(value))
        )

        _strobe_n(GPIO_OUT, out & ~WR_MASK, out | WR_MASK, count)

    @micropython.viper
    def _bus_write16(self, value: int):
        pout = ptr32(GPIO_OUT)
        out: int = (
            (pout[0] & ~DATA_MASK)
            | DC_MASK
            | int(_rev16(value))
        )

        pout[0] = out & ~WR_MASK
        pout[0] = out | WR_MASK

    @micropython.viper
    def _cmd(self, value: int):
        pout = ptr32(GPIO_OUT)

        out: int = (
            (pout[0] & ~(DC_MASK | DATA_MASK))
            | int(_rev16(value))
        )

        pout[0] = out & ~WR_MASK   # WR low
        pout[0] = out | WR_MASK    # WR high

    @micropython.viper
    def _data(self, v:int):
        pout = ptr32(GPIO_OUT)
        out:int = (
            pout[0] & ~DATA_MASK | DC_MASK
            | int(_rev16(v))
        )

        pout[0] = out & ~WR_MASK
        pout[0] = out | WR_MASK

    @micropython.viper
    def _cmddata(self, c: int, d: int):
        pout = ptr32(GPIO_OUT)
        v:int = (
            pout[0] & ~(DC_MASK | DATA_MASK)
            | int(_rev16(c))
        )
        pout[0] = v & ~WR_MASK
        pout[0] = v | WR_MASK

        v:int = (
            pout[0] & ~DATA_MASK | DC_MASK
            | int(_rev16(d))
        )

        pout[0] = v & ~WR_MASK
        pout[0] = v | WR_MASK

    @micropython.viper
    def _bus_write16_buf(self, buf):
        pout = ptr32(GPIO_OUT)
        base_low:int = pout[0] & ~DATA_MASK & ~WR_MASK | DC_MASK
        i:int = 0
        buf_p = ptr16(buf)
        buf_len:int = int(len(buf)) // 2

        while i < buf_len:
            low:int = base_low | int(_rev16(buf_p[i]))
            pout[0] = low
            pout[0] = low | WR_MASK
            i += 1

    def _set_sm1_freq(self, freq=4):
        if freq > 20 and freq < CLOCK:  
            self.sm1_freq = freq
            return int(self.sm1_freq)
        elif freq == 4:
            return int(self.sm1_freq)
        else:
            print("Invalid frequency, try another")
            raise

    @micropython.viper
    def _bus_write16_buf_dmapio(self, buf, width, height):
        # Pin-order reversal (DB0=GPIO15..DB15=GPIO0) now happens in
        # hardware via out_shiftdir=SHIFT_LEFT in _pio_16wr_dma -- no
        # software pass needed here anymore. bswap (see _dma_ctrl_le) is
        # a separate, independent fix for source-buffer endianness, not
        # for pin order, so it stays regardless of this.
        ptr32(GPIO_SET)[0] = DC_MASK
        # Lock WR HIGH via OUTOVER during sm1.init() — the SIO→PIO FUNCSEL transition
        # briefly drives WR LOW (PIO output register = 0 before sideset_init applies).
        # Atomic SET/CLR leave FUNCSEL intact after sm1.init() changes it to PIO.
        ptr32(GPIO_SET)[0]        = DC_MASK       # DC=1 before FUNCSEL switch
        ptr32(GPIO_WR_CTRL_SET)[0] = OUTOVER_HIGH  # lock WR HIGH
        sm1.init(_pio_16wr_dma, freq=self.sm1_freq, out_base=machine.Pin(0), sideset_base=machine.Pin(17))
        ptr32(GPIO_WR_CTRL_CLR)[0] = OUTOVER_HIGH  # release — PIO already holds WR=1
        sm1.active(1)
        # count is in 32-bit words (size=2) -- each DMA transfer carries
        # 2 pixels, since the PIO program consumes one 32-bit FIFO word
        # as two 16-bit out(pins,16) pulls.
        _dma.config(read=buf, write=PIO0_TXF1, count=int(width * height)//int(DMASIZE),
                    ctrl=_dma_ctrl_le, trigger=True)
        # t0 = time.ticks_us()
        while _dma.active():
            pass
        while sm1.tx_fifo():
            pass
        # t1 = time.ticks_us()
        # print(f"{t1-t0:,} us DMA run time")
        time.sleep_us(1)
        sm1.active(0)
        self._re_pin()

    @micropython.viper
    def _re_pin(self):
        # Restore GPIO0-15 (data bus) and WR (GPIO17) to SIO so the
        # bit-bang path continues to work
        i: int = 0
        while i < 16:
            Pin(i, Pin.OUT, value=0)
            i += 1
        Pin(17, Pin.OUT, value=1)  # WR idle-high

    @micropython.viper
    def _bus_write16_buf_be(self, buf):
        # Read 4 bytes (2 big-endian pixels) per ptr32 load — halves SRAM transactions vs ptr8×2.
        # ptr32 on little-endian ARM: word = byte0 | (byte1<<8) | (byte2<<16) | (byte3<<24)
        # File layout per pair: [pix0_hi, pix0_lo, pix1_hi, pix1_lo]
        # → pix0 for display = (byte0<<8)|byte1 = ((word&0xFF)<<8)|((word>>8)&0xFF)
        # → pix1 for display = (byte2<<8)|byte3 = (((word>>16)&0xFF)<<8)|((word>>24)&0xFF)
        pout = ptr32(GPIO_OUT)
        base_low:int = pout[0] & ~DATA_MASK & ~WR_MASK | DC_MASK
        i:int = 0
        buf_p = ptr32(buf)
        buf_len:int = int(len(buf)) >> 2  # number of 4-byte words

        while i < buf_len:
            word:int = buf_p[i]
            pix0:int = ((word & 0xFF) << 8) | ((word >> 8) & 0xFF)
            low0:int = base_low | int(_rev16(pix0))
            pout[0] = low0
            pout[0] = low0 | WR_MASK
            pix1:int = (((word >> 16) & 0xFF) << 8) | ((word >> 24) & 0xFF)
            low1:int = base_low | int(_rev16(pix1))
            pout[0] = low1
            pout[0] = low1 | WR_MASK
            i += 1

    def hw_reset(self):
        # Timing matches the vendor demo (NT35510.h, nt35510_Initial) --
        # the low pulse was previously 50ms vs the vendor's 100ms. A
        # cold-start panel may reset fine either way, but a "warm" panel
        # (already running from a prior init, since only the RP2350 --
        # not the panel -- power-cycles between runs) is more likely to
        # need the full spec'd low-pulse width to fully reset.
        self.rst.high(); time.sleep_ms(50)
        self.rst.low(); time.sleep_ms(100)
        self.rst.high(); time.sleep_ms(50)

    @micropython.viper
    def set_window(self, x0: int, y0: int, x1: int, y1: int):
        pout = ptr32(GPIO_OUT)
        g:int  = pout[0]
        cb:int = g & ~DC_MASK & ~DATA_MASK
        db:int = g & ~DATA_MASK | DC_MASK
        wr:int = WR_MASK
        v:int  = 0

        # MADCTL=0x00 (portrait/vertical) -- the vendor demo (NT35510.h,
        # LCD_SetPos_Vertical) sends this before every window write.
        # Every command/data value below goes through _rev16() since
        # DB0-DB15 = GPIO15..GPIO0 (reversed), not a simple <<4 shift.
        v = cb | int(_rev16(0x3600))
        pout[0] = v & ~wr
        pout[0] = v | wr
        v = db | int(_rev16(0))
        pout[0] = v & ~wr
        pout[0] = v | wr

        v = cb | int(_rev16(0x2A00))
        pout[0] = v & ~wr;  pout[0] = v | wr
        v = db | int(_rev16(x0 >> 8))
        pout[0] = v & ~wr
        pout[0] = v | wr
        v = cb | int(_rev16(0x2A01))
        pout[0] = v & ~wr
        pout[0] = v | wr
        v = db | int(_rev16(x0 & 0xFF))
        pout[0] = v & ~wr
        pout[0] = v | wr
        v = cb | int(_rev16(0x2A02))
        pout[0] = v & ~wr
        pout[0] = v | wr
        v = db | int(_rev16(x1 >> 8))
        pout[0] = v & ~wr
        pout[0] = v | wr
        v = cb | int(_rev16(0x2A03))
        pout[0] = v & ~wr
        pout[0] = v | wr
        v = db | int(_rev16(x1 & 0xFF))
        pout[0] = v & ~wr
        pout[0] = v | wr
        v = cb | int(_rev16(0x2B00))
        pout[0] = v & ~wr
        pout[0] = v | wr
        v = db | int(_rev16(y0 >> 8))
        pout[0] = v & ~wr
        pout[0] = v | wr
        v = cb | int(_rev16(0x2B01))
        pout[0] = v & ~wr
        pout[0] = v | wr
        v = db | int(_rev16(y0 & 0xFF))
        pout[0] = v & ~wr
        pout[0] = v | wr
        v = cb | int(_rev16(0x2B02))
        pout[0] = v & ~wr
        pout[0] = v | wr
        v = db | int(_rev16(y1 >> 8))
        pout[0] = v & ~wr
        pout[0] = v | wr
        v = cb | int(_rev16(0x2B03))
        pout[0] = v & ~wr
        pout[0] = v | wr
        v = db | int(_rev16(y1 & 0xFF))
        pout[0] = v & ~wr
        pout[0] = v | wr
        v = cb | int(_rev16(0x2C00))
        pout[0] = v & ~wr
        pout[0] = v | wr

    @micropython.viper
    def fill_rect(self, x: int, y: int, width: int, height: int, color: int):
        self.set_window(x, y, x + width - 1, y + height - 1)
        self._bus_write16_fast(color, width*height)

    @micropython.viper
    def fill(self,color: int):
        self.fill_rect(0, 0, self.width, self.height, color)

    @micropython.viper
    def draw_buf(self, x: int, y: int, width: int, height: int, buf: object):
        self.set_window(x, y, x + width - 1, y + height - 1)
        self._bus_write16_buf_dmapio(buf, width, height)

    @micropython.viper
    def draw_buf_slow(self, x: int, y: int, width: int, height: int, buf: object):
        self.set_window(x, y, x + width - 1, y + height - 1)
        self._bus_write16_buf(buf)

    @micropython.viper
    def draw_buf_be(self, x: int, y: int, width: int, height: int, buf: object):
        # Big-endian variant: swaps bytes during draw, skipping a separate switch_bytes pass.
        self.set_window(x, y, x + width - 1, y + height - 1)
        self._bus_write16_buf_be(buf)

    @micropython.viper
    def draw_framebuf(self, x: int, y: int, fb: object):
        # only works with MyFrameBuffer
        self.draw_buf(x, y, fb.width, fb.height, fb.buffer)

    @micropython.viper
    def draw_framebuf_slow(self, x: int, y: int, fb: object):
        # only works with MyFrameBuffer
        self.draw_buf_slow(x, y, fb.width, fb.height, fb.buffer)

    @micropython.viper
    def pixel(self, x:int,y:int,color:int):
        self.set_window(x, y, x, y)
        self._bus_write16(color)

    @micropython.viper
    def hline(self, x:int,y:int,w:int,color:int):
        self.set_window(x, y, x+w-1, y)
        _bus_write16 = self._bus_write16
        for i in range(w):
            _bus_write16(color)

    @micropython.viper
    def vline(self, x:int,y:int,h:int,color:int):
        self.set_window(x, y, x, y+h-1)
        _bus_write16 = self._bus_write16
        for i in range(h):
            _bus_write16(color)

    def fb_text(self, text, x=0, y=0, color=-1, bg=0):
        str_length = max(8, len(text) * 8 + 8)
        fb = self.MyFrameBuffer(str_length, 8)
        if bg:
            fb.fill(bg)
        else:
            fb.fill(0)
        fb.text(text, 0, 0, color)
        self.draw_framebuf(x, y, fb)

    def line(self, x0:int, y0:int, x1:int, y1:int, color:int):
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        while True:
            self.pixel(x0, y0, color)
            if x0 == x1 and y0 == y1:
                break
            err2 = err * 2
            if err2 > -dy:
                err -= dy
                x0 += sx
            if err2 < dx:
                err += dx
                y0 += sy

    def init_extra(self):
        # Verified against the actual EastRising demo firmware for this
        # panel (ER-TFT043-9_8051_Tutorial/ER-TFT043-9_8080_16Bit/NT35510.h,
        # nt35510_Initial()) -- the previous version of this sequence was
        # not sourced from this exact panel's demo and had several analog
        # bias registers (VGH, VGLX ratio, VGMP/VGSP, VCOM) and the whole
        # post-unlock display-control block wrong, which put the panel in
        # a marginal operating point (inconsistent behavior across resets
        # rather than a clean failure).
        _cmd = self._cmd
        _data = self._data

        # LV2 page 1 -- analog bias (AVDD/AVEE/VCL/VGH/VGL/VCOM)
        _cmd(0xF000); _data(0x55)
        _cmd(0xF001); _data(0xAA)
        _cmd(0xF002); _data(0x52)
        _cmd(0xF003); _data(0x08)
        _cmd(0xF004); _data(0x01)

        _cmd(0xB000); _data(0x0C)  # AVDD 5.2V
        _cmd(0xB001); _data(0x0C)
        _cmd(0xB002); _data(0x0C)
        _cmd(0xB600); _data(0x34)  # AVDD ratio
        _cmd(0xB601); _data(0x34)
        _cmd(0xB602); _data(0x34)

        _cmd(0xB100); _data(0x0C)  # AVEE -5.2V
        _cmd(0xB101); _data(0x0C)
        _cmd(0xB102); _data(0x0C)
        _cmd(0xB700); _data(0x34)  # AVEE ratio
        _cmd(0xB701); _data(0x34)
        _cmd(0xB702); _data(0x34)

        _cmd(0xB200); _data(0x00)  # VCL -2.5V
        _cmd(0xB201); _data(0x00)
        _cmd(0xB202); _data(0x00)
        _cmd(0xB800); _data(0x34)  # VCL ratio
        _cmd(0xB801); _data(0x34)
        _cmd(0xB802); _data(0x34)

        _cmd(0xBF00); _data(0x01)  # VGH 15V (free pump)
        _cmd(0xB300); _data(0x08)
        _cmd(0xB301); _data(0x08)
        _cmd(0xB302); _data(0x08)
        _cmd(0xB900); _data(0x34)  # VGH ratio
        _cmd(0xB901); _data(0x34)
        _cmd(0xB902); _data(0x34)

        _cmd(0xB500); _data(0x08)  # VGL_REG -10V
        _cmd(0xB501); _data(0x08)
        _cmd(0xB502); _data(0x08)
        _cmd(0xBA00); _data(0x14)  # VGLX ratio
        _cmd(0xBA01); _data(0x14)
        _cmd(0xBA02); _data(0x14)

        _cmd(0xBC00); _data(0x00)  # VGMP/VGSP 4.5V/0V
        _cmd(0xBC01); _data(0x80)
        _cmd(0xBC02); _data(0x00)
        _cmd(0xBD00); _data(0x00)  # VGMN/VGSN -4.5V/0V
        _cmd(0xBD01); _data(0x80)
        _cmd(0xBD02); _data(0x00)

        _cmd(0xBE00); _data(0x00)  # VCOM
        _cmd(0xBE01); _data(0x50)

        # Gamma tables R+/G+/B+/R-/G-/B- (0xD1xx-0xD6xx) -- identical
        # curve on all six per the vendor sequence.
        gamma = (
            0x00, 0x37, 0x00, 0x50, 0x00, 0x70, 0x00, 0x8A, 0x00, 0x9F,
            0x00, 0xB7, 0x00, 0xD9, 0x01, 0x0D, 0x01, 0x32, 0x01, 0x6C,
            0x01, 0x9C, 0x01, 0xE9, 0x02, 0x29, 0x02, 0x2B, 0x02, 0x69,
            0x02, 0xAD, 0x02, 0xD8, 0x03, 0x11, 0x03, 0x37, 0x03, 0x64,
            0x03, 0x84, 0x03, 0xA0, 0x03, 0xB0, 0x03, 0xB9, 0x03, 0xBE,
            0x03, 0xC1,
        )
        for page in (0xD100, 0xD200, 0xD300, 0xD400, 0xD500, 0xD600):
            for offset, value in enumerate(gamma):
                _cmd(page + offset); _data(value)

        # LV2 page 0 -- display control / timing
        _cmd(0xF000); _data(0x55)
        _cmd(0xF001); _data(0xAA)
        _cmd(0xF002); _data(0x52)
        _cmd(0xF003); _data(0x08)
        _cmd(0xF004); _data(0x00)

        _cmd(0xB100); _data(0xFC)
        _cmd(0xB101); _data(0x00)

        _cmd(0xB400); _data(0x10)

        _cmd(0xB600); _data(0x05)  # source hold time

        _cmd(0xB700); _data(0x70)  # gate EQ control
        _cmd(0xB701); _data(0x70)

        _cmd(0xB800); _data(0x01)  # source EQ control (mode 2)
        _cmd(0xB801); _data(0x05)
        _cmd(0xB802); _data(0x05)
        _cmd(0xB803); _data(0x05)

        _cmd(0xBC00); _data(0x00)  # inversion mode (column)
        _cmd(0xBC01); _data(0x00)
        _cmd(0xBC02); _data(0x00)

        _cmd(0xCC00); _data(0x03)  # BOE's setting (default)
        _cmd(0xCC01); _data(0x50)
        _cmd(0xCC02); _data(0x50)

        _cmd(0xBD00); _data(0x01)  # display timing
        _cmd(0xBD01); _data(0x84)
        _cmd(0xBD02); _data(0x07)
        _cmd(0xBD03); _data(0x31)
        _cmd(0xBD04); _data(0x00)

        _cmd(0x3500); _data(0x00)  # tearing effect line off


if __name__ == "__main__":
    from machine import PWM
    backlight = PWM(Pin(20))
    backlight.freq(50_000)
    backlight.duty_u16(65535)
    d = NT35510()
    print(f"NT35510 initialize, Display: {d.width}X{d.height}")
    print(f"Clock freq: {CLOCK:,} hz")
    sl = time.sleep
    # sl(5)

    # d.fill(0xF800)  # red
    # print("first color")
    # sl(.8)
    # d.fill(0x07E0)  # green
    # sl(.8)
    # d.fill(0x001F)  # blue
    # sl(1)
    # # import sys
    # # sys.exit(0)
    # c = color565(150,200,150)
    # print("timing start")
    # t0 = time.ticks_ms()
    # for i in range(100):
    #     d.fill(cx_bright(c,i))
    # t1 = time.ticks_ms()
    # print("Time:",time.ticks_diff(t1,t0),"ms")
    # print(f"Time per frame: {time.ticks_diff(t1,t0)/100} ms")
    # d.fill(cx_bright(c,i))
    # t0 = time.ticks_us()
    # d.fill(cx_bright(c,i))
    # t1 = time.ticks_us()
    # print("Time:",time.ticks_diff(t1,t0),"us")

    # import sdio
    # sd = sdio.SDCard()
    # import os
    # os.mount(sd, "/sd")
    # novs = os.listdir("/sd")
    # print(novs)
    # name = "ZARQA_210_WN"
    # f"/sd/novels/{name}/Images/Cover_320-448.raw"
    # buf = bytearray(480*700*2)
    # path = "/sample4_480-700.raw"
    # with open(path, "rb") as f:
    #     f.readinto(buf)
    #     d.draw_buf(0, 0, 480, 700, buf)
    d.fill(0)
    buf = bytearray(d.width*700*2)
    with open("sample4_480-700.raw","rb") as f:
        f.readinto(buf)
        if buf_inv: _reverse16_buf(buf, len(buf))
        t0 = time.ticks_us()
        d.draw_buf(0, 0, 480, 700, buf)
        t1 = time.ticks_us()
        print(f"{t1-t0:,} us DMA from PSRAM")
    # d.fill(-1)

    # buf = bytearray(100*20*2)
    # import framebuf
    # fb = d.MyFrameBuffer(100, 20, buf)
    # fb.fill(0x7e0) # shows red
    # fb.text("Hello World", 0, 0, 0xFFFF)
    # d.draw_framebuf(0, 710, fb)
    # sl(30)
    # for i in range(16): # this is correct
    #     x = (i % 4) * 120
    #     y = (i // 4) * 200
    #     d.fill_rect(x,y,120,200,1<<(15-i))
    # sl(100)

    # time.sleep(1)
    # d.fill(cx_bright(c,0))
    # machine.freq(CLOCK//2)