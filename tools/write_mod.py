"""Write new mod_system_fwr_position_view.ltx from final_ov.json (+ keep untouched P&V sections)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import scene

src_json, out_path = sys.argv[1:3]
res = json.load(open(src_json))
old = scene.read_mod(scene.PV_MOD)
CLS_RU = {'rifle': 'винтовка/ПП/дробовик', 'scoped': 'с оптикой', 'pistol': 'пистолет', 'launcher': 'гранатомёт'}
ORDER = ['hands_position', 'hands_position_16x9', 'hands_orientation', 'hands_orientation_16x9',
         'item_position', 'item_orientation',
         'aim_hud_offset_pos', 'aim_hud_offset_pos_16x9', 'aim_hud_offset_rot', 'aim_hud_offset_rot_16x9',
         'gl_hud_offset_pos', 'gl_hud_offset_pos_16x9', 'gl_hud_offset_rot', 'gl_hud_offset_rot_16x9']

lines = ["""; ============================================================================
; FWR Position & View для FWR CS Edition (IX-Ray) - положение рук, версия 2
; Подобрано под hud_fov 55 / fov 70 / 16:9 по офлайн-превью моделей и анимаций.
;
; Прицеливание: линия прицела строго по центру, оружие без завала (у P&V был
;   завал 2-3 град.). АН-94, АКС-74У, MP5 приближены к глазу как остальные.
; Простой: единый стиль от позы прицеливания - вправо/вниз, лёгкий завал и
;   доворот внутрь. Длинноствол: задняя часть ~11 см от глаза.
; Пистолеты: максимально близко, но перезарядка/доставание не ближе 13 см
;   и не больше 12% экрана (у ПБ/ПМ было 6.6 см и 26%).
; Нож, гранаты, болт, бинокль, детекторы - как в P&V.
; Чтобы вернуть позиции FWR CS - удалите папку ixr_addons\\fwr_position_view.
; ============================================================================
"""]
done = set()
for sect in sorted(res, key=lambda s: (res[s]['info']['cls'], s)):
    ov, info = res[sect]['ov'], res[sect]['info']
    keys = dict(ov)
    gl = (scene.weapon_section(sect).get('grenade_launcher_status') or '0').strip()
    if gl not in ('1', '2'):
        keys = {k: v for k, v in keys.items() if not k.startswith('gl_hud_offset')}
    if info['base'] == 'pv':
        for k in ('item_position', 'item_orientation'):
            if k in old.get(sect, {}):
                keys[k] = old[sect][k]
    fname = scene.all_sections()[sect]['__fname__']
    lines.append(f"; {fname} - {CLS_RU[info['cls']]}, основа {'P&V' if info['base'] == 'pv' else 'FWR CS'}; "
                 f"перезарядка: {info['cover'] * 100:.0f}% экрана, ближе всего {info['minz'] * 100:.0f} см")
    lines.append(f'![{sect}]')
    for k in ORDER:
        if k in keys:
            lines.append(f'{k:32}= {keys[k]}')
    lines.append('')
    done.add(sect)
lines.append('; ---- без изменений относительно P&V ----')
for sect, kv in old.items():
    if sect in done:
        continue
    lines.append(f'![{sect}]')
    for k in ORDER:
        if k in kv:
            lines.append(f'{k:32}= {kv[k]}')
    lines.append('')
text = '\n'.join(lines) + '\n'
open(out_path, 'wb').write(text.replace('\n', '\r\n').encode('cp1251'))
print('written', out_path, len(done), 'tuned +', len([s for s in old if s not in done]), 'kept')
