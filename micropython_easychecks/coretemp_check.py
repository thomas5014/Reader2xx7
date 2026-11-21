import machine
import time

# Initialize the internal temperature sensor on ADC channel 4
sensor_temp = machine.ADC(8)

while True:
    # Read raw 16-bit value and convert to voltage
    raw_value = sensor_temp.read_u16()
    voltage = raw_value * 3.3 / 65535
    
    # Convert voltage to Celsius using the Pico formula
    temperature = 27 - (voltage - 0.706) / 0.001721
    
    print(f"Temperature: {temperature:.2f} °C")
    time.sleep(.1)
