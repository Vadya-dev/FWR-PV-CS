"""Minimal X-Ray (IX-Ray) .db archive reader: lists / extracts files.
usage: python -I xdb.py <archive.db> <lzo2.dll> <out_dir> [prefix1 prefix2 ...]
       python -I xdb.py <archive.db> <lzo2.dll> --list
"""
import ctypes, os, struct, sys

N, F, THRESHOLD = 4096, 60, 2
N_CHAR = 256 - THRESHOLD + F
T = N_CHAR * 2 - 1
R = T - 1
MAX_FREQ = 0x4000

d_code = bytes([0]*32 + [1]*16 + [2]*16 + [3]*16 + [4]*8 + [5]*8 + [6]*8 + [7]*8 + [8]*8 + [9]*8 + [10]*8 + [11]*8
               + sum([[c]*4 for c in range(0x0C, 0x18)], []) + sum([[c]*2 for c in range(0x18, 0x30)], []) + list(range(0x30, 0x40)))
d_len = bytes([3]*32 + [4]*48 + [5]*64 + [6]*48 + [7]*48 + [8]*16)
assert len(d_code) == 256 and len(d_len) == 256


def lzhuf_decode(src):
    pos = 0
    getbuf = 0
    getlen = 0

    def getb():
        nonlocal pos
        if pos >= len(src):
            return 0
        b = src[pos]; pos += 1
        return b

    def getbit():
        nonlocal getbuf, getlen
        while getlen <= 8:
            getbuf |= getb() << (8 - getlen)
            getlen += 8
        i = getbuf
        getbuf = (getbuf << 1) & 0xFFFFFFFF
        getlen -= 1
        return (i & 0x8000) >> 15

    def getbyte():
        nonlocal getbuf, getlen
        while getlen <= 8:
            getbuf |= getb() << (8 - getlen)
            getlen += 8
        i = getbuf
        getbuf = (getbuf << 8) & 0xFFFFFFFF
        getlen -= 8
        return (i & 0xff00) >> 8

    freq = [0] * (T + 1)
    prnt = [0] * (T + N_CHAR + 1)
    son = [0] * T
    for i in range(N_CHAR):
        freq[i] = 1; son[i] = i + T; prnt[i + T] = i
    i, j = 0, N_CHAR
    while j <= R:
        freq[j] = freq[i] + freq[i + 1]; son[j] = i; prnt[i] = prnt[i + 1] = j
        i += 2; j += 1
    freq[T] = 0xffff; prnt[R] = 0

    def reconst():
        j = 0
        for i in range(T):
            if son[i] >= T:
                freq[j] = (freq[i] + 1) // 2; son[j] = son[i]; j += 1
        i, j = 0, N_CHAR
        while j < T:
            k = i + 1
            f = freq[j] = freq[i] + freq[k]
            k = j - 1
            while f < freq[k]:
                k -= 1
            k += 1
            freq[k + 1:j + 1] = freq[k:j]; freq[k] = f
            son[k + 1:j + 1] = son[k:j]; son[k] = i
            i += 2; j += 1
        for i in range(T):
            k = son[i]
            if k >= T:
                prnt[k] = i
            else:
                prnt[k] = prnt[k + 1] = i

    def update(c):
        if freq[R] == MAX_FREQ:
            reconst()
        c = prnt[c + T]
        while True:
            freq[c] += 1; k = freq[c]
            l = c + 1
            if k > freq[l]:
                l += 1
                while k > freq[l]:
                    l += 1
                l -= 1
                freq[c] = freq[l]; freq[l] = k
                i = son[c]; prnt[i] = l
                if i < T: prnt[i + 1] = l
                j = son[l]; son[l] = i
                prnt[j] = c
                if j < T: prnt[j + 1] = c
                son[c] = j
                c = l
            c = prnt[c]
            if c == 0:
                break

    textsize = getb() | (getb() << 8) | (getb() << 16) | (getb() << 24)
    out = bytearray()
    text_buf = bytearray(b' ' * (N + F))
    r = N - F
    count = 0
    while count < textsize:
        c = son[R]
        while c < T:
            c += getbit(); c = son[c]
        c -= T
        update(c)
        if c < 256:
            out.append(c); text_buf[r] = c; r = (r + 1) & (N - 1); count += 1
        else:
            i = getbyte()
            cc = d_code[i] << 6
            jj = d_len[i] - 2
            while jj:
                i = (i << 1) + getbit(); jj -= 1
            p = cc | (i & 0x3f)
            i = (r - p - 1) & (N - 1)
            j = c - 255 + THRESHOLD
            for k in range(j):
                b = text_buf[(i + k) & (N - 1)]
                out.append(b); text_buf[r] = b; r = (r + 1) & (N - 1); count += 1
    return bytes(out)


