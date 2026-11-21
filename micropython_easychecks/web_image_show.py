# Download a JPEG over WiFi (HTTP/HTTPS, follows redirects) into RAM and show it
# on the NT35510. Credentials come from a device-side wifi_secrets.py
# (SSID = "...", PASSWORD = "...") so they never live in this file.
#
# Order matters here: WiFi/download first, display init after. The CYW43 +
# display conflict is still under investigation (see tri_combo_check.py), so
# the network work is finished and the radio idle before the panel is touched.
import time, gc, io, socket
import network

URL = "https://picsum.photos/id/237/480/700.jpg"   # any JPEG URL; baseline or progressive


def connect():
    SSID, PASSWORD = "quack3", "drfluffy"
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(SSID, PASSWORD)
        t0 = time.ticks_ms()
        while not wlan.isconnected():
            if time.ticks_diff(time.ticks_ms(), t0) > 15000:
                raise RuntimeError("WiFi connect timeout, status=%d" % wlan.status())
            time.sleep_ms(100)
    print("WiFi up:", wlan.ifconfig())
    return wlan


def http_get(url, max_redirects=5):
    for _ in range(max_redirects + 1):
        proto, _, host, path = url.split("/", 3)
        path = "/" + path
        port = 443 if proto == "https:" else 80
        if ":" in host:
            host, port = host.split(":")
            port = int(port)
        addr = socket.getaddrinfo(host, port)[0][-1]
        s = socket.socket()
        s.settimeout(15)
        s.connect(addr)
        if proto == "https:":
            import ssl
            s = ssl.wrap_socket(s, server_hostname=host)
        s.write(("GET %s HTTP/1.0\r\nHost: %s\r\nUser-Agent: mpy\r\n"
                 "Accept: image/jpeg\r\nConnection: close\r\n\r\n" % (path, host)).encode())

        status = s.readline()
        code = int(status.split()[1])
        headers = {}
        while True:
            line = s.readline()
            if not line or line == b"\r\n":
                break
            k, _, v = line.decode().partition(":")
            headers[k.strip().lower()] = v.strip()

        if code in (301, 302, 303, 307, 308):
            s.close()
            url = headers["location"]
            if url.startswith("/"):
                url = "%s//%s%s" % (proto, host, url)
            print("redirect ->", url)
            continue
        if code != 200:
            s.close()
            raise RuntimeError("HTTP %d" % code)

        body = io.BytesIO()
        chunk = bytearray(4096)
        mv = memoryview(chunk)
        total = 0
        while True:
            n = s.readinto(chunk)
            if not n:
                break
            body.write(mv[:n])
            total += n
        s.close()
        body.seek(0)
        return body, total
    raise RuntimeError("too many redirects")


wlan = connect()
gc.collect()
t0 = time.ticks_us()
img, size = http_get(URL)
t1 = time.ticks_us()
print("downloaded %d bytes in %.2f s" % (size, time.ticks_diff(t1, t0) / 1e6))
wlan.active(False)   # radio off before the display goes live
gc.collect()

import stbjpeg, nt35510
from machine import PWM, Pin

nt = nt35510.NT35510()
nt.fill(0)


def blit_cb(x, y, w, h, buf):
    nt.draw_buf(x, y, w, h, buf)


t0 = time.ticks_us()
stbjpeg.decode(img, blit_cb, max_w=480, max_h=800)
t1 = time.ticks_us()
print(f"decode+blit: {time.ticks_diff(t1, t0):,} us")

backlight = PWM(Pin(20))
backlight.freq(50_000)
backlight.duty_u16(65535)
