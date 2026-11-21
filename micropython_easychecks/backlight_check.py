import machine
import time

class TPS61165:
    def __init__(self, pin_num, freq=50000):
        """
        Initializes the TPS61165 on a specific hardware PWM pin.
        Recommended frequency is between 5kHz and 100kHz for PWM mode.
        """
        self.ctrl_pin = machine.Pin(pin_num)
        self.pwm = machine.PWM(self.ctrl_pin)
        self.pwm.freq(freq)
        self.turn_off()

    def set_brightness(self, percentage):
        """
        Sets brightness from 0.0 (off) to 100.0 (full brightness).
        MicroPython duty cycles span from 0 to 65535.
        """
        if percentage < 0: percentage = 0
        if percentage > 100: percentage = 100
        
        # Calculate 16-bit duty cycle fraction
        duty_cycle = int((percentage / 100.0) * 65535)
        self.pwm.duty_u16(duty_cycle)

    def turn_off(self):
        """Forces the CTRL pin LOW to drop the driver into deep shutdown mode."""
        self.pwm.duty_u16(0)
        # Leaving the pin completely low for > 2.5ms engages shutdown
        
    def deinit(self):
        """Cleans up the hardware PWM instance."""
        self.pwm.deinit()


# --- APPLICATION SETUP FOR THE RP2350B ---

# 1. Choose any available GPIO pin tied to the CTRL line (e.g., GPIO 15)
LED_CTRL_PIN = 35 #20
backlight = TPS61165(pin_num=LED_CTRL_PIN, freq=50_000)

print("TPS61165 Backlight Controller initialized via PWM.")

# 2. Test breathing loop (fades backlight up and down)
try:
    backlight.set_brightness(100)
    while True:
        # print("Fading up...")
        # for duty in range(0, 101, 5):  # 0% to 100%
        #     backlight.set_brightness(duty)
        #     time.sleep_ms(50)
            
        # print("Fading down...")
        # for duty in range(100, -1, -5): # 100% to 0%
        #     backlight.set_brightness(duty)
        #     time.sleep_ms(50)
            
        time.sleep(1) # Pause at off state

except KeyboardInterrupt:
    # print("\nShutting down backlight.")
    # backlight.turn_off()
    backlight.deinit()

# .1275 - .13
# idle = .013