import network
import socket
import time
import json
import gc
import binascii
from machine import Pin

# --- CONFIGURATION ---
WIFI_SSID = "quack3"
WIFI_PASSWORD = "drfluffy"
SERVER_PORT = 80
ATTENUATION_THRESHOLD = -80  # Alert threshold in dBm

# Initialize the onboard LED (on Pico W / RM2 modules, 'LED' points to the CYW43 pin)
led = Pin('LED', Pin.OUT)
led.off()

# Global cache for network scans to avoid blocking the server repeatedly
cached_scan_data = []
last_scan_time = 0
SCAN_INTERVAL = 20  # Rescan every 20 seconds automatically

def get_security_name(sec_code):
    """Maps MicroPython security integers to human-readable strings."""
    sec_map = {0: "Open", 1: "WEP", 2: "WPA", 3: "WPA2", 4: "WPA/WPA2"}
    return sec_map.get(sec_code, "Unknown")

def connect_wifi():
    """Initializes and connects to the Wi-Fi network."""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    if not wlan.isconnected():
        print(f"Connecting to {WIFI_SSID}...")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        
        # Wait for connection with a timeout
        timeout = 20
        while not wlan.isconnected() and timeout > 0:
            # Blink the LED during connection phase
            led.toggle()
            time.sleep(0.5)
            timeout -= 0.5
            
    if wlan.isconnected():
        print("Connected successfully!")
        print("IP Info:", wlan.ifconfig())
        led.on()  # Solid on indicates successful link setup
        time.sleep(1)
        led.off()
        return wlan
    else:
        raise RuntimeError("Wi-Fi connection failed. Verify credentials.")

def perform_wifi_scan(wlan):
    """Scans for nearby networks safely, handling potential memory constraints."""
    global cached_scan_data, last_scan_time
    gc.collect()  # Clear memory before heavy scanning operation
    try:
        raw_scan = wlan.scan()
        scanned_nets = []
        for ap in raw_scan:
            ssid = ap[0].decode('utf-8', 'ignore')
            if not ssid:
                ssid = "[Hidden Network]"
            
            bssid = binascii.hexlify(ap[1], ':').decode()
            scanned_nets.append({
                "ssid": ssid,
                "bssid": bssid,
                "channel": ap[2],
                "rssi": ap[3],
                "security": get_security_name(ap[4])
            })
        # Sort by signal strength descending
        cached_scan_data = sorted(scanned_nets, key=lambda x: x['rssi'], reverse=True)
        last_scan_time = time.time()
    except Exception as e:
        print("Scan failed or timed out:", e)
        # Keep old cache or set empty to prevent crashing the server loop
        if not cached_scan_data:
            cached_scan_data = []
    gc.collect()

