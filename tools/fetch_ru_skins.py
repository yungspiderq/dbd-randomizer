# -*- coding: utf-8 -*-
"""Добывает РУССКИЕ названия наборов одежды с русской вики (Fandom).

Запуск:  python tools/fetch_ru_skins.py [--pages=N] [--only=Имя,Имя]
Сеть:    https://dead-by-daylight.fandom.com/ru/api.php
Результат: tools/skin_names_ru.py (таблица FILE_TO_RU) + кэш викитекста в
           tools/wiki_cache/ru/ (в .gitignore, поэтому повторный запуск добирает
           только недостающие страницы).

Зачем отдельный инструмент
--------------------------
RU-названий наборов нет ни в `Module:Datatable/Cosmetics` (wiki.gg, только
английский), ни в других открытых датасетах: русская вики хранит их в статьях
«<Персонаж> (наборы одежды)» (~98 страниц ручной разметки). Статья устроена
таблицами:

    |+ Нечаянный свидетель (глубокий разрыв 2)          <- РУССКОЕ имя набора
    |-
    | colspan="4" … | Однажды в глубоком детстве…        <- описание
    |-
    | rowspan="3" | [[File:WI_outfit_019_03.png|152px]] || …

то есть имя набора связано с **именем файла** `filename` из данных wiki.gg —
сопоставление точное, без привязки к порядку следования.

Fandom закрыт Cloudflare для «ботовых» User-Agent и для части дата-центров,
поэтому в песочнице/CI скрипт может получить 403 — это не ошибка кода:
запустите его на своей машине (`pip install -r requirements.txt` не нужен,
только стандартная библиотека). Страницы кэшируются, так что прерванный запуск
продолжается с места остановки.

После заполнения таблицы пересоберите базу:  python tools/resolve_skins.py
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
PAUSE = 0.4                       # вежливая пауза между запросами, c

# Имя персонажа в dbd_data.py -> заголовок статьи на русской вики, если он
# отличается (обычная статья «<Имя> (наборы одежды)» подразумевается).
TITLE_OVERRIDES = {
    "Аврора": "Аврора Стардоттир",
    # «Тень» (The Shape) на русской вики может называться по-другому —
    # fetch_titles покажет отсутствующие страницы, дополните таблицу.
}


def api(**kw):
    kw.setdefault("format", "json")
    kw.setdefault("formatversion", "2")
    url = RU_API + "?" + urllib.parse.urlencode(kw)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def title_for(ru_char):
    return f"{TITLE_OVERRIDES.get(ru_char, ru_char)} {SUFFIX}"


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
# разбор статьи
# ============================================================================
CAPTION_RE = re.compile(r"^\|\+\s*(.+?)\s*$", re.M)
OUTFIT_IMG_RE = re.compile(r"\[\[(?:File|Изображение|Файл):([^\]|#]+?\.png)", re.I)


def clean_caption(text):
    """Заголовок таблицы -> имя набора: без вики-разметки и лишних пробелов."""
    text = re.sub(r"\[\[(?:File|Изображение|Файл):[^\]]*\]\]", "", text, flags=re.I)
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", text)
    text = text.replace("'''", "").replace("''", "")
    text = text.replace("\xa0", " ").replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", text).strip()


def parse_page(wikitext):
    """{имя файла (нижний регистр): (исходное имя файла, RU-название набора)}."""
    out = {}
    blocks = wikitext.split("{|")
    for block in blocks[1:]:
        block = block.split("|}")[0]
        cap = CAPTION_RE.search(block)
        if not cap:
            continue
        name = clean_caption(cap.group(1))
        if not name or len(name) > 90:
            continue
        img = OUTFIT_IMG_RE.search(block)
        if not img:
            continue
        fn = img.group(1).strip()
        if "_outfit" not in fn.lower() and not re.search(r"_outfit\d*", fn, re.I):
            continue                                   # не набор (иконка/печать)
        out.setdefault(fn.lower(), (fn, name))
    return out


def load_existing():
    """FILE_TO_RU из уже сгенерированного файла (чтобы не терять добавленное)."""
    path = os.path.join(HERE, "skin_names_ru.py")
    if not os.path.exists(path):
        return {}, {}
    ns = {}
    with open(path, encoding="utf-8") as fh:
        exec(compile(fh.read(), path, "exec"), ns)      # noqa: S102 — свой файл
    return dict(ns.get("FILE_TO_RU") or {}), dict(ns.get("PAGE_STATS") or {})


def write_table(file_to_ru, page_stats):
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write('# -*- coding: utf-8 -*-\n')
        fh.write('"""Сгенерировано tools/fetch_ru_skins.py — НЕ править вручную.\n\n')
        fh.write('Русские названия наборов одежды: имя файла превью (нижний регистр)\n')
        fh.write('-> название из русской вики (dead-by-daylight.fandom.com/ru, статьи\n')
        fh.write('«<Персонаж> (наборы одежды)», перевод взят из официальной Steam-версии).\n\n')
        fh.write('Сопоставление по имени файла (filename из Module:Datatable/Cosmetics),\n')
        fh.write('поэтому порядок записей и состав статей не важны. Пустая/частичная\n')
        fh.write('таблица — не ошибка: resolve_skins.py оставит английские имена.\n"""\n\n')
        fh.write("# сколько наборов найдено на каждой странице (для отчёта)\n")
        fh.write("PAGE_STATS = {\n")
        for title in sorted(page_stats):
            fh.write(f"    {title!r}: {page_stats[title]},\n")
        fh.write("}\n\n")
        fh.write("FILE_TO_RU = {\n")
        for key in sorted(file_to_ru):
            fh.write(f"    {key!r}: {file_to_ru[key]!r},\n")
        fh.write("}\n")


