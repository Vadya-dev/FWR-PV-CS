"""Before/after HTML: for each weapon idle / aim / worst reload, old (current mod) vs new (overrides json)."""
import base64, io, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import scene, tune, hudview as hv

src_json, out_html = sys.argv[1:3]
only = sys.argv[3:]
res = json.load(open(src_json))
NAMES = {'wpn_ak74_hud': 'АК-74', 'wpn_abakan_hud': 'АН-94 «Абакан»', 'wpn_ak74u_hud': 'АКС-74У', 'wpn_lr300_hud': 'LR-300',
         'wpn_mp5_hud': 'MP5', 'wpn_sig550_hud': 'SIG 550', 'wpn_groza_hud': 'ОЦ-14 «Гроза»', 'wpn_val_hud': 'АС «Вал»',
         'wpn_pkm_hud': 'ПКМ', 'wpn_fn2000_hud': 'FN F2000', 'wpn_bm16_hud': 'БМ-16', 'wpn_toz34_hud': 'ТОЗ-34',
         'wpn_spas12_hud': 'SPAS-12', 'wpn_winchester1300_hud': 'Winchester 1300', 'wpn_svd_hud': 'СВД', 'wpn_svu_hud': 'СВУ',
         'wpn_vintorez_hud': 'ВСС «Винторез»', 'wpn_gauss_hud': 'Гаусс', 'wpn_l85_hud': 'L85', 'wpn_g36_hud': 'G36',
         'wpn_beretta_hud': 'Beretta 92', 'wpn_colt1911_hud': 'Colt 1911', 'wpn_desert_eagle_hud': 'Desert Eagle',
         'wpn_fort_hud': 'Форт-12', 'wpn_hpsa_hud': 'Browning HP', 'wpn_pb_hud': 'ПБ', 'wpn_pm_hud': 'ПМ',
         'wpn_sig220_hud': 'SIG P220', 'wpn_usp_hud': 'USP', 'wpn_walther_hud': 'Walther P99',
         'wpn_rpg7_hud': 'РПГ-7', 'wpn_rg-6_hud': 'РГ-6'}
W, H = 320, 180


def png_b64(img):
    p = os.path.join(os.environ.get('TEMP', '.'), '_tmp_hud.png')
    img.save_png(p)
    return base64.b64encode(open(p, 'rb').read()).decode()


def row(h):
    i1, *_ = scene.snapshot(h, 'idle', 0, W, H)
    i2, *_ = scene.snapshot(h, 'aim', 0, W, H)
    cm = tune.close_metrics(h, step=4)
    if cm['key']:
        i3, *_ = scene.snapshot(h, 'reload', cm['frame'], W, H, anim_key=cm['key'])
    else:
        i3 = hv.Image(W, H)
    return [png_b64(i) for i in (i1, i2, i3)], cm


parts = []
for sect in (only or sorted(res, key=lambda s: (res[s]['info']['cls'], s))):
    info = res[sect]['info']
    old_imgs, ocm = row(scene.Hud(sect))
    new_imgs, ncm = row(scene.Hud(sect, res[sect]['ov'], use_pv=info['base'] == 'pv'))
    def cells(imgs):
        return ''.join(f'<img src="data:image/png;base64,{b}">' for b in imgs)
    parts.append(f"""<section><h2>{NAMES.get(sect, sect)} <small>{sect}</small></h2>
<div class="pair"><div><div class="lab">было</div>{cells(old_imgs)}<div class="m">перезарядка: {ocm['cover']*100:.0f}% экрана, ближе всего {ocm['minz']*100:.0f} см</div></div>
<div><div class="lab">стало</div>{cells(new_imgs)}<div class="m">перезарядка: {ncm['cover']*100:.0f}% экрана, ближе всего {ncm['minz']*100:.0f} см</div></div></div></section>""")
    print('done', sect, flush=True)

html = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FWR позиции рук</title><style>
:root{{--bg:#16181b;--fg:#e6e6e6;--mut:#9aa0a6;--card:#202328}}
@media (prefers-color-scheme: light){{:root:not([data-theme="dark"]){{--bg:#f4f4f2;--fg:#1d1d1d;--mut:#5f6368;--card:#ffffff}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,Segoe UI,sans-serif;margin:0;padding:16px}}
h1{{font-size:20px;margin:0 0 4px}} p{{color:var(--mut);margin:0 0 16px;max-width:900px}}
section{{background:var(--card);border-radius:10px;padding:12px;margin:0 0 14px}}
h2{{font-size:16px;margin:0 0 8px}} small{{color:var(--mut);font-weight:400}}
.pair{{display:grid;grid-template-columns:1fr;gap:10px}} @media(min-width:1100px){{.pair{{grid-template-columns:1fr 1fr}}}}
.pair img{{width:33.333%;height:auto;display:inline-block;vertical-align:top}}
.lab{{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);margin-bottom:4px}}
.m{{font-size:12px;color:var(--mut);margin-top:4px}}
</style></head><body><h1>Положение рук FWR — было / стало</h1>
<p>Офлайн-превью по моделям и анимациям игры, hud_fov 55, 16:9. В каждой строке: простой, прицеливание, самый «близкий» кадр перезарядки или доставания. Обвесы, которых нет по умолчанию, скрыты. Цвета условные.</p>
{''.join(parts)}</body></html>"""
open(out_html, 'w', encoding='utf-8').write(html)
print('html', out_html)
