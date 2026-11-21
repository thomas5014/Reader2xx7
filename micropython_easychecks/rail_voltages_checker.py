from machine import Pin, ADC
import time

bat = ADC(Pin(45))  # Voltage input for 3.3V rail
sys = ADC(Pin(46))  # Voltage input for 5V rail

while True:
    # Read raw ADC values
    raw_v3 = bat.read_u16()
    raw_v5 = sys.read_u16()

    # Convert raw ADC values to voltages (assuming 12-bit ADC and 3.3V reference)
    voltage_3v = (raw_v3 / 65355) * 3.3 * 3
    voltage_5v = (raw_v5 / 65355) * 3.3 * 3

    print(f"batV Rail Voltage: {voltage_3v:.3f} V")
    print(f"sysV Rail Voltage: {voltage_5v:.3f} V\n")

    time.sleep(.01)  # Delay for readability