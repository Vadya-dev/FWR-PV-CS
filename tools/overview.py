"""Render idle / aim / reload-closest for many hud sections. usage: overview.py out_prefix [use_pv 0/1] [sections...]"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
import scene

out = sys.argv[1]
use_pv = sys.argv[2] != '0' if len(sys.argv) > 2 else True
secs = sys.argv[3:] or sorted(k for k, v in scene.all_sections().items() if k.endswith('_hud') and 'item_visual' in v)
W, H = 320, 180
per = 8
report = {}
for start in range(0, len(secs), per):
    cells = []
    for s in secs[start:start + per]:
        h = scene.Hud(s, use_pv=use_pv)
        try:
            i1, st1, _ = scene.snapshot(h, 'idle', 0, W, H)
            i2, st2, _ = scene.snapshot(h, 'aim', 0, W, H)
            f, mz = scene.closest_frame(h)
            i3, st3, _ = scene.snapshot(h, 'reload', f, W, H)
        except Exception as e:
            print('ERR', s, e); continue
        cells += [i1, i2, i3]
        report[s] = {'idle_minz': round(st1['minz'], 3), 'aim_minz': round(st2['minz'], 3), 'reload_minz': round(mz, 3), 'reload_frame': f}
        print(s, report[s])
    scene.sheet(cells, 3, W, H, path=f'{out}_{start // per}.png')
json.dump(report, open(out + '.json', 'w'), indent=1)
