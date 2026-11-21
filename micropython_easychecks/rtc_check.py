import machine
import time

class RV3028:
    def __init__(self, i2c):
        self.i2c = i2c
        self.address = 0x52
        
        # Core Register Mappings (From Micro Crystal Datasheet)
        self.REG_SEC = 0x00
        self.REG_MIN = 0x01
        self.REG_HOUR = 0x02
        self.REG_WEEKDAY = 0x03
        self.REG_DATE = 0x04
        self.REG_MONTH = 0x05
        self.REG_YEAR = 0x06
        self.REG_EEPROM_BACKUP = 0x37  # EEPROM backup configuration register
        self.REG_STATUS   = 0x0E   # bit 7 = EEbusy
        self.REG_CONTROL1 = 0x0F   # bit 3 = EERD
        self.REG_EECMD    = 0x27

        # Verify device presence
        try:
            self.i2c.readfrom(self.address, 1)
        except Exception:
            raise RuntimeError(f"RV-3028 not detected on I2C address {hex(self.address)}")
            
        # Ensure battery/capacitor backup switchover is turned ON
        self._enable_backup_switchover()

    def _bcd_to_dec(self, bcd):
        """Converts Binary Coded Decimal to normal integer."""
        return ((bcd >> 4) * 10) + (bcd & 0x0F)

    def _dec_to_bcd(self, dec):
        """Converts standard decimal integer to Binary Coded Decimal."""
        return ((dec // 10) << 4) | (dec % 10)

    def _enable_backup_switchover(self):
        current = self.i2c.readfrom_mem(self.address, self.REG_EEPROM_BACKUP, 1)[0]
        updated = current | 0x0C          # BSM = 11 (Level Switching Mode)
        if current == updated:
            return                        # already committed, skip EEPROM wear

        ctrl1 = self.i2c.readfrom_mem(self.address, self.REG_CONTROL1, 1)[0]

        # 1. Disable automatic EEPROM->RAM refresh
        self.i2c.writeto_mem(self.address, self.REG_CONTROL1, bytes([ctrl1 | 0x08]))
        self._wait_eebusy()

        # 2. Update the RAM mirror with the new config byte
        self.i2c.writeto_mem(self.address, self.REG_EEPROM_BACKUP, bytes([updated]))

        # 3. Commit ALL Configuration RAM (0x30-0x37) into EEPROM
        self.i2c.writeto_mem(self.address, self.REG_EECMD, bytes([0x00]))
        self.i2c.writeto_mem(self.address, self.REG_EECMD, bytes([0x11]))   # Update All
        time.sleep_ms(63)                 # t_UPDATE ~= 63 ms
        self._wait_eebusy()

        # 4. Re-enable automatic refresh
        self.i2c.writeto_mem(self.address, self.REG_CONTROL1, bytes([ctrl1 & ~0x08]))

    def _wait_eebusy(self, timeout_ms=200):
        t0 = time.ticks_ms()
        while self.i2c.readfrom_mem(self.address, self.REG_STATUS, 1)[0] & 0x80:
            if time.ticks_diff(time.ticks_ms(), t0) > timeout_ms:
                raise RuntimeError("RV-3028: EEbusy timeout")
            time.sleep_ms(1)

    def set_time(self, year, month, date, weekday, hour, minute, second):
        """Sets the calendar clock. Year input format: 4-digit (e.g., 2026)."""
        # RV-3028 tracks years 00-99 (Offset from 2000)
        short_year = year % 100
        
        data = bytes([
            self._dec_to_bcd(second),
            self._dec_to_bcd(minute),
            self._dec_to_bcd(hour),
            self._dec_to_bcd(weekday), # 0=Sunday, 1=Monday... 6=Saturday
            self._dec_to_bcd(date),
            self._dec_to_bcd(month),
            self._dec_to_bcd(short_year)
        ])
        # Bulk burst write starting from seconds register
        self.i2c.writeto_mem(self.address, self.REG_SEC, data)
        print("RTC time updated.")

    def read_time(self):
        """Reads and returns a formatted dictionary of the current date and time."""
        # Read 7 contiguous bytes representing the full clock profile
        raw = self.i2c.readfrom_mem(self.address, self.REG_SEC, 7)
        
        return {
            "second":  self._bcd_to_dec(raw[0] & 0x7F),
            "minute":  self._bcd_to_dec(raw[1] & 0x7F),
            "hour":    self._bcd_to_dec(raw[2] & 0x3F), # Masking out 24h formatting bits
            "weekday": self._bcd_to_dec(raw[3] & 0x07),
            "date":    self._bcd_to_dec(raw[4] & 0x3F),
            "month":   self._bcd_to_dec(raw[5] & 0x1F),
            "year":    self._bcd_to_dec(raw[6]) + 2000
        }

if __name__ == "__main__":
    # --- EXECUTION ON THE RP2350B ---

    # 1. Init your software I2C pipeline
    i2c_bus = machine.I2C(0, sda=28, scl=29, freq=400000)
    devices = i2c_bus.scan()
    print([hex(devices[i]) for i in range(len(devices))])
    # 2. Fire up the RTC module instance
    rtc = RV3028(i2c_bus)

    # 3. UNCOMMENT TO SET THE CURRENT TIME ONCE, THEN RE-COMMENT AND RE-RUN:
    # Parameters: (Year, Month, Date, Weekday [0-6], Hour, Minute, Second)
    # rtc.set_time(2026, 7, 29, 3, 13, 45, 0)
    # rtc.set_time(2026, 9, 20, 1, 15, 33, 10)

    # 4. Continual clock readout
    while True:
        t = rtc.read_time()
        # Format out into an easy-to-read ISO timestamp string
        print(f"Timestamp: {t['year']:04d}-{t['month']:02d}-{t['date']:02d} {t['hour']:02d}:{t['minute']:02d}:{t['second']:02d}")
        time.sleep(1)
