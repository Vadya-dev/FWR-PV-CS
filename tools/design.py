"""Target pose design: aim fix (roll, eye relief) + idle style L. Produces overrides per hud section."""
import math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import hudview as hv
import scene, tune


def roll_of(W):
    return math.degrees(math.atan2(-W[0][1], W[1][1]))


def target_aim(h, rear_target=None, dz=None, fix_roll=True):
    """A_new = Rz(roll fix) . T(0,0,dz) . A_old   (keeps sight line on camera axis)"""
    att, A, la, li, I, Wa, Wi = tune.mats(h)
    rs, _ = tune.rear_sight(h)
    if dz is None:
        dz = (rear_target - rs) if (rear_target is not None and rs < 1e8) else 0.0
    T = hv.translated(hv.ident(), (0, 0, dz))
    A2 = hv.mul(T, A)
    if fix_roll:
        W2 = hv.mul(hv.mul(A2, la), I)
        r = roll_of(W2)
        # rotation about camera z by angle that cancels roll: X-Ray rotateZ(a) turns up vector by -a in our measure?
        for sgn in (1, -1):
            Rz = hv.rotZ(sgn * math.radians(r))
            if abs(roll_of(hv.mul(hv.mul(hv.mul(Rz, A2), la), I))) < abs(r) * 0.5 + 1e-6:
                A2 = hv.mul(Rz, A2)
                break
    return A2, (rs + dz if rs < 1e8 else None)


def style(d, hpb, pivot_z):
    return tune.L_make(d, hpb, (0, 0, pivot_z))


def design(sect, rear_target=None, dz=None, d=(0.07, -0.03, -0.05), hpb=(0, 0, 0), fix_roll=True, keep_gl=True, use_pv=True, pivot_z=None):
    h = scene.Hud(sect, use_pv=use_pv)
    att, A, la, li, I, Wa, Wi = tune.mats(h)
    A2, rear = target_aim(h, rear_target, dz, fix_roll)
    pz = pivot_z if pivot_z is not None else (rear if rear else 0.2)
    L = style(d, hpb, pz)
    A_gl = None
    if keep_gl and (h.g('gl_hud_offset_pos') or h.g('gl_hud_offset_rot')):
        A_gl = hv.mul(h.aim('gl'), att)
    ov = tune.synth(h, A2, L, A_gl)
    return ov


def preview(sect, ov, path, use_pv=True, extra_states=(('reload', None),), W=480, H=270):
    h = scene.Hud(sect, ov, use_pv=use_pv)
    cells = []
    i1, *_ = scene.snapshot(h, 'idle', 0, W, H); cells.append(i1)
    i2, *_ = scene.snapshot(h, 'aim', 0, W, H); cells.append(i2)
    cm = tune.close_metrics(h, step=4)
    if cm['key']:
        i3, *_ = scene.snapshot(h, 'reload', cm['frame'], W, H, anim_key=cm['key']); cells.append(i3)
    return cells, cm
