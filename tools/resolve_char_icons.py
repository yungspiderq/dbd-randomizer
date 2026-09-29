# -*- coding: utf-8 -*-
"""Генерирует карты портретов/сил/предметов в dbd_icons.py.

Запуск:  python tools/resolve_char_icons.py
Сеть:    https://deadbydaylight.wiki.gg/api.php (кэш в tools/wiki_cache/)

Состав выходных карт
--------------------
SURVIVOR_PORTRAITS  RU имя выжившего  -> файл Survivor*.png (Module:Datatable/Icons);
POWER_ICONS         RU имя силы       -> файл IconPowers *.png (имя силы берётся из
                    Module:Datatable/Loadout по номеру убийцы, сопоставленному с dbd_data);
ITEM_ICONS          RU имя предмета   -> файл iconItems *.png;
KILLER_SPRITE       спрайт-лист портретов маньяков: url + размер кадра + таблица
                    «RU имя -> позиция кадра» (Module:KillerPortraitsSprite); кроп
                    делает IconStore на лету и кэширует в icons_cache/.

Все выбранные имена файлов проверяются через API imageinfo: несуществующих файлов
в карты не попадают (персонаж/сила останутся без иконки, текст не пострадает).
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from char_names_ru_en import SURVIVOR_RU_EN, KILLER_RU_SPRITE, ITEM_RU_EN  # noqa: E402
import dbd_data as DATA                                                      # noqa: E402

API = "https://deadbydaylight.wiki.gg/api.php"
UA = {"User-Agent": "DBDcharFetcher/2.5 (portraits; see repository)"}
CACHE = os.path.join(ROOT, "tools", "wiki_cache")


def api(**kw):
    kw.setdefault("format", "json")
    url = API + "?" + urllib.parse.urlencode(kw)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def module_wikitext(page, cache_name):
    path = os.path.join(CACHE, cache_name)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    wt = api(action="parse", page=page, prop="wikitext")["parse"]["wikitext"]["*"]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(wt)
    return wt


def _variants(name):
    """Файлы на вики залиты в разных написаниях: пробел/подчёркивание, регистр первой буквы."""
    out = [name]
    for base in (name, name.replace(" ", "_"), name.replace("_", " ")):
        out.append(base[0].upper() + base[1:])
        out.append(base[0].lower() + base[1:])
    return list(dict.fromkeys(out))


def stored_file_names():
    """Реальные имена файлов на диске wiki.gg (allimages): только они дают рабочий URL."""
    path = os.path.join(CACHE, "char_files.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return set(json.load(fh))
    out = set()
    for prefix in ("IconPowers", "iconItems", "IconItems", "Survivor",
                   "T_UI_iconItems", "T_UI_iconPowers", "IconSkills"):
        cont = None
        while True:
            kw = dict(action="query", list="allimages", aiprefix=prefix, ailimit="500")
            if cont:
                kw["aicontinue"] = cont
            d = api(**kw)
            out.update(i["name"] for i in d["query"]["allimages"])
            if "continue" in d:
                cont = d["continue"]["aicontinue"]
            else:
                break
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(sorted(out), fh, ensure_ascii=False)
    return out


def resolve_files(names):
    """Для каждого имени возвращает реально залитый вариант файла (или None)."""
    stored = stored_file_names()
    out = {}
    for n in dict.fromkeys(names):
        out[n] = next((c for c in _variants(n) if c in stored), None)
    return out


def main():
    icons_wt = module_wikitext("Module:Datatable/Icons", "Module_Datatable_Icons.wiki")
    load_wt = module_wikitext("Module:Datatable/Loadout", "Module_Datatable_Loadout.wiki")
    sprite_wt = module_wikitext("Module:KillerPortraitsSprite", "Module_KillerPortraitsSprite.wiki")

    icons = {}
    for m in re.finditer(r'\[(["\'])(.*?)\1\]\s*=\s*\{[^{}]*?iconFile\s*=\s*"([^"]+)"', icons_wt):
        icons[m.group(2).replace("\\'", "'")] = m.group(3)

    # силы: EN имя -> номер убийцы; номер = порядок в dbd_data.KILLERS
    powers_en = {}
    i = load_wt.index("p.powers = {")
    for m in re.finditer(r'\[(["\'])(.*?)\1\]\s*=\s*\{[^{}]*?killer\s*=\s*(\d+)',
                         load_wt[i:load_wt.index("p.powersCount", i)]):
        powers_en[m.group(2).replace("\\'", "'")] = int(m.group(3))
    killers_order = list(DATA.KILLERS)

    power_icons, surv_ports, item_icons = {}, {}, {}
    for en, num in powers_en.items():
        if 1 <= num <= len(killers_order) and en in icons:
            power_icons[DATA.KILLERS[killers_order[num - 1]]["power"]] = icons[en]
    for ru, en in SURVIVOR_RU_EN.items():
        if en in icons:
            surv_ports[ru] = icons[en]
    for ru, en in ITEM_RU_EN.items():
        if en in icons:
            item_icons[ru] = icons[en]

    # спрайт маньяков
    ids = dict(re.findall(r"\['([^']+)'\]\s*=\s*\{ pos = (\d+)", sprite_wt))
    sprite_url = None
    d = api(action="query", titles="File:KillerPortraitsSprite.png", prop="imageinfo", iiprop="url|size")
    pg = list(d["query"]["pages"].values())[0]
    info = pg["imageinfo"][0]
    sprite_url = info["url"].split("?")[0]
    width = info["width"]
    size = int(re.search(r"width\s*=\s*'(\d+)'", sprite_wt).group(1))
    cols = width // size
    ports = {ru: int(ids[sid]) for ru, sid in KILLER_RU_SPRITE.items() if sid in ids}

    # проверка существования файлов + подбор написания
    candidates = list(surv_ports.values()) + list(item_icons.values()) + list(power_icons.values())
    resolved = resolve_files(candidates)
    miss = sorted({c for c in candidates if not resolved.get(c)})
    surv_ports = {k: resolved[v] for k, v in surv_ports.items() if resolved.get(v)}
    item_icons = {k: resolved[v] for k, v in item_icons.items() if resolved.get(v)}
    power_icons = {k: resolved[v] for k, v in power_icons.items() if resolved.get(v)}
    print(f"портретов выживших {len(surv_ports)}, иконок предметов {len(item_icons)}, "
          f"иконок сил {len(power_icons)}, кадров спрайта {len(ports)}")
    if miss:
        print("файлы не найдены (пропущены):", miss)

    import dbd_icons
    perks, addons = dict(dbd_icons.PERK_ICONS), dict(dbd_icons.ADDON_ICONS)
    out = os.path.join(ROOT, "dbd_icons.py")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write('# -*- coding: utf-8 -*-\n')
        fh.write('"""Сгенерировано tools/resolve_icons.py, tools/resolve_addon_icons.py и\n')
        fh.write('tools/resolve_char_icons.py — НЕ править вручную.\n\n')
        fh.write('Русское имя навыка/аддона/персонажа/силы/предмета -> имя файла иконки на\n')
        fh.write('deadbydaylight.wiki.gg. Иконки НЕ лежат в репозитории: приложение качает их\n')
        fh.write('по мере надобности и кэширует локально (см. IconStore в dbd_icons_store.py).\n"""\n\n')
        fh.write('ICON_BASE = "https://deadbydaylight.wiki.gg/images/"\n\n')
        for name, mapping in (("PERK_ICONS", perks), ("ADDON_ICONS", addons),
                              ("SURVIVOR_PORTRAITS", surv_ports), ("POWER_ICONS", power_icons),
                              ("ITEM_ICONS", item_icons)):
            fh.write(f"{name} = {{\n")
            for ru in sorted(mapping):
                fh.write(f"    {ru!r}: {mapping[ru]!r},\n")
            fh.write("}\n\n")
        fh.write("KILLER_SPRITE = {\n")
        fh.write(f"    'url': {sprite_url!r},\n")
        fh.write(f"    'size': {size},\n")
        fh.write(f"    'cols': {cols},\n")
        fh.write("    'ports': {\n")
        for ru in sorted(ports):
            fh.write(f"        {ru!r}: {ports[ru]},\n")
        fh.write("    },\n}\n")
    print(f"Записано: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
