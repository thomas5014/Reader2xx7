import nt35510, os
import machine; print(machine.ADC(45).read_u16()*9.9/65536)
nt = nt35510.NT35510()
from nt35510 import color565

machine.freq(258_000_000)

def push_raw_buf(x0,y0,w,h,buf):
    nt.draw_buf(x0,y0,w,h)

# buf = bytearray(1024*1024) # this can be a trade off, either you can try to pull in the entire image into the slower psram or you can only take a segment into the faster sram. rn -> 1MB or something like 200-400KB
# with open("Leviathen_decode_sample.jpg","rb") as f:
#     end = f.readinto(buf)
#     print(dir(f),end)
#     f.close()

# will probably need a second buffer for the deocoded image before it is pusehed to the screen.

# container parsing

import struct

MARKER_NAMES = {
    0xD8: "SOI", 0xD9: "EOI", 0xDA: "SOS",
    0xDB: "DQT", 0xC0: "SOF0", 0xC2: "SOF2",
    0xC4: "DHT", 0xDD: "DRI", 0xFE: "COM",
}

for m in range(0xE0, 0xF0):
    MARKER_NAMES[m] = f"APP{m - 0xE0}"
print(MARKER_NAMES)

# ref:
# PSRAM ID: kgd=0x5d eid=0x53
# ['__class__', '__enter__', '__exit__', '__next__', 'close', 'read', 'readinto', 'readline', 'write', '__del__', 'flush', 'readlines', 'seek', 'tell'] 453820
# bytearray(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xe2\x01\xd8ICC_PROFILE\x00\x01\x01\x00\x00\x01\xc8\x00\x00\x00\x00\x040\x00\x00mntrRGB XYZ \x07\xe0\x00\x01\x00\x01\x00\x00\x00\x00\x00\x00acsp\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')

def parse_markers(f):
    """Walk marker segments from an already-open file object positioned at byte 0.
    Yields (marker_byte, offset_of_payload, length_of_payload) for each segment,
    stopping once SOS is found (entropy data follows and needs Stage 5)."""

    f.seek(0)
    soi = f.read(2)
    if not soi == b'\xff\xd8':
        raise
    pos = 2

    while True:
        f.seek(pos)
        hdr = f.read(2)
        if hdr[0] != 0xff: print("not ff", hdr, pos); raise
        marker = hdr[1]
        pos += 2

        if marker == 0xD9:
            print("EOI found, stopping marker parsing")
            return
        if 0xD0 <= marker <= 0xD7:
            print("lone restart marker, skipping gracefully")
            pos += 2
            continue

        length = struct.unpack(">H", f.read(2))[0]   # continues from hdr's read, no reseek needed
        payload_offset = pos + 2            # past the FFxx marker + 2 length bytes
        yield marker, payload_offset, length - 2

        if marker == 0xDA:
            print("SOS found, stopping marker parsing")
            return marker, pos, 10 # 10 is a fudge number
        pos += length

ZIGZAG = [
     0,  1,  8, 16,  9,  2,  3, 10,
    17, 24, 32, 25, 18, 11,  4,  5,
    12, 19, 26, 33, 40, 48, 41, 34,
    27, 20, 13,  6,  7, 14, 21, 28,
    35, 42, 49, 56, 57, 50, 43, 36,
    29, 22, 15, 23, 30, 37, 44, 51,
    58, 59, 52, 45, 38, 31, 39, 46,
    53, 60, 61, 54, 47, 55, 62, 63,
]

def parse_dqt(payload):
    """payload: the raw bytes for one DQT segment (length bytes, as read via
    f.seek(payload_offset); f.read(length)). Returns {table_id: 8x8 list of lists
    in natural row-major order}."""
    tables = {}
    i = 0
    while i < len(payload):
        Pq = payload[i] >> 4
        Tq = payload[i] & 0x0f

        if Pq != 0: raise NotImplementedError("16-bit DQT not supported")

        zzo_vals = payload[i+1 : i+65]

        nat = [0] * 64                       # TODO5 fix: [0]*64, not []*64
        for k in range(64):
            nat[ZIGZAG[k]] = zzo_vals[k]

        table = [nat[r*8:(r+1)*8] for r in range(8)]   # TODO5: reshape to 8x8
        tables[Tq] = table                              # TODO6: store by table id
        i += 65                                         # TODO7: advance past this table

    return tables

