"""Offline build analysis and complete searchable catalog over the existing DB.

Rules are curated, not win-rate predictions. Unclassified perks remain neutral.
"""
from collections import Counter
from itertools import combinations

from perk_cards import perk_info

GROUPS = {
    "SURVIVOR": {
        "Истощение": ("Спринтер", "Гибкость", "Ловкое приземление", "Крепкий орешек", "На волю", "Драматургия", "Ударный забег"),
        "Ремонт": ("Дежавю", "Прояви себя", "Устойчивость", "Потенциальная энергия", "Техник", "Полная сосредоточенность", "Выдержка"),
        "Лечение": ("Познания в ботанике", "Сам себе доктор", "Сострадание", "Эмпатическая связь", "Мы справимся", "Отчаянные меры", "Самоучка", "Дар: круг исцеления"),
        "Скрытность": ("Быстрый и тихий", "Железная воля", "Городской бег", "Легковес", "Искажение", "Дар: уход в тень", "Спокойствие духа", "Легкоступ"),
        "Спасение": ("Одолженное время", "Нянька", "Освобождение", "Решающий удар", "Ради людей", "Мы будем жить вечно"),
        "Финал": ("Адреналин", "Надежда", "Проснись", "Никто не остался позади"),
        "Предметы": ("Строим на века", "Уроки улиц", "Туз в рукаве", "Мародерское чутье", "Аптекарь"),
        "Информация": ("Связь", "Сострадание", "Тревога", "Кровные узы", "Уникальная возможность", "Дар: освещение", "Детективное чутье"),
    },
    "KILLER": {
        "Контроль генераторов": ("Чертик из табакерки", "Порча: погибель", "Секущий крюк: резонанс боли", "Мрачные объятья", "Безжалостный шторм", "Соленое море", "Угасающий свет", "Танатофобия"),
        "Поиск": ("Барбекю и чили", "Зов медсестры", "Шепоты", "Сумеречные шпионы", "Явление мрака", "Секущий крюк: пучина ярости", "Наблюдение"),
        "Погоня": ("Розыгрыш", "Оставьте лучшее напоследок", "Поиграть со своей жертвой", "Растворение", "Оглушительный гром"),
        "Лечение": ("Клоунофобия", "Небрежный мясник", "Зов медсестры", "Танатофобия", "Секущий крюк: дар боли", "Тлетворное касание"),
        "Финал": ("Порча: никому не скрыться от смерти", "Помни меня", "Кровавый смотритель", "Ненависть"),
    },
}
PAIRS = {
    "SURVIVOR": (
        ("Сам себе доктор", "Познания в ботанике", "Самолечение получает поддержку от навыка на скорость лечения."),
        ("Мы справимся", "Сострадание", "После спасения можно быстро лечить раненых союзников, которых помогает найти аура."),
        ("Быстрый и тихий", "Потанцуй со мной", "Быстрое преодоление препятствия может одновременно скрыть звук и следы."),
        ("Надежда", "Адреналин", "Оба навыка помогают в финальной фазе матча."),
        ("Строим на века", "Уроки улиц", "Восстановление зарядов и экономия предметов поддерживают длительное использование."),
    ),
    "KILLER": (
        ("Небрежный мясник", "Зов медсестры", "Замедление лечения обычными атаками увеличивает окно для обнаружения лечащихся выживших."),
        ("Мрачные объятья", "Секущий крюк: резонанс боли", "Оба навыка вознаграждают подвешивание разных выживших и создают давление на генераторы."),
        ("Наблюдение", "Порча: погибель", "Автоматическая регрессия может помогать отслеживать возобновление ремонта."),
    ),
}


def key(value):
    return " ".join("".join(c if c.isalnum() else " " for c in str(value or "").casefold().replace("ё", "е")).split())


def tags(side, name):
    return [group for group, names in GROUPS.get(side, {}).items() if name in names]


