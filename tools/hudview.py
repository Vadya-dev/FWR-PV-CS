"""Offline X-Ray/IX-Ray HUD preview: OGF/OMF loading, skinning, IX-Ray HUD transform chain, software raster.
Pure Python (no numpy)."""
import math, os, struct, zlib, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON = os.environ.get('FWR_ADDON') or os.path.join(REPO, 'ixr_addons', 'fwr_cs_edition')
# vanilla CS meshes (hands etc.) extracted with tools/xdb.py, see tools/README.md
VANILLA = os.environ.get('FWR_VANILLA') or os.path.join(REPO, 'tools', '_vanilla')
RESDIRS = [os.path.join(ADDON, 'meshes'), os.path.join(VANILLA, 'meshes')]

# ------------------------------------------------------------------ math (column-vector 4x4, M[r][c])


def ident():
    return [[1.0, 0, 0, 0], [0, 1.0, 0, 0], [0, 0, 1.0, 0], [0, 0, 0, 1.0]]


def from_ijkc(i, j, k, c=(0, 0, 0)):
    return [[i[0], j[0], k[0], c[0]], [i[1], j[1], k[1], c[1]], [i[2], j[2], k[2], c[2]], [0, 0, 0, 1.0]]


def mul(A, B):
    return [[A[r][0] * B[0][c] + A[r][1] * B[1][c] + A[r][2] * B[2][c] + A[r][3] * B[3][c] for c in range(4)] for r in range(4)]


def inv(M):
    R = [[M[c][r] for c in range(3)] for r in range(3)]  # transpose rot (assumes orthonormal)
    t = [M[r][3] for r in range(3)]
    out = ident()
    for r in range(3):
        for c in range(3):
            out[r][c] = R[r][c]
        out[r][3] = -(R[r][0] * t[0] + R[r][1] * t[1] + R[r][2] * t[2])
    return out


def xf(M, p):
    x, y, z = p
    return (M[0][0] * x + M[0][1] * y + M[0][2] * z + M[0][3],
            M[1][0] * x + M[1][1] * y + M[1][2] * z + M[1][3],
            M[2][0] * x + M[2][1] * y + M[2][2] * z + M[2][3])


def hpb(h, p, b):
    sh, ch, sp, cp, sb, cb = math.sin(h), math.cos(h), math.sin(p), math.cos(p), math.sin(b), math.cos(b)
    cc, cs, sc, ss = ch * cb, ch * sb, sh * cb, sh * sb
    return from_ijkc((cc - sp * ss, -cp * sb, sp * cs + sc), (sp * sc + cs, cp * cb, ss - sp * cc), (-cp * sh, sp, cp * ch))


def rotX(a):
    c, s = math.cos(a), math.sin(a)
    return from_ijkc((1, 0, 0), (0, c, s), (0, -s, c))


def rotY(a):
    c, s = math.cos(a), math.sin(a)
    return from_ijkc((c, 0, -s), (0, 1, 0), (s, 0, c))


def rotZ(a):
    c, s = math.cos(a), math.sin(a)
    return from_ijkc((c, s, 0), (-s, c, 0), (0, 0, 1))


def translated(M, t):
    M = [row[:] for row in M]
    M[0][3], M[1][3], M[2][3] = t
    return M


def quat_xform(q, t):
    x, y, z, w = q
    xx, yy, zz, xy, xz, yz, wx, wy, wz = x * x, y * y, z * z, x * y, x * z, y * z, w * x, w * y, w * z
    i = (1 - 2 * (yy + zz), 2 * (xy - wz), 2 * (xz + wy))
    j = (2 * (xy + wz), 1 - 2 * (xx + zz), 2 * (yz - wx))
    k = (2 * (xz - wy), 2 * (yz + wx), 1 - 2 * (xx + yy))
    return from_ijkc(i, j, k, t)


def slerp(a, b, t):
    d = sum(x * y for x, y in zip(a, b))
    if d < 0:
        b = tuple(-x for x in b); d = -d
    if d > 0.9995:
        r = tuple(x + (y - x) * t for x, y in zip(a, b))
    else:
        th = math.acos(d); s = math.sin(th)
        wa, wb = math.sin((1 - t) * th) / s, math.sin(t * th) / s
        r = tuple(wa * x + wb * y for x, y in zip(a, b))
    n = math.sqrt(sum(x * x for x in r)) or 1
    return tuple(x / n for x in r)


