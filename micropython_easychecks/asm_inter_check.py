@micropython.viper
def _rev16(v: int) -> int:
    # Bit-reverse the low 16 bits of v (classic branchless swap-pairs /
    # swap-nibbles / swap-bytes technique -- portable, doesn't depend on
    # whether asm_thumb exposes RBIT). Needed because DB0-DB15 are wired
    # to GPIO15..GPIO0 (reversed), not a simple GPIOn+offset shift: to
    # put value-bit i on GPIO(15-i), the value has to actually be
    # bit-reversed before it lands in GPIO_OUT bits 0-15.
    v = ((v & 0x5555) << 1) | ((v >> 1) & 0x5555)
    v = ((v & 0x3333) << 2) | ((v >> 2) & 0x3333)
    v = ((v & 0x0F0F) << 4) | ((v >> 4) & 0x0F0F)
    v = ((v & 0x00FF) << 8) | ((v >> 8) & 0x00FF)
    return v & 0xFFFF

@micropython.asm_thumb
def _rev16_2(r0) -> int:
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


# print(bin(_rev16_2(0b0000_1111_1100_0101)))
# 0b1100_1100_1100_1100_1100_0011_1100_10001
# 0b0000_0000_0011_1111_0000_1111_1100_0101
# 0b0000_0000_0011_1111_0000_1111_0000_0000

