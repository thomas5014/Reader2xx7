import network
import binascii

wlan = network.WLAN(network.STA_IF)
wlan.active(True)

# 1. Fetch Local Hardware MAC Address
mac = wlan.config('mac')
print("RM2 MAC Address:", binascii.hexlify(mac, ':').decode())

# 2. Scan for detailed neighborhood AP data
print("\nScanning nearby networks...")
networks = wlan.scan()
print(f"{'SSID':<20} {'BSSID':<18} {'Channel':<8} {'RSSI (dBm)':<10} {'Security':<8}")
print("-" * 65)

for ap in networks:
    ssid = ap[0].decode('utf-8', 'ignore')
    bssid = binascii.hexlify(ap[1], ':').decode()
    channel = ap[2]
    rssi = ap[3]
    security = ap[4]
    
    print(f"{ssid:<20} {bssid:<18} {channel:<8} {rssi:<10} {security:<8}")