def attach_matrix(pos, rot_deg):
    return translated(hpb(*[math.radians(v) for v in rot_deg]), pos)


def aim_matrix(off, rot_rad):
    return translated(mul(rotZ(rot_rad[2]), mul(rotY(rot_rad[1]), rotX(rot_rad[0]))), off)


def decompose_aim(M):
    """inverse of aim_matrix: R = Rz*Ry*Rx -> (x,y,z) radians, offset"""
    # R = Rz Ry Rx ; use matrix elements (row r, col c)
    # compute numerically by solving: build R and extract
    r20 = M[2][0]
    # For R = Rz(c) Ry(b) Rx(a) with these X-Ray (transposed) rotations, derive via search
    best = None
    # analytic extraction using generic approach: try candidates from atan2 and verify
    import itertools
    cands = []
    for sgn in (1, -1):
        pass
    # numeric refine (Gauss-Newton on 3 angles)
    a = b = c = 0.0
    for _ in range(60):
        R = aim_matrix((0, 0, 0), (a, b, c))
        err = [R[r][k] - M[r][k] for r in range(3) for k in range(3)]
        J = []
        h = 1e-6
        for d in range(3):
            v = [a, b, c]; v[d] += h
            R2 = aim_matrix((0, 0, 0), v)
            J.append([(R2[r][k] - R[r][k]) / h for r in range(3) for k in range(3)])
        # normal equations 3x3
        JTJ = [[sum(J[p][n] * J[q][n] for n in range(9)) for q in range(3)] for p in range(3)]
        JTe = [sum(J[p][n] * err[n] for n in range(9)) for p in range(3)]
        delta = solve3(JTJ, JTe)
        a, b, c = a - delta[0], b - delta[1], c - delta[2]
        if max(abs(x) for x in delta) < 1e-10:
            break
    return (M[0][3], M[1][3], M[2][3]), (a, b, c)


def solve3(A, b):
    import copy
    M = [A[i][:] + [b[i]] for i in range(3)]
    for i in range(3):
        p = max(range(i, 3), key=lambda r: abs(M[r][i]))
        M[i], M[p] = M[p], M[i]
        if abs(M[i][i]) < 1e-15:
            return [0, 0, 0]
        for r in range(3):
            if r != i:
                f = M[r][i] / M[i][i]
                for c in range(i, 4):
                    M[r][c] -= f * M[i][c]
    return [M[i][3] / M[i][i] for i in range(3)]


# ------------------------------------------------------------------ chunk io


def iter_chunks(buf, start=0, end=None):
    pos, end = start, (len(buf) if end is None else end)
    while pos + 8 <= end:
        cid, size = struct.unpack_from('<II', buf, pos)
        yield cid & 0x7FFFFFFF, pos + 8, size
        pos += 8 + size


def strz(buf, pos):
    e = buf.index(b'\0', pos)
    return buf[pos:e].decode('cp1251', 'replace'), e + 1


def find_mesh(rel):
    rel = rel.replace('/', '\\')
    for d in RESDIRS:
        p = os.path.join(d, rel)
        if os.path.isfile(p):
            return p
    return None


# ------------------------------------------------------------------ OGF

VT = {0x12071980: 1, 1: 1, 2 * 0x12071980: 2, 2: 2, 4 * 0x12071980: 3, 3: 3, 5 * 0x12071980: 4, 4: 4}


