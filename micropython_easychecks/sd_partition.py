# sd_partition.py -- adaptive partition-offset wrapper for os.mount().
#
# Most retail SD cards ship pre-partitioned (an MBR at block 0, with the
# actual FAT filesystem starting some sectors later -- commonly 2048 or
# 8192), but MicroPython's os.mount() expects the FAT boot sector to sit
# directly at block 0 -- it doesn't walk a partition table itself. This
# wraps a raw SDCard block-device object, figures out at construction
# time which situation the card is actually in, and transparently adds
# the right offset to every block access so os.mount() always sees
# "block 0" as wherever the real filesystem actually starts.
#
# Usage:
#   import sd, os
#   from sd_partition import PartitionedSDCard
#   raw_sd = sd.SDCard(spi, cs)
#   part = PartitionedSDCard(raw_sd)
#   os.mount(part, '/sd')

# Common FAT12/16/32 partition type codes (LBA and CHS variants).
_FAT_TYPES = (0x01, 0x04, 0x06, 0x0B, 0x0C, 0x0E, 0x1B, 0x1C, 0x1E)


class PartitionedSDCard:
    def __init__(self, sd):
        self.sd = sd
        self.offset = self._find_offset()

    def _find_offset(self):
        buf = bytearray(512)
        self.sd.readblocks(0, buf)

        if buf[510] != 0x55 or buf[511] != 0xAA:
            raise OSError("block 0 has no valid boot/MBR signature (55 AA missing)")

        # Already a bare FAT boot sector, no partition table -- these
        # fields are only present in an actual FAT VBR, never in an
        # MBR's boot-loader bytes.
        if bytes(buf[54:59]) == b"FAT12" or bytes(buf[54:59]) == b"FAT16":
            return 0
        if bytes(buf[82:87]) == b"FAT32":
            return 0

        # Otherwise treat it as an MBR: scan the 4 partition entries for
        # the first one with a recognized FAT type code.
        seen_types = []
        for i in range(4):
            entry = 446 + 16 * i
            ptype = buf[entry + 4]
            seen_types.append(ptype)
            if ptype in _FAT_TYPES:
                start_lba = (
                    buf[entry + 8]
                    | (buf[entry + 9] << 8)
                    | (buf[entry + 10] << 16)
                    | (buf[entry + 11] << 24)
                )
                print("PartitionedSDCard: found FAT partition (type 0x{:02x}) at LBA {}".format(
                    ptype, start_lba
                ))
                return start_lba

        # Nothing recognized -- print what's actually there so this isn't
        # a dead end. 0x07 (shared with NTFS) most commonly means exFAT
        # on SD cards, which MicroPython's built-in FatFS can't mount at
        # all regardless of offset -- SDXC cards (>=32GB) are required by
        # the SD Association's own spec to ship exFAT-formatted, so this
        # is the likely case if the card is a newer/larger one.
        print("PartitionedSDCard: partition entry types found: {}".format(
            ["0x{:02x}".format(t) for t in seen_types]
        ))
        if 0x07 in seen_types:
            print("PartitionedSDCard: type 0x07 present -- likely exFAT, which "
                  "MicroPython's built-in os.mount()/FatFS cannot read regardless "
                  "of partition offset. The card would need reformatting to FAT32.")

        raise OSError("no FAT partition found in MBR at block 0")

    def readblocks(self, block_num, buf):
        self.sd.readblocks(block_num + self.offset, buf)

    def writeblocks(self, block_num, buf):
        self.sd.writeblocks(block_num + self.offset, buf)

    def ioctl(self, op, arg):
        if op == 4:  # block count -- relative to the partition, not the whole disk
            total = self.sd.ioctl(4, arg)
            return total - self.offset if total is not None else None
        return self.sd.ioctl(op, arg)


if __name__ == "__main__":
    from machine import SoftSPI, Pin                                                                                                                                                           
    import sd, os                                                                                                                                                                          
    csP = 27; mosiP = 22; clkP = 23; misoP = 24                                                    
    spi = SoftSPI(baudrate=100_000, sck=Pin(clkP), mosi=Pin(mosiP), miso=Pin(misoP))
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
    psd = PartitionedSDCard(sd)
    print("sd set")
    os.mount(psd, "/sd")