# --- HTML DASHBOARD TEMPLATE ---
# Uses Tailwind CSS via the allowed CDN for clean layouts and mobile-first responsiveness.
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RM2 Wireless Diagnostic Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-900 text-gray-100 font-sans antialiased minimum-h-screen">
    <div class="max-w-6xl mx-auto p-4 md:p-8">
        
        <!-- Header -->
        <header class="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 pb-4 border-b border-gray-800 gap-4">
            <div>
                <h1 class="text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-teal-400 to-blue-500">
                    Raspberry Pi RM2
                </h1>
                <p class="text-sm text-gray-400 mt-1">Live MicroPython Wi-Fi Attenuation & Signal Diagnostics</p>
            </div>
            <div class="flex items-center gap-2 bg-gray-800 px-4 py-2 rounded-lg border border-gray-700">
                <span class="w-3 h-3 bg-emerald-500 rounded-full animate-pulse"></span>
                <span class="text-xs font-mono text-gray-300" id="uptime-display">System Online</span>
            </div>
        </header>

        <!-- Main Grid Layout -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
            
            <!-- Live Attenuation / RSSI Gauge Card -->
            <div class="bg-gray-800 p-6 rounded-xl border border-gray-700 shadow-xl flex flex-col justify-between">
                <div>
                    <h2 class="text-lg font-bold text-gray-300 mb-2">Signal Attenuation (RSSI)</h2>
                    <p class="text-xs text-gray-400 mb-4">Real-time signal loss metrics updated automatically every 2s.</p>
                </div>
                <div class="flex flex-col items-center justify-center my-4">
                    <div class="relative flex items-center justify-center w-36 h-36 rounded-full border-4 border-dashed border-teal-500/30">
                        <span class="text-4xl font-black text-white" id="rssi-value">--</span>
                        <span class="text-xs font-bold text-teal-400 absolute bottom-6">dBm</span>
                    </div>
                    <div class="w-full bg-gray-700 rounded-full h-2.5 mt-6 overflow-hidden">
                        <div id="rssi-progress" class="bg-gradient-to-r from-teal-500 to-blue-500 h-2.5 rounded-full transition-all duration-500" style="width: 0%"></div>
                    </div>
                </div>
                <div class="text-center text-xs font-semibold py-1 rounded bg-gray-900/50 mt-2 text-gray-400" id="signal-quality-label">
                    Evaluating signal...
                </div>
            </div>

            <!-- Local Interface Diagnostics Card -->
            <div class="bg-gray-800 p-6 rounded-xl border border-gray-700 shadow-xl lg:col-span-2">
                <h2 class="text-lg font-bold text-gray-300 mb-2">Network Configuration</h2>
                <p class="text-xs text-gray-400 mb-4">Active adapter assignment details read from wlan.ifconfig().</p>
                
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div class="bg-gray-900/60 p-4 rounded-lg border border-gray-700/50">
                        <span class="text-xs text-gray-500 block uppercase font-mono tracking-wider">Device IP Address</span>
                        <span class="text-lg font-mono font-medium text-gray-200" id="net-ip">0.0.0.0</span>
                    </div>
                    <div class="bg-gray-900/60 p-4 rounded-lg border border-gray-700/50">
                        <span class="text-xs text-gray-500 block uppercase font-mono tracking-wider">Subnet Mask</span>
                        <span class="text-lg font-mono font-medium text-gray-200" id="net-mask">0.0.0.0</span>
                    </div>
                    <div class="bg-gray-900/60 p-4 rounded-lg border border-gray-700/50">
                        <span class="text-xs text-gray-500 block uppercase font-mono tracking-wider">Gateway Router</span>
                        <span class="text-lg font-mono font-medium text-gray-200" id="net-gateway">0.0.0.0</span>
                    </div>
                    <div class="bg-gray-900/60 p-4 rounded-lg border border-gray-700/50">
                        <span class="text-xs text-gray-500 block uppercase font-mono tracking-wider">DNS Server</span>
                        <span class="text-lg font-mono font-medium text-gray-200" id="net-dns">0.0.0.0</span>
                    </div>
                </div>
                <div class="mt-4 pt-4 border-t border-gray-700/50 flex justify-between items-center text-xs font-mono text-gray-400">
                    <span>Hardware MAC: <span id="net-mac" class="text-gray-200">00:00:00:00:00:00</span></span>
                </div>
            </div>
        </div>

        <!-- Surrounding Networks Scan Table -->
        <div class="bg-gray-800 rounded-xl border border-gray-700 shadow-xl overflow-hidden">
            <div class="p-6 border-b border-gray-700 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                <div>
                    <h2 class="text-lg font-bold text-gray-300">Surrounding Access Points</h2>
                    <p class="text-xs text-gray-400 mt-0.5">Discovered local environments using regional radio channel parameters.</p>
                </div>
                <button id="btn-scan" onclick="triggerScan()" class="bg-gradient-to-r from-teal-500 to-teal-600 hover:from-teal-600 hover:to-teal-700 text-white text-xs font-bold py-2 px-4 rounded-lg shadow-md transition-all duration-200 disabled:opacity-50">
                    Scan Environment
                </button>
            </div>
            <div class="overflow-x-auto">
                <table class="w-full text-left border-collapse">
                    <thead>
                        <tr class="bg-gray-900/40 text-xs font-mono uppercase tracking-wider text-gray-400 border-b border-gray-700">
                            <th class="p-4">SSID</th>
                            <th class="p-4">BSSID (MAC)</th>
                            <th class="p-4 text-center">Channel</th>
                            <th class="p-4 text-center">Security</th>
                            <th class="p-4 text-right">RSSI</th>
                        </tr>
                    </thead>
                    <tbody id="network-table-body" class="divide-y divide-gray-700/60 text-sm">
                        <tr>
                            <td colspan="5" class="p-8 text-center text-gray-500 font-medium">Click Scan Environment to query neighboring signals.</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

    </div>

    <!-- Dashboard Logic Script -->
    <script>
        function updateDashboard() {
            fetch('/api/data')
                .then(response => {
                    if (!response.ok) throw new Error("HTTP error " + response.status);
                    return response.json();
                })
                .then(data => {
                    const rssi = data.rssi;
                    document.getElementById('rssi-value').innerText = rssi;
                    
                    let percentage = Math.round(((rssi + 100) / 70) * 100);
                    percentage = Math.max(0, Math.min(100, percentage));
                    document.getElementById('rssi-progress').style.width = percentage + '%';
                    
                    let label = "Unknown Signal Status";
                    let colorClass = "text-gray-400";
                    if (rssi >= -50) { label = "Excellent (Minimal Attenuation)"; colorClass = "text-emerald-400"; }
                    else if (rssi >= -67) { label = "Good (Stable Connection)"; colorClass = "text-teal-400"; }
                    else if (rssi >= -80) { label = "Fair (Noticeable Attenuation)"; colorClass = "text-amber-400"; }
                    else { label = "Critical (Severe Attenuation Loss)"; colorClass = "text-rose-400"; }
                    
                    const labelEl = document.getElementById('signal-quality-label');
                    labelEl.innerText = label;
                    labelEl.className = `text-center text-xs font-semibold py-1 rounded bg-gray-900/50 mt-2 ${colorClass}`;

                    document.getElementById('net-ip').innerText = data.ifconfig[0];
                    document.getElementById('net-mask').innerText = data.ifconfig[1];
                    document.getElementById('net-gateway').innerText = data.ifconfig[2];
                    document.getElementById('net-dns').innerText = data.ifconfig[3];
                    document.getElementById('net-mac').innerText = data.mac;
                })
                .catch(err => console.error("Telemetry fetch failed:", err));
        }

        function triggerScan() {
            const btn = document.getElementById('btn-scan');
            btn.disabled = true;
            btn.innerText = "Scanning Active... Please Wait";
            
            fetch('/api/scan')
                .then(response => {
                    if (!response.ok) throw new Error("HTTP error " + response.status);
                    return response.json();
                })
                .then(networks => {
                    const tbody = document.getElementById('network-table-body');
                    tbody.innerHTML = '';
                    
                    if (networks.length === 0) {
                        tbody.innerHTML = `<tr><td colspan="5" class="p-8 text-center text-gray-500">No active environments located or scan timed out. Try again.</td></tr>`;
                    } else {
                        networks.forEach(net => {
                            let rssiColor = "text-emerald-400";
                            if (net.rssi < -75) rssiColor = "text-rose-400";
                            else if (net.rssi < -60) rssiColor = "text-amber-400";

                            tbody.innerHTML += `
                                <tr class="hover:bg-gray-700/30 transition-colors">
                                    <td class="p-4 font-semibold text-gray-200">${net.ssid}</td>
                                    <td class="p-4 font-mono text-xs text-gray-400">${net.bssid}</td>
                                    <td class="p-4 text-center font-mono text-gray-300">${net.channel}</td>
                                    <td class="p-4 text-center text-xs"><span class="px-2 py-0.5 rounded bg-gray-900/60 text-gray-400 font-mono">${net.security}</span></td>
                                    <td class="p-4 text-right font-mono font-bold ${rssiColor}">${net.rssi} dBm</td>
                                </tr>
                            `;
                        });
                    }
                })
                .catch(err => {
                    console.error("Radio scan failed:", err);
                    document.getElementById('network-table-body').innerHTML = 
                        `<tr><td colspan="5" class="p-8 text-center text-rose-400">Scan request timed out or memory limit reached. Try refreshing.</td></tr>`;
                })
                .finally(() => {
                    btn.disabled = false;
                    btn.innerText = "Scan Environment";
                });
        }

        // Initialize telemetry loop
        setInterval(updateDashboard, 2000);
        updateDashboard();
        
        // Delay the initial boot environment scan slightly to let the socket establish cleanly
        setTimeout(triggerScan, 1500);
    </script>