def parse_sof0(payload):
    """Returns {"precision":int, "height":int, "width":int,
        "components": {component_id: {"h":H, "v":V, "tq":Tq}}}""" # ok fine i lied
    precision      = payload[0]
    height         = struct.unpack(">H", payload[1:3])[0]
    width          = struct.unpack(">H", payload[3:5])[0]
    num_components = payload[5]
    Nf             = {}

    offset = 6
    i = 0
    while i < num_components:
        cid = payload[offset]
        hv = payload[offset + 1]
        h = hv >> 4; v = hv & 0x0f
        tq = payload[offset + 2]
        Nf[cid] = [h,v,tq]
        offset += 3
        i += 1

    Nf["precision"] = precision
    Nf["height"]    = height
    Nf["width"]     = width
    Nf["num_comp"]  = num_components

    return Nf

def parse_dht(payload):
    """Returns {(table_class, table_id): {(code_length, code_value): symbol}}
    table_class: 0 = DC table, 1 = AC table"""
    tables = {}
    i = 0
    while i < len(payload):
        Tc = payload[i] >> 4
        Th = payload[i] & 0x0f
        counts = payload[i+1 : i+17]
        total = sum(counts)
        symbols = payload[i+17 : i+17+total]
        i += 17 + total

        code = 0
        sym_idx = 0
        code_table = {}
        for length in range(1,17):
            n = counts[length-1]
            for _ in range(n):
                code_table[(length, code)] = symbols[sym_idx]
                sym_idx += 1
                code += 1
            code <<= 1

        tables[(Tc,Th)] = code_table
    return tables

def parse_sos(payload):
    """Returns {component_id: {"td": DC_table_id, "ta": AC_table_id}}"""
    num_components = payload[0]
    scan_components = {}
    offset = 1
    i = 0
    while i < num_components:
        cs = payload[offset] # component selector
        td = payload[offset + 1] >> 4
        ta = payload[offset + 1] & 0x0f
        scan_components[cs] = {"td": td, "ta": ta}
        offset += 2
        i += 1
    return scan_components

class BitReader:
    def __init__(self, f):
        self.f = f
        self.byte = 0
        self.nbits = 0          # unconsumed bits left in self.byte
        self.marker_hit = -1   # set to the marker byte if entropy data ends

    def _next_byte(self) -> int:
        b = self.f.read(1)
        if not b:
            raise EOFError("unexpected end of file in entropy data")
        b = b[0]
        if b == 0xFF:
            nxt = self.f.read(1)[0]
            if nxt == 0x00:
                return 0xFF                      # stuffed -- real data byte 0xFF
            else:
                self.marker_hit = nxt            # restart marker or real marker
                self.f.seek(self.f.tell() - 2)   # un-read FF + marker, caller decides
                return -1
        return b

    @micropython.viper
    def get_bit(self) -> int:
        if int(self.nbits) == 0:
            b = int(self._next_byte()) # line 200
            if b == -1:
                return -1
            self.byte = int(b)
            self.nbits = 8
        self.nbits = int(self.nbits) - 1
        return (int(self.byte) >> int(self.nbits)) & 1    # MSB-first within each byte

    @micropython.viper
    def get_bits(self, n: int) -> int:
        value: int = 0
        i: int = 0
        bit: int = 0
        while i < n:
            bit = int(self.get_bit())
            if bit == -1:
                return -1
            value = (value << 1) | bit
            i += 1
        return value

    # @micropython.viper
    def decode_huffman(self, code_table: int):
        code: int = 0
        length: int = 1
        while length < 17:
            bit = int(self.get_bit())
            if bit == -1:
                return None
            code = (code << 1) | bit
            if (length, code) in code_table:
                return code_table[(length, code)]
            length += 1
        raise ValueError("bad Huffman code: no match up to 16 bits")

def extend(v, s):
    vt = 1 << (s - 1)
    if v < vt:
        return v - (1 << s) + 1
    return v