class Model:
    def __init__(self, path):
        self.path = path
        data = open(path, 'rb').read()
        self.meshes = []  # list of (pos list, bones list, weights list, tris list)
        self.bone_names, self.bone_parent = [], []
        self.bind_local = []
        self.refs = []
        top = {cid: (off, size) for cid, off, size in iter_chunks(data)}
        if 9 in top:
            off, size = top[9]
            for _, coff, csize in iter_chunks(data, off, off + size):
                self._load_mesh(data, coff, coff + csize)
        else:
            self._load_mesh(data, 0, len(data))
        if 13 in top:
            off, size = top[13]
            n = struct.unpack_from('<I', data, off)[0]
            p = off + 4
            parents = []
            for _ in range(n):
                nm, p = strz(data, p)
                par, p = strz(data, p)
                p += 60
                self.bone_names.append(nm.lower()); parents.append(par.lower())
            self.bone_parent = [self.bone_names.index(x) if x in self.bone_names else -1 for x in parents]
        if 16 in top:
            off, size = top[16]
            p = off
            for _ in self.bone_names:
                vers = struct.unpack_from('<I', data, p)[0]; p += 4
                _, p = strz(data, p)
                p += 112
                p += 4 + 48 + 4 + 4 + 4 + 4 + 4
                if vers > 0:
                    p += 4
                rx, ry, rz, tx, ty, tz = struct.unpack_from('<6f', data, p); p += 24
                p += 4 + 12
                self.bind_local.append(translated(hpb(-ry, -rx, -rz), (tx, ty, tz)))
            assert p == off + size, (path, p, off + size)
        if 24 in top:
            off, size = top[24]
            n = struct.unpack_from('<I', data, off)[0]; p = off + 4
            for _ in range(n):
                s, p = strz(data, p); self.refs.append(s)
        elif 19 in top:
            off, size = top[19]
            s, _ = strz(data, off)
            self.refs = [x.strip() for x in s.split(',') if x.strip()]
        # bind model transforms
        n = len(self.bone_names)
        self.bind_model = [None] * n
        for b in range(n):
            self._bind(b)
        self.m2b = [inv(M) for M in self.bind_model]
        self.motions = {}

    def _bind(self, b):
        if self.bind_model[b] is None:
            par = self.bone_parent[b]
            P = ident() if par < 0 else self._bind(par)
            self.bind_model[b] = mul(P, self.bind_local[b])
        return self.bind_model[b]

    def _load_mesh(self, data, start, end):
        ch = {cid: (off, size) for cid, off, size in iter_chunks(data, start, end)}
        if 3 not in ch or 4 not in ch:
            return
        off, size = ch[3]
        vtype, cnt = struct.unpack_from('<II', data, off)
        kind = VT.get(vtype)
        p = off + 8
        pos, bones, weights = [], [], []
        if kind == 1:
            for _ in range(cnt):
                v = struct.unpack_from('<14fI', data, p); p += 60
                pos.append(v[0:3]); bones.append((v[14],)); weights.append((1.0,))
        elif kind == 2:
            for _ in range(cnt):
                m0, m1 = struct.unpack_from('<2H', data, p)
                v = struct.unpack_from('<15f', data, p + 4); p += 64
                w = v[12]
                pos.append(v[0:3]); bones.append((m0, m1)); weights.append((1 - w, w))
        elif kind == 3:
            for _ in range(cnt):
                m = struct.unpack_from('<3H', data, p)
                v = struct.unpack_from('<16f', data, p + 6); p += 70
                w0, w1 = v[12], v[13]
                pos.append(v[0:3]); bones.append(m); weights.append((w0, w1, 1 - w0 - w1))
        elif kind == 4:
            for _ in range(cnt):
                m = struct.unpack_from('<4H', data, p)
                v = struct.unpack_from('<17f', data, p + 8); p += 76
                w0, w1, w2 = v[12], v[13], v[14]
                pos.append(v[0:3]); bones.append(m); weights.append((w0, w1, w2, 1 - w0 - w1 - w2))
        else:
            raise ValueError(f'vertex type {vtype:#x} in {self.path}')
        off, size = ch[4]
        icnt = struct.unpack_from('<I', data, off)[0]
        idx = struct.unpack_from(f'<{icnt}H', data, off + 4)
        if 6 in ch:
            o, s = ch[6]
            swcnt = struct.unpack_from('<I', data, o + 16)[0]
            if swcnt:
                ioff, ntris, _ = struct.unpack_from('<IHH', data, o + 20)
                idx = idx[ioff:ioff + ntris * 3]
        tris = [(idx[i], idx[i + 1], idx[i + 2]) for i in range(0, len(idx) - 2, 3)]
        self.meshes.append((pos, bones, weights, tris))

    # -------------------------------------------------------------- motions
    def add_omf(self, path):
        data = open(path, 'rb').read()
        top = {cid: (off, size) for cid, off, size in iter_chunks(data)}
        off, size = top[15]
        p = off
        vers, nparts = struct.unpack_from('<HH', data, p); p += 4
        track_bone = {}
        for _ in range(nparts):
            _, p = strz(data, p)
            nb = struct.unpack_from('<H', data, p)[0]; p += 2
            for _ in range(nb):
                nm, p = strz(data, p)
                midx = struct.unpack_from('<I', data, p)[0]; p += 4
                track_bone[midx] = nm.lower()
        ntracks = len(track_bone)
        off, size = top[14]
        sub = {cid: (o, s) for cid, o, s in iter_chunks(data, off, off + size)}
        cnt = struct.unpack_from('<I', data, sub[0][0])[0]
        for m in range(cnt):
            o, s = sub[m + 1]
            name, p = strz(data, o)
            length = struct.unpack_from('<I', data, p)[0]; p += 4
            tracks = {}
            for t in range(ntracks):
                fl = data[p]; p += 1
                fft = fl & 8
                qsz = 16 if fft else 8
                if fl & 2:
                    rk = (p, 1); p += qsz
                else:
                    p += 4; rk = (p, length); p += length * qsz
                if fl & 1:
                    p += 4
                    if fft:
                        tk = ('f', p, length); p += length * 12; sizeT = None
                        initT = None
                    else:
                        if fl & 4:
                            tk = ('h', p, length); p += length * 6
                        else:
                            tk = ('b', p, length); p += length * 3
                        sizeT = struct.unpack_from('<3f', data, p); p += 12
                        initT = struct.unpack_from('<3f', data, p); p += 12
                else:
                    tk = None; sizeT = None
                    initT = struct.unpack_from('<3f', data, p); p += 12
                tracks[track_bone[t]] = (fl, rk, tk, sizeT, initT)
            self.motions[name.lower()] = (data, length, tracks)

    def motion_len(self, name):
        return self.motions[name.lower()][1]

    def pose(self, motion, frame, lock_root=False):
        """model-space bone matrices for motion at (float) frame.
        lock_root: IX-Ray forces hud item root bone transform to identity (player_hud.cpp)"""
        local = []
        if motion is None:
            local = list(self.bind_local)
        else:
            data, length, tracks = self.motions[motion.lower()]
            f0 = int(math.floor(frame)) % length
            f1 = (f0 + 1) % length
            d = frame - math.floor(frame)
            for b, nm in enumerate(self.bone_names):
                tr = tracks.get(nm)
                if tr is None:
                    local.append(self.bind_local[b]); continue
                fl, rk, tk, sizeT, initT = tr
                fft = fl & 8
                def q_at(i):
                    p0, n = rk
                    i = 0 if n == 1 else i
                    if fft:
                        return struct.unpack_from('<4f', data, p0 + i * 16)
                    v = struct.unpack_from('<4h', data, p0 + i * 8)
                    return tuple(x / 32767.0 for x in v)
                q = slerp(q_at(f0), q_at(f1), d) if rk[1] > 1 else q_at(0)
                if tk is None:
                    t = initT
                else:
                    kind, p0, n = tk
                    def t_at(i):
                        if kind == 'f':
                            return struct.unpack_from('<3f', data, p0 + i * 12)
                        if kind == 'h':
                            v = struct.unpack_from('<3h', data, p0 + i * 6)
                        else:
                            v = struct.unpack_from('<3b', data, p0 + i * 3)
                        return tuple(v[k] * sizeT[k] + initT[k] for k in range(3))
                    a, bb = t_at(f0), t_at(f1)
                    t = tuple(a[k] + (bb[k] - a[k]) * d for k in range(3))
                local.append(quat_xform(q, t))
        model = [None] * len(self.bone_names)
        if lock_root:
            for b, par in enumerate(self.bone_parent):
                if par < 0:
                    model[b] = ident()

        def calc(b):
            if model[b] is None:
                par = self.bone_parent[b]
                model[b] = local[b] if par < 0 else mul(calc(par), local[b])
            return model[b]
        for b in range(len(model)):
            calc(b)
        return model

    def skin(self, model_pose, world):
        """returns list of meshes: (verts(list of xyz), tris)"""
        R = [mul(world, mul(model_pose[b], self.m2b[b])) for b in range(len(model_pose))]
        out = []
        for pos, bones, weights, tris in self.meshes:
            vs = []
            for P, bs, ws in zip(pos, bones, weights):
                if len(bs) == 1:
                    vs.append(xf(R[bs[0]], P))
                else:
                    x = y = z = 0.0
                    for bi, w in zip(bs, ws):
                        if w == 0:
                            continue
                        a = xf(R[bi], P)
                        x += a[0] * w; y += a[1] * w; z += a[2] * w
                    vs.append((x, y, z))
            out.append((vs, tris))
        return out


