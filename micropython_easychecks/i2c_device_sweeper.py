# note: this will takw for ever and i wish i had just looked at my documentation
# this is very overkill and agressive

import machine 
import time

# The RP2350B package exposes 48 GPIO pins (0 to 47)
MAX_GPIO = 47

def sweep_i2c_pins():
    print("Starting I2C pin sweep across GPIO 0 to %d..." % MAX_GPIO)
    print("This will check all combinations. Please wait...\n")
    
    found_devices_count = 0
    
    # Nested loops to test every pin pair combination
    for sda_pin in range(MAX_GPIO + 1):
        for scl_pin in range(MAX_GPIO + 1):
            
            # Skip pairing a pin with itself
            if sda_pin == scl_pin:
                continue
                
            try:
                # Initialize bit-banged software I2C on current pin pair
                # Internal pull-ups are enabled by default in SoftI2C
                i2c = machine.SoftI2C(
                    sda=machine.Pin(sda_pin),
                    scl=machine.Pin(scl_pin),
                    freq=100000
                )
                
                # Scan the bus for responses (addresses 0x08 to 0x77)
                devices = i2c.scan()
                
                if devices:
                    found_devices_count += len(devices)
                    for device in devices:
                        print(f"-> SUCCESS: Found device at address [ {hex(device)} ]")
                        print(f"   Pins configuration: SDA = GPIO {sda_pin} | SCL = GPIO {scl_pin}\n")
                        
            except Exception as e:
                # Silently catch initialization errors (e.g., pins reserved by system)
                continue

    print("Sweep complete.")
    if found_devices_count == 0:
        print("No I2C devices were detected. Check your wiring or external pull-up resistors.")
    else:
        print(f"Total successful pin combinations found: {found_devices_count}")

# Execute the sweep
# sweep_i2c_pins()
i2c = machine.I2C(1,sda=20,scl=21,freq=100_000)
print(i2c.scan())

i2c = machine.I2C(0,sda=22,scl=23,freq=100_000)
print(i2c.scan())