"""Shift the idle HUD pose in camera space while keeping aim (and GL aim) poses identical.
usage: retune.py <png_out> <sect>[:scope] dx dy dz [--json out.json]
hands_position' = hands_position + D ; aim_pos' = aim_pos - Ra*D (same for gl) -> aimed pose unchanged.
Prints idle metrics for still / walk fwd+left (IX-Ray hud_base movement offsets) and the worst reload frame."""
import json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hudview as hv
import scene, tune

W, H = 480, 270
FWD = ((0, -0.005, -0.035), (0, 0, 0))
LEFT = ((-0.03, -0.018, 0), (0, 0, -3.5))
RIGHT = ((0.03, -0.005, 0), (0, 0, 5))


def force_scope():
    orig = scene.hidden_bones
    def hb(h, item, _o=orig):
        hide = _o(h, item)
        keep = {i for i, n in enumerate(item.bone_names) if n == 'wpn_scope'}
        ch = True
        while ch:
            ch = False
            for b, p in enumerate(item.bone_parent):
                if p in keep and b not in keep:
                    keep.add(b); ch = True
        return hide - keep
    scene.hidden_bones = hb


def fmt(v):
    return ','.join(('%.6f' % x).rstrip('0').rstrip('.') if abs(x) > 1e-9 else '0' for x in v)


def shifted(h, D):
    pos = scene.vec(h.g('hands_position'))
    out = {}
    newpos = tuple(pos[i] + D[i] for i in range(3))
    for suf in ('', '_16x9'):
        out['hands_position' + suf] = fmt(newpos)
    has_gl = (scene.weapon_section(h.sect).get('grenade_launcher_status') or '0').strip() != '0'
    for pre in ('aim_hud_offset', 'gl_hud_offset'):
        if h.g(pre + '_pos') is None and h.g(pre + '_rot') is None:
            continue
        if pre == 'gl_hud_offset' and not has_gl:
            continue
        off = scene.vec(h.g(pre + '_pos')); rot = scene.vec(h.g(pre + '_rot'))
        A = hv.aim_matrix((0, 0, 0), rot)
        RD = hv.xf(A, D)
        new = tuple(off[i] - RD[i] for i in range(3))
        for suf in ('', '_16x9'):
            out[pre + '_pos' + suf] = fmt(new)
    return out


def moved(h, ov, mv):
    pos = scene.vec((ov or {}).get('hands_position') or h.g('hands_position'))
    rot = scene.vec(h.g('hands_orientation'))
    o = dict(ov or {})
    p2 = pos; r2 = rot
    for (dp, dr) in mv:
        p2 = tuple(p2[i] + dp[i] for i in range(3)); r2 = tuple(r2[i] + dr[i] for i in range(3))
    for suf in ('', '_16x9'):
        o['hands_position' + suf] = fmt(p2); o['hands_orientation' + suf] = fmt(r2)
    return o


def metrics(h, state='idle', frame=0, key=None):
    meshes, _ = scene.build(h, state, frame, key)
    img = hv.Image(W, H)
    hv.render(img, meshes, scene.HUD_FOV)
    it = hv.Image(W, H)
    hv.render(it, [m for m in meshes if m[3] == 'item'], scene.HUD_FOV)
    cx, cy = W / 2, H / 2
    pix = [(k % W, k // W, z) for k, z in enumerate(it.z) if z < 1e8]
    cover = len(pix) / (W * H)
    dmin = min((math.hypot(x + .5 - cx, y + .5 - cy) for x, y, z in pix), default=1e9) / H  # in screen heights
    zmin = min((z for x, y, z in pix), default=0)
    central = sum(1 for x, y, z in pix if math.hypot(x + .5 - cx, y + .5 - cy) < 0.25 * H) / (math.pi * (0.25 * H) ** 2)
    img.cross()
    return img, dict(cover=round(cover, 3), d_center=round(dmin, 3), z_near=round(zmin, 3), central=round(central, 3))


if __name__ == '__main__':
    out = sys.argv[1]
    sect, _, flag = sys.argv[2].partition(':')
    D = tuple(float(x) for x in sys.argv[3:6])
    if flag == 'scope':
        force_scope()
    h0 = scene.Hud(sect)
    ov = shifted(h0, D)
    h = scene.Hud(sect, ov)
    cells = []
    res = {}
    for name, mv in (('idle', ()), ('fwd+left', (FWD, LEFT)), ('fwd+right', (FWD, RIGHT))):
        hh = scene.Hud(sect, moved(h0, ov, mv)) if mv else h
        img, m = metrics(hh)
        cells.append(img); res[name] = m
    img, m = metrics(h, 'aim'); cells.append(img); res['aim'] = m
    cm = tune.close_metrics(h, step=4) if '--fast' not in sys.argv else {'key': None}
    if cm['key']:
        img, m = metrics(h, 'reload', cm['frame'], cm['key']); cells.append(img)
        res['reload_worst'] = dict(m, key=cm['key'], frame=cm['frame'], minz_all=round(cm['minz'], 3), cover_max=round(cm['cover'], 3))
    scene.sheet(cells, 3, W, H, out)
    print(sect, 'D=', D)
    for k, v in res.items():
        print(f'  {k:12s} {v}')
    for k, v in ov.items():
        if not k.endswith('_16x9'):
            print(f'  {k} = {v}')
    if '--json' in sys.argv:
        json.dump(ov, open(sys.argv[sys.argv.index('--json') + 1], 'w'), indent=1)