_cache = {}


def load_model(rel):
    rel = rel.lower().replace('/', '\\')
    if not rel.endswith('.ogf'):
        rel += '.ogf'
    if rel not in _cache:
        p = find_mesh(rel)
        if p is None:
            raise FileNotFoundError(rel)
        _cache[rel] = Model(p)
    return _cache[rel]


def load_hands_with(hands_rel, weapon_dir_rel):
    """hands model + all hand omfs found in the weapon folder (FWR first)"""
    H = load_model(hands_rel)
    key = ('hands_omf', weapon_dir_rel)
    if key not in _cache:
        found = False
        for d in RESDIRS:
            folder = os.path.join(d, weapon_dir_rel)
            if os.path.isdir(folder):
                for f in os.listdir(folder):
                    if f.endswith('.omf') and ('_hand_' in f or f.startswith('wpn_hand') or f.startswith('dev_hand')):
                        H.add_omf(os.path.join(folder, f)); found = True
                if found:
                    break
        _cache[key] = True
    return H


def load_item_motions(M):
    if getattr(M, '_omf_loaded', False):
        return M
    for r in M.refs:
        p = find_mesh(r + '.omf')
        if p:
            M.add_omf(p)
    M._omf_loaded = True
    return M


# ------------------------------------------------------------------ raster