def analyze(db, build, empty=()):
    b = build or {}
    side = b.get("side", "")
    names = [n for n in b.get("perks", []) if n and n not in empty]
    counts = Counter(t for n in names for t in tags(side, n))
    warnings, synergy = [], []
    if len(names) != len(set(names)):
        warnings.append("В билде повторяются навыки.")
    if b and len(names) < 4:
        warnings.append("Заполнено меньше четырёх слотов навыков.")
    for n in names:
        if not perk_info(db, side, n)["found"]:
            warnings.append("Навык отсутствует в каталоге этой стороны: " + n)
    if side == "SURVIVOR" and counts["Истощение"] > 1:
        warnings.append("Несколько навыков истощения: общее состояние может помешать использовать их подряд. Это не делает комбинацию автоматически плохой.")
    for a, c, note in PAIRS.get(side, ()):
        if a in names and c in names:
            synergy.append(a + " + " + c + " — " + note)
    if side == "SURVIVOR" and "Без сожаления" in names:
        for n in ("Сам себе доктор", "Внутренняя сила"):
            if n in names:
                warnings.append(n + " не поможет восстановить здоровье при «Без сожаления».")
    if side == "KILLER" and "Порча: погибель" in names and "Чертик из табакерки" in names:
        warnings.append("Пока «Погибель» активна, её автоматическая регрессия ограничивает ручное повреждение генераторов для «Чертика из табакерки».")
    pool = db.get("killers", {}).get(b.get("char"), {}).get("addons", []) if side == "KILLER" else db.get("survivor_items", {}).get(b.get("category"), {}).get("addons", [])
    for addon in b.get("addons", []):
        if addon and addon not in empty and addon not in pool:
            warnings.append("Аддон не найден в пуле выбранного персонажа или предмета: " + addon)
    return {"hasBuild": bool(b), "character": b.get("char", ""), "filled": len(names),
            "classified": sum(bool(tags(side, n)) for n in names),
            "groups": [{"name": n, "count": v} for n, v in counts.most_common()],
            "perks": [{"name": n, "tags": ", ".join(tags(side, n)) or "Нет ручной классификации"} for n in names],
            "synergies": synergy, "warnings": warnings}


def catalog(db, side, kind, query="", page=0, size=30, playable=lambda names: names):
    if side not in ("KILLER", "SURVIVOR"):
        return {"rows": [], "total": 0, "page": 0, "pages": 1}
    chars = db.get("killers" if side == "KILLER" else "survivors", {})
    rows = []
    def add(name, owner="", category="", detail="", icon=None):
        rows.append({"name": name, "owner": owner, "category": category,
                     "detail": detail, "icon": icon or name, "kind": kind, "side": side})
    if kind == "characters":
        for name, info in chars.items():
            perks = info.get("perks", []) if isinstance(info, dict) else info
            power = info.get("power", "") if isinstance(info, dict) else ""
            add(name, "", power, ("Сила: " + power + "\n" if power else "") + "Навыки: " + ", ".join(perks))
    elif kind == "perks":
        common = db.get("killer_common_perks" if side == "KILLER" else "surv_common_perks", [])
        names = set(common)
        for info in chars.values():
            names.update(info.get("perks", []) if isinstance(info, dict) else info)
        for name in names:
            info = perk_info(db, side, name)
            add(name, info["owner"], info["kind"], info["description"])
    elif kind == "addons":
        pools = chars if side == "KILLER" else db.get("survivor_items", {})
        for owner, info in pools.items():
            for name in set(playable(info.get("addons", []))):
                add(name, owner if side == "KILLER" else "", "" if side == "KILLER" else owner)
    elif kind == "items" and side == "SURVIVOR":
        for category, info in db.get("survivor_items", {}).items():
            for name in info.get("items", []):
                add(name, "", category, "Категория: " + category + "\nСовместимых аддонов: " + str(len(info.get("addons", []))))
    needle = key(query)
    rows = [r for r in rows if not needle or needle in key(" ".join((r["name"], r["owner"], r["category"])))]
    rows.sort(key=lambda r: (key(r["name"]), key(r["owner"]), key(r["category"])))
    total = len(rows)
    pages = max(1, (total + size - 1) // size)
    page = max(0, min(int(page), pages - 1))
    return {"rows": rows[page * size:(page + 1) * size], "total": total, "page": page, "pages": pages}