####################################################################

quant_tables = {}   # table_id -> 8x8
huff_tables  = {}   # (class, id) -> {(length,code): symbol}
sof0_info    = None
scan_info    = None
sos_offset = sos_length = None

def decode_dc(br, dc_table, predictor):
    """Returns the new DC coefficient value. Caller stores it as the
    predictor to pass in next time for this same component."""
    s = br.decode_huffman(dc_table)
    if s == 0:
        diff = 0
    else:
        v = br.get_bits(s)
        diff = extend(v, s)
    return predictor + diff

def decode_ac(br, ac_table):
    """Returns a 64-element list (zigzag order), position 0 left as 0 --
    caller fills position 0 with the DC value separately."""
    coeffs = [0] * 64
    k = 1
    while k <= 63:
        rs = br.decode_huffman(ac_table) # ac luminance symbol<-whatever that means

        if rs == 0x00: break #print("EOB hit at:",k); break
        elif rs == 0xF0: k += 16; continue
        else:
            r = rs >> 4; s = rs & 0x0F # get run length of zeros and size cat
            k += r
            v = br.get_bits(s)
            coeffs[k] = extend(v,s)
            k += 1

    return coeffs

def unzigzag(coeffs):
    nat = [0] * 64
    k = 0
    while k < 64:
        nat[ZIGZAG[k]] = coeffs[k]
        k += 1
    return nat

with open("Leviathen_decode_sample.jpg", "rb") as f:   # or whichever sample you've got on-device
    for marker, offset, length in parse_markers(f):
        name = MARKER_NAMES.get(marker, hex(marker))
        print(f"\noffset {offset:6d}  FF{marker:02X}  {name:8s} length={length}")
        
        if marker == 0xDB: # DQT
            f.seek(offset)
            payload = f.read(length)
            tables = parse_dqt(payload)
            quant_tables.update(tables)

            for tid, t in tables.items():
                print(f"table {tid}: dc(0,0)={t[0][0]}  sample row0={t[0]}")

        elif marker == 0xC0:   # SOF0
            f.seek(offset)
            sof0_info = parse_sof0(f.read(length))
            print(sof0_info)

        elif marker == 0xC4:   # DHT
            f.seek(offset)
            result = parse_dht(f.read(length))
            huff_tables.update(result)

            for (tc, th), ct in result.items():
                kind = "DC" if tc == 0 else "AC"
                print(f"{kind} table {th}: {len(ct)} codes, lengths {sorted(set(l for l,_ in ct))}")

        elif marker == 0xDA:
            f.seek(offset)
            scan_info = parse_sos(f.read(length))
            sos_offset, sos_length = offset, length # still don't trust length
            print("Start of Scan(SOS), result:", scan_info)

entropy_start = sos_offset + sos_length
f = open("Leviathen_decode_sample.jpg", "rb")   # keep this one open, don't use `with` here
f.seek(entropy_start)
br = BitReader(f)

####################################################################

print(huff_tables.keys(), "\n\n", quant_tables.keys())
################################# reshape huff table
temp = huff_tables
del huff_tables
huff_tables = []
huff_tables.append(temp[(0,0)]);huff_tables.append(temp[(1,0)]);huff_tables.append(temp[(0,1)]);huff_tables.append(temp[(1,1)])

dc_table_y = huff_tables[0]   # class 0 = DC, id 0 = the table component 1 (Y) uses
symbol = br.decode_huffman(dc_table_y)
print("first DC Huffman symbol (size category):", symbol)

v = br.get_bits(symbol)
diff = extend(v, symbol)
dc_value = 0 + diff      # predictor starts at 0 -- this is the very first block in the scan
print("first DC coefficient:", dc_value, " (raw bits were", v, ")")


ac_table = huff_tables[1]
lum_coeffs = decode_ac(br,ac_table)
lum_coeffs[0] = dc_value
print("Lum coeffs:",lum_coeffs)

nat_lum = unzigzag(lum_coeffs)