class Image:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.px = bytearray(w * h * 3)
        self.z = [1e9] * (w * h)
        for y in range(h):
            t = y / h
            if t < 0.55:
                c = (int(150 + 60 * t), int(165 + 50 * t), int(190 + 30 * t))
            else:
                c = (int(120 - 40 * (t - .55)), int(98 - 30 * (t - .55)), int(70 - 20 * (t - .55)))
            row = bytes(c) * w
            self.px[y * w * 3:(y + 1) * w * 3] = row

    def save_png(self, path):
        raw = b''.join(b'\0' + bytes(self.px[y * self.w * 3:(y + 1) * self.w * 3]) for y in range(self.h))
        def chunk(t, d):
            return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
        png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', self.w, self.h, 8, 2, 0, 0, 0)) + \
            chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b'')
        open(path, 'wb').write(png)

    def blit(self, other, ox, oy):
        for y in range(other.h):
            s = y * other.w * 3
            d = ((oy + y) * self.w + ox) * 3
            self.px[d:d + other.w * 3] = other.px[s:s + other.w * 3]

    def rect(self, x0, y0, x1, y1, col):
        for x in range(max(0, x0), min(self.w, x1)):
            for y in (y0, y1 - 1):
                if 0 <= y < self.h:
                    i = (y * self.w + x) * 3; self.px[i:i + 3] = bytes(col)
        for y in range(max(0, y0), min(self.h, y1)):
            for x in (x0, x1 - 1):
                if 0 <= x < self.w:
                    i = (y * self.w + x) * 3; self.px[i:i + 3] = bytes(col)

    def cross(self):
        cx, cy = self.w // 2, self.h // 2
        for d in range(-6, 7):
            for (x, y) in ((cx + d, cy), (cx, cy + d)):
                i = (y * self.w + x) * 3; self.px[i:i + 3] = b'\xff\x30\x30'


