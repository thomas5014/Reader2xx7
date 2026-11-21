import time
from machine import Pin
import rp2

# ==========================================
# 1. PIO PROGRAM: AUTOMATIC BIT REVERSAL
# ==========================================
@rp2.asm_pio(
    out_shiftdir=rp2.PIO.SHIFT_LEFT,  # Pull shifts out LSB-first
    in_shiftdir=rp2.PIO.SHIFT_RIGHT     # Push shifts in MSB-first (Reverses order!)
)
def bit_reverser():
    pull()            # Pull 32-bit data from TX FIFO into OSR
    mov(x, invert(osr))        # Move all 32 bits from OSR to X register
    
    # We move bits from X back to the TX FIFO via the ISR.
    # Because 'in_shiftdir' is opposite to 'out_shiftdir', 
    # shifting bits into ISR and pushing to RX FIFO reverses them.
    (x, 32)        # Shift X into ISR
    push()            # Push reversed data to RX FIFO


# ==========================================
# 2. HOST PYTHON DRIVER
# ==========================================

# Initialize the State Machine on State Machine 0, using our program
# Frequency doesn't matter for this pure-register calculation
sm = rp2.StateMachine(0, bit_reverser, freq=1_000_000)
sm.active(1)

# Test Data: 0x0000000F (Binary: 0000...00001111)
# Reversed it should become: 0xF0000000 (Binary: 11110000...0000)
test_value = 0x0000000F

print(f"Sending to PIO:  {bin(test_value):>034s} (Hex: {hex(test_value)})")

# Send data to TX FIFO
sm.put(test_value)

# Read the processed data back from RX FIFO
result = sm.get()

print(f"Received back:   {bin(result):>034s} (Hex: {hex(result)})")

# Clean up
sm.active(0)
