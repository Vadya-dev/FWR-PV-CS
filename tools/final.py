"""Compute new HUD poses for all weapons -> overrides json.
Style (hud_fov 55, 16:9):
  aim   : sight line kept on the camera axis; weapon rolled upright (P&V aimed with 2-3 deg cant);
          excluded weapons brought to P&V eye relief.
  idle  : canonical offset from the aimed pose (right/down, slight inward cant & yaw),
          rear of the weapon ~11 cm from the eye for long guns;
          pistols: as close as possible while reload/draw stays <= 12% screen and >= 13 cm.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import scene, design, tune

RIFLE_STYLE = dict(d=(0.068, -0.036), hpb=(2.0, -1.0, -6.0))
PISTOL_STYLE = dict(d=(0.05, -0.05), hpb=(3.0, -3.0, -8.0))
IDLE_REAR = 0.11

# sect: (class, aim rear target or None (keep), use P&V base)
TABLE = {
    'wpn_ak74_hud': ('rifle', None, True), 'wpn_lr300_hud': ('rifle', None, True),
    'wpn_groza_hud': ('rifle', None, True), 'wpn_val_hud': ('rifle', None, True),
    'wpn_pkm_hud': ('rifle', None, True), 'wpn_sig550_hud': ('rifle', None, True),
    'wpn_bm16_hud': ('rifle', None, True), 'wpn_toz34_hud': ('rifle', None, True),
    'wpn_spas12_hud': ('rifle', None, True), 'wpn_winchester1300_hud': ('rifle', None, True),
    'wpn_abakan_hud': ('rifle', 0.16, False), 'wpn_ak74u_hud': ('rifle', 0.15, False),
    'wpn_mp5_hud': ('rifle', 0.14, False),
    'wpn_svd_hud': ('scoped', None, True), 'wpn_svu_hud': ('scoped', None, True),
    'wpn_vintorez_hud': ('scoped', None, True), 'wpn_gauss_hud': ('scoped', None, True),
    'wpn_l85_hud': ('scoped', None, True), 'wpn_g36_hud': ('scoped', None, True),
    'wpn_fn2000_hud': ('scoped', None, False),
    'wpn_beretta_hud': ('pistol', None, True), 'wpn_colt1911_hud': ('pistol', None, True),
    'wpn_desert_eagle_hud': ('pistol', None, True), 'wpn_fort_hud': ('pistol', None, True),
    'wpn_hpsa_hud': ('pistol', None, True), 'wpn_pb_hud': ('pistol', None, True),
    'wpn_pm_hud': ('pistol', None, True), 'wpn_sig220_hud': ('pistol', None, True),
    'wpn_usp_hud': ('pistol', None, True), 'wpn_walther_hud': ('pistol', None, True),
    'wpn_rpg7_hud': ('launcher', None, False), 'wpn_rg-6_hud': ('launcher', None, False),
}
# per-weapon idle overrides (d relative to the aimed pose, pivot at the rear sight)
SPECIAL = {
    # RG-6: sight looks 23 deg up relative to the barrels -> level the barrels in idle (FWR CS framing)
    'wpn_rg-6_hud': dict(d=(0.10, -0.03, 0.12), hpb=(2.0, -23.0, -6.0)),
    # FN2000: bullpup with integrated optic, rear sight not detectable -> FWR CS-like framing
    'wpn_fn2000_hud': dict(d=(0.10, 0.0, 0.19), hpb=(4.0, 0.0, -6.0)),
}
FIXED_DZ = {'wpn_l85_hud': 0.06}  # huge reload animation: accept P&V-like reload size instead of a far idle
COVER_MAX = {'pistol': 0.12, 'rifle': 0.28, 'scoped': 0.30, 'launcher': 0.30}
MINZ_MIN = {'pistol': 0.13, 'rifle': 0.06, 'scoped': 0.05, 'launcher': 0.08}


def make(sect, cls, rear_t, use_pv, dz_idle):
    h = scene.Hud(sect, use_pv=use_pv)
    _, rear = design.target_aim(h, rear_t, None if rear_t else 0.0, True)
    rear = rear if rear else 0.2
    st = PISTOL_STYLE if cls == 'pistol' else RIFLE_STYLE
    if sect in SPECIAL:
        sp = SPECIAL[sect]
        return design.design(sect, rear_target=rear_t, dz=None if rear_t else 0.0,
                             d=(sp['d'][0], sp['d'][1], sp['d'][2] + dz_idle), hpb=sp['hpb'],
                             use_pv=use_pv, pivot_z=rear), rear
    if cls in ('pistol', 'launcher'):
        d = (st['d'][0], st['d'][1], dz_idle)
    else:
        d = (st['d'][0], st['d'][1], IDLE_REAR - rear + dz_idle)
    return design.design(sect, rear_target=rear_t, dz=None if rear_t else 0.0, d=d, hpb=st['hpb'],
                         use_pv=use_pv, pivot_z=rear), rear


def solve(sect, only=None):
    cls, rear_t, use_pv = TABLE[sect]
    start = -0.08 if cls == 'pistol' else 0.0
    dz = FIXED_DZ.get(sect, start)
    for it in range(10):
        ov, rear = make(sect, cls, rear_t, use_pv, dz)
        h = scene.Hud(sect, ov, use_pv=use_pv)
        cm = tune.close_metrics(h, step=4)
        ok = cm['cover'] <= COVER_MAX[cls] and cm['minz'] >= MINZ_MIN[cls]
        print(f'  {sect} dz={dz:+.2f} cover={cm["cover"]:.3f} minz={cm["minz"]:.3f} ({cm["key"]}@{cm["frame"]}) {"OK" if ok else ""}', flush=True)
        if ok or dz >= 0.12 or sect in FIXED_DZ:
            return ov, dict(cls=cls, rear=rear, dz=dz, cover=cm['cover'], minz=cm['minz'], base='pv' if use_pv else 'cs')
        dz += 0.02


if __name__ == '__main__':
    out = sys.argv[1]
    only = sys.argv[2:]
    res = json.load(open(out)) if os.path.isfile(out) else {}
    for sect in (only or TABLE):
        ov, info = solve(sect)
        res[sect] = {'ov': ov, 'info': info}
        json.dump(res, open(out, 'w'), indent=1)
