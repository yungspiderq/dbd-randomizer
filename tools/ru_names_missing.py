# -*- coding: utf-8 -*-
"""Дозаполнение русских названий наборов: CSV-шаблон и таблица ручных имён.

Зачем
-----
Русская вики покрывает не всё: в статьях «<Персонаж> (наборы одежды)» и
«<Персонаж> (кастомизация)» нет
* 111 «скинов персонажей» (Look-See, Krampus, Baba Yaga, Xenomorph Queen,
  Scooby-Doo и т.п.) — их на русской вики нет вообще;
* ~350 наборов (свежие коллекции 2024-2026, часть старых магазинных);
* дефолтных и «кровавых» наборов у большинства персонажей — их элементы на
  русской вики лежат под другими именами файлов, чем в Module:…/Pieces, поэтому
  связать их автоматически нельзя.

Выводить такие имена «правилом» нельзя: род и форма в русском клиенте не
выводятся из имени персонажа (реальные названия — «Кровавый Призрак», но
«Кровавая чума», «Окровавленная Лара Крофт» и «Чертов Алан Уэйк»), а дефолтный
набор не всегда называется именем персонажа. Поэтому недостающее заполняется
вручную — официальными именами из русского клиента игры.

Как пользоваться
----------------
    python tools/ru_names_missing.py --csv     # выгрузить шаблон (UTF-8 BOM, для Excel)
    # заполнить колонку name_ru в tools/skin_names_missing.csv
    python tools/ru_names_missing.py           # собрать tools/skin_names_manual.py
    python tools/resolve_skins.py              # пересобрать dbd_skins.py
    python smoke_test.py

`--check` печатает, сколько записей ещё без русского названия и у каких
персонажей. Заполнять можно частями: пустые строки CSV просто игнорируются,
а уже собранные имена из `skin_names_manual.py` не теряются (CSV
перегенерируется вместе с ними).
"""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

CSV_PATH = os.path.join(HERE, "skin_names_missing.csv")
OUT = os.path.join(HERE, "skin_names_manual.py")
COLUMNS = ("id", "char", "name_en", "kind", "rarity_ru", "file", "date", "name_ru")


def load_skins():
    import dbd_skins as SK
    return SK


def current_manual():
    if not os.path.exists(OUT):
        return {}
    ns = {}
    with open(OUT, encoding="utf-8") as fh:
        exec(compile(fh.read(), OUT, "exec"), ns)      # noqa: S102 — свой файл
    return {int(k): str(v) for k, v in (ns.get("SKIN_RU") or {}).items() if str(v).strip()}


def missing(SK, manual, keep_filled=False):
    """Записи без RU-названия. keep_filled=True — оставить уже заполненные вручную
    (чтобы перегенерация CSV не теряла работу)."""
    out = []
    for sid, info in sorted(SK.SKINS_BY_ID.items()):
        if info.get("name_ru"):
            continue
        if sid in manual and not keep_filled:
            continue
        out.append({
            "id": sid,
            "char": info.get("char", ""),
            "name_en": info.get("name", ""),
            "kind": "скин персонажа" if info.get("kind") == "coschar" else "набор одежды",
            "rarity_ru": info.get("rarity_ru", ""),
            "file": info.get("file", ""),
            "date": info.get("date", ""),
            "name_ru": manual.get(sid, ""),
        })
    out.sort(key=lambda r: (r["char"], r["kind"], r["id"]))
    return out


def write_csv(rows):
    # BOM — чтобы Excel сразу открывал кириллицу
    with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, delimiter=";")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return CSV_PATH


def read_simple_csv(path):
    """CSV из tools/ru_names_sheet.py: только колонки id и name_ru."""
    out = {}
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh, delimiter=";"):
            try:
                sid = int((row.get("id") or "").strip())
            except (TypeError, ValueError):
                continue
            name = (row.get("name_ru") or "").strip()
            if name:
                out[sid] = name
    return out


def read_csv():
    """Заполненные строки CSV. Пустая ячейка name_ru означает «имя убрано»."""
    if not os.path.exists(CSV_PATH):
        return None
    out = {}
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh, delimiter=";"):
            try:
                sid = int((row.get("id") or "").strip())
            except ValueError:
                continue
            name = (row.get("name_ru") or "").strip()
            if name:
                out[sid] = name
    return out


def write_manual(manual, SK):
    total = len(SK.SKINS_BY_ID)
    auto = sum(1 for i in SK.SKINS_BY_ID.values() if i.get("name_ru"))
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write('# -*- coding: utf-8 -*-\n')
        fh.write('"""Собрано tools/ru_names_missing.py из skin_names_missing.csv — '
                 'НЕ править вручную.\n\n')
        fh.write('Русские названия, которых нет на русской вики: id набора -> официальное\n')
        fh.write('название из русского клиента игры (скины персонажей, свежие коллекции,\n')
        fh.write('дефолтные и «кровавые» наборы).\n\n')
        fh.write('Порядок обновления: заполнить tools/skin_names_missing.csv ->\n')
        fh.write('python tools/ru_names_missing.py -> python tools/resolve_skins.py.\n"""\n\n')
        fh.write("SKIN_RU = {\n")
        for sid in sorted(manual):
            info = SK.SKINS_BY_ID.get(sid, {})
            fh.write(f"    {sid}: {manual[sid]!r},")
            if info:
                fh.write(f"  # {info.get('char', '')} · {info.get('name', '')}")
            fh.write("\n")
        fh.write("}\n")
    return total, auto


def main(argv):
    SK = load_skins()
    manual = current_manual()
    if "--check" in argv:
        rows = missing(SK, manual)
        print(f"всего записей: {len(SK.SKINS_BY_ID)}")
        print(f"с RU-названием (вики): {sum(1 for i in SK.SKINS_BY_ID.values() if i.get('name_ru'))}")
        print(f"с RU-названием (вручную): {len(manual)}")
        print(f"осталось заполнить: {len(rows)}")
        by_char = {}
        for r in rows:
            by_char[r["char"]] = by_char.get(r["char"], 0) + 1
        print("топ персонажей:", ", ".join(f"{c} ({n})" for c, n in
                                           sorted(by_char.items(), key=lambda x: -x[1])[:10]))
        kinds = {}
        for r in rows:
            kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
        print("по типам:", kinds)
        return 0

    # CSV — единственный источник ручных имён: заполненные строки становятся
    # именами, очищенные — удаляются (иначе отменить правку было нельзя).
    filled = read_csv()
    if filled is not None:
        manual = filled
    for a in argv:
        if a.startswith("--merge="):
            extra = read_simple_csv(a.split("=", 1)[1])
            manual.update(extra)
            print(f"из внешнего CSV добавлено имён: {len(extra)}")
    path = write_csv(missing(SK, manual, keep_filled=True))
    rows = missing(SK, manual)
    total, auto = write_manual(manual, SK)
    print(f"CSV-шаблон: {path} (строк к заполнению: {len(rows)})")
    print(f"{OUT}: имён {len(manual)}")
    print(f"покрытие: {auto} (вики) + {len(manual)} (вручную) = {auto + len(manual)} из {total}")
    if rows:
        print(f"осталось без RU-названия: {len(rows)} — заполните колонку name_ru в CSV "
              f"и запустите скрипт снова")
    print("Дальше:  python tools/resolve_skins.py")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
