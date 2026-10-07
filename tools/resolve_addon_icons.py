# -*- coding: utf-8 -*-
"""Генерирует карту ADDON_ICONS (русское имя аддона -> файл иконки на wiki.gg).

Запуск:  python tools/resolve_addon_icons.py
Сеть:    https://deadbydaylight.wiki.gg/api.php (результаты кэшируются в tools/wiki_cache/)

Как работает
------------
1. Берёт из Module:Datatable/Loadout список аддонов (англ. имя -> id/редкость/владелец),
   из Module:Datatable/Icons — англ. имя -> имя файла иконки.
2. Русские имена (те, что лежат в dbd_data.py) переводятся в английские таблицей
   tools/addon_names_ru_en.py (сверена с RU-вики и Steam-локализацией).
3. Имя файла проверяется по списку реально загруженных на wiki.gg файлов (allimages):
   «IconAddon x.png» и «IconAddon_x.png» — разные файлы, берём существующий.
4. Обновляет ТОЛЬКО блок ADDON_ICONS в dbd_icons.py (секции перков, портретов,
   сил, предметов и классов остаются нетронутыми).

Аддоны, полностью удалённые из игры, в таблицу wiki.gg не входят — у них иконки нет,
они попадают в tools/addon_unresolved.json (в git не коммитится).
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

from addon_names_ru_en import ADDON_RU_EN, ITEM_ADDON_RU_EN  # noqa: E402
import dbd_data as DATA                                       # noqa: E402

API = "https://deadbydaylight.wiki.gg/api.php"
UA = {"User-Agent": "DBDiconFetcher/2.2 (addon icons; see repository)"}
CACHE = os.path.join(ROOT, "tools", "wiki_cache")
FILE_PREFIXES = ("IconAddon_", "FulliconAddon_", "IconItems_", "T_UI_iconAddon")

KEY = re.compile(r'^\s*\[(["\'])(.*?)\1\]\s*=\s*\{(.*)\},?\s*$')
ICON_RE = re.compile(r'\[(["\'])(.*?)\1\]\s*=\s*\{[^{}]*?iconFile\s*=\s*"([^"]+)"')


def api(**kw):
    kw.setdefault("format", "json")
    url = API + "?" + urllib.parse.urlencode(kw)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def _cached(name):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, name)
    return path if os.path.exists(path) else None


def module_wikitext(page, cache_name):
    hit = _cached(cache_name)
    if hit:
        with open(hit, encoding="utf-8") as fh:
            return fh.read()
    wt = api(action="parse", page=page, prop="wikitext")["parse"]["wikitext"]["*"]
    with open(os.path.join(CACHE, cache_name), "w", encoding="utf-8") as fh:
        fh.write(wt)
    return wt


def fetch_file_names():
    hit = _cached("addon_files.json")
    if hit:
        with open(hit, encoding="utf-8") as fh:
            return set(json.load(fh))
    out = set()
    for prefix in FILE_PREFIXES:
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
    with open(os.path.join(CACHE, "addon_files.json"), "w", encoding="utf-8") as fh:
        json.dump(sorted(out), fh, ensure_ascii=False)
    return out


def lua_block(src, name):
    i = src.index("p.%s = {" % name)
    depth, j = 0, src.index("{", i)
    for k in range(j, len(src)):
        if src[k] == "{":
            depth += 1
        elif src[k] == "}":
            depth -= 1
            if depth == 0:
                return src[j:k + 1]
    raise SystemExit("не найден конец блока p.%s" % name)


def lua_str(s):
    """В Lua кавычка внутри строки экранируется обратным слешем — убираем его."""
    return s.replace("\\'", "'").replace('\\"', '"')


def parse_addons(wt):
    out = {}
    for ln in lua_block(wt, "addons").split("\n")[1:]:
        m = KEY.match(ln)
        if not m:
            continue
        body = m.group(3)
        out[lua_str(m.group(2))] = {
            "decom": bool(re.search(r"\bdecom\s*=\s*true", body)),
            "unused": bool(re.search(r"\bunused\s*=\s*true", body)),
        }
    return out


def parse_icons(wt):
    return {lua_str(m.group(2)): m.group(3) for m in ICON_RE.finditer(wt)}


def pick_file(icon_file, known):
    """Имя файла в datatable может отличаться пробелом/подчёркиванием от залитого."""
    for cand in (icon_file, icon_file.replace(" ", "_"), icon_file.replace("_", " ")):
        if cand in known:
            return cand
    return None


def main():
    loadout = module_wikitext("Module:Datatable/Loadout", "Module_Datatable_Loadout.wiki")
    icons_wt = module_wikitext("Module:Datatable/Icons", "Module_Datatable_Icons.wiki")
    known = fetch_file_names()
    addons = parse_addons(loadout)
    icons = parse_icons(icons_wt)
    print(f"wiki.gg: аддонов {len(addons)}, записей иконок {len(icons)}, файлов {len(known)}")

    resolved, unresolved = {}, []
    groups = [(k, ADDON_RU_EN.get(k, {}), DATA.KILLERS[k].get("addons", []))
              for k in DATA.KILLERS]
    groups += [(c, ITEM_ADDON_RU_EN.get(c, {}), DATA.SURVIVOR_ITEMS[c].get("addons", []))
               for c in DATA.SURVIVOR_ITEMS]

    total_ru = sum(len(ru_names) for _k, _m, ru_names in groups)
    for key, mapping, ru_names in groups:
        for ru in ru_names:
            en = mapping.get(ru)
            if not en:
                unresolved.append({"group": key, "ru": ru, "reason": "нет RU->EN"})
                continue
            if en not in icons:
                unresolved.append({"group": key, "ru": ru, "en": en,
                                   "reason": "нет иконки в datatable"})
                continue
            fname = pick_file(icons[en], known)
            if not fname:
                unresolved.append({"group": key, "ru": ru, "en": en,
                                   "reason": "файл не найден на wiki.gg", "want": icons[en]})
                continue
            resolved[ru] = fname

    print(f"сопоставлено {len(resolved)} из {total_ru} аддонов базы "
          f"({100 * len(resolved) // max(1, total_ru)} %)")
    if unresolved:
        print(f"без иконки ({len(unresolved)}):")
        for u in unresolved:
            print("   ", u.get("group"), "|", u["ru"], "|", u.get("en", ""), "|", u["reason"])
        with open(os.path.join(ROOT, "tools", "addon_unresolved.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(unresolved, fh, ensure_ascii=False, indent=1)

    # ---- обновляем ТОЛЬКО блок ADDON_ICONS в dbd_icons.py ------------------
    # Файл состоит из секций (PERK_ICONS, ADDON_ICONS, портреты, силы, предметы,
    # классы), каждая живёт между маркерами/соседними блоками. Перезписывать файл
    # целиком нельзя: сотрутся секции других генераторов (кейс v2.15.0).
    out = os.path.join(ROOT, "dbd_icons.py")
    with open(out, encoding="utf-8") as fh:
        src = fh.read()
    start = src.index("ADDON_ICONS = {")
    end = src.index("\n}\n", start) + len("\n}\n")
    block = ["ADDON_ICONS = {\n"]
    for ru in sorted(resolved):
        block.append(f"    {ru!r}: {resolved[ru]!r},\n")
    block.append("}\n")
    src = src[:start] + "".join(block) + src[end:]
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(src)
    print(f"Записано: {out}  (ADDON_ICONS {len(resolved)}, остальные секции нетронуты)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