def read_chunks(data):
    pos, res = 0, {}
    while pos + 8 <= len(data):
        t, s = struct.unpack_from('<II', data, pos)
        res[t & 0x7FFFFFFF] = (bool(t & 0x80000000), pos + 8, s)
        pos += 8 + s
    return res


def main():
    arc, dll = sys.argv[1], sys.argv[2]
    fh = open(arc, 'rb')
    ch = {}
    pos = 0
    total = os.path.getsize(arc)
    while pos + 8 <= total:
        fh.seek(pos)
        t, s = struct.unpack('<II', fh.read(8))
        ch[t & 0x7FFFFFFF] = (bool(t & 0x80000000), pos + 8, s)
        pos += 8 + s

    class _Data:
        def __getitem__(self, sl):
            fh.seek(sl.start)
            return fh.read(sl.stop - sl.start)
    data = _Data()
    comp, off, size = ch[1]
    hdr = data[off:off + size]
    if comp:
        hdr = lzhuf_decode(hdr)
    entries = []
    p = 0
    while p < len(hdr):
        bs = struct.unpack_from('<H', hdr, p)[0]; p += 2
        rec = hdr[p:p + bs]; p += bs
        size_real, size_comp, crc = struct.unpack_from('<III', rec, 0)
        name = rec[12:bs - 4].decode('cp1251')
        ptr = struct.unpack_from('<I', rec, bs - 4)[0]
        entries.append((name, size_real, size_comp, ptr))
    if sys.argv[3] == '--list':
        for e in entries:
            print(e[0], e[1])
        return
    out_dir = sys.argv[3]
    prefixes = [x.lower() for x in sys.argv[4:]]
    lzo = ctypes.CDLL(dll)
    lzo.__lzo_init_v2.restype = ctypes.c_int
    # lzo_init() macro: __lzo_init_v2(LZO_VERSION, sizeof(short), sizeof(int), sizeof(long), sizeof(lzo_uint32_t), sizeof(lzo_uint), lzo_sizeof_dict_t, sizeof(char*), sizeof(lzo_voidp), sizeof(lzo_callback_t))
    n = 0
    for name, sr, sc, ptr in entries:
        lname = name.lower()
        if prefixes and not any(lname.startswith(px) for px in prefixes):
            continue
        if sr == 0 and sc == 0 and ptr == 0:
            continue
        raw = data[ptr:ptr + sc]
        if sr == sc:
            buf = raw
        else:
            dst = ctypes.create_string_buffer(sr)
            dlen = ctypes.c_size_t(sr)
            rc = lzo.lzo1x_decompress_safe(raw, ctypes.c_size_t(sc), dst, ctypes.byref(dlen), None)
            if rc != 0:
                print('! lzo error', rc, name); continue
            buf = dst.raw[:dlen.value]
        dest = os.path.join(out_dir, name)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, 'wb') as fo:
            fo.write(buf)
        n += 1
    print('extracted', n)


if __name__ == '__main__':
    main()
