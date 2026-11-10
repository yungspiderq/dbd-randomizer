"""Short DBD add-on notes and optional live wiki.gg effect categories.

Descriptions in this module are independently worded factual gameplay summaries,
not reproduced wiki articles. The wiki.gg Module:Datatable/Loadout tags field is
retrieved asynchronously. Unknown effects are left unknown, not invented.
"""
from __future__ import annotations

import json
import re
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

from tools.addon_names_ru_en import ADDON_RU_EN, ITEM_ADDON_RU_EN

SOURCE = "https://deadbydaylight.wiki.gg/wiki/Module:Datatable/Loadout/Descriptions"
INDEX_API = "https://deadbydaylight.wiki.gg/api.php"
CACHE_TTL = 14 * 24 * 3600
UA = "DBDRandomizerQt/2.28.0 (addon effect category cache; project: yungspiderq/dbd-randomizer)"

# Independently phrased factual descriptions of selected game modifications.
# Source: DBD wiki.gg / Module:Datatable/Loadout/Descriptions, The Trapper.
VERIFIED_RU = {
    "Кровавая пружина": "Выживший, обезвредивший капкан в здоровом состоянии, получает ранение.",
    "Радужный камень": "Раз в 30 секунд случайный деактивированный капкан устанавливается автоматически.",
    "Маслянистая пружина": "После возврата капкана в рабочее состояние аура его последнего обезвредившего становится видна на несколько секунд.",
    "Натяжная пружина": "Если выживший выбрался из капкана, через 2 секунды тот снова активируется.",
    "Точильный камень": "Выживший, самостоятельно освободившийся из капкана, переходит в состояние при смерти.",
    "Дополнительная пружина": "На обезвреживание капкана требуется больше времени.",
    "Крепежные инструменты": "Ускоряют установку капкана, а побег или спасение из капкана занимают больше времени.",
    "Ржавые челюсти": "Выживший, раненый капканом, временно получает эффект «Увечье».",
    "Смоляная бутылка": "Делает капканы темнее и менее заметными на карте.",
    "Зазубренные челюсти": "Получивший урон от капкана выживший страдает от эффекта «Кровотечение» до полного лечения.",
    "Комплект из 4-х спиральных пружин": "Продлевает время обезвреживания капкана примерно на треть.",
    "Кофейная гуща": "Усиливает ускорение после установки капкана на 5%.",
    "Удлиненная челюсть": "Освободившийся из капкана выживший получает эффект «Глубокая рана».",
    "Медвежий жир": "Установка капканов становится бесшумной.",
    "Мягкие челюсти": "Капкан удерживает выжившего, не нанося урона; за попадание начисляются дополнительные игровые очки.",
    "Самодельный бандаж": "При попадании маньяка в собственный капкан тот обезвреживается вместо удержания.",
}

