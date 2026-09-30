# -*- coding: utf-8 -*-
"""Добывает РУССКИЕ названия наборов одежды с русской вики (Fandom).

Запуск:  python tools/fetch_ru_skins.py [--pages=N] [--only=Имя,Имя]
Сеть:    https://dead-by-daylight.fandom.com/ru/api.php
Результат: tools/skin_names_ru.py (FILE_TO_RU, PIECE_FILE_TO_RU, PAGE_STATS)
           + кэш викитекста в tools/wiki_cache/ru/ (в .gitignore, поэтому
           повторный запуск докачивает только недостающие статьи).

Зачем отдельный инструмент
--------------------------
RU-названий наборов нет ни в `Module:Datatable/Cosmetics` (wiki.gg, только
английский), ни в других открытых датасетах: русская вики хранит их в статьях
«<Персонаж> (наборы одежды)» (~98 страниц ручной разметки, перевод взят из
официальной Steam-версии). Статья устроена таблицами:

    |+ Нечаянный свидетель (глубокий разрыв 2)          <- РУССКОЕ имя набора
    |-
    | colspan="4" … | Однажды в глубоком детстве…        <- описание
    |-
    | rowspan="3" | [[File:WI_outfit_019_03.png|152px]] || …

то есть имя набора связано с **именем файла** `filename` из данных wiki.gg —
сопоставление точное, без привязки к порядку следования.

Второй источник — статьи «<Персонаж> (кастомизация)»: там лежат
1. редкие наборы, которых нет в статьях про одежду (например консольный
   «Игра окончена» у Охотника — раздел «Приставка»);
2. отдельные элементы внешности (голова/маска, торс, ноги, оружие) с РУССКИМИ
   именами и файлами. По ним `tools/resolve_skins.py` достраивает RU-названия
   наборов, которых в статьях про одежду нет вовсе:
   * дефолтный набор называется как его голова/маска («The Trapper» -> «Эван»);
   * «кровавый» — как кровавая версия элемента («Bloody Trapper» -> «Кровавый Эван»);
   * у новых персонажей (Аврора, Правосудие) вместо картинок стоит `Missing.png`,
     поэтому сопоставить набор по файлу нельзя — выручают имена элементов.

Fandom закрыт Cloudflare для «ботовых» User-Agent и для части дата-центров,
поэтому в песочнице/CI скрипт может получить 403 — это не ошибка кода: он
отработает по кэшу и подскажет, где докачать остальное (на своей машине или
через workflow `.github/workflows/fetch-ru-skins.yml`, который прикладывает
результат артефактом).

После заполнения таблиц пересоберите базу:  python tools/resolve_skins.py
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import dbd_data as DATA                                          # noqa: E402

RU_API = "https://dead-by-daylight.fandom.com/ru/api.php"
UA = {"User-Agent": "DBDRandomizer/2.11 (RU skin names; https://github.com/"
                    "yungspiderq/dbd-randomizer)",
      "Accept": "application/json",
      "Accept-Language": "ru,en;q=0.8"}
CACHE = os.path.join(ROOT, "tools", "wiki_cache", "ru")
OUT = os.path.join(HERE, "skin_names_ru.py")
SUFFIX = "(наборы одежды)"
SUFFIX_CUSTOM = "(кастомизация)"
PAUSE = 0.4                       # вежливая пауза между запросами, c

# Имя персонажа в dbd_data.py -> заголовок статьи на русской вики, если он
# отличается (обычная статья «<Имя> (наборы одежды)» подразумевается).
TITLE_OVERRIDES = {
    "Аврора": "Аврора Стардоттир",
}


def api(**kw):
    kw.setdefault("format", "json")
    kw.setdefault("formatversion", "2")
    url = RU_API + "?" + urllib.parse.urlencode(kw)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def title_for(ru_char, suffix=SUFFIX):
    return f"{TITLE_OVERRIDES.get(ru_char, ru_char)} {suffix}"


def all_characters():
    return sorted(set(DATA.KILLERS) | set(DATA.SURVIVORS))


def fetch_titles(titles):
    """Какие заголовки существуют: {заголовок: pageid} (батчи по 50)."""
    found = {}
    for i in range(0, len(titles), 50):
        chunk = titles[i:i + 50]
        d = api(action="query", titles="|".join(chunk), prop="revisions", rvprop="ids")
        for p in (d.get("query") or {}).get("pages", []):
            if "missing" not in p:
                found[p["title"]] = p["pageid"]
        time.sleep(PAUSE)
    return found


def cache_path(title):
    safe = re.sub(r"[^\wа-яА-ЯёЁ .()-]", "_", title)
    return os.path.join(CACHE, safe + ".wiki")


def fetch_wikitext(title, pageid):
    path = cache_path(title)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    d = api(action="parse", pageid=pageid, prop="wikitext")
    wt = d["parse"]["wikitext"]
    os.makedirs(CACHE, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(wt)
    time.sleep(PAUSE)
    return wt


# ============================================================================
# разбор статей
# ============================================================================
CAPTION_RE = re.compile(r"^\|\+\s*(.+?)\s*$", re.M)
IMG_RE = re.compile(r"\[\[(?:File|Изображение|Файл):\s*([^\]|#]+?\.png)", re.I)
OUTFIT_IMG_RE = re.compile(
    r"\[\[(?:File|Изображение|Файл):\s*([^\]|#]*?_outfit[^\]|#]*?\.png)", re.I)
ROW_SPLIT_RE = re.compile(r"^\|-$", re.M)
# строка элемента: «|[[File:X.png|96px]]» + «|Имя» + «|Описание» (разделители —
# перевод строки или «||»). Картинку вырезаем ЦЕЛИКОМ: внутри неё есть свой «|»
# (размер), поэтому простое разбиение по «|» дало бы «96px]]» вместо имени.
PIECE_ROW_RE = re.compile(
    r"^\|\s*\[\[(?:File|Изображение|Файл):\s*([^\]|#]+?\.png)[^\]]*\]\]\s*"
    r"(?:\|\||\|)\s*(.+)$", re.I | re.S)
# заглушки русской вики: такой файл не указывает на конкретный набор/элемент
PLACEHOLDER_FILES = {"missing.png", "pechat.png", "missing_file.png", "nocover.png"}


def strip_markup(text):
    """Убирает шаблоны/ссылки/жирный — остаётся только имя."""
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = re.sub(r"\[\[(?:File|Изображение|Файл):[^\]]*\]\]", "", text, flags=re.I)
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", text)
    text = text.replace("'''", "").replace("''", "").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


clean_caption = strip_markup                     # прежнее имя для совместимости


def parse_page_blocks(wikitext):
    """[(RU-название набора, имя файла набора или None)] — по порядку в статье.

    Нюансы разметки русской вики:
    * в заголовке таблицы бывает «печать» — `|+ Генри Крил [[File:Pechat.png|32px]]`,
      поэтому файл набора ищем ТОЛЬКО в теле таблицы (после строки `|+`);
    * файл набора — единственный с `_outfit` в имени (остальные картинки строки:
      голова/торос/ноги/оружие), берём первый такой;
    * у новых персонажей вместо картинок стоит заглушка `Missing.png` — по файлу
      набор не определить, возвращаем None (дальше работает цепочка по элементам).
    """
    blocks = []
    for block in wikitext.split("{|")[1:]:
        block = block.split("|}")[0]
        cap = CAPTION_RE.search(block)
        if not cap:
            continue
        name = strip_markup(cap.group(1))
        if not name or len(name) > 90:
            continue
        body = block[cap.end():]                       # печать из заголовка не берём
        fn = None
        m = OUTFIT_IMG_RE.search(body)
        if m:
            cand = m.group(1).strip()
            if cand.lower() not in PLACEHOLDER_FILES:
                fn = cand
        blocks.append((name, fn))
    return blocks


def parse_page(wikitext):
    """{имя файла набора (нижний регистр): (исходное имя, RU-название)}."""
    out = {}
    for name, fn in parse_page_blocks(wikitext):
        if fn:
            out.setdefault(fn.lower(), (fn, name))
    return out


def parse_pieces_page(wikitext):
    """{имя файла элемента (нижний регистр): RU-имя элемента}.

    Таблицы элементов НЕ имеют подписи `|+` и выглядят так:

        |'''Иконка'''
        |'''Название'''
        |'''Описание'''
        |-
        |[[File:Trapper_Head01.png|96px]]
        |Эван
        |Искривленная бездушная маска скрывает лицо владельца…

    Таблицы с подписью — это наборы, их разбирает parse_page_blocks.
    """
    out = {}
    for block in wikitext.split("{|")[1:]:
        block = block.split("|}")[0]
        if CAPTION_RE.search(block):
            continue                                   # это набор, а не элемент
        for row in ROW_SPLIT_RE.split(block)[1:]:
            m = PIECE_ROW_RE.match(row.strip())
            if not m:
                continue
            fn = m.group(1).strip()
            if fn.lower() in PLACEHOLDER_FILES:
                continue
            # имя — первая ячейка после картинки: режем по «||», переводу строки
            # или одиночному «|», которые НЕ внутри [[…]]/{{…}}
            rest = m.group(2)
            name = strip_markup(re.split(r"\|\||\n\s*\||\|", rest, maxsplit=1)[0])
            if not name or len(name) > 80:
                continue
            out.setdefault(fn.lower(), name)
    return out


# ============================================================================
# таблица результатов
# ============================================================================
def load_existing():
    """Уже собранные таблицы — чтобы не терять добавленное и работать по частям."""
    if not os.path.exists(OUT):
        return {}, {}, {}
    ns = {}
    with open(OUT, encoding="utf-8") as fh:
        exec(compile(fh.read(), OUT, "exec"), ns)      # noqa: S102 — свой файл
    return (dict(ns.get("FILE_TO_RU") or {}), dict(ns.get("PAGE_STATS") or {}),
            dict(ns.get("PIECE_FILE_TO_RU") or {}))


def write_table(file_to_ru, page_stats, piece_to_ru):
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write('# -*- coding: utf-8 -*-\n')
        fh.write('"""Сгенерировано tools/fetch_ru_skins.py — НЕ править вручную.\n\n')
        fh.write('Русские названия наборов одежды и элементов внешности: имя файла\n')
        fh.write('(нижний регистр) -> название из русской вики\n')
        fh.write('(dead-by-daylight.fandom.com/ru, статьи «<Персонаж> (наборы одежды)»\n')
        fh.write('и «<Персонаж> (кастомизация)», перевод взят из официальной Steam-версии).\n\n')
        fh.write('Сопоставление по имени файла (filename из Module:Datatable/Cosmetics и\n')
        fh.write('Module:Datatable/Cosmetics/Pieces), поэтому порядок записей и состав\n')
        fh.write('статей не важны. Пустая/частичная таблица — не ошибка: resolve_skins.py\n')
        fh.write('оставит английские имена там, где русских не нашлось.\n"""\n\n')
        fh.write("# сколько наборов найдено на каждой странице (для отчёта)\n")
        fh.write("PAGE_STATS = {\n")
        for title in sorted(page_stats):
            fh.write(f"    {title!r}: {page_stats[title]},\n")
        fh.write("}\n\n")
        fh.write("# наборы: имя файла превью -> RU-название\n")
        fh.write("FILE_TO_RU = {\n")
        for key in sorted(file_to_ru):
            fh.write(f"    {key!r}: {file_to_ru[key]!r},\n")
        fh.write("}\n\n")
        fh.write("# элементы внешности (статьи «(кастомизация)»): имя файла -> RU-имя.\n")
        fh.write("# Нужны, чтобы достроить RU-названия наборов, которых нет в статьях\n")
        fh.write("# «(наборы одежды)»: дефолтный набор называется как его голова/маска,\n")
        fh.write("# «кровавый» — как её кровавая версия, а у новых персонажей (Аврора,\n")
        fh.write("# Правосудие) на русской вики вместо картинок стоит Missing.png.\n")
        fh.write("PIECE_FILE_TO_RU = {\n")
        for key in sorted(piece_to_ru):
            fh.write(f"    {key!r}: {piece_to_ru[key]!r},\n")
        fh.write("}\n")


