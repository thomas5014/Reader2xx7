@micropython.asm_thumb
def add_one(r0):
    add(r0, 1)
print(add_one(1))

@micropython.asm_thumb
def fill_nobx(r0, r1, r2):
    label(fill_loop)
    cmp(r2, 0)
    beq(fill_done)
    str(r1, [r0, 0])
    add(r0, r0, 4)
    sub(r2, r2, 1)
    b(fill_loop)
    label(fill_done)

fill_nobx(0x11000000, 0x22222222, 4)
print("fill_nobx ok -- RESET NOW")
