from nt35510 import MyFrameBuffer, color565, SM1_FREQ, NT35510; nt = NT35510()
from font_blit_check import Font, BG
from color_control import make_palette, PALETTE_WHITE, PALETTE_BLUE
from time import sleep, ticks_ms, ticks_diff
from ina_check import INA226
from rtc_check import RV3028
from accel_check import LIS2DW12
from cst3240 import CST3240
from machine import Pin, ADC, freq, I2C
from micropython import const
import os, gc, network, _thread
import micropython

irq = Pin(32, Pin.IN, Pin.PULL_UP)
tp_func = lambda : print("Touch detected!")

i2c0_clock = const(400_000)  # 400kHz I2C clock speed

i2c0 = I2C(0, sda=28, scl=29, freq=i2c0_clock)
i2c1 = I2C(1, sda=30, scl=31, freq=i2c0_clock)

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect("1530Wifi", "drfluffy")  # connect to the network

INA = INA226(i2c0)
RTC = RV3028(i2c0)
ACL = LIS2DW12(i2c1,addr=0x18)
CST = CST3240(i2c1, rst_pin=Pin(33, Pin.OUT), irq_pin=irq) 

global_time = ticks_ms()

def touch_isr(pin):
    # print("ISR: Touch event detected!",pin)
    global global_time
    current_time = ticks_ms()
    if ticks_diff(current_time, global_time) > 50:  # Debounce for 50ms
        # print("IRQ: Touch event detected!")
        tp_func()
        global_time = current_time

irq.irq(trigger=Pin.IRQ_FALLING, handler=touch_isr)

Title = Font("/fonts/Strong-18-17x18.raw2")
Main = Font("/fonts/Roboto-16-14x18.raw2")

P_LtBlue = make_palette(40,100,255)

Title.draw_text_bytes("Stats/Status",MyFrameBuffer,10,10,0,PALETTE_WHITE)
nt.fill_rect(5,27,240,2,color565(40,100,255))

data = {}
scanlist = []

def update_adc_rails(x,y): # all comments in this func are bullshit, ignore
    global data
    if data.get("rails") is None:
        data["rails"] = {"batV":0,"sysV":0,"tempC":0}
    rbat = ADC(45).read_u16()  # Voltage input for batV rail
    rsys = ADC(46).read_u16()  # Voltage input for 5V rail
    tcore = ADC(8).read_u16()  # Temperature read from main chip core
    vtcore = (tcore / 65355) * 3.3
    voltage_3v = (rbat / 65355) * 3.3 * 3
    voltage_5v = (rsys / 65355) * 3.3 * 3
    temp_c = 27 - (vtcore - 0.706)/0.001721
    if data["rails"]["batV"] == voltage_3v and data["rails"]["sysV"] == voltage_5v and data["rails"]["tempC"] == temp_c:
        return
    # nt.fill_rect(x,y,240,40,color565(*BG))
    Main.draw_text_bytes(f"batV Rail Voltage: {voltage_3v:.3f} V",MyFrameBuffer,x,y,0,P_LtBlue)
    Main.draw_text_bytes(f"sysV Rail Voltage: {voltage_5v:.3f} V",MyFrameBuffer,x,y+20,0,P_LtBlue)
    Main.draw_text_bytes(f"Temperature: {temp_c:.1f} °C",MyFrameBuffer,x,y+40,0,P_LtBlue)

def show_sys_clocks(x,y):
    global data
    if data.get("clocks") is None:
        data["clocks"] = {"cpu":0,"sm1":0,"i2c":0}
    if data["clocks"]["cpu"] == freq() and data["clocks"]["sm1"] == SM1_FREQ and data["clocks"]["i2c"] == i2c0_clock:
        return
    # nt.fill_rect(x,y,240,40,color565(*BG))
    Main.draw_text_bytes(f"CPU Clock: {freq()/1_000_000:.0f} MHz",MyFrameBuffer,x,y,0,P_LtBlue)
    Main.draw_text_bytes(f"SM1 Clock: {SM1_FREQ/1_000_000:.0f} MHz",MyFrameBuffer,x,y+20,0,P_LtBlue)
    Main.draw_text_bytes(f"I2C Clock: {i2c0_clock/1_000:.0f} KHz",MyFrameBuffer,x,y+40,0,P_LtBlue)

def show_ina_stats(x,y):
    global data
    if data.get("ina") is None:
        data["ina"] = {"bus":0,"shunt":0,"current":0,"power":0}
    bus_voltage = INA.read_bus_voltage()
    shunt_voltage = INA.read_shunt_voltage()
    shunt_current_ma = shunt_voltage / 0.04
    system_power_mw = bus_voltage * shunt_current_ma
    # nt.fill_rect(x,y,240,80,color565(*BG))
    Main.draw_text_bytes(f"Bus Voltage:   {bus_voltage:.3f} V",MyFrameBuffer,x,y,0,P_LtBlue)
    Main.draw_text_bytes(f"Shunt Voltage: {shunt_voltage:.4f} mV",MyFrameBuffer,x,y+20,0,P_LtBlue)
    Main.draw_text_bytes(f"Shunt current: {shunt_current_ma:.4f} mA",MyFrameBuffer,x,y+40,0,P_LtBlue)
    Main.draw_text_bytes(f"System power: {system_power_mw:,.2f} mW",MyFrameBuffer,x,y+60,0,P_LtBlue)