# ============================================================================
# main
# ============================================================================
def read_cached(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def process(path, kind, file_to_ru, piece_to_ru, page_stats, title):
    wt = read_cached(path)
    if kind == "custom":
        outfits, pieces = parse_page(wt), parse_pieces_page(wt)
        for key, (_fn, name) in outfits.items():
            file_to_ru.setdefault(key, name)
        for key, name in pieces.items():
            piece_to_ru.setdefault(key, name)
        page_stats[title] = len(outfits)
        return len(outfits), len(pieces)
    pairs = parse_page(wt)
    for key, (_fn, name) in pairs.items():
        file_to_ru[key] = name
    page_stats[title] = len(pairs)
    return len(pairs), 0


def main(argv):
    only, limit = None, None
    for a in argv:
        if a.startswith("--only="):
            only = set(x.strip() for x in a.split("=", 1)[1].split(",") if x.strip())
        elif a.startswith("--pages="):
            limit = int(a.split("=", 1)[1])
    chars = [c for c in all_characters() if not only or c in only]

    # что хотим снять: статья про одежду + статья про кастомизацию каждого персонажа
    wanted = {}                                    # title -> kind
    for c in chars:
        wanted[title_for(c)] = "outfits"
        wanted[title_for(c, SUFFIX_CUSTOM)] = "custom"

    file_to_ru, page_stats, piece_to_ru = load_existing()

    # что уже лежит в кэше — сеть для этого не нужна
    cached = {t: cache_path(t) for t in wanted
              if os.path.exists(cache_path(t)) and os.path.getsize(cache_path(t)) > 0}
    todo_local = [(t, None, cached[t], wanted[t]) for t in sorted(cached)]

    rest = [t for t in wanted if t not in cached]
    found, offline = {}, False
    if rest:
        try:
            found = fetch_titles(rest)
        except urllib.error.HTTPError as exc:
            if exc.code != 403:
                raise
            offline = True
            print("Fandom ответил 403 (Cloudflare не пускает этот IP/User-Agent) — "
                  "работаю только по кэшу. Остальное докачает запуск на своей машине "
                  "или workflow .github/workflows/fetch-ru-skins.yml.")
        except Exception as exc:                            # нет сети — не беда
            offline = True
            print(f"вики недоступна ({exc}) — работаю только по кэшу.")

    todo_remote = [(t, found[t], None, wanted[t]) for t in sorted(found)]
    if limit:
        todo_remote = todo_remote[:limit]
    missing = ([] if offline else
               sorted(t for t in wanted if t not in found and t not in cached))

    print(f"персонажей: {len(chars)}; статей в кэше: {len(cached)}; "
          f"найдено на вики: {len(found)}; к скачиванию: {len(todo_remote)}")
    if missing:
        print("НЕТ на русской вики (дополните TITLE_OVERRIDES, если заголовок другой):")
        for t in missing:
            print("   -", t)

    done = 0
    for title, pageid, path, kind in todo_local + todo_remote:
        try:
            if path is None:
                path = cache_path(title)
                fetch_wikitext(title, pageid)
            n_out, n_pieces = process(path, kind, file_to_ru, piece_to_ru,
                                      page_stats, title)
        except Exception as exc:
            print(f"  ! {title}: {exc}")
            continue
        done += 1
        if done % 10 == 0 or kind == "custom":
            print(f"  {title}: наборов {n_out}, элементов {n_pieces} "
                  f"(всего RU-названий {len(file_to_ru)}, элементов {len(piece_to_ru)})")
        write_table(file_to_ru, page_stats, piece_to_ru)   # пишем после каждой страницы

    write_table(file_to_ru, page_stats, piece_to_ru)
    print(f"\nЗаписано: {OUT}")
    print(f"RU-названий наборов: {len(file_to_ru)}; RU-имён элементов: {len(piece_to_ru)}; "
          f"статей разобрано: {len(page_stats)}")
    zero = [t for t, n in page_stats.items() if n == 0]
    if zero:
        print("статьи, где наборы не нашлись (Missing.png / только элементы): "
              + ", ".join(zero))
    print("Дальше:  python tools/resolve_skins.py   (пересоберёт dbd_skins.py с name_ru)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
