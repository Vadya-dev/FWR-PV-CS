# tools — подбор положения рук

Скрипты на чистом Python 3 (без numpy), которыми сгенерирован `ixr_addons/fwr_position_view`.
Они повторяют HUD-цепочку IX-Ray: камера · смещение прицеливания · `hands_position/orientation` · кость рук `lead_gun` · `item_position/orientation`, корневая кость оружия принудительно единичная (как в `player_hud.cpp`).

| Файл | Что делает |
|---|---|
| `xdb.py` | читает/распаковывает архивы `.db` игры (заголовок LZHuf, данные LZO через `bin\lzo2.dll` игры) |
| `ltxdiff.py` | разбор `.ltx` и сравнение по ключам |
| `hudview.py` | загрузка OGF/OMF, скиннинг, программный растеризатор, PNG |
| `scene.py` | сборка HUD-сцены из конфигов FWR + DLTX-файла позиций |
| `tune.py` | анализ поз: прицеливание/простой, метрики «насколько близко» в перезарядке |
| `design.py` | синтез поз: выравнивание прицела, стиль простоя |
| `final.py` | таблица стволов и подбор → `final_ov.json` |
| `write_mod.py` | `final_ov.json` → `mod_system_fwr_position_view.ltx` |
| `compare_html.py` | страница «было / стало» |
| `overview.py` | листы превью по всем стволам |

## Подготовка

Нужны модели рук из ванильных архивов игры (их нет в FWR):

```
python -I tools\xdb.py "<игра>\resources\resources.db0" "<игра>\bin\lzo2.dll" tools\_vanilla "meshes\dynamics\weapons\" "meshes\dynamics\devices\"
```

Пути можно переопределить переменными окружения `FWR_ADDON`, `FWR_VANILLA`, `PV_MOD`.
HUD FOV превью — `HUD_FOV` в `scene.py` (55).

## Типичный цикл

```
python -I tools\final.py tools\final_ov.json wpn_pb_hud      # пересчитать один ствол
python -I tools\write_mod.py tools\final_ov.json ixr_addons\fwr_position_view\configs\mod_system_fwr_position_view.ltx
python -I tools\compare_html.py tools\final_ov.json docs\preview.html wpn_pb_hud
```

Стиль и классы стволов задаются в начале `final.py` (`RIFLE_STYLE`, `PISTOL_STYLE`, `TABLE`, `SPECIAL`).
Внимание: `write_mod.py` и `compare_html.py` берут «старые» значения из текущего `PV_MOD` — для сравнения со старой версией укажите её через `PV_MOD`.
