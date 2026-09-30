# -*- coding: utf-8 -*-
"""Генерирует dbd_skins.py: ВСЕ наборы одежды (скины) с wiki.gg.

Запуск:  python tools/resolve_skins.py
Сеть:    https://deadbydaylight.wiki.gg/api.php (кэш в tools/wiki_cache/)

Источники
---------
* Module:Datatable/Cosmetics
    - p.outfits  — все наборы: id, персонаж (killer/survivor = id), редкость,
      англ. имя, файл превью (filename), дата выхода, цена;
    - p.cosChars — «скины персонажей» (Look-See, Krampus, Baba Yaga, Xenomorph
      Queen и т.п.): отдельная таблица со СВОЕЙ нумерацией id, превью —
      CC{id:03d}_charSelect_portrait.png;
    - комментарий в шапке модуля — таблица номеров редкости.
* Module:Datatable — p.killers / p.survivors: id персонажа -> англ. имя
  (единственный надёжный способ сопоставить число из Cosmetics с персонажем:
  номера спрайт-файлов K01..K37 НЕ совпадают с id, у Hag/Shape порядок другой).
* Module:Datatable/Cosmetics/Pieces — p.heads / p.masks / p.torsos / …: id
  детали -> файл. Используется как запасное превью, если файла набора на вики
  нет (например K44_outfit_01.png у Правосудия ещё не залит).
* tools/char_map_ru.py — англ. имя персонажа -> русское имя из dbd_data.py.
* tools/skin_names_ru.py — РУССКИЕ названия наборов (имя файла -> название),
  снятые tools/fetch_ru_skins.py со статей «<Персонаж> (наборы одежды)» русской
  вики (dead-by-daylight.fandom.com/ru). Таблица может быть частичной: тогда у
  записей просто не будет поля name_ru и UI покажет английское имя.

Картинки
--------
Превью берётся не полноразмерным файлом (512x512, ~100-300 КБ), а миниатюрой
MediaWiki `images/thumb/<file>/256px-<file>` (~40 КБ): приложение показывает
их размером 26 px и 110 px, а «скачать все иконки» не тянет сотни мегабайт.
Существование каждого файла проверяется через action=query (titles=File:…),
результат кэшируется в tools/wiki_cache/skin_file_exists.json — повторный запуск
без правок данных сети не требует.

RU-названий наборов в открытых данных нет (русская вики хранит их внутри статей
«<Персонаж> (наборы одежды)», это ~100 страниц ручной разметки), поэтому v2
показывает английские имена + картинку + редкость: по картинке набор находится в
русском клиенте мгновенно. Ключи стабильны (id набора), так что RU-имена можно
добавить позже таблицей SKIN_RU_OVERRIDES без ломающих изменений.

«fakeOutfit» (одиночные предметы — торс/голова без полного набора, 912 шт.) в
основной список НЕ попадают: у них в данных вики нет ни имени, ни картинки.
Они выгружаются отдельной компактной таблицей FAKE_SKINS на будущее.
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from char_map_ru import KILLER_EN_RU, SURVIVOR_EN_RU, RARITIES   # noqa: E402
import dbd_data as DATA                                          # noqa: E402
# RU-названия (заполняется tools/fetch_ru_skins.py). Импорт МОДУЛЕМ, а не
# `from … import A, B`: таблицы добавлялись постепенно, и ImportError на одной
# из них обнулял бы обе.
try:
    import skin_names_ru as _RU
except ImportError:                                              # pragma: no cover
    _RU = None
SKIN_RU_NAMES = dict(getattr(_RU, "FILE_TO_RU", {}) or {}) if _RU else {}
PIECE_RU_NAMES = dict(getattr(_RU, "PIECE_FILE_TO_RU", {}) or {}) if _RU else {}

API = "https://deadbydaylight.wiki.gg/api.php"
UA = {"User-Agent": "DBDskinFetcher/2.11 (skins; see repository)"}
CACHE = os.path.join(ROOT, "tools", "wiki_cache")
THUMB_WIDTH = 256
# id «скинов персонажей» (p.cosChars) нумеруются отдельно и пересекаются с id
# наборов (1..111 есть в обеих таблицах) — сдвигаем их, чтобы ключи не слипались.
COSCHAR_ID_OFFSET = 10000
TITLES_PER_REQUEST = 50


# ============================================================================
# сеть + кэш
# ============================================================================
def api(retries=3, **kw):
    kw.setdefault("format", "json")
    url = API + "?" + urllib.parse.urlencode(kw)
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except Exception as exc:                            # pragma: no cover
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"API-запрос не удался: {last}")


def module_wikitext(page, cache_name, force=False):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, cache_name)
    if os.path.exists(path) and not force:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    wt = api(action="parse", page=page, prop="wikitext")["parse"]["wikitext"]["*"]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(wt)
    return wt


def lua_block(wikitext, table):
    """Тело таблицы `<table> = { ... }` из Lua-модуля вики.

    В Module:Datatable таблицы объявлены как `killers = {` с последующим
    `p.killers = killers`, в Cosmetics — сразу как `p.outfits = {`; берём
    первое объявление (однострочные `p.x = x` нас не интересуют).
    """
    m = re.search(rf"^(?:local\s+|p\.)?{re.escape(table)}\s*=\s*\{{", wikitext, re.M)
    if not m:
        raise ValueError(f"таблица {table} не найдена")
    end = wikitext.index("\n}\n", m.start())
    return wikitext[m.start():end]


def row_fields(row):
    """Поля одной Lua-строки: {'id': '5', 'name': '"Krampus"', 'rarity': '7'}."""
    out = {}
    for m in re.finditer(r'(\w+) = (?:"((?:[^"\\]|\\.)*)"|\'([^\']*)\'|(\{[^{}]*\})|([\w.\-]+))', row):
        key = m.group(1)
        val = m.group(2) if m.group(2) is not None else (
            m.group(3) if m.group(3) is not None else (
                m.group(4) if m.group(4) is not None else m.group(5)))
        out[key] = val
    return out


# ============================================================================
# персонажи: id -> русское имя
# ============================================================================
def character_names(datatable_wt):
    """(убийцы id->RU, выжившие id->RU) по Module:Datatable + char_map_ru."""
    killers, survivors, unknown = {}, {}, []

    def collect(table, mapping, dest):
        for m in re.finditer(r'\{id = (\d+), name = ([\"\'])(.*?)\2', lua_block(datatable_wt, table)):
            cid, en = int(m.group(1)), m.group(3)
            ru = mapping.get(en)
            if ru is None:
                unknown.append(f"{table}:{cid} {en!r}")
                continue
            dest[cid] = ru

    collect("killers", KILLER_EN_RU, killers)
    collect("survivors", SURVIVOR_EN_RU, survivors)
    if unknown:
        raise SystemExit("Нет русского имени для персонажей (дополните tools/char_map_ru.py): "
                         + ", ".join(unknown))
    # страховка: имя обязано совпадать с тем, что в базе приложения
    bad = [ru for ru in killers.values() if ru not in DATA.KILLERS]
    bad += [ru for ru in survivors.values() if ru not in DATA.SURVIVORS]
    if bad:
        raise SystemExit("Имена не совпадают с dbd_data.py: " + ", ".join(sorted(set(bad))))
    return killers, survivors


# ============================================================================
# файлы картинок
# ============================================================================
def file_exists_map(names):
    """{имя файла: True/False} — проверка через action=query с кэшем на диске."""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, "skin_file_exists.json")
    cached = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                cached = json.load(fh)
        except (OSError, ValueError):
            cached = {}
    todo = [n for n in dict.fromkeys(names) if n not in cached]
    for i in range(0, len(todo), TITLES_PER_REQUEST):
        chunk = todo[i:i + TITLES_PER_REQUEST]
        d = api(action="query", titles="|".join("File:" + n for n in chunk))
        q = d.get("query") or {}
        pages = {}
        for p in (q.get("pages") or {}).values():
            pages[p["title"]] = p
        for n in q.get("normalized", []):
            if n["to"] in pages:
                pages[n["from"]] = pages[n["to"]]
        for n in chunk:
            p = pages.get("File:" + n) or pages.get("File:" + n.replace("_", " "))
            cached[n] = bool(p and "missing" not in p and not p.get("invalid"))
        print(f"  файлы: проверено {min(i + TITLES_PER_REQUEST, len(todo))}/{len(todo)}", flush=True)
    if todo:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(cached, fh, ensure_ascii=False, sort_keys=True)
    return cached


def thumb_rel(filename):
    """Относительный путь миниатюры 256 px (IconStore прибавит ICON_BASE)."""
    return f"thumb/{filename}/{THUMB_WIDTH}px-{filename}"


# ============================================================================
# разбор данных
# ============================================================================
def clean_name(name):
    """Неразрывные пробелы и «типографские» кавычки вики -> обычные."""
    return (name.replace("\xa0", " ").replace("’", "'").replace("‘", "'")
                .replace("“", '"').replace("”", '"').strip())


def parse_outfits(cos_wt, killers_ru, survivors_ru):
    """Полные наборы (fakeOutfit не берём) и отдельно одиночные предметы."""
    outfits, fakes = [], []
    for row in re.findall(r"\{id = \d+,.*", lua_block(cos_wt, "outfits")):
        f = row_fields(row)
        cid = int(f["id"])
        side = "KILLER" if "killer" in f else ("SURVIVOR" if "survivor" in f else None)
        cnum = int(f.get("killer") or f.get("survivor") or 0)
        ru = (killers_ru if side == "KILLER" else survivors_ru).get(cnum)
        if side is None or ru is None:
            continue
        rec = {
            "id": cid, "side": side, "char": ru,
            "rarity": int(f.get("rarity") or 0),
            "name": clean_name(f.get("name", "")),
            "file": f.get("filename") or "",
            "date": f.get("rDate") or "",
            "pieces": f.get("pieces") or "",
            "kind": "outfit",
            "fake": f.get("fakeOutfit") == "true",
        }
        (fakes if rec["fake"] else outfits).append(rec)
    return outfits, fakes


def parse_coschars(cos_wt, killers_ru, survivors_ru):
    out = []
    for row in re.findall(r"\{id = \d+,.*", lua_block(cos_wt, "cosChars")):
        f = row_fields(row)
        side = "KILLER" if "killer" in f else "SURVIVOR"
        cnum = int(f.get("killer") or f.get("survivor") or 0)
        ru = (killers_ru if side == "KILLER" else survivors_ru).get(cnum)
        if ru is None:
            continue
        cid = int(f["id"])
        out.append({
            "id": COSCHAR_ID_OFFSET + cid, "raw_id": cid, "side": side, "char": ru,
            "rarity": int(f.get("rarity") or 0),
            "name": clean_name(f.get("name", "")),
            "file": f"CC{cid:03d}_charSelect_portrait.png",
            "date": "", "pieces": "", "kind": "coschar", "fake": False,
        })
    return out


def norm_file(name):
    """Имя файла к сравнению: MediaWiki считает «x y.png» и «x_y.png» одним файлом."""
    return name.strip().lower().replace(" ", "_")


def parse_pieces(pieces_wt):
    """{(таблица, id детали): файл} — запасные превью."""
    pieces = {}
    for table in ("heads", "masks", "torsos", "bodies", "upperBodies", "legs", "weapons", "arms", "hands"):
        try:
            block = lua_block(pieces_wt, table)
        except ValueError:
            continue
        for row in re.findall(r"\{id = \d+,.*", block):
            m = re.search(r'filename = "([^"]+)"', row)
            i = re.search(r"\{id = (\d+),", row)
            if m and i:
                pieces[(table, int(i.group(1)))] = m.group(1)
    return pieces


def parse_piece_names(pieces_wt):
    """{(таблица, id детали): EN-имя детали} — для цепочки RU-имён наборов."""
    names = {}
    for table in ("heads", "masks", "torsos", "bodies", "upperBodies", "legs",
                  "weapons", "arms", "hands"):
        try:
            block = lua_block(pieces_wt, table)
        except ValueError:
            continue
        for row in re.findall(r"\{id = \d+,.*", block):
            i = re.search(r"\{id = (\d+),", row)
            n = re.search(r'name = "((?:[^"\\]|\\.)*)"', row)
            if i and n:
                names[(table, int(i.group(1)))] = n.group(1)
    return names


def pieces_of(rec):
    """[(таблица, id)] из `pieces = {heads = 5, torsos = 21}`."""
    out = []
    for m in re.finditer(r"(\w+) = (\d+)", rec.get("pieces") or ""):
        out.append((m.group(1), int(m.group(2))))
    return out


PIECE_PRIORITY = ("heads", "masks", "torsos", "bodies", "upperBodies", "legs",
                  "weapons", "arms", "hands")


def ru_names_by_pieces(recs, pieces, piece_names):
    """RU-названия наборов через имена их элементов (статьи «(кастомизация)»).

    Зачем: статьи «(наборы одежды)» покрывают не всё. Не хватает
    * дефолтных и «кровавых» наборов — их на русской вики нет в списке одежды,
      зато есть их элементы («Эван» / «Кровавый Эван»);
    * наборов новых персонажей: у Авроры и Правосудия вместо картинок стоит
      `Missing.png`, то есть сопоставить по файлу нельзя в принципе;
    * редких наборов, которые лежат в статьях «(кастомизация)».

    Цепочка: файл элемента (RU-статья) -> (таблица, id) элемента по
    Module:Datatable/Cosmetics/Pieces -> наборы, в чьём `pieces` есть этот id.
    Название присваивается, только если ВСЕ известные RU-имена элементов набора
    совпадают (одно имя на набор) — иначе запись остаётся с английским названием:
    лучше никак, чем неверно.
    """
    if not PIECE_RU_NAMES:
        return {}, {}
    file_to_key = {norm_file(f): key for key, f in pieces.items()}
    ru_by_key = {}                                   # (таблица, id) -> {RU-имя}
    unmatched = set()
    for fn, ru in PIECE_RU_NAMES.items():
        key = file_to_key.get(norm_file(fn))
        if key is None:
            unmatched.add(fn)
            continue
        ru_by_key.setdefault(key, set()).add(ru)
    owners = {}                                      # id набора -> {RU-имя}
    for rec in recs:
        names = set()
        for key in pieces_of(rec):
            names |= ru_by_key.get(key, set())
        if len(names) == 1:
            owners[rec["id"]] = next(iter(names))
    return owners, unmatched


def fallback_file(rec, pieces, exists):
    """Превью из детали набора (голова/маска/торс), если файла набора нет."""
    got = dict(pieces_of(rec))
    for table in PIECE_PRIORITY:
        if table in got:
            fn = pieces.get((table, got[table]))
            if fn and exists.get(fn):
                return fn
    for table, pid in sorted(got.items()):
        fn = pieces.get((table, pid))
        if fn and exists.get(fn):
            return fn
    return None


# ============================================================================
# запись dbd_skins.py
# ============================================================================
def q(s):
    return repr(s)


def write_module(path, skins, char_skins, skin_files, fakes_by_char, game_version, stamp):
    n_outfit = sum(1 for s in skins.values() if s["kind"] == "outfit")
    n_char = len(skins) - n_outfit
    n_img = sum(1 for s in skins.values() if s["file"])
    n_ru = sum(1 for s in skins.values() if s.get("name_ru"))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write('# -*- coding: utf-8 -*-\n')
        fh.write('"""Сгенерировано tools/resolve_skins.py — НЕ править вручную.\n\n')
        fh.write('Наборы одежды (скины): id -> данные + файл превью на wiki.gg.\n')
        fh.write(f'Источник: Module:Datatable/Cosmetics (патч {game_version}, снято {stamp}).\n')
        fh.write(f'Наборов: {n_outfit}, «скинов персонажей» (cosChars): {n_char}, '
                 f'с превью: {n_img}, с RU-названием: {n_ru}.\n\n')
        fh.write('Имена английские: RU-названий нет в открытых данных, картинка позволяет\n')
        fh.write('найти набор в русском клиенте. Ключи стабильны (id набора).\n\n')
        fh.write('id «скина персонажа» = COSCHAR_ID_OFFSET + id из p.cosChars: у обеих\n')
        fh.write('таблиц вики своя нумерация, и на 1..111 они пересекаются.\n\n')
        fh.write('FAKE_SKINS — одиночные предметы (торс/голова без полного набора): в вики\n')
        fh.write('у них нет ни имени, ни картинки, поэтому в розыгрыш они не попадают.\n')
        fh.write('Превью — миниатюра 256 px: SKIN_FILES хранит путь `thumb/<файл>/256px-<файл>`\n')
        fh.write('(IconStore прибавляет ICON_BASE из dbd_icons.py); полноразмерный файл лежит\n')
        fh.write('по пути SKIN_BASE + поле `file`.\n\n')
        fh.write('Поле `name_ru` есть только у записей, найденных в tools/skin_names_ru.py\n')
        fh.write('(русская вики, статьи «<Персонаж> (наборы одежды)»): заполняется\n')
        fh.write('инструментом tools/fetch_ru_skins.py, пока покрытие частичное.\n"""\n\n')
        fh.write('SKIN_BASE = "https://deadbydaylight.wiki.gg/images/"\n')
        fh.write(f'THUMB_WIDTH = {THUMB_WIDTH}\n')
        fh.write(f'COSCHAR_ID_OFFSET = {COSCHAR_ID_OFFSET}\n')
        fh.write(f'GAME_VERSION = {q(game_version)}\n')
        fh.write(f'DATA_STAMP = {q(stamp)}\n\n')
        fh.write("RARITY_RU = {\n")
        for num in sorted(RARITIES):
            fh.write(f"    {num}: {q(RARITIES[num][1])},\n")
        fh.write("}\n\n")
        fh.write("RARITY_EN = {\n")
        for num in sorted(RARITIES):
            fh.write(f"    {num}: {q(RARITIES[num][0])},\n")
        fh.write("}\n\n")

        fh.write("SKINS_BY_ID = {\n")
        for sid in sorted(skins):
            s = skins[sid]
            fh.write(f"    {sid}: {{'name': {q(s['name'])}, 'char': {q(s['char'])}, "
                     f"'side': {q(s['side'])}, 'rarity': {s['rarity']}, "
                     f"'rarity_ru': {q(s['rarity_ru'])}, 'file': {q(s['file'] or '')}, "
                     f"'kind': {q(s['kind'])}")
            if s.get("name_ru"):
                fh.write(f", 'name_ru': {q(s['name_ru'])}")
                if s.get("ru_from") == "piece":
                    fh.write(", 'name_ru_from': 'piece'")
            if s.get("date"):
                fh.write(f", 'date': {q(s['date'])}")
            fh.write("},\n")
        fh.write("}\n\n")

        fh.write("# RU имя персонажа -> id наборов (сортировка: по дате выхода, затем по id)\n")
        fh.write("CHAR_SKINS = {\n")
        for ru in sorted(char_skins):
            fh.write(f"    {q(ru)}: {list(char_skins[ru])!r},\n")
        fh.write("}\n\n")

        fh.write("# ключи вида 'skin:<id>' -> путь миниатюры (для общего IconStore)\n")
        fh.write("SKIN_FILES = {\n")
        for key in sorted(skin_files, key=lambda k: int(k.split(':')[1])):
            fh.write(f"    {q(key)}: {q(skin_files[key])},\n")
        fh.write("}\n\n")

        fh.write("# одиночные предметы без имени/картинки: RU имя -> [(id, редкость, сторона)]\n")
        fh.write("FAKE_SKINS = {\n")
        for ru in sorted(fakes_by_char):
            items = ", ".join(f"({i}, {r}, {q(side)})" for i, r, side in fakes_by_char[ru])
            fh.write(f"    {q(ru)}: [{items}],\n")
        fh.write("}\n")
    return n_outfit, n_char, n_img


