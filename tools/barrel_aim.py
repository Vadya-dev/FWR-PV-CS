"""Barrel-on-crosshair idle: rotate each idle pose about the weapon origin so the fire direction
(item +Z = get_LastFD) is parallel to the camera axis -> the barrel's vanishing point is the crosshair,
where the actor's shots go. Aim (and GL aim) poses are kept identical by recomputing their offsets.
usage: barrel_aim.py <out.json> sect [sect ...]"""
import json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hudview as hv
import scene, tune, retune


def bore(W):
    k = (W[0][2], W[1][2], W[2][2])
    return (math.degrees(math.atan2(k[0], k[2])), math.degrees(math.atan2(k[1], math.hypot(k[0], k[2]))))


def rot_to_z(k):
    """minimal rotation matrix (4x4) mapping unit vector k onto +Z"""
    z = (0.0, 0.0, 1.0)
    ax = (k[1] * z[2] - k[2] * z[1], k[2] * z[0] - k[0] * z[2], k[0] * z[1] - k[1] * z[0])
    s = math.sqrt(sum(a * a for a in ax)); c = sum(a * b for a, b in zip(k, z))
    if s < 1e-9:
        return hv.ident()
    x, y, w = (a / s for a in ax)
    C = 1 - c
    R = [[c + x * x * C, x * y * C - w * s, x * w * C + y * s, 0],
         [y * x * C + w * s, c + y * y * C, y * w * C - x * s, 0],
         [w * x * C - y * s, w * y * C + x * s, c + w * w * C, 0],
         [0, 0, 0, 1.0]]
    return R


def fmt(v, n=6):
    return ','.join(('%.*f' % (n, x)).rstrip('0').rstrip('.') if abs(x) > 1e-9 else '0' for x in v)


def solve(sect):
    h = scene.Hud(sect)
    att, A, la, li, I, Wa, Wi = tune.mats(h)
    k = (Wi[0][2], Wi[1][2], Wi[2][2])
    p = (Wi[0][3], Wi[1][3], Wi[2][3])
    R = rot_to_z(k)
    Rp = hv.xf(R, p)
    M = hv.translated(R, tuple(p[i] - Rp[i] for i in range(3)))
    att2 = hv.mul(M, att)
    pos = (att2[0][3], att2[1][3], att2[2][3])
    hpb = tuple(math.degrees(x) for x in tune.get_hpb(att2))
    aim2 = hv.mul(A, hv.inv(att2))
    off, rot = hv.decompose_aim(aim2)
    ov = {}
    for suf in ('', '_16x9'):
        ov['hands_position' + suf] = fmt(pos)
        ov['hands_orientation' + suf] = fmt(hpb, 4)
        ov['aim_hud_offset_pos' + suf] = fmt(off)
        ov['aim_hud_offset_rot' + suf] = fmt(rot)
    if h.g('gl_hud_offset_pos') is not None or h.g('gl_hud_offset_rot') is not None:
        g = scene.vec(h.g('gl_hud_offset_pos')); gr = scene.vec(h.g('gl_hud_offset_rot'))
        if any(abs(x) > 1e-9 for x in g + gr):
            Agl = hv.mul(h.aim('gl'), att)
            gl2 = hv.mul(Agl, hv.inv(att2))
            goff, grot = hv.decompose_aim(gl2)
            for suf in ('', '_16x9'):
                ov['gl_hud_offset_pos' + suf] = fmt(goff)
                ov['gl_hud_offset_rot' + suf] = fmt(grot)
    # verify
    h2 = scene.Hud(sect, ov)
    att_, A_, la_, li_, I_, Wa2, Wi2 = tune.mats(h2)
    aim_err = max(abs(Wa2[r][c] - Wa[r][c]) for r in range(3) for c in range(4))
    gl_err = 0.0
    if 'gl_hud_offset_pos' in ov:
        G1 = hv.mul(hv.mul(hv.mul(h.aim('gl'), att), la), I)
        G2 = hv.mul(hv.mul(hv.mul(h2.aim('gl'), h2.attach()), la_), I_)
        gl_err = max(abs(G2[r][c] - G1[r][c]) for r in range(3) for c in range(4))
    m_old = retune.metrics(h)[1]
    m_new = retune.metrics(h2)[1]
    walk_old = retune.metrics(scene.Hud(sect, retune.moved(h, None, (retune.FWD, retune.LEFT))))[1]
    walk_new = retune.metrics(scene.Hud(sect, retune.moved(h2, ov, (retune.FWD, retune.LEFT))))[1]
    info = dict(bore_old=[round(x, 2) for x in bore(Wi)], bore_new=[round(x, 3) for x in bore(Wi2)],
                aim_err=aim_err, gl_err=gl_err, idle_old=m_old, idle_new=m_new, walk_old=walk_old, walk_new=walk_new,
                rot_deg=round(math.degrees(math.acos(max(-1, min(1, k[2])))), 2))
    return ov, info


if __name__ == '__main__':
    out = sys.argv[1]
    res = {}
    for s in sys.argv[2:]:
        ov, info = solve(s)
        res[s] = {'ov': ov, 'info': info}
        print(s, info, flush=True)
    json.dump(res, open(out, 'w'), indent=1)
