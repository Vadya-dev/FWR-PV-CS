"""Pose analysis / synthesis for HUD configs.
W_aim  = A . lead_aim . I        (A = Aim . Attach)
W_idle = Attach . lead_idle . I
Idle style L:  W_idle = L . W_aim   ->  Attach = L . A . lead_aim . inv(lead_idle)
"""
import math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import hudview as hv
import scene

KEYS_AIM = ('anm_idle_aim', 'anm_idle')


def lead(h, key, frame=0):
    hands, item = h.models()
    hb, _ = h.anim(key)
    if hb is None and key == 'anm_idle_aim':
        hb, _ = h.anim('anm_idle')
    hm = scene.pick(hands.motions, hb)
    p = hands.pose(hm, frame if hm else 0)
    return p[hands.bone_names.index('lead_gun')]


def mats(h):
    att = h.attach()
    A = hv.mul(h.aim(), att)
    I = h.item_attach()
    la, li = lead(h, 'anm_idle_aim'), lead(h, 'anm_idle')
    W_aim = hv.mul(hv.mul(A, la), I)
    W_idle = hv.mul(hv.mul(att, li), I)
    return att, A, la, li, I, W_aim, W_idle


def get_hpb(M):
    i = (M[0][0], M[1][0], M[2][0]); j = (M[0][1], M[1][1], M[2][1]); k = (M[0][2], M[1][2], M[2][2])
    cy = math.sqrt(j[1] ** 2 + i[1] ** 2)
    if cy > 1e-6:
        return -math.atan2(k[0], k[2]), -math.atan2(-k[1], cy), -math.atan2(i[1], j[1])
    return -math.atan2(-i[2], i[0]), -math.atan2(-k[1], cy), 0.0


def L_from(W_idle, W_aim, pivot):
    L = hv.mul(W_idle, hv.inv(W_aim))
    # express as T(pivot+d) R T(-pivot)
    R = [row[:] for row in L]; R[0][3] = R[1][3] = R[2][3] = 0
    pr = hv.xf(R, pivot)
    d = tuple(L[r][3] + pr[r] - pivot[r] for r in range(3))
    h_, p_, b_ = get_hpb(R)
    return d, (math.degrees(h_), math.degrees(p_), math.degrees(b_))


def L_make(d, hpb_deg, pivot):
    R = hv.hpb(*[math.radians(x) for x in hpb_deg])
    pr = hv.xf(R, pivot)
    return hv.translated(R, tuple(pivot[r] + d[r] - pr[r] for r in range(3)))


def rear_sight(h, W_aim=None):
    """distance to the nearest weapon geometry on the sight axis in the aimed pose"""
    meshes, _ = scene.build(h, 'aim', 0)
    best = 1e9; front = 0
    for v, t, c, tag in meshes:
        if tag != 'item':
            continue
        used = {i for tt in t for i in tt}
        for i in used:
            x, y, z = v[i]
            if abs(x) < 0.012 and -0.03 < y < 0.006 and z > 0.02:
                best = min(best, z); front = max(front, z)
    return best, front


def fmt(v, n=6):
    return ','.join(f'{x:.{n}f}'.rstrip('0').rstrip('.') if abs(x) > 1e-9 else '0' for x in v)


def synth(h, A, L, A_gl=None):
    """config overrides for target aimed pose A and idle style matrix L"""
    _, _, la, li, I, _, _ = mats(h)
    att = hv.mul(hv.mul(hv.mul(L, A), la), hv.inv(li))
    hpos = (att[0][3], att[1][3], att[2][3])
    hrot = tuple(math.degrees(x) for x in get_hpb(att))
    aim = hv.mul(A, hv.inv(att))
    off, rot = hv.decompose_aim(aim)
    out = {}
    for suf in ('', '_16x9'):
        out['hands_position' + suf] = fmt(hpos)
        out['hands_orientation' + suf] = fmt(hrot, 4)
        out['aim_hud_offset_pos' + suf] = fmt(off)
        out['aim_hud_offset_rot' + suf] = fmt(rot)
    if A_gl is not None:
        g = hv.mul(A_gl, hv.inv(att))
        goff, grot = hv.decompose_aim(g)
        for suf in ('', '_16x9'):
            out['gl_hud_offset_pos' + suf] = fmt(goff)
            out['gl_hud_offset_rot' + suf] = fmt(grot)
    return out


def close_metrics(h, keys=('anm_reload', 'anm_reload_empty', 'anm_add_cartridge', 'anm_show', 'anm_idle_sprint'), step=3, W=192, H=108):
    """worst-case: nearest item point in front of camera inside view, and max screen coverage of the item"""
    hands, item = h.models()
    worst = {'minz': 1e9, 'cover': 0.0, 'key': None, 'frame': 0}
    for key in keys:
        hb, _ = h.anim(key)
        hm = scene.pick(hands.motions, hb)
        if hm is None:
            continue
        for f in range(0, hands.motion_len(hm), step):
            meshes, _ = scene.build(h, 'reload', f, key)
            img = hv.Image(W, H)
            items = [m for m in meshes if m[3] == 'item']
            hv.render(img, items, scene.HUD_FOV)
            zs = [z for z in img.z if z < 1e8]
            cover = len(zs) / (W * H)
            mz = min(zs) if zs else 1e9
            if mz < worst['minz'] or cover > worst['cover']:
                worst['minz'] = min(worst['minz'], mz)
                if cover > worst['cover']:
                    worst['cover'] = cover; worst['key'] = key; worst['frame'] = f
    return worst