# Independently paraphrased mechanics from the public DBD wiki. Effect values
# change with patches; avoid numeric claims unless they are stable and sourced.
# Keep the owner/category as part of the key: add-on names may overlap.
OTHER_KILLER_EFFECTS = {
    ("Свинья", "Видеокассета"): "Все выжившие начинают матч с обратным капканом на голове.",
    ("Свинья", "Модифицированный таймер"): "Уменьшает время до срабатывания активированного обратного капкана.",
    ("Кошмар", "Садовые грабли"): "Увеличивает площадь ловушки сна.",
    ("Кошмар", "Зеленое платье"): "Увеличивает время, необходимое выжившему для пробуждения.",
    ("Кошмар", "Скакалка"): "Продлевает замедление от ловушек сна.",
    ("Хороший парень", "Каска"): "Позволяет сразу разрушать паллеты при пробегании под ними.",
    ("Хороший парень", "Радужный амулет"): "Продлевает режим «Привет-привет»; обычная атака завершает его.",
    ("Хороший парень", "Коробка хорошего парня"): "Ускоряет восстановление после успешной атаки «Резать и кромсать».",
}
SURVIVOR_EFFECTS = {
    ("Фонарики", "Батарейка"): "Увеличивает время работы фонарика.",
    ("Фонарики", "Аккумулятор с мощным зарядом"): "Увеличивает время работы фонарика.",
    ("Фонарики", "Фокусирующая линза"): "Изменяет параметры луча фонарика: увеличивает дальность и яркость, но сужает луч.",
    ("Аптечки", "Бинты"): "Увеличивают доступные заряды аптечки для лечения.",
    ("Аптечки", "Медицинские ножницы"): "Ускоряют лечение при использовании аптечки.",
    ("Аптечки", "Иголка и нитка"): "Повышает вероятность проверок реакции при лечении и бонус за отличную проверку.",
    ("Ящики с инструментами", "Катушка проволоки"): "Увеличивает количество зарядов ящика с инструментами.",
    ("Ящики с инструментами", "Старые запчасти"): "Увеличивают количество зарядов ящика с инструментами.",
    ("Ящики с инструментами", "Режущая проволока"): "Ускоряет саботаж крюков с помощью ящика с инструментами.",
    ("Ящики с инструментами", "Ножовка"): "Ускоряет саботаж крюков с помощью ящика с инструментами.",
    ("Ящики с инструментами", "Чистая тряпка"): "Увеличивает скорость ремонта при использовании ящика с инструментами.",
    ("Ящики с инструментами", "Защитные перчатки"): "Скрывают уведомление маньяку после успешного саботажа крюка.",
    ("Ящики с инструментами", "Руководство"): "Подавляет обычные проверки реакции во время ремонта ящиком с инструментами.",
    ("Ящики с инструментами", "Новая деталь"): "Позволяет уменьшить требуемый объём ремонта генератора после специальной проверки реакции; одноразовая.",
    ("Ключи", "Уникальное обручальное кольцо"): "Постоянно раскрывает вам ауру одержимости, а вашу ауру — одержимости.",
    ("Ключи", "Пронзительный свист"): "Сокращает время подготовки к использованию ключа.",
}

CATEGORY_RU = {
    "Deafened": "приглушение звука", "Blindness": "слепота",
    "KillerBlind": "ослепление маньяка", "Detonation": "срабатывание",
    "EffectRadius": "радиус действия", "EffectDuration": "длительность эффекта",
    "EffectRange": "дальность эффекта", "ActionSpeed": "скорость действия",
    "Charges": "заряды", "Capacity": "ёмкость", "DepletionRate": "расход ресурса",
    "Detection": "обнаружение", "Haste": "ускорение", "Hindered": "замедление",
    "Healing": "лечение", "Generators": "генераторы", "GruntsOfPain": "звуки персонажа",
    "Haemorrhage": "кровотечение", "Mangled": "увечье", "DeepWound": "глубокая рана",
    "Exposed": "уязвимость", "Oblivious": "забывчивость", "Undetectable": "незаметность",
    "Aura": "ауры", "Hook": "крюки", "ExitBlocker": "ворота",
    "Hatch": "люк", "ExtendedAbility": "особая способность", "ItemDrop": "потеря предмета",
    "Range": "дальность", "Illusions": "иллюзии", "Speed": "скорость",
    "ActionNoise": "шум действий", "ActionTime": "время действия",
    "Repairing": "ремонт", "Repair": "ремонт", "RepairRequirement": "объём ремонта",
    "RepairingProficiency": "эффективность ремонта", "Sabotage": "саботаж крюков",
    "SabotageProficiency": "эффективность саботажа", "HealingProficiency": "эффективность лечения",
    "SkillChecks": "проверки реакции", "SkillCheckProbability": "частота проверок реакции",
    "SkillCheckDifficulty": "сложность проверок реакции", "SkillCheckPenalty": "штраф за проверку реакции",
    "SkillCheckBonus": "бонус проверок реакции",
    "LoudNoiseNotifications": "громкие уведомления", "EffectWindow": "окно действия",
    "PowerCooldown": "восстановление силы", "PowerRange": "дальность силы",
    "PowerRecovery": "перезарядка силы", "PowerDuration": "время действия силы",
    "PowerCapacity": "заряды силы", "PowerObject": "объекты силы",
    "ProjectileSpeed": "скорость снаряда", "PowerAlternate": "вариант силы",
    "MovementSpeed": "скорость передвижения", "SkillCheckProbability": "частота проверок реакции",
}


