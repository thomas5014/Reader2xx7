import machine, time
machine.freq(150_000_000)
print("freq", machine.freq())
opt = 1
if opt == 0:
    from machine import SoftSPI, Pin                                                                                                                                                           
    import sd, os                                                                                                                                                                          
    csP = 27; mosiP = 22; clkP = 23; misoP = 24                                                    
    spi = SoftSPI(baudrate=12_00_000, sck=Pin(clkP), mosi=Pin(mosiP), miso=Pin(misoP))
    cs  = Pin(csP, Pin.OUT, value=1)
    # Pull-ups: MISO must not float (Samsung tri-states it between responses,
    # SanDisk tends to drive it high — hence "SanDisk works, Samsung doesn't").
    # DAT1/DAT2 are unused in SPI mode but shouldn't float either.
    # Pin(misoP, Pin.IN, Pin.PULL_UP)   # MISO / DAT0
    Pin(25, Pin.IN, Pin.PULL_UP)   # DAT1 (unused in SPI mode)
    Pin(26, Pin.IN, Pin.PULL_UP)   # DAT2 (unused in SPI mode)
    print(dir(spi))
    try:
       cs(0)
       print(spi.read(32,450))
    finally:
       cs(1)
    print("spi set")
    sd = sd.SDCard(spi, cs)
    print("sd set")
    os.mount(sd, '/sd')                                                                                                                                                                        
    print(os.listdir('/sd')) 
    buf = bytearray(480*700*2)
    t0 = time.ticks_ms()
    with open("/sd/berto_480-700.raw","rb") as f:
        f.readinto(buf)
    print("read done")
    t1 = time.ticks_ms()
    print(t1-t0)
    while True:                                                                                                                                                      
        buf = bytearray(512)                                                                                                                                                                       
        sd.readblocks(0, buf)
                                                                                                                                                                                                    
        # Check MBR signature
        print("55 AA present:", buf[510] == 0x55 and buf[511] == 0xAA)
        print(f"bytes 510-511: {buf[510]:02X} {buf[511]:02X}")                                                                                                                                     
                                                                                                                                                                                                    
        # Also dump the first 16 bytes and last 16 bytes for sanity                                                                                                                                
        #print("tail:", bbytes(buf).hex())
        print(''.join([f"{i:02x} " for i in buf[438:]]))
        import time
        time.sleep(1)
elif opt == 1:
  # New sdio pinout:
  # CLK:       23
  # CMD/mosi:  22
  # DAT0/miso: 24
  # DAT1/nc:   25
  # DAT2/nc:   26
  # DAT3/cs:   27
  import sdio, os
  sd = sdio.SDCard()
  print(dir(sd))
  buf = bytearray(512)
  sd.readblocks(100, buf)  # sanity check
  print(''.join([f"{i:02x} " for i in buf[438:]]))
  os.mount(sd, "/sd")
  for _ in range(10):
    try:
      files = os.listdir("/sd")
      print("SD Card Files:", files)
    except Exception as e:
      import sys
      sys.print_exception(e)  
  with open("/sd/write_test.txt","w") as f:
     f.write("Hello World!!")
     f.close()
  print("done")
  os.listdir("sd")  