def dequantize(nat_coeffs, quant_table_8x8):
    # nat_coeffs: flat list of 64 (natural order). quant_table_8x8: list of 8 rows of 8.
    out = [0] * 64
    pos = 0
    while pos < 64:
        row, col = pos // 8, pos % 8
        out[pos] = nat_coeffs[pos] * quant_table_8x8[row][col]
        pos += 1
    return out

dq = dequantize(nat_lum, quant_tables[0])
print("expanded/reordered lum:");
for i in range(0,64,8): print(dq[i:i+8])
print("quant table 0:");
for i in range(0,8): print(quant_tables[0][i])

import math

COS_TABLE = [[math.cos((2*x + 1) * u * math.pi / 16) for u in range(8)] for x in range(8)]
print("Cosine Table:",COS_TABLE )
C = [1 / math.sqrt(2)] + [1.0] * 7   # C[0] = 1/sqrt(2), C[1..7] = 1
print("C:",C)

import array

SCALE = 16384  # 2**14 fractional bits -- plenty of precision, no overflow risk
CW = array.array('h', [
    round(C[u] * COS_TABLE[x][u] * SCALE)
    for x in range(8) for u in range(8)
])  # C[u] folded in once here -- one multiply fewer at runtime too

def idct_1d(inp):   # inp: ints (your dequantized coefficients are already ints)
    out = [0] * 8
    x = 0
    while x < 4:
        b = x * 8
        e = inp[0]*CW[b+0] + inp[2]*CW[b+2] + inp[4]*CW[b+4] + inp[6]*CW[b+6]
        o = inp[1]*CW[b+1] + inp[3]*CW[b+3] + inp[5]*CW[b+5] + inp[7]*CW[b+7]
        out[x]     = (e + o + 16384) >> 15   # +16384 rounds to nearest instead of truncating
        out[7 - x] = (e - o + 16384) >> 15
        x += 1
    return out
    

def idct_2d(block):   # block: list of 8 rows of 8
    rows = [0] * 64
    r = 0
    while r < 64:
        rows[r:r+8] = idct_1d(block[r:r+8])
        r += 8
    out = [0.0] * 64
    c = 0
    while c < 8:
        col = idct_1d([rows[c+r*8] for r in range(8)])
        r = 0
        while r < 8:
            out[r*8 + c] = col[r]
            r += 1
        c += 1
    return out

# Pre-allocate global processing buffers once to avoid GC thrashing
idct_in  = memoryview(array.array('h', dq))  # Fill this with your dequantized block
idct_tmp = memoryview(array.array('h', [0] * 64))  # Intermediate workspace
idct_out = memoryview(array.array('h', [0] * 64))  # Holds the final 0-255 pixels

@micropython.viper
def process_idct_2d(p_inp: ptr16, p_tmp: ptr16, p_out: ptr16, p_cw: ptr16):
    # --- STAGE 1: 1D IDCT on Rows (p_inp -> p_tmp) ---
    r = 0
    while r < 64:
        x = 0
        while x < 4:
            b = x * 8
            # In-line 1D IDCT row calculation
            e = (int(p_inp[r+0]) * int(p_cw[b+0]) + 
                 int(p_inp[r+2]) * int(p_cw[b+2]) + 
                 int(p_inp[r+4]) * int(p_cw[b+4]) + 
                 int(p_inp[r+6]) * int(p_cw[b+6]))
                 
            o = (int(p_inp[r+1]) * int(p_cw[b+1]) + 
                 int(p_inp[r+3]) * int(p_cw[b+3]) + 
                 int(p_inp[r+5]) * int(p_cw[b+5]) + 
                 int(p_inp[r+7]) * int(p_cw[b+7]))
            
            # Fixed-point scale down (+16384 for round-to-nearest)
            p_tmp[r + x]     = (e + o + 16384) >> 15
            p_tmp[r + 7 - x] = (e - o + 16384) >> 15
            x += 1
        r += 8

    # --- STAGE 2: 1D IDCT on Columns & Level Shift (p_tmp -> p_out) ---
    c = 0
    while c < 8:
        x = 0
        while x < 4:
            b = x * 8
            # In-line 1D IDCT column calculation (strided by 8)
            e = (int(p_tmp[c + 0]) * int(p_cw[b+0]) + 
                 int(p_tmp[c + 16]) * int(p_cw[b+2]) + 
                 int(p_tmp[c + 32]) * int(p_cw[b+4]) + 
                 int(p_tmp[c + 48]) * int(p_cw[b+6]))
                 
            o = (int(p_tmp[c + 8]) * int(p_cw[b+1]) + 
                 int(p_tmp[c + 24]) * int(p_cw[b+3]) + 
                 int(p_tmp[c + 40]) * int(p_cw[b+5]) + 
                 int(p_tmp[c + 56]) * int(p_cw[b+7]))
            
            val1 = (e + o + 16384) >> 15
            val2 = (e - o + 16384) >> 15
            
            # --- STAGE 3: Integrated Level Shift & Clamping (0-255) ---
            val1 += 128
            if val1 < 0: val1 = 0
            elif val1 > 255: val1 = 255
            p_out[x * 8 + c] = val1
            
            val2 += 128
            if val2 < 0: val2 = 0
            elif val2 > 255: val2 = 255
            p_out[(7 - x) * 8 + c] = val2
            
            x += 1
        c += 1


