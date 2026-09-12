import network, urequests, sys

# configuring as station interface - ie make as for data like laptop, not "look im an accessable network point"
wlan = network.WLAN(network.STA_IF)

# turns it on, idk
wlan.active(True)

# print the IP Address
ip_address = wlan.ifconfig()[0]
print(f"\n Connected! Device IP address is: {ip_address}")

# Looking for networks
result = wlan.scan()
print(f"Local networks in range: {result}")

# trying to connect to preconfigured network
wlan.connect("quack3","drfluffy")

# the did-it-work check
status = wlan.isconnected()
print(f"Successful connect to quack3?: {status}")
if not status:
    print("unsuccessful, stopping here")
    sys.exit(1)

# Try and get web response
response = urequests.get("http://google.com")
print(dir(response),response)
print(f'response from google.com was: {"successful" if response.status_code == 200 else "unsuccessful"}')
response.close()

import socket

# 2. Start the Socket Server
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(('', 80))  # Port 80 is the standard HTTP port
s.listen(5)
print("Server is listening for browser requests...\n")

while True:
    try:
        conn, addr = s.accept()
        print(f"Browser connected from: {addr}")
        request = conn.recv(1024)
        
        # Simple HTML Web Page
        html = """<!DOCTYPE html>
        <html>
        <head><title>RM2 Web Server</title></head>
        <body>
            <h1>Hello from your RM2 Module!</h1>
            <p>The socket connection is working perfectly.</p>
            <font size="40pt" color="red" style="border-size:1px;border-color:blue;border-style:dashed;padding:10px">Hello!!</font>
        </body>
        </html>"""
        
        # Send HTTP Headers and HTML Body
        conn.send('HTTP/1.1 200 OK\n')
        conn.send('Content-Type: text/html\n')
        conn.send('Connection: close\n\n')
        conn.sendall(html)
        conn.close()
        print("Page sent and connection closed.")
    except Exception as e:
        print("Error:", e)

