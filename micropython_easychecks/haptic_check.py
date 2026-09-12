from machine import I2C, Pin
import time

en = Pin(41, Pin.OUT)
en.value(1)

# Define I2C (adjust pins according to your board)
i2c = I2C(0, scl=Pin(29), sda=Pin(28), freq=400000)

# DRV2605 I2C address
DRV_ADDR = 0x5a

def write_reg(reg, val):
    i2c.writeto_mem(DRV_ADDR, reg, bytearray([val]))

# 1. Reset the chip
write_reg(0x01, 0x80)  
time.sleep(0.1)

# 2. Wake out of standby
write_reg(0x01, 0x00)  # Drop standby completely
time.sleep_ms(10)

# 3. Configure Feedback Control (Register 0x1A)
# Set Bit 7 to 1 (LRA Mode).
# Unset the lower bits to disable the strict closed-loop behavior.
write_reg(0x1A, 0x80)

# 3.5 Diagnostic: uses the DRV2605's own back-EMF sensing to check
# whether the LRA is actually present and responding, rather than
# inferring it from board inspection alone. Confirmed against the
# DRV2605L datasheet (Table 4/5): in Diagnostic mode (MODE=6), DIAG_RESULT
# (status bit 3) reads 0 = actuator functioning normally, 1 = actuator
# not present, shorted, timing out, or giving out-of-range back-EMF.
#
# MUST run after N_ERM_LRA is set (step 3, above), not before: FEEDBACK_
# CONTROL defaults to ERM mode (N_ERM_LRA=0), and ERM vs LRA back-EMF
# characteristics are different enough that testing an LRA while the
# chip still expects an ERM response can fail the diagnostic even on a
# perfectly healthy actuator. (First attempt at this ran before step 3
# and reported a false DIAG_RESULT=1 for exactly this reason.)
write_reg(0x01, 0x06)   # MODE = 6 (Diagnostics)
write_reg(0x0C, 0x01)   # GO -- starts the diagnostic test

for _ in range(100):    # wait for GO to self-clear (test complete)
    if i2c.readfrom_mem(DRV_ADDR, 0x0C, 1)[0] & 1 == 0:
        break
    time.sleep_ms(2)
else:
    print("WARNING: diagnostic GO bit never cleared")

diag_status = i2c.readfrom_mem(DRV_ADDR, 0x00, 1)[0]
print(f"Diagnostic Status Register: {bin(diag_status)}")
if diag_status & (1 << 3):
    print("DIAG_RESULT=1: actuator NOT detected (open/shorted/no back-EMF)")
else:
    print("DIAG_RESULT=0: actuator responding normally -- LRA is present")

write_reg(0x01, 0x00)   # back out of Diagnostics mode before continuing
                         # (0x1A/FEEDBACK_CONTROL is a separate register
                         # from MODE, untouched by the mode switching above)

# 4. Switch to Open-Loop Mode (Register 0x1D - Control3)
# Setting Bit 0 to 1 explicitly forces LRA Open-Loop mode.
write_reg(0x1D, 0x01)

# 5. Set Manual LRA Frequency (Register 0x20, OL_LRA_PERIOD -- NOT 0x22,
# which is LRA_PERIOD, a *measured/reported* value from back-EMF
# zero-crossing detection, not something you set. Confirmed against
# the DRV2605L datasheet register map, Table 3.)
# Formula: LRA Period = 1 / (200 Hz * 98.46 us) = ~51 (0x33)
write_reg(0x20, 0x33)

# 6. Set Voltages for Vybronics 2.0V Rated Spec
write_reg(0x16, 0x53)  # Rated voltage (~2.0V)
write_reg(0x17, 0x56)  # Overdrive clamp voltage (~2.05V)

# 7. Select Library and Trigger a Continuous Buzz
write_reg(0x03, 0x06)  # LRA Library
write_reg(0x02, 0x00)  # Internal Trigger Mode
write_reg(0x04, 47)    # Effect 47 = Continuous Buzz 100%
write_reg(0x05, 47)    # Chain it again to make it longer
write_reg(0x06, 0)     # End Sequence

# 8. Fire!
# Fire wave
write_reg(0x0c, 0x01)  # Using 0x0C (The explicit GO Register) rather than Mode 0x01


print("LRA Open-Loop 200Hz sequence fired! Feel for a steady buzz.")


status = i2c.readfrom_mem(DRV_ADDR, 0x00, 1)[0]
print(f"Status Register: {bin(status)}")

# Per the DRV2605L register map (Table 3): bit0=OC_DETECT, bit1=OVER_TEMP,
# bit3=DIAG_RESULT (a stale diagnostic flag, not overcurrent), bit2=Reserved.
# The previous version checked bit3/bit2 -- checking DIAG_RESULT and an
# always-zero reserved bit, so a real overcurrent/overtemp condition would
# never have been flagged.
if status & (1 << 0):
    print("⚠️ WARNING: Overcurrent detected! (Check for a short circuit in your motor wires)")
if status & (1 << 1):
    print("⚠️ WARNING: Overtemperature detected!")