def main(argv):
    only, limit = None, None
    for a in argv:
        if a.startswith("--only="):
            only = set(x.strip() for x in a.split("=", 1)[1].split(",") if x.strip())
        elif a.startswith("--pages="):
            limit = int(a.split("=", 1)[1])
    chars = [c for c in all_characters() if not only or c in only]
    titles = {c: title_for(c) for c in chars}
    file_to_ru, page_stats = load_existing()
    cached_pages = {}
    if os.path.isdir(CACHE):
        for c, t in titles.items():
            p = cache_path(t)
            if os.path.exists(p) and os.path.getsize(p) > 0:
                cached_pages[t] = p

    print(f"персонажей: {len(chars)} (в кэше статей: {len(cached_pages)})")
    try:
        found = fetch_titles([t for t in titles.values() if t not in cached_pages])
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            raise SystemExit(
                "Fandom ответил 403: Cloudflare не пускает этот User-Agent/IP "
                "(песочница/CI). Запустите скрипт на своей машине — кэш в "
                "tools/wiki_cache/ru/ позволит продолжить с места остановки.")
        raise
    all_titles = dict(found)
    for t, p in cached_pages.items():
        all_titles.setdefault(t, None)

    missing = sorted(t for c, t in titles.items()
                     if t not in found and t not in cached_pages)
    todo = []
    for c, t in titles.items():
        if t in cached_pages:
            todo.append((t, None, cached_pages[t]))
        elif t in found:
            todo.append((t, found[t], None))
    if limit:
        todo = [x for x in todo if x[2] is None][:limit] + [x for x in todo if x[2]]
    print(f"статей на вики: {len(found)}, к скачиванию: "
          f"{sum(1 for x in todo if x[2] is None)}, из кэша: {sum(1 for x in todo if x[2])}")
    if missing:
        print("НЕТ статьи на русской вики (дополните TITLE_OVERRIDES, если имя другое):")
        for t in missing:
            print("   -", t)

    for title, pageid, path in todo:
        try:
            if path:
                with open(path, encoding="utf-8") as fh:
                    wt = fh.read()
            else:
                wt = fetch_wikitext(title, pageid)
        except Exception as exc:
            print(f"  ! {title}: {exc}")
            continue
        pairs = parse_page(wt)
        for key, (_fn, name) in pairs.items():
            file_to_ru[key] = name
        page_stats[title] = len(pairs)
        print(f"  {title}: наборов {len(pairs)} (всего в таблице {len(file_to_ru)})")
        write_table(file_to_ru, page_stats)      # пишем после каждой страницы

    write_table(file_to_ru, page_stats)
    print(f"\nЗаписано: {OUT}")
    print(f"RU-названий: {len(file_to_ru)}; страниц разобрано: {len(page_stats)}")
    print("Дальше:  python tools/resolve_skins.py   (пересоберёт dbd_skins.py с name_ru)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
