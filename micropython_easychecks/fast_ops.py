# fast_ops.py — shared viper + asm_thumb primitives for the PSRAM and
# NOR-flash testers (psram_check.py, nor_flash_check.py).
#
# Split of labor:
#   - asm_thumb: fixed-pattern fill/verify (asm_fill32/asm_verify32),
#     self-referential address-pattern fill/verify, and a CRC32. These are
#     hand-written Thumb-2 so the inner loop is exactly the instructions
#     below — no bytecode dispatch, no implicit bounds checks.
#   - viper: the LFSR (xorshift32) pattern generator/verifier. Doing this
#     one in viper instead of asm_thumb is a deliberate choice: viper's
#     typed ptr32 indexing is close to asm_thumb speed here (the loop body
#     is dominated by three shift/xor ops, not by dispatch overhead) and
#     it's far less error-prone to write and modify than hand-rolling a
#     32-bit xorshift in Thumb-2.
#
# Target: RP2350 (Cortex-M33), MicroPython rp2 port. asm_thumb works on any
# Cortex-M target; the viper functions have no RP2-specific assumptions
# either, so this module is portable to other Cortex-M boards.
#
# asm_thumb calling convention used throughout (see MicroPython docs,
# reference/asm_thumb2_*.html): up to 3 args in r0/r1/r2, return value in
# r0, r0-r3 are scratch, r4-r7 must be push/pop'd if used, functions must
# end with an explicit bx(lr). Return type is annotated -> int / -> uint
# so a result with the MSB set (e.g. our -1 "not found" sentinel, or a
# CRC32 above 0x7fffffff) round-trips correctly instead of being
# reinterpreted as a huge positive number.

import micropython

# ---------------------------------------------------------------------
# asm_thumb: fixed 32-bit pattern fill / verify
# ---------------------------------------------------------------------


@micropython.asm_thumb
def asm_fill32(r0, r1, r2):
    # r0 = dest byte address, r1 = 32-bit pattern, r2 = word count
    label(fill_loop)
    cmp(r2, 0)
    beq(fill_done)
    str(r1, [r0, 0])
    add(r0, r0, 4)
    sub(r2, r2, 1)
    b(fill_loop)
    label(fill_done)


@micropython.asm_thumb
def asm_verify32(r0, r1, r2) -> int:
    # r0 = ptr, r1 = expected 32-bit pattern, r2 = word count
    # returns the word index of the first mismatch, or -1 if all match
    push({r4})
    mov(r3, 0)  # r3 = word index
    label(ver_loop)
    cmp(r3, r2)
    bge(ver_ok)
    ldr(r4, [r0, 0])
    cmp(r4, r1)
    bne(ver_bad)
    add(r0, r0, 4)
    add(r3, r3, 1)
    b(ver_loop)
    label(ver_bad)
    mov(r0, r3)
    pop({r4})
    b(END)
    label(ver_ok)
    mov(r0, 0)
    sub(r0, r0, 1)  # r0 = -1
    pop({r4})
    label(END)


# ---------------------------------------------------------------------
# asm_thumb: self-referential address pattern (classic bus/address test —
# each word is made to hold its own byte address, so a stuck or shorted
# address line shows up as two locations reading back the same value).
# ---------------------------------------------------------------------


@micropython.asm_thumb
def asm_addr_fill32(r0, r1):
    # r0 = base ptr, r1 = word count. word[i] = address_of(word[i])
    label(af_loop)
    cmp(r1, 0)
    beq(af_done)
    str(r0, [r0, 0])
    add(r0, r0, 4)
    sub(r1, r1, 1)
    b(af_loop)
    label(af_done)


@micropython.asm_thumb
def asm_addr_verify32(r0, r1) -> int:
    # r0 = base ptr, r1 = word count -> first bad word index, or -1
    push({r4, r5})
    mov(r4, r0)  # r4 = current address (r0 is clobbered as scratch below)
    mov(r5, 0)  # r5 = word index
    label(av_loop)
    cmp(r5, r1)
    bge(av_ok)
    ldr(r3, [r4, 0])
    cmp(r3, r4)
    bne(av_bad)
    add(r4, r4, 4)
    add(r5, r5, 1)
    b(av_loop)
    label(av_bad)
    mov(r0, r5)
    pop({r4, r5})
    b(END)
    label(av_ok)
    mov(r0, 0)
    sub(r0, r0, 1)  # r0 = -1
    pop({r4, r5})
    label(END)