def render(img, meshes_colored, fov_deg, near=0.01):
    W, H = img.w, img.h
    asp = H / W
    cot = 1.0 / math.tan(math.radians(fov_deg) / 2)
    sx, sy = asp * cot * W / 2, cot * H / 2
    L = (0.35, 0.55, -0.75)
    ln = math.sqrt(sum(x * x for x in L)); L = tuple(x / ln for x in L)
    px, zb = img.px, img.z
    stats = {'minz': 1e9, 'bbox': [W, H, 0, 0], 'pix': 0}
    for verts, tris, col, tag in meshes_colored:
        proj = []
        for (x, y, z) in verts:
            if z <= near:
                proj.append(None)
            else:
                proj.append((W / 2 + x * sx / z, H / 2 - y * sy / z, z))
        for a, b, c in tris:
            pa, pb, pc = proj[a], proj[b], proj[c]
            if pa is None or pb is None or pc is None:
                continue
            va, vb, vc = verts[a], verts[b], verts[c]
            ux, uy, uz = vb[0] - va[0], vb[1] - va[1], vb[2] - va[2]
            wx, wy, wz = vc[0] - va[0], vc[1] - va[1], vc[2] - va[2]
            nx, ny, nz = uy * wz - uz * wy, uz * wx - ux * wz, ux * wy - uy * wx
            nl = math.sqrt(nx * nx + ny * ny + nz * nz) or 1
            shade = 0.3 + 0.7 * abs(nx * L[0] + ny * L[1] + nz * L[2]) / nl
            cr = bytes((min(255, int(col[0] * shade)), min(255, int(col[1] * shade)), min(255, int(col[2] * shade))))
            x0 = int(max(0, math.floor(min(pa[0], pb[0], pc[0]))))
            x1 = int(min(W - 1, math.ceil(max(pa[0], pb[0], pc[0]))))
            y0 = int(max(0, math.floor(min(pa[1], pb[1], pc[1]))))
            y1 = int(min(H - 1, math.ceil(max(pa[1], pb[1], pc[1]))))
            if x0 > x1 or y0 > y1:
                continue
            det = (pb[0] - pa[0]) * (pc[1] - pa[1]) - (pc[0] - pa[0]) * (pb[1] - pa[1])
            if abs(det) < 1e-9:
                continue
            iza, izb, izc = 1 / pa[2], 1 / pb[2], 1 / pc[2]
            for y in range(y0, y1 + 1):
                fy = y + 0.5
                # find span via barycentrics
                xs = []
                for (p, q) in ((pa, pb), (pb, pc), (pc, pa)):
                    if (p[1] <= fy < q[1]) or (q[1] <= fy < p[1]):
                        xs.append(p[0] + (fy - p[1]) * (q[0] - p[0]) / (q[1] - p[1]))
                if len(xs) < 2:
                    continue
                xl = max(x0, int(math.ceil(min(xs) - 0.5)))
                xr = min(x1, int(math.floor(max(xs) - 0.5)))
                for x in range(xl, xr + 1):
                    fx = x + 0.5
                    l1 = ((pc[0] - fx) * (pa[1] - fy) - (pa[0] - fx) * (pc[1] - fy)) / det
                    l2 = ((pa[0] - fx) * (pb[1] - fy) - (pb[0] - fx) * (pa[1] - fy)) / det
                    l0 = 1 - l1 - l2
                    iz = l0 * iza + l1 * izb + l2 * izc
                    z = 1 / iz if iz > 0 else 1e9
                    k = y * W + x
                    if z < zb[k]:
                        zb[k] = z
                        px[k * 3:k * 3 + 3] = cr
        if tag == 'item':
            used = {i for t in tris for i in t}
            for i in used:
                v, pp = verts[i], proj[i]
                if v[2] < stats['minz']:
                    stats['minz'] = v[2]
                if pp:
                    bb = stats['bbox']
                    bb[0] = min(bb[0], pp[0]); bb[1] = min(bb[1], pp[1]); bb[2] = max(bb[2], pp[0]); bb[3] = max(bb[3], pp[1])
    return stats