def level_shift(idct_block):
    out = [0]*64
    v = 0
    while v < 64:
        val = idct_block[v] + 128
        out[v] = min(255, max(0, val))
        v += 1
    return out

print(idct_1d(dq))
def idct_2d(dq):
    idct_in  = array.array('h', dq)
    process_idct_2d(idct_in,idct_tmp,idct_out,CW)
    return idct_out
print("pixels:")
for i in range(0,64,8): print(pixels[i:i+8])

##########################################################

def decode_block(br, dc_table, ac_table, quant_table, dc_predictor):
    """Returns (8x8 level-shifted block, new_dc_predictor)."""
    dc = decode_dc(br, dc_table, dc_predictor)
    ac_coeffs = decode_ac(br, ac_table)
    ac_coeffs[0] = dc
    nat = unzigzag(ac_coeffs)
    dq = dequantize(nat, quant_table)
    pixels = level_shift(idct_2d(dq))
    return pixels, dc

f.seek(entropy_start)
br = BitReader(f)   # fresh reader, right at the real start of the scan data

# Test decoding a few blocks to see if it works:
# Y = decode_block(br, huff_tables[(0,0)], huff_tables[(1,0)], quant_tables[0], 0)
# Y1 = decode_block(br, huff_tables[(0,0)], huff_tables[(1,0)], quant_tables[0], Y[1])
# Y2 = decode_block(br, huff_tables[(0,0)], huff_tables[(1,0)], quant_tables[0], Y1[1])
# Y3 = decode_block(br, huff_tables[(0,0)], huff_tables[(1,0)], quant_tables[0], Y2[1])
# print("Y block:")
# print(Y[0],Y1[0],Y2[0],Y3[0])
# for i in range(0,64,8): print(Y[0][i:i+8], "  ", Y1[0][i:i+8])
# print("\n")
# for i in range(0,64,8): print(Y2[0][i:i+8], "  ", Y3[0][i:i+8])
# Cb = decode_block(br, huff_tables[(0,1)], huff_tables[(1,1)], quant_tables[1], 0)
# print("Cb block:")
# for i in range(0,64,8): print(Cb[0][i:i+8])
# Cr = decode_block(br, huff_tables[(0,1)], huff_tables[(1,1)], quant_tables[1], 0)
# print("Cr block:")
# for i in range(0,64,8): print(Cr[0][i:i+8])
# print(Cb[0],Cr[0])

########################################stitching stuff

Hmax = max(sof0_info[cid][0] for cid in (1, 2, 3))
Vmax = max(sof0_info[cid][1] for cid in (1, 2, 3))
mcu_w, mcu_h = 8 * Hmax, 8 * Vmax
mcus_x = (sof0_info["width"]  + mcu_w - 1) // mcu_w
mcus_y = (sof0_info["height"] + mcu_h - 1) // mcu_h
print(f"{mcus_x} x {mcus_y} MCUs, each {mcu_w}x{mcu_h}px")   # expect 31 x 292 for your image

