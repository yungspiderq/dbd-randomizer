# -*- coding: utf-8 -*-
"""Генерирует dbd_skins.py: наборы одежды (скины) с картинками.

Запуск:  python tools/resolve_skins.py
Сеть:    https://deadbydaylight.wiki.gg/api.php (кэш в tools/wiki_cache/)

Источники
---------
* Module:Datatable/Cosmetics  — наборы: id, персонаж (killer/survivor = номер),
  редкость, англ. имя;
* Module:Datatable/Loadout    — p.skills: номер персонажа -> англ. имя (чтобы
  привязать набор к русскому имени персонажа из dbd_data.py);
* Module:Datatable/Various    — p.rarities: номер редкости -> англ. ярлык;
* файлы CC{id:03d}_charSelect_portrait.png на wiki.gg — превью набора
  (проверяются по списку реально залитых файлов, fallback — iconFile из
  Module:Datatable/Icons).

RU-названий наборов в открытых данных НЕТ (ру-вики хранит их в статьях
«<Персонаж> (наборы одежды)», парсинг ~50 страниц пока не оправдан), поэтому
v1 показывает английские имена + картинку + редкость: по картинке набор
находится в русском клиенте игры мгновенно. Карта построена по id наборов,
так что RU-имена можно добавить позже таблицей SKIN_RU_OVERRIDES без ломающих
изменений.
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

from char_names_ru_en import (SURVIVOR_RU_EN, KILLER_RU_SPRITE,
                              KILLER_RU_PORTRAIT)  # noqa: E402
import dbd_data as DATA                                          # noqa: E402

API = "https://deadbydaylight.wiki.gg/api.php"
UA = {"User-Agent": "DBDskinFetcher/2.10 (skins; see repository)"}
CACHE = os.path.join(ROOT, "tools", "wiki_cache")

RARITY_RU = {
    "Common": "обычный", "Rare": "редкий", "Very Rare": "очень редкий",
    "Ultra Rare": "крайне редкий", "Iridescent": "радужный", "Limited": "лимитированный",
    "Event": "ивентовый", "Uncommon": "необычный", "Special": "особый",
}


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


def stored_file_names():
    path = os.path.join(CACHE, "skin_files.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return set(json.load(fh))
    out = set()
    for prefix in ("CC0", "CC1", "S0", "S1", "S2", "S3", "S4", "S5", "K0", "K1", "K2"):
        cont = None
        while True:
            kw = dict(action="query", list="allimages", aiprefix=prefix, ailimit="500")
            if cont:
                kw["aicontinue"] = cont
            d = api(**kw)
            got = [i["name"] for i in d["query"]["allimages"]]
            out.update(g for g in got if "charSelect" in g or "outfit" in g.lower())
            if "continue" in d:
                cont = d["continue"]["aicontinue"]
            else:
                break
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(sorted(out), fh, ensure_ascii=False)
    return out


def main():
    cos = module_wikitext("Module:Datatable/Cosmetics", "Module_Datatable_Cosmetics.wiki")
    load = module_wikitext("Module:Datatable/Loadout", "Module_Datatable_Loadout.wiki")
    various = module_wikitext("Module:Datatable/Various", "Module_Datatable_Various.wiki")
    icons_wt = module_wikitext("Module:Datatable/Icons", "Module_Datatable_Icons.wiki")

    # номер персонажа -> RU имя (из спрайт-модулей: K01..K44, S01..S44)
    knum_ru = {}
    for ru, sid in KILLER_RU_SPRITE.items():
        knum_ru[int(sid[1:3])] = ru
    for ru, fname in KILLER_RU_PORTRAIT.items():
        m0 = re.match(r"K(\d+)", fname)
        if m0:
            knum_ru[int(m0.group(1))] = ru
    spr_s = module_wikitext("Module:SurvivorPortraitsSprite",
                            "Module_SurvivorPortraitsSprite.wiki")
    def norm(s):
        return re.sub(r"[^a-z0-9]", "", s.lower())
    surv_by_norm = {norm(v): k for k, v in SURVIVOR_RU_EN.items()}
    MANUAL_S = {"S42": "Аэстри Язар"}          # TheTroupe -> дуо из dbd_data
    snum_ru = {}
    for sid, token, _pos in re.findall(
            r"\['(S\d+) ([A-Za-z'\- ]+) Portrait'\]\s*=\s*\{ pos = (\d+)", spr_s):
        snum_ru[int(sid[1:])] = MANUAL_S.get(sid) or surv_by_norm.get(norm(token))
    # редкости
    rarities = {}
    m = re.search(r"p\.rarities\s*=\s*\{(.*?)\n\}", various, re.S)
    if m:
        for mm in re.finditer(r"\[(\d+)\]\s*=\s*\"([^\"]+)\"", m.group(1)):
            rarities[int(mm.group(1))] = mm.group(2)
    # iconFile fallback
    icons = {}
    for mm in re.finditer(r'\[(["\'])(.*?)\1\]\s*=\s*\{[^{}]*?iconFile\s*=\s*"([^"]+)"', icons_wt):
        icons[mm.group(2)] = mm.group(3)

    stored = stored_file_names()

    def variant_ok(name):
        return name in stored

    skins_by_id, char_skins = {}, {}
    missing_img = 0
    for m in re.finditer(r"\{id = (\d+), (killer|survivor) = (\d+),\s*rarity = (\d+), "
                         r"name = \"([^\"]+)\"", cos):
        sid, side, cnum, rar, name = (int(m.group(1)), m.group(2), int(m.group(3)),
                                      int(m.group(4)), m.group(5))
        ru_char = knum_ru.get(cnum) if side == "killer" else snum_ru.get(cnum)
        if not ru_char:
            continue
        if ru_char not in DATA.KILLERS and ru_char not in DATA.SURVIVORS:
            continue
        fname = f"CC{sid:03d}_charSelect_portrait.png"
        if not variant_ok(fname):
            alt = icons.get(name)
            fname = alt if alt and variant_ok(alt.replace(" ", "_")) or (alt and alt in stored) else None
            if fname and fname not in stored:
                fname = fname.replace(" ", "_") if fname.replace(" ", "_") in stored else None
        if not fname:
            missing_img += 1
        rar_label = rarities.get(rar, "")
        skins_by_id[sid] = {
            "name": name,
            "char": ru_char,
            "side": "KILLER" if side == "killer" else "SURVIVOR",
            "rarity": rar,
            "rarity_ru": RARITY_RU.get(rar_label, rar_label),
            "file": fname,
        }
        char_skins.setdefault(ru_char, []).append(sid)

    print(f"наборов: {len(skins_by_id)}, персонажей с наборами: {len(char_skins)}, "
          f"без картинки: {missing_img}")

    out = os.path.join(ROOT, "dbd_skins.py")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write('# -*- coding: utf-8 -*-\n')
        fh.write('"""Сгенерировано tools/resolve_skins.py — НЕ править вручную.\n\n')
        fh.write('Наборы одежды (скины): id -> данные + файл превью на wiki.gg.\n')
        fh.write('Имена английские: RU-названий нет в открытых данных (v1), картинка\n')
        fh.write('позволяет найти набор в русском клиенте. Ключи стабильны (id).\n"""\n\n')
        fh.write('SKIN_BASE = "https://deadbydaylight.wiki.gg/images/"\n\n')
        fh.write("SKINS_BY_ID = {\n")
        for sid in sorted(skins_by_id):
            s = skins_by_id[sid]
            fh.write(f"    {sid}: {{'name': {s['name']!r}, 'char': {s['char']!r}, "
                     f"'side': {s['side']!r}, 'rarity': {s['rarity']}, "
                     f"'rarity_ru': {s['rarity_ru']!r}, 'file': {s['file']!r}}},\n")
        fh.write("}\n\n")
        fh.write("CHAR_SKINS = {\n")
        for ru in sorted(char_skins):
            fh.write(f"    {ru!r}: {sorted(char_skins[ru])!r},\n")
        fh.write("}\n\n")
        fh.write("# ключи вида 'skin:<id>' — для общего IconStore\n")
        fh.write("SKIN_FILES = {\n")
        for sid in sorted(skins_by_id):
            f = skins_by_id[sid]["file"]
            if f:
                fh.write(f"    'skin:{sid}': {f!r},\n")
        fh.write("}\n")
    print(f"Записано: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
