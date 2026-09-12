import network, urequests, sys, time

# configuring as station interface - ie make as for data like laptop, not "look im an accessable network point"
wlan = network.WLAN(network.STA_IF)

# turns it on, idk
wlan.active(True)

for i in range(3):
    print("Connecting to Wi-Fi network (attempt {}/3)...".format(i+1))
    # trying to connect to preconfigured network
    wlan.connect("quack3","drfluffy")

    # the did-it-work check
    status = wlan.isconnected()
    print(f"Successful connect to quack3?: {status}")
    if status:
        break
    print("unsuccessful, retrying...")


# Monitor attenuation (RSSI) in a loop
print("Starting signal attenuation test (Press Ctrl+C to stop)...")
try:
    while True:
        # Fetch current RSSI in dBm
        rssi = wlan.status('rssi')
        print(f"Current Signal Strength (RSSI): {rssi} dBm")
        time.sleep(.2)
except KeyboardInterrupt:
    print("Test stopped.")
    wlan.disconnect()
    wlan.active(False)