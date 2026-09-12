import network, time

wlan = network.WLAN(network.STA_IF)  # create station interface
wlan.active(True)  # activate the interface
wlan.connect("quack3", "drfluffy")  # connect to the network
if wlan.isconnected():
    print("Connected to Wi-Fi")
    print("IP Address:", wlan.ifconfig()[0])
    print(dir(wlan))
    mode = int(input("Enter mode (1 for pwr-save else 2 for preformance): "))
    if mode == 1:
        wlan.config(pm=network.WLAN.PM_POWERSAVE)  # Set power save mode
        print("Power save mode enabled")
    elif mode == 2:
        wlan.config(pm=network.WLAN.PM_PERFORMANCE)  # Set performance mode
        print("Performance mode enabled")
    import requests, machine, micropython
    micropython.alloc_emergency_exception_buf(100)

    class TimeoutException(Exception):
        """Custom exception raised when a function takes too long."""
        pass

    def raise_timeout(arg):
        """Executes on the main thread to interrupt current execution."""
        raise TimeoutException("Function execution timed out!")

    def timer_isr(timer_obj):
        """Triggers when the hardware timer expires."""
        # Schedule the exception-raising function to execute in the main thread loop
        micropython.schedule(raise_timeout, None)

    timeout_timer = machine.Timer(-1)
    timeout_timer.init(mode=machine.Timer.ONE_SHOT, period=30000, callback=timer_isr)

    try:
        t0 = time.ticks_ms()
        res = requests.get(url='http://www.baidu.com/')
        t1 = time.ticks_ms()
        timeout_timer.deinit()
        print(f"Request took {t1 - t0} ms") 
        print(res.text)
    except Exception as e:
        print(f"Request time out: {e}")

    result = input("Do you want to host found html (y/n)?: ")
    if result.lower() == 'y':
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('', 80))  # Port 80 is the standard HTTP port
        s.listen(5)
        print("Server is listening for browser requests...\n")

        while True:
            conn, addr = s.accept()
            print(f"Browser connected from: {addr}")
            request = conn.recv(1024)

            # Simple HTML Web Page
            html = res.text

            # Send HTTP Headers and HTML Body
            conn.send('HTTP/1.1 200 OK\n')
            conn.send('Content-Type: text/html\n')
            conn.send('Connection: close\n\n')
            conn.sendall(html)
            conn.close()
else:
    print("Failed to connect to Wi-Fi")