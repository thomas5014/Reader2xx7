import machine
machine.freq(150_000_000)
print("freq", machine.freq())

written = 0
import sdio, os, time, gc

sd = sdio.SDCard()

block_size = sd.ioctl(5, 0) or 512
block_count = sd.ioctl(4, 0)
print(f"block size={block_size}  block count={block_count}  total={block_count*block_size/1e6:.1f} MB")

# --- Raw block-device speed test (read-only, safe anywhere on the card) ---
# Reads well past any filesystem metadata so it can't be mistaken for a
# cached/short-circuited access; pure sequential readblocks() throughput.
def raw_read_speed(num_blocks=2048, start_block=200_000, chunk_blocks=8):
    buf = bytearray(block_size * chunk_blocks)
    t0 = time.ticks_us()
    done = 0
    blk = start_block
    while done < num_blocks:
        n = min(chunk_blocks, num_blocks - done)
        sd.readblocks(blk, buf if n == chunk_blocks else memoryview(buf)[: n * block_size])
        blk += n
        done += n
    dt = time.ticks_diff(time.ticks_us(), t0)
    total_bytes = num_blocks * block_size
    mbps = total_bytes / (dt / 1e6) / 1e6
    print(f"raw sequential read:  {total_bytes/1024:.0f} KB in {dt/1000:.1f} ms -> {mbps:.2f} MB/s")

raw_read_speed()

# --- Filesystem-level speed test (safe: confined to one file we create/delete) ---
def fs_speed_test(path="/sd/speedtest.bin", total_bytes=4 * 1024 * 1024, chunk=4096):
    global written
    buf = bytearray(chunk)
    for i in range(chunk):
        buf[i] = i & 0xFF

    gc.collect()
    t0 = time.ticks_us()
    written = 0
    with open(path, "wb") as f:
        while written < total_bytes:
            n = f.write(buf)
            written += n
    dt = time.ticks_diff(time.ticks_us(), t0)
    wmbps = written / (dt / 1e6) / 1e6
    print(f"file write: {written/1024:.0f} KB in {dt/1000:.1f} ms -> {wmbps:.2f} MB/s")

    gc.collect()
    t0 = time.ticks_us()
    read_total = 0
    with open(path, "rb") as f:
        while True:
            n = f.readinto(buf)
            if not n:
                break
            read_total += n
    dt = time.ticks_diff(time.ticks_us(), t0)
    rmbps = read_total / (dt / 1e6) / 1e6
    print(f"file read:  {read_total/1024:.0f} KB in {dt/1000:.1f} ms -> {rmbps:.2f} MB/s")

    os.remove(path)


try:
    os.stat("/sd")
except OSError:
    os.mount(sd, "/sd")

# try:
#     fs_speed_test() 
# except Exception as e:
#     print(f"Error: {e},  written: {written}")
fs_speed_test() 