# ---------------------------------------------------------------------
# asm_thumb: CRC32 (bit-by-bit, reflected, poly 0xEDB88320 — the standard
# CRC-32/ISO-HDLC construction). Chainable: pass the previous call's
# return value back in as init_crc to checksum data across multiple
# calls/chunks. Callers are responsible for the usual 0xFFFFFFFF seed and
# final-XOR convention if they want a "textbook" CRC32; for the
# self-consistency checks in these testers (does the checksum of what we
# read match the checksum of what we wrote?) that convention doesn't
# matter as long as both sides use it the same way.
# ---------------------------------------------------------------------


@micropython.asm_thumb
def asm_crc32(r0, r1, r2) -> uint:
    # r0 = byte ptr, r1 = length in bytes, r2 = initial crc
    push({r4, r5, r6, r7, lr})
    mov(r4, r2)  # r4 = crc accumulator
    movwt(r5, 0xEDB88320)  # r5 = polynomial
    mov(r6, r1)  # r6 = remaining byte count
    mov(r7, r0)  # r7 = current byte pointer

    label(crc_byte)
    cmp(r6, 0)
    beq(crc_done)
    ldrb(r3, [r7, 0])
    add(r7, r7, 1)
    eor(r4, r3)
    mov(r0, 8)  # r0 = bit counter for this byte

    label(crc_bit)
    mov(r2, r4)
    mov(r1, 1)
    and_(r2, r1)  # r2 = crc & 1
    lsr(r4, r1)  # crc >>= 1
    cmp(r2, 0)
    beq(crc_noxor)
    eor(r4, r5)  # crc ^= poly
    label(crc_noxor)
    sub(r0, r0, 1)
    cmp(r0, 0)
    bgt(crc_bit)

    sub(r6, r6, 1)
    b(crc_byte)

    label(crc_done)
    mov(r0, r4)
    pop({r4, r5, r6, r7, lr})


# ---------------------------------------------------------------------
# viper: 32-bit xorshift LFSR pattern generator/verifier. Two flavours:
# the *_buf variants take a buffer-protocol object (bytearray/memoryview)
# and are what you want for anything that's a normal Python object
# (safe — GC-tracked, bounds implied by the object's own length). The
# *_addr variants take a raw integer address and word count, for the
# advanced/expert raw-memory-mapped-address mode in psram_check.py.
#
# Both fill/verify take a `state` (the LFSR seed / chained state) and
# fill/verify return the *ending* state, so callers can process data in
# chunks: state = lfsr_fill_buf(chunk, state) for each chunk in turn, and
# the same chaining on the verify side, to test something too big to
# hold as one buffer without the pattern just repeating every chunk.
# ---------------------------------------------------------------------


@micropython.viper
def lfsr_fill_buf(buf, state: int) -> int:
    p = ptr32(buf)
    n = int(len(buf)) >> 2
    x = int(state)
    i = 0
    while i < n:
        x ^= (x << 13) & int(0xFFFFFFFF)
        x ^= x >> 17
        x ^= (x << 5) & int(0xFFFFFFFF)
        x &= int(0xFFFFFFFF)
        p[i] = x
        i += 1
    return x


@micropython.viper
def lfsr_verify_buf(buf, state: int) -> int:
    # returns the word index of the first mismatch within this buffer,
    # or -1 if all match (note: -1 here, not the ending state — callers
    # that need to chain across chunks on a passing run should just call
    # lfsr_fill_buf's twin math themselves, or re-derive state from the
    # write side, since a verify pass has nothing useful to chain from
    # once it's found a match all the way through)
    p = ptr32(buf)
    n = int(len(buf)) >> 2
    x = state
    i = 0
    while i < n:
        x ^= (x << 13) & int(0xFFFFFFFF)
        x ^= x >> 17
        x ^= (x << 5) & int(0xFFFFFFFF)
        x &= int(0xFFFFFFFF)
        if p[i] != x:
            return i
        i += 1
    return -1


@micropython.viper
def lfsr_fill_addr(addr: int, word_count: int, state: int) -> int:
    p = ptr32(addr)
    x = state
    i = 0
    while i < word_count:
        x ^= (x << 13) & int(0xFFFFFFFF)
        x ^= x >> 17
        x ^= (x << 5) & int(0xFFFFFFFF)
        x &= int(0xFFFFFFFF)
        p[i] = x
        i += 1
    return x


@micropython.viper
def lfsr_verify_addr(addr: int, word_count: int, state: int) -> int:
    p = ptr32(addr)
    x = state
    i = 0
    while i < word_count:
        x ^= (x << 13) & int(0xFFFFFFFF)
        x ^= x >> 17
        x ^= (x << 5) &int(0xFFFFFFFF)
        x &= int(0xFFFFFFFF)
        if p[i] != x:
            return i
        i += 1
    return -1


# A fixed, non-zero default seed (state 0 is a fixed point of xorshift —
# it would just generate an endless stream of zero words).
DEFAULT_SEED = 0xACE1ACE1