def main(force=False):
    cos_wt = module_wikitext("Module:Datatable/Cosmetics", "Module_Datatable_Cosmetics.wiki", force)
    dt_wt = module_wikitext("Module:Datatable", "Module_Datatable.wiki", force)
    pieces_wt = module_wikitext("Module:Datatable/Cosmetics/Pieces",
                                "Module_Datatable_Cosmetics_Pieces.wiki", force)

    m = re.search(r"--Game Version: ([\w.]+)", cos_wt)
    game_version = m.group(1) if m else "?"
    m = re.search(r"--Timestamp: ([\d\-: .]+)", cos_wt)
    stamp = (m.group(1).strip() if m else time.strftime("%Y-%m-%d"))[:19]

    killers_ru, survivors_ru = character_names(dt_wt)
    print(f"персонажей: убийц {len(killers_ru)}, выживших {len(survivors_ru)} "
          f"(патч {game_version}, данные вики от {stamp})")

    outfits, fakes = parse_outfits(cos_wt, killers_ru, survivors_ru)
    coschars = parse_coschars(cos_wt, killers_ru, survivors_ru)
    pieces = parse_pieces(pieces_wt)
    piece_names = parse_piece_names(pieces_wt)
    print(f"наборов: {len(outfits)}, скинов персонажей: {len(coschars)}, "
          f"одиночных предметов (fakeOutfit): {len(fakes)}, деталей в Pieces: {len(pieces)}")

    wanted = [r["file"] for r in outfits if r["file"]] + [r["file"] for r in coschars]
    print(f"проверяю {len(set(wanted))} файлов превью на вики…")
    exists = file_exists_map(wanted)

    # запасные превью нужны только тем записям, чей файл набора не залит
    need_fallback = [r for r in outfits + coschars if r["file"] and not exists.get(r["file"])]
    cand = []
    for rec in need_fallback:
        got = dict(pieces_of(rec))
        for table in PIECE_PRIORITY:
            fn = pieces.get((table, got[table])) if table in got else None
            if fn:
                cand.append(fn)
        for table, pid in sorted(got.items()):
            fn = pieces.get((table, pid))
            if fn:
                cand.append(fn)
    if cand:
        print(f"  у {len(need_fallback)} записей файла набора нет — "
              f"проверяю {len(set(cand))} файлов деталей…")
        exists.update(file_exists_map(cand))

    # RU-названия: сначала по файлу набора (точный источник), затем — для
    # непокрытых — по русским именам их элементов (статьи «(кастомизация)»).
    for rec in coschars + outfits:
        rec["name_ru"] = SKIN_RU_NAMES.get(rec["file"].strip().lower(), "") if rec["file"] else ""
    by_pieces, unmatched_pieces = ru_names_by_pieces(outfits, pieces, piece_names)
    n_by_pieces = 0
    for rec in outfits:
        if not rec["name_ru"] and rec["id"] in by_pieces:
            rec["name_ru"] = by_pieces[rec["id"]]
            rec["ru_from"] = "piece"
            n_by_pieces += 1
    print(f"RU-названий: по файлу набора {sum(1 for r in outfits + coschars if r['name_ru']) - n_by_pieces}, "
          f"по элементам {n_by_pieces}; имён элементов в таблице {len(PIECE_RU_NAMES)}"
          + (f", из них не сопоставлено {len(unmatched_pieces)}" if unmatched_pieces else ""))

    skins, char_skins, skin_files = {}, {}, {}
    stats = {"no_image": 0, "fallback": 0, "ru": 0, "ru_piece": n_by_pieces}
    for rec in coschars + outfits:
        sid = rec["id"]
        fn = rec["file"] if exists.get(rec["file"]) else None
        if fn is None:
            # файла набора на вики нет (свежий контент): пробуем превью детали
            fn = fallback_file(rec, pieces, exists)
            if fn:
                stats["fallback"] += 1
            else:
                stats["no_image"] += 1
        rar = rec["rarity"]
        name_ru = rec["name_ru"]
        if name_ru:
            stats["ru"] += 1
        skins[sid] = {
            "name": rec["name"], "name_ru": name_ru,
            "char": rec["char"], "side": rec["side"],
            "rarity": rar, "rarity_ru": RARITIES.get(rar, ("?", "?"))[1],
            "file": fn or "", "date": rec["date"], "kind": rec["kind"],
            "ru_from": rec.get("ru_from", "file" if name_ru else ""),
        }
        if fn:
            skin_files[f"skin:{sid}"] = thumb_rel(fn)

    # порядок в списке персонажа: сначала «скины персонажей», затем по дате выхода
    def sort_key(sid):
        s = skins[sid]
        d = s.get("date") or ""
        iso = ""
        m = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", d)
        if m:
            iso = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
        return (0 if s["kind"] == "coschar" else 1, iso or "9999", sid)

    for sid in sorted(skins, key=sort_key):
        char_skins.setdefault(skins[sid]["char"], []).append(sid)

    fakes_by_char = {}
    for rec in fakes:
        fakes_by_char.setdefault(rec["char"], []).append((rec["id"], rec["rarity"], rec["side"]))

    out = os.path.join(ROOT, "dbd_skins.py")
    n_outfit, n_char, n_img = write_module(out, skins, char_skins, skin_files,
                                           fakes_by_char, game_version, stamp)
    per_char = sorted((len(v), k) for k, v in char_skins.items())
    print(f"персонажей с наборами: {len(char_skins)} "
          f"(минимум {per_char[0][0]} у «{per_char[0][1]}», максимум {per_char[-1][0]} у «{per_char[-1][1]}»)")
    print(f"записей: {n_outfit} наборов + {n_char} скинов персонажей, "
          f"с превью {n_img} ({stats['fallback']} — превью детали вместо отсутствующего файла набора), "
          f"без превью {stats['no_image']}")
    print(f"с RU-названием: {stats['ru']} из {len(skins)} "
          f"(по файлу {stats['ru'] - stats['ru_piece']}, по элементам {stats['ru_piece']})")
    left = [s for s in skins.values() if not s.get("name_ru")]
    by_char = {}
    for s in left:
        by_char[s["char"]] = by_char.get(s["char"], 0) + 1
    print(f"без RU-названия: {len(left)} "
          f"(наборов {sum(1 for s in left if s['kind'] == 'outfit')}, "
          f"скинов персонажей {sum(1 for s in left if s['kind'] == 'coschar')}); "
          f"персонажей затронуто {len(by_char)}")
    if unmatched_pieces:
        print(f"  имён элементов, не найденных в Module:…/Pieces: {len(unmatched_pieces)}")
    print(f"одиночных предметов (FAKE_SKINS): {len(fakes)}")
    print(f"Записано: {out} ({os.path.getsize(out) // 1024} КБ)")
    return 0


if __name__ == "__main__":
    sys.exit(main(force="--force" in sys.argv))