def show_rtc_time(x,y):
    global data
    if data.get("rtc") is None:
        data["rtc"] = {"year":0,"month":0,"date":0,"hour":0,"minute":0,"second":0}
    t = RTC.read_time()
    if data["rtc"]["year"] == t['year'] and data["rtc"]["month"] == t['month'] and data["rtc"]["date"] == t['date'] and data["rtc"]["hour"] == t['hour'] and data["rtc"]["minute"] == t['minute'] and data["rtc"]["second"] == t['second']:
        return
    # nt.fill_rect(x,y,240,40,color565(*BG))
    Main.draw_text_bytes(f"Timestamp: {t['year']:04d}-{t['month']:02d}-{t['date']:02d} {t['hour']:02d}:{t['minute']:02d}:{t['second']:02d}",MyFrameBuffer,x,y,0,P_LtBlue)

def show_accel_stats(x,y):
    global data
    if data.get("accel") is None:
        data["accel"] = {"x":0,"y":0,"z":0,"temp":0}
    x_val, y_val, z_val = ACL.get()
    temp_val = ACL.temperature()
    if data["accel"]["x"] == x_val and data["accel"]["y"] == y_val and data["accel"]["z"] == z_val and data["accel"]["temp"] == temp_val:
        return
    # nt.fill_rect(x,y,240,80,color565(*BG))
    Main.draw_text_bytes(f"Accel X: {x_val:>5} mg",MyFrameBuffer,x,y,0,P_LtBlue)
    Main.draw_text_bytes(f"Accel Y: {y_val:>5} mg",MyFrameBuffer,x,y+20,0,P_LtBlue)
    Main.draw_text_bytes(f"Accel Z: {z_val:>5} mg",MyFrameBuffer,x,y+40,0,P_LtBlue)
    Main.draw_text_bytes(f"Temperature: {temp_val:.1f} °C",MyFrameBuffer,x,y+60,0,P_LtBlue)

def show_mem_stats(x,y):
    stat = os.statvfs("/")
    size = stat[1] * stat[2]
    free = stat[0] * stat[3]
    used = size - free
    if data.get("mem") is None:
        data["mem"] = {"size":0,"used":0,"free":0}
    if data["mem"]["size"] == size and data["mem"]["used"] == used and data["mem"]["free"] == free:
        return
    # nt.fill_rect(x,y,240,80,color565(*BG))

    KB = 1024
    MB = 1024 * 1024

    Main.draw_text_bytes(f"Size : {{:,}} bytes, {{:,}} KB, {{}} MB".format(size, size / KB, size / MB),MyFrameBuffer,x,y,0,P_LtBlue)
    Main.draw_text_bytes(f"Used : {{:,}} bytes, {{:,}} KB, {{}} MB".format(used, used / KB, used / MB),MyFrameBuffer,x,y+20,0,P_LtBlue)
    Main.draw_text_bytes(f"Free : {{:,}} bytes, {{:,}} KB, {{}} MB".format(free, free / KB, free / MB),MyFrameBuffer,x,y+40,0,P_LtBlue)
    # micropython.mem_info(1)
    # Main.draw_text_bytes(f"Free memory: {{gc.mem_free():,}} Bytes",MyFrameBuffer,x,y+60,0,P_LtBlue)

def show_near_network_stats(x,y):
    Title.draw_text_bytes("Network Stats",MyFrameBuffer,x+10,y,0,PALETTE_WHITE)
    if not wlan.isconnected():
        Main.draw_text_bytes("Not connected to Wi-Fi",MyFrameBuffer,x,y+20,0,P_LtBlue)
    else:
        ip_address = wlan.ifconfig()[0]
        Main.draw_text_bytes(f"IP Address: {ip_address}",MyFrameBuffer,x,y+20,0,P_LtBlue)
        Main.draw_text_bytes(f"Signal Strength: {wlan.status('rssi')} dBm",MyFrameBuffer,x,y+40,0,P_LtBlue)

    scan = scanlist
    Main.draw_text_bytes(f"Local Networks in Range: {len(scan)}",MyFrameBuffer,x,y+80,0,P_LtBlue)
    nt.fill_rect(x,y+100,320,180,color565(*BG))
    for i, net in enumerate(scan[:9]):  # Show only the first 9 networks
        ssid = net[0].decode('utf-8')
        rssi = net[3]
        Main.draw_text_bytes(f"{i+1}. SSID: {ssid}, RSSI: {rssi} dBm", MyFrameBuffer, x, y + 100 + i * 20, 0, P_LtBlue)

def wlan_scan():
    global scanlist
    while True:
        scanlist = wlan.scan()
        sleep(4)

tp_func = lambda : Main.draw_text_bytes(f"Touch: {CST.read_touch()}",MyFrameBuffer,10,750,0,P_LtBlue)
_thread.start_new_thread(wlan_scan, ())
try:
    while True:
        show_near_network_stats(10,400)
        for _ in range(8):
            update_adc_rails(10,40)
            show_sys_clocks(10,100)
            show_ina_stats(10,160)
            show_rtc_time(10,770)
            show_accel_stats(10,240)
            show_mem_stats(10,320)
            sleep(.4)
except KeyboardInterrupt:
    _thread.exit()
    print("Exiting...")