</body>
</html>
"""

def serve_dashboard():
    """Starts the optimized web server loop using chunked streams to handle dashboard traffic safely."""
    global cached_scan_data, last_scan_time
    
    wlan = connect_wifi()
    mac_address = binascii.hexlify(wlan.config('mac'), ':').decode()
    
    # Establish TCP Socket Stream Listener
    addr = socket.getaddrinfo('0.0.0.0', SERVER_PORT)[0][-1]
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    
    # Set timeout to allow concurrent background hardware monitoring loop execution
    s.settimeout(1.0) 
    s.listen(5)
    
    print(f"\nDashboard Server Active! Point your web browser to: http://{wlan.ifconfig()[0]}")
    
    while True:
        # Hardware alert check execution step
        try:
            current_rssi = wlan.status('rssi')
            if current_rssi <= ATTENUATION_THRESHOLD and current_rssi != 0:
                led.toggle()
            else:
                led.off()
        except Exception:
            pass

        client = None
        try:
            gc.collect()  # Proactively clear heap space before socket blocks
            
            try:
                client, client_addr = s.accept()
            except OSError:
                # Socket accept timeout, cycle back around to perform hardware routines
                continue
                
            request = client.recv(1024).decode('utf-8')
            if not request:
                client.close()
                continue
                
            request_line = request.split('\r\n')[0]
            try:
                method, path, _ = request_line.split(' ')
            except ValueError:
                client.close()
                continue
            
            # Route: GET /api/data
            if path == "/api/data":
                payload = {
                    "rssi": wlan.status('rssi'),
                    "ifconfig": list(wlan.ifconfig()),
                    "mac": mac_address
                }
                response = json.dumps(payload)
                client.send("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n")
                client.send(response)
            
            # Route: GET /api/scan
            elif path == "/api/scan":
                print("Executing synchronous environmental background scan...")
                perform_wifi_scan(wlan)
                response = json.dumps(cached_scan_data)
                client.send("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n")
                client.send(response)
                
            # Route: GET / (Serve Dashboard Application Shell via Safe Chunked Transfers)
            elif path == "/":
                client.send("HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n")
                
                # CRITICAL: Stream the large HTML string in small 1KB blocks to prevent socket memory exhaustion
                total_len = len(HTML_TEMPLATE)
                chunk_size = 1024
                for i in range(0, total_len, chunk_size):
                    client.send(HTML_TEMPLATE[i:i+chunk_size])
                
            else:
                client.send("HTTP/1.1 404 Not Found\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\n404 Content Not Found")
                
            client.close()
            
        except Exception as err:
            print("Runtime Connection Error:", err)
            if client:
                try:
                    client.close()
                except:
                    pass

# Execution entry point protection
if __name__ == '__main__':
    try:
        serve_dashboard()
    except KeyboardInterrupt:
        print("\nWeb Server Terminated via Hardware Interrupt.")
        led.off()
