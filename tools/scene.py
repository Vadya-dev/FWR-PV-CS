"""HUD scene from weapon configs (FWR addon + DLTX overrides)."""
import math, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
import hudview as hv
from ltxdiff import parse

ADDON = hv.ADDON
PV_MOD = os.environ.get('PV_MOD') or os.path.join(hv.REPO, 'ixr_addons', 'fwr_position_view', 'configs',
                                                   'mod_system_fwr_position_view.ltx')
HANDS = r'dynamics\weapons\wpn_hand\wpn_hand_01'
HUD_FOV = 55.0

_secs = None


def all_sections():
    global _secs
    if _secs is None:
        _secs = {}
        for sub in ('weapons', 'misc'):
            d = os.path.join(ADDON, 'configs', sub)
            for f in os.listdir(d):
                if f.endswith('.ltx'):
                    s, _ = parse(os.path.join(d, f))
                    for k, v in s.items():
                        if not k.startswith('__'):
                            v['__fname__'] = f
                            _secs[k] = v
    return _secs


def read_mod(path):
    out, cur = {}, None
    if not os.path.isfile(path):
        return out
    for line in open(path, 'rb').read().decode('cp1251', 'replace').splitlines():
        t = line.split(';', 1)[0].strip()
        if not t:
            continue
        m = re.match(r'^!\[([^\]]+)\]', t)
        if m:
            cur = out.setdefault(m.group(1).strip().lower(), {}); continue
        if cur is not None and '=' in t:
            k, v = t.split('=', 1); cur[k.strip().lower()] = v.strip()
    return out


def vec(s, default=(0.0, 0.0, 0.0)):
    if s is None:
        return tuple(default)
    return tuple(float(x.strip().rstrip('f')) for x in s.split(',')[:3])


class Hud:
    def __init__(self, sect, overrides=None, use_pv=True):
        self.sect = sect
        base = dict(all_sections()[sect])
        if use_pv:
            base.update(read_mod(PV_MOD).get(sect, {}))
        if overrides:
            base.update(overrides)
        self.cfg = base

    def g(self, key, ws=True):
        if ws and (key + '_16x9') in self.cfg:
            return self.cfg[key + '_16x9']
        return self.cfg.get(key)

    def attach(self):
        return hv.attach_matrix(vec(self.g('hands_position')), vec(self.g('hands_orientation')))

    def aim(self, kind='aim'):
        pre = 'aim_hud_offset' if kind == 'aim' else 'gl_hud_offset'
        return hv.aim_matrix(vec(self.g(pre + '_pos')), vec(self.g(pre + '_rot')))

    def item_attach(self):
        return hv.attach_matrix(vec(self.cfg.get('item_position')), vec(self.cfg.get('item_orientation')))

    def anim(self, key):
        v = self.cfg.get(key)
        for suf in ('_2', '_1', '_0'):
            if v:
                break
            v = self.cfg.get(key + suf)
        if not v:
            return None, None
        parts = [p.strip() for p in v.split(',')]
        base = parts[0]
        add = parts[1] if len(parts) > 1 and parts[1] else base
        return base, add

    def models(self):
        vis = self.cfg['item_visual'].strip()
        item = hv.load_item_motions(hv.load_model(vis))
        folder = os.path.dirname(vis.replace('/', '\\'))
        hands = hv.load_hands_with(HANDS, folder)
        return hands, item


def weapon_section(hud_sect):
    for name, d in all_sections().items():
        if d.get('hud', '').strip().lower() == hud_sect and not name.endswith('_hud'):
            return d
    return {}


def hidden_bones(h, item):
    w = weapon_section(h.sect)
    hide = set()
    for key, bone in (('scope_status', 'wpn_scope'), ('silencer_status', 'wpn_silencer'), ('grenade_launcher_status', 'wpn_launcher')):
        st = (w.get(key) or '0').strip()
        if st != '1' and bone in item.bone_names:
            hide.add(item.bone_names.index(bone))
    changed = True
    while changed:
        changed = False
        for b, par in enumerate(item.bone_parent):
            if par in hide and b not in hide:
                hide.add(b); changed = True
    return hide


def filter_tris(item, skinned, hide):
    if not hide:
        return skinned
    out = []
    for (verts, tris), (pos, bones, weights, _) in zip(skinned, item.meshes):
        bad = [any(b in hide and w > 0 for b, w in zip(bs, ws)) for bs, ws in zip(bones, weights)]
        out.append((verts, [t for t in tris if not (bad[t[0]] or bad[t[1]] or bad[t[2]])]))
    return out


def pick(motions, name):
    if name is None:
        return None
    n = name.lower()
    if n in motions:
        return n
    for i in range(1, 9):
        if f'{n}{i}' in motions:
            return f'{n}{i}'
    return None


def build(h, state='idle', frame=0.0, anim_key=None):
    hands, item = h.models()
    key = anim_key or {'idle': 'anm_idle', 'aim': 'anm_idle_aim', 'reload': 'anm_reload', 'show': 'anm_show',
                       'sprint': 'anm_idle_sprint'}[state]
    hb, ib = h.anim(key)
    if hb is None and state == 'aim':
        hb, ib = h.anim('anm_idle')
    hm = pick(hands.motions, hb)
    im = pick(item.motions, ib) or pick(item.motions, hb)
    trans = h.aim() if state == 'aim' else hv.ident()
    hands_w = hv.mul(trans, h.attach())
    hp = hands.pose(hm, frame if hm else 0)
    lead = hands.bone_names.index('lead_gun')
    item_w = hv.mul(hv.mul(hands_w, hp[lead]), h.item_attach())
    ip = item.pose(im, frame if im else 0, lock_root=True)
    meshes = [(v, t, (205, 160, 125), 'hands') for v, t in hands.skin(hp, hands_w)]
    meshes += [(v, t, (125, 135, 160), 'item') for v, t in filter_tris(item, item.skin(ip, item_w), hidden_bones(h, item))]
    info = {'hands_motion': hm, 'item_motion': im, 'len': hands.motion_len(hm) if hm else 1, 'item_w': item_w}
    return meshes, info


def snapshot(h, state, frame=0.0, w=384, hgt=216, anim_key=None):
    meshes, info = build(h, state, frame, anim_key)
    img = hv.Image(w, hgt)
    st = hv.render(img, meshes, HUD_FOV)
    img.cross()
    return img, st, info


def closest_frame(h, anim_key='anm_reload', step=2):
    hands, item = h.models()
    hb, ib = h.anim(anim_key)
    hm = pick(hands.motions, hb)
    if hm is None:
        return 0, 1e9
    best = (0, 1e9)
    for f in range(0, hands.motion_len(hm), step):
        meshes, _ = build(h, 'reload', f, anim_key)
        mz = min(v[2] for m in meshes if m[3] == 'item' for v in m[0])
        if mz < best[1]:
            best = (f, mz)
    return best


def sheet(cells, cols, w=384, hgt=216, path=None):
    rows = (len(cells) + cols - 1) // cols
    out = hv.Image(w * cols, hgt * rows)
    for i, img in enumerate(cells):
        out.blit(img, (i % cols) * w, (i // cols) * hgt)
        out.rect((i % cols) * w, (i // cols) * hgt, (i % cols + 1) * w, (i // cols + 1) * hgt, (20, 20, 20))
    if path:
        out.save_png(path)
    return out
