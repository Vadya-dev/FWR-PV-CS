"""Write ixr_addons/fwr_barrel_aim from barrel/all.json. usage: write_barrel_addon.py <all.json> <addon_dir>"""
import json, os, sys

res = json.load(open(sys.argv[1]))
addon = sys.argv[2]
cfg = os.path.join(addon, 'configs')
os.makedirs(cfg, exist_ok=True)

ORDER = ['hands_position', 'hands_position_16x9', 'hands_orientation', 'hands_orientation_16x9',
         'aim_hud_offset_pos', 'aim_hud_offset_pos_16x9', 'aim_hud_offset_rot', 'aim_hud_offset_rot_16x9',
         'gl_hud_offset_pos', 'gl_hud_offset_pos_16x9', 'gl_hud_offset_rot', 'gl_hud_offset_rot_16x9']

lines = [
    '; ============================================================================',
    '; FWR Barrel Aim - ствол смотрит в перекрестие (DLTX поверх FWR Position & View)',
    ';',
    '; Пуля у игрока всегда летит по оси камеры, то есть в перекрестие. Здесь поза',
    ';   простоя каждого ствола довёрнута вокруг самого оружия так, что ось ствола',
    ';   (направление выстрела модели, get_LastFD) параллельна оси камеры: ствол',
    ';   визуально уходит точно в перекрестие - куда смотрит дуло, туда и летит пуля.',
    '; Прицеливание и подствольник пересчитаны и совпадают с P&V один в один.',
    '; Положение оружия на экране почти не меняется; пропадает только разворот',
    ';   ствола внутрь (2-4 град.). Во время качания/инерции ствол на миг отходит.',
    '; Удалить - удалите папку ixr_addons\\fwr_barrel_aim (вернётся вид P&V).',
    '; Файл грузится после mod_system_fwr_position_view.ltx (порядок по имени).',
    '; ============================================================================',
    '',
]
for sect in sorted(res):
    ov, info = res[sect]['ov'], res[sect]['info']
    lines.append('; %s: ствол был %+.2f / %+.2f град. (лево-право / вверх-вниз), довёрнут на %.2f град.' % (
        sect, info['bore_old'][0], info['bore_old'][1], info['rot_deg']))
    lines.append('![%s]' % sect)
    for k in ORDER:
        if k in ov:
            lines.append('%-31s = %s' % (k, ov[k]))
    lines.append('')

path = os.path.join(cfg, 'mod_system_fwr_pv_barrel_aim.ltx')
open(path, 'wb').write('\r\n'.join(lines).encode('cp1251'))
open(os.path.join(addon, 'addon.init'), 'wb').write(b'name: FWR Barrel Aim\r\ndepends: FWR Position and View\r\n')
print('written', path, len(res), 'sections')