def english_name(side, character, category, name):
    mapping = ADDON_RU_EN.get(character, {}) if side == "KILLER" else ITEM_ADDON_RU_EN.get(category, {})
    return mapping.get(name, "")


def read_live_tags():
    params = urllib.parse.urlencode({
        "action": "parse", "page": "Module:Datatable/Loadout",
        "prop": "wikitext", "format": "json",
    })
    req = urllib.request.Request(
        INDEX_API + "?" + params,
        headers={"User-Agent": UA, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=16) as response:
        payload = json.load(response)
    content = payload["parse"]["wikitext"]["*"]
    if len(content) > 8_000_000:
        raise RuntimeError("Unexpected wiki module size")
    result = {}
    inside = False
    for line in content.splitlines():
        if "p.addons = {" in line:
            inside = True
            continue
        if not inside:
            continue
        match = re.match(r'^\s*\["((?:\\.|[^"])*)"\]\s*=\s*\{(.*)\},?\s*$', line)
        if not match:
            continue
        name, body = match.groups()
        tag_match = re.search(r"\btags\s*=\s*\{([^}]*)\}", body)
        tags = re.findall(r'["\x27]([^"\x27]+)["\x27]', tag_match.group(1)) if tag_match else []
        result[name.replace('\\"', '"')] = tags[:10]
    return result


class AddonEffectLibrary:
    def __init__(self, root, on_change=None):
        self.path = Path(root) / "addon_effect_categories.json"
        self.on_change = on_change
        self.categories = {}
        self.loading = False
        self._last_attempt = 0.0
        self._lock = threading.Lock()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data.get("categories"), dict):
                self.categories = data["categories"]
        except (FileNotFoundError, ValueError, OSError, AttributeError):
            pass

    def get(self, side, character, category, name):
        if not name:
            return {"name": "", "effect": "", "summary": "", "categories": [], "source": SOURCE, "verified": False}
        english = english_name(side, character, category, name)
        note = ""
        if side == "KILLER":
            note = (VERIFIED_RU.get(name, "") if character == "Охотник" else
                    OTHER_KILLER_EFFECTS.get((character, name), ""))
        elif side == "SURVIVOR":
            note = SURVIVOR_EFFECTS.get((category, name), "")
        tags = self.categories.get(english, []) if english else []
        summary = (
            "Связан с механиками: " +
            ", ".join(dict.fromkeys(CATEGORY_RU.get(tag, tag) for tag in tags if tag))
            if tags else ""
        )
        return {
            "name": name,
            "english": english,
            "effect": note,
            "summary": summary,
            "categories": [CATEGORY_RU.get(tag, tag) for tag in tags if tag],
            "source": SOURCE,
            "verified": bool(note),
        }

    def refresh_async(self):
        with self._lock:
            if self.loading or (time.time() - self._last_attempt < 300):
                return
            self._last_attempt = time.time()
            try:
                if self.categories and time.time() - self.path.stat().st_mtime < CACHE_TTL:
                    return
            except OSError:
                pass
            self.loading = True

        def worker():
            try:
                new_data = read_live_tags()
                if len(new_data) > 200:
                    self.categories = new_data
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    tmp = self.path.with_suffix(".tmp")
                    tmp.write_text(json.dumps(
                        {"source": SOURCE, "categories": new_data},
                        ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
                    tmp.replace(self.path)
                    if self.on_change:
                        self.on_change()
            except (OSError, ValueError, KeyError, RuntimeError):
                pass
            finally:
                with self._lock:
                    self.loading = False
        threading.Thread(target=worker, daemon=True, name="addon-effects").start()