dc_pred = {1: 0, 2: 0, 3: 0}   # Y, Cb, Cr -- persists for the whole scan

def decode_mcu():
    blocks = []
    i = 0
    while i < 4:   # Hmax*Vmax = 4 Y blocks
        px, dc_pred[1] = decode_block(br, huff_tables[0], huff_tables[1], quant_tables[0], dc_pred[1])
        blocks.append(px)
        i += 1
    px, dc_pred[2] = decode_block(br, huff_tables[2], huff_tables[3], quant_tables[1], dc_pred[2])
    blocks.append(px)
    px, dc_pred[3] = decode_block(br, huff_tables[2], huff_tables[3], quant_tables[1], dc_pred[3])
    blocks.append(px)
    return blocks   # [Y, Y1, Y2, Y3, Cb, Cr]

all_blocks = []
for i in range(3):
    all_blocks.extend(decode_mcu())

# print(all_blocks)   # should be identical to your current hardcoded `data`

width, height = sof0_info["width"], sof0_info["height"]

def decode_and_blit_row(mcu_row):
    row_h = min(mcu_h, height - mcu_row * mcu_h)       # clip bottom edge on the last row
    buf = memoryview(bytearray(mcus_x * mcu_w * row_h * 2))          # RGB565, 2 bytes/pixel
    a = 0
    b = 0
    bi = 0
    mcu_col = 0
    while mcu_col < mcus_x:
        t0 = time.ticks_us()
        # ys_block, cb, cr = decode_mcu()[:4], None, None
        blocks = decode_mcu()   # [Y, Y1, Y2, Y3, Cb, Cr]
        ys_block = blocks[:4]
        cb, cr = blocks[4], blocks[5]
        a += time.ticks_us() - t0
        t0 = time.ticks_us()
        R = 0
        while R < row_h:
            C = 0
            while C < mcu_w:
                yb = (R >= 8) * 2 + (C >= 8)
                y = ys_block[yb][(R % 8) * 8 + (C % 8)]
                r, c = R // 2, C // 2
                cb_v, cr_v = cb[r * 8 + c], cr[r * 8 + c]

                rr = y + 1.402 * (cr_v - 128)
                gg = y - 0.344136 * (cb_v - 128) - 0.714136 * (cr_v - 128)
                bb = y + 1.772 * (cb_v - 128)
                clip = lambda v: max(0, min(255, int(v)))

                color = color565(clip(rr), clip(gg), clip(bb))
                px_offset = (R * mcus_x * mcu_w + mcu_col * mcu_w + C) * 2
                buf[px_offset] = color >> 8
                buf[px_offset + 1] = color & 0xFF
                C += 1
            R += 1
        mcu_col += 1
        b += time.ticks_us() - t0
    real_w = min(mcus_x * mcu_w, width)
    print(mcu_row * mcu_h, real_w, row_h)
    nt.draw_buf(0, mcu_row * mcu_h, mcus_x * mcu_w, row_h, buf)   # draw only the real width, discard right-edge padding
    print(f"times: a: {a:,}, b: {b:,}")
    return buf, real_w, row_h

f.seek(entropy_start)
br = BitReader(f)
dc_pred = {1: 0, 2: 0, 3: 0}

import time
import ubinascii

for mcu_row in range(10):
    t0 = time.ticks_us()
    dat = decode_and_blit_row(mcu_row)
    t1 = time.ticks_us()
    buf, real_w, row_h = dat
    # print(ubinascii.hexlify(buf).decode())
    print(f"Decoded and blitted row {mcu_row} in {(t1 - t0)/1000:.1f} ms")
    print(f"Row {mcu_row}: {real_w}x{row_h} pixels, buffer length {len(buf)}")

# Decoded and blitted row 0 in 11551.6 ms starting point
# Decoded and blitted row 0 in 11466.5 ms for -> while
# times: a: 9,819,197, b: 1,720,268. a -> decode mcus, b -> color mixing
# Decoded and blitted row 0 in 5144.4 ms idek how to track this anymore
# Decoded and blitted row 0 in 3958.2 ms
# times: a: 1,620,779, b: 1,632,292
# Decoded and blitted row 0 in 3254.5 ms