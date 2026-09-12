import machine
import time

class INA226:
    def __init__(self, i2c, address=0x40):
        self.i2c = i2c
        self.address = address
        
        # Internal Register Map (From TI Datasheet)
        self.REG_CONFIG = 0x00
        self.REG_SHUNTVOLTAGE = 0x01
        self.REG_BUSVOLTAGE = 0x02
        
        # Test communication during initialization
        try:
            self.i2c.readfrom(self.address, 1)
        except Exception:
            raise RuntimeError(f"INA226 not found at I2C address {hex(address)}")

    def _read_register_16(self, reg):
        """Reads a 16-bit big-endian integer from the specified register."""
        # Request data from register
        data = self.i2c.readfrom_mem(self.address, reg, 2)
        # Combine 2 bytes into a 16-bit unsigned integer
        value = (data[0] << 8) | data[1]
        return value

    def read_bus_voltage(self):
        """Returns the Bus Voltage in Volts (LSB = 1.25 mV)."""
        raw_vbus = self._read_register_16(self.REG_BUSVOLTAGE)
        # Convert to float Volts
        return raw_vbus * 0.00125

    def read_shunt_voltage(self):
        """Returns the Shunt Voltage drop in Millivolts (LSB = 2.5 uV)."""
        raw_vshunt = self._read_register_16(self.REG_SHUNTVOLTAGE)
        
        # Handle 16-bit two's complement sign for negative current directions
        if raw_vshunt & 0x8000:
            raw_vshunt -= 0x10000
            
        # Convert to float Millivolts (2.5 uV = 0.0025 mV)
        return raw_vshunt * 0.0025


# --- APPLICATION CODE EXECUTING ON THE RP2350B ---

# 1. Initialize I2C pins (Change pin numbers to your actual physical setup)
# Ensure your RP2350B image supports the selected pins!
i2c_bus = machine.SoftI2C(sda=28, scl=29, freq=400_000)
print(i2c_bus.scan())

# 1.5 Initialize adc pins
vsys = machine.ADC(machine.Pin(45))  # Voltage input for 3.3V rail
vbat = machine.ADC(machine.Pin(46))

# 2. Instantiate the driver
sensor = INA226(i2c_bus, address=0x40)
print("INA226 communication initialized successfully.\n")

# 2.5 test backlight power
backlight = machine.PWM(machine.Pin(20))
backlight.freq(50_000)
backlight.duty_u16(30_000)

# 2.9 varible for averaging
av = 0
times = 0

# 3. Continuous data polling loop
while True:
    try:
        bus_voltage = sensor.read_bus_voltage()
        shunt_voltage = sensor.read_shunt_voltage()
        raw_v3 = vsys.read_u16()
        
        print(f"Bus Voltage:   {bus_voltage:.3f} V,  {(raw_v3 / 65355) * 3.3 * 3}v")
        print(f"Shunt Voltage: {shunt_voltage:.4f} mV")
        print(f"Shunt current: {shunt_voltage / 0.04:.4f} mA")
        print(f"System power: {shunt_voltage**2 / 0.04:,.2f} mW")
        print(f"Current based runtime : {10800/(shunt_voltage**2 / 0.04):.2f} H")
        print("-" * 30)
        av += shunt_voltage**2 / 40
        times += 1
        time.sleep(1)
        
    except KeyboardInterrupt:
        print("\nPolling stopped.")
        print(f"Average power: {av*1000/times:.4f}mw")
        break


#Average power: 412.5028mw at 46% brightness