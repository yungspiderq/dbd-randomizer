# -*- coding: utf-8 -*-
"""Генерирует блок CLASSES_2V8 в dbd_data.py — классы режима «2 против 8».

Запуск:  python tools/resolve_classes.py [--force]
Сеть:    https://dead-by-daylight.fandom.com/ru/api.php
         (кэш викитекста в tools/wiki_cache/ru_classes/ — коммитится, поэтому
         повторный запуск сети не требует вовсе)

Источник
--------
Категория «2 против 8» на русской вики: 9 статей «<Класс> (класс)» —
Беглец, Проводник, Медик, Разведчик, Факельщик (выжившие) и Громила,
Наводящий ужас, Наемный убийца, Тень (убийцы). Из каждой статьи берутся:
* русское имя класса и английское (`'''Беглец''' (англ. "''Escapist''")`);
* сторона — по фразе «в роли [[Выжившие|выжившего]]» / «в роли [[Убийца|убийцы]]»;
* иконка класса — `{{Инфобокс_навык|image1 = [[File:…]]}}`;
* НАБОР НАВЫКОВ ПОСЛЕДНЕГО «появления»: у режима две итерации
  («Первое появление» 2024 года и «Второе появление» 2026-го), у части классов
  раздел один. Берётся последний по порядку раздел — это текущий вид класса.

Fandom закрывает Cloudflare доступ для дата-центров, поэтому при 403 скрипт
работает по кэшу и подсказывает запустить GitHub Actions
(`.github/workflows/fetch-2v8-classes.yml`) или выполнить запуск на своей машине.

Тексты навыков приводятся ДОСЛОВНО по русской вики: часть описаний там не
переведена (статьи помечены категорией «Проблема локализации») — такие куски
остаются английскими, как в источнике.
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

RU_API = "https://dead-by-daylight.fandom.com/ru/api.php"
UA = {"User-Agent": "DBDRandomizer/2.12 (2v8 classes; https://github.com/"
                    "yungspiderq/dbd-randomizer)",
      "Accept": "application/json", "Accept-Language": "ru,en;q=0.8"}
CACHE = os.path.join(ROOT, "tools", "wiki_cache", "ru_classes")
CATEGORY = "Категория:2 против 8"
DATA_PY = os.path.join(ROOT, "dbd_data.py")
ICONS_PY = os.path.join(ROOT, "dbd_icons.py")
ICONS_BEGIN = "# === CLASS_ICONS BEGIN (tools/resolve_classes.py) ==="
ICONS_END = "# === CLASS_ICONS END ==="
MARK_BEGIN = "# === CLASSES_2V8 BEGIN (сгенерировано tools/resolve_classes.py) ==="
MARK_END = "# === CLASSES_2V8 END ==="
PAUSE = 0.4


def api(**kw):
    kw.setdefault("format", "json")
    kw.setdefault("formatversion", "2")
    url = RU_API + "?" + urllib.parse.urlencode(kw)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


# ============================================================================
# разбор статьи
# ============================================================================
APPEARANCE_RE = re.compile(r"^==(Первое появление|Второе появление|Третье появление)==\s*$", re.M)
CLASS_ICON_RE = re.compile(r"image1\s*=[\s\S]{0,120}?(?:File|Файл):\s*([^\]|#\n]+?\.png)", re.I)
HEAD_RE = re.compile(r"'''([^']+)'''\s*\(англ\.\s*[\"']{0,2}''?([^\"']+)''?[\"']{0,2}\)")
ROW_SPLIT_RE = re.compile(r"^\|-$", re.M)
IMG_RE = re.compile(r"\[\[(?:File|Файл):\s*([^\]|#]+?\.png)", re.I)


def strip_markup(text):
    text = re.sub(r"\{\{QColor\|([^{}]*)\}\}", r"\1", text)
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = re.sub(r"\[\[(?:File|Файл):[^\]]*\]\]", "", text, flags=re.I)
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", text)
    text = text.replace("'''", "").replace("''", "").replace("\xa0", " ")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    # маркеры «*» в начале строк убираем: в карточке они превращаются в «• »
    text = re.sub(r"(?m)^\s*\*\s*", "", text)
    return re.sub(r"\n{2,}", "\n", text).strip()


def parse_article(wikitext):
    """(ru, en, side, icon, [навыки последнего «появления»]) или None."""
    head = HEAD_RE.search(wikitext)
    if not head:
        return None
    ru = head.group(1).strip()
    en = head.group(2).strip().strip("'\"")
    low = wikitext[:1200].lower()
    if "в роли" in low and "убийц" in low[low.index("в роли"):low.index("в роли") + 80]:
        side = "KILLER"
    elif "выживш" in low:
        side = "SURVIVOR"
    else:
        side = "SURVIVOR" if "[[Выжившие|" in wikitext else "KILLER"
    icon = CLASS_ICON_RE.search(wikitext)
    icon = icon.group(1).strip() if icon else ""

    # последнее «появление» = текущий набор навыков класса
    marks = list(APPEARANCE_RE.finditer(wikitext))
    if not marks:
        return ru, en, side, icon, []
    start = marks[-1].end()
    end = len(wikitext)
    for m in re.finditer(r"^==[^=]", wikitext[start:], re.M):
        end = start + m.start()
        break
    block = wikitext[start:end]

    skills = []
    for tbl in block.split("{|")[1:]:
        tbl = tbl.split("|}")[0]
        for row in ROW_SPLIT_RE.split(tbl):
            row = row.strip()
            if not row.startswith("|"):
                continue
            img = IMG_RE.search(row)
            if not img:
                continue
            cells = [c.strip() for c in re.split(r"(?m)^\|", row) if c.strip()]
            if len(cells) < 3:
                continue
            role = strip_markup(cells[1])
            text = strip_markup("\n".join(cells[2:]))
            skills.append({"role": role, "icon": img.group(1).strip(), "text": text})
    return ru, en, side, icon, skills


# ============================================================================
# сеть / кэш
# ============================================================================
def cache_path(title):
    return os.path.join(CACHE, re.sub(r"[^\wа-яА-ЯёЁ .()-]", "_", title) + ".wiki")


def class_pages():
    path = os.path.join(CACHE, "_pages.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    d = api(action="query", list="categorymembers", cmtitle=CATEGORY, cmlimit="100")
    titles = sorted(p["title"] for p in d["query"]["categorymembers"]
                    if p["title"].endswith("(класс)"))
    os.makedirs(CACHE, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(titles, fh, ensure_ascii=False, indent=1)
    return titles


def wikitext(title, force=False):
    path = cache_path(title)
    if os.path.exists(path) and os.path.getsize(path) > 0 and not force:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    d = api(action="parse", page=title, prop="wikitext")
    wt = d["parse"]["wikitext"]
    os.makedirs(CACHE, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(wt)
    time.sleep(PAUSE)
    return wt


def icon_urls(filenames):
    """{имя файла: абсолютный URL} — иконки классов и навыков лежат на RU-вики."""
    path = os.path.join(CACHE, "_icons.json")
    cached = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                cached = json.load(fh)
        except (OSError, ValueError):
            cached = {}
    todo = [f for f in dict.fromkeys(filenames) if f and f not in cached]
    for i in range(0, len(todo), 25):
        chunk = todo[i:i + 25]
        try:
            d = api(action="query", titles="|".join("File:" + f for f in chunk),
                    prop="imageinfo", iiprop="url")
        except Exception as exc:
            print(f"  ! не удалось получить URL иконок: {exc}")
            break
        pages = {p["title"]: p for p in (d.get("query") or {}).get("pages", [])}
        for n in (d.get("query") or {}).get("normalized", []):
            if n["to"] in pages:
                pages[n["from"]] = pages[n["to"]]
        for f in chunk:
            p = pages.get("File:" + f) or pages.get("Файл:" + f.replace("_", " "))
            info = (p or {}).get("imageinfo") or [{}]
            cached[f] = info[0].get("url") or ""
    if todo:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(cached, fh, ensure_ascii=False, indent=1, sort_keys=True)
    return cached


# ============================================================================
# запись в dbd_data.py
# ============================================================================
def build_block(classes, urls):
    lines = [MARK_BEGIN,
             '# Классы режима «2 против 8» (русские названия и описания — дословно из',
             '# статей русской вики «<Класс> (класс)», категория «2 против 8»;',
             '# часть описаний на вики не переведена — такие куски оставлены английскими).',
             '# icon/url — абсолютные адреса картинок на RU-вики: ассеты Behaviour,',
             '# в репозитории не хранятся (см. IconStore).',
             'CLASSES_2V8 = {',
             '    "SURVIVOR": [', ]

    def emit(entry, indent):
        pad = " " * indent
        out = [f'{pad}{{']
        out.append(f'{pad}    "ru": {entry["ru"]!r}, "en": {entry["en"]!r},')
        out.append(f'{pad}    "icon": {entry["icon"]!r}, "url": {entry["url"]!r},')
        out.append(f'{pad}    "skills": [')
        for sk in entry["skills"]:
            out.append(f'{pad}        {{"role": {sk["role"]!r}, "icon": {sk["icon"]!r},')
            out.append(f'{pad}         "url": {sk["url"]!r}, "text": {sk["text"]!r}}},')
        out.append(f'{pad}    ],')
        out.append(f'{pad}}},')
        return out

    for side in ("SURVIVOR", "KILLER"):
        for entry in classes[side]:
            lines += emit(entry, 8)
        if side == "SURVIVOR":
            lines += ['    ],', '    "KILLER": [']
    lines += ['    ],', '}', MARK_END]
    return "\n".join(lines) + "\n"


def write_block(block):
    with open(DATA_PY, encoding="utf-8") as fh:
        src = fh.read()
    if MARK_BEGIN in src:
        start = src.index(MARK_BEGIN)
        end = src.index(MARK_END) + len(MARK_END)
        src = src[:start] + block.rstrip("\n") + src[end:]
    else:
        src = src.rstrip("\n") + "\n\n\n" + block
    with open(DATA_PY, "w", encoding="utf-8") as fh:
        fh.write(src)


def write_class_icons(classes):
    """Перезаписывает блок CLASS_ICONS в dbd_icons.py (ключ -> абсолютный URL).

    Карта держится отдельно от PERK_ICONS/ADDON_ICONS, потому что иконки классов
    есть только на русской вики: IconStore понимает абсолютные URL и кэширует их
    как обычные картинки. Блок перезаписывается целиком — руками его править не
    нужно (иначе данные и иконки разъезжаются, как было с SelfSufficient).
    """
    rows, seen = [], set()
    for side in ("SURVIVOR", "KILLER"):
        for entry in classes[side]:
            if entry.get("url"):
                rows.append(f"    'class:{entry['ru']}': {entry['url']!r},")
            for sk in entry["skills"]:
                fn = sk.get("icon") or ""
                if fn and sk.get("url") and fn not in seen:
                    seen.add(fn)
                    rows.append(f"    'classskill:{fn}': {sk['url']!r},")
    block = "\n".join([
        ICONS_BEGIN,
        "# Иконки классов режима «2 против 8» и их навыков: ключ -> абсолютный URL",
        "# русской вики (на wiki.gg этих файлов нет). Ключи:",
        '#   "class:<RU имя класса>"   — иконка класса',
        '#   "classskill:<имя файла>"  — иконка навыка класса',
        "CLASS_ICONS = {"] + rows + ["}", ICONS_END]) + "\n"
    with open(ICONS_PY, encoding="utf-8") as fh:
        src = fh.read()
    if ICONS_BEGIN in src:
        start = src.index(ICONS_BEGIN)
        end = src.index(ICONS_END) + len(ICONS_END)
        src = src[:start] + block.rstrip("\n") + src[end:]
    else:
        src = src.rstrip("\n") + "\n\n\n" + block
    with open(ICONS_PY, "w", encoding="utf-8") as fh:
        fh.write(src)
    return len(rows)


def main(argv):
    force = "--force" in argv
    try:
        titles = class_pages()
    except urllib.error.HTTPError as exc:
        if exc.code != 403:
            raise
        cached = os.path.join(CACHE, "_pages.json")
        if not os.path.exists(cached):
            raise SystemExit("Fandom ответил 403 и кэша нет: запустите на своей машине "
                             "или через Actions → fetch-2v8-classes.")
        with open(cached, encoding="utf-8") as fh:
            titles = json.load(fh)
        print("Fandom ответил 403 — работаю по кэшу.")
    except Exception as exc:
        raise SystemExit(f"Не удалось получить список статей: {exc}")

    classes = {"SURVIVOR": [], "KILLER": []}
    icons = []
    offline = 0
    for title in titles:
        path = cache_path(title)
        if not force and os.path.exists(path) and os.path.getsize(path) > 0:
            wt = open(path, encoding="utf-8").read()
        else:
            try:
                wt = wikitext(title, force)
            except urllib.error.HTTPError as exc:
                if exc.code == 403:
                    offline += 1
                    continue
                raise
        parsed = parse_article(wt)
        if not parsed:
            print(f"  ! {title}: не разобрался заголовок класса")
            continue
        ru, en, side, icon, skills = parsed
        icons += [icon] + [s["icon"] for s in skills]
        classes[side].append({"ru": ru, "en": en, "icon": icon, "url": "",
                              "skills": skills})
        print(f"  {title}: {ru} ({en}), {side}, навыков {len(skills)}")
    if offline:
        print(f"  (403 на {offline} статьях — нужен запуск на машине/в Actions)")

    try:
        urls = icon_urls(icons)
    except Exception as exc:
        print(f"  ! URL иконок недоступны ({exc}) — останутся пустыми")
        urls = {}
    lower = {k.lower(): v for k, v in urls.items() if v}

    def url_of(fn):
        """Имя файла в статье и в кэше может отличаться регистром."""
        return urls.get(fn) or lower.get((fn or "").lower(), "")

    n_icon = 0
    for side in classes:
        for entry in classes[side]:
            entry["url"] = url_of(entry["icon"])
            n_icon += bool(entry["url"])
            for sk in entry["skills"]:
                sk["url"] = url_of(sk["icon"])
                n_icon += bool(sk["url"])

    total = sum(len(v) for v in classes.values())
    write_block(build_block(classes, urls))
    n_icons = write_class_icons(classes)
    print(f"\nклассов: {total} (выживших {len(classes['SURVIVOR'])}, "
          f"убийц {len(classes['KILLER'])}), иконок с URL: {n_icon}")
    print(f"Записано: {DATA_PY} (блок CLASSES_2V8); "
          f"{ICONS_PY} (CLASS_ICONS: {n_icons})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
