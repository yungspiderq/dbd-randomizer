# -*- coding: utf-8 -*-
"""
DBD Ultimate Search Randomizer — SURV & KILLER  (v2, исправленная)
=================================================================
Рандомизатор билдов + автоэкипировка через поиск в инвентаре Dead by Daylight.

Запуск:
    python dbd_randomizer.py            # GUI
    python dbd_randomizer.py --selftest # проверка базы и генератора без GUI

Зависимости (Windows):
    pip install pyautogui pydirectinput pyperclip keyboard
    необязательно: pip install pytesseract   (проверка результата поиска по OCR)

Горячие клавиши во время автоэкипировки:
    F9  — немедленный СТОП (настраивается)
    мышь в левый верхний угол экрана — аварийный стоп (pyautogui FAILSAFE)

Что исправлено относительно v1 — см. README.md (полный аудит).
"""

import ctypes
import copy
import json
import os
import queue
import random
import shutil
import subprocess
import sys
import threading
import time

import pyperclip

# tkinter импортируется лениво (в main()), чтобы `--selftest` работал и на машинах
# без графической среды — например, в CI или на второй ОС.
tk = ttk = messagebox = filedialog = simpledialog = None


def _load_tk():
    global tk, ttk, messagebox, filedialog, simpledialog
    import tkinter as _tk
    from tkinter import ttk as _ttk, messagebox as _mb, filedialog as _fd
    from tkinter import simpledialog as _sd
    tk, ttk, messagebox, filedialog, simpledialog = _tk, _ttk, _mb, _fd, _sd
    return _tk


try:
    import dbd_data as DATA
    import dbd_github as GH
except ImportError:                       # запуск из другой директории
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import dbd_data as DATA
    import dbd_github as GH

APP_DIR = os.path.dirname(os.path.abspath(__file__))
APP_VERSION = GH.APP_VERSION
CONFIG_FILE = os.path.join(APP_DIR, "dbd_randomizer_config.json")
LEGACY_CONFIG = os.path.join(APP_DIR, "dbd_randomizer_config.txt")
DB_FILE = os.path.join(APP_DIR, "dbd_database.json")
BACKEND_NAME = "pydirectinput"            # DirectInput нужен для полноэкранного DBD

# ----------------------------------------------------------------------------
# Windows: DPI awareness ДО создания окон, иначе координаты мыши и координаты
# игры разъезжаются при масштабе != 100%.
# ----------------------------------------------------------------------------
def _set_dpi_awareness():
    if os.name != "nt":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)          # PER_MONITOR_AWARE
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


# ----------------------------------------------------------------------------
# Бэкенд ввода. pyautogui/pydirectinput импортируются только на Windows,
# поэтому «сухой прогон» (--selftest, галка Dry-run) работает где угодно.
# ----------------------------------------------------------------------------
class InputUnavailable(RuntimeError):
    pass


class _Input:
    def __init__(self):
        self.pyautogui = None
        self.pydirectinput = None
        self.available = False
        self.reason = ""
        if os.name != "nt":
            self.reason = "нужна Windows (pydirectinput/DirectInput)"
            return
        try:
            import pyautogui
            import pydirectinput
        except Exception as exc:                                # pragma: no cover
            self.reason = f"не установлены библиотеки: {exc}"
            return
        self.pyautogui, self.pydirectinput = pyautogui, pydirectinput
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.0
        for attr in ("PAUSE", "FAILSAFE"):
            if hasattr(pydirectinput, attr):
                setattr(pydirectinput, attr, 0.0 if attr == "PAUSE" else True)
        self.available = True

    # -- низкоуровневые примитивы -------------------------------------------
    def position(self):
        if not self.available:
            raise InputUnavailable(self.reason)
        return self.pyautogui.position()

    def move(self, x, y, steps=6):
        if not self.available:
            raise InputUnavailable(self.reason)
        pdi = self.pydirectinput
        if steps <= 1 or not hasattr(pdi, "moveTo"):
            pdi.moveTo(int(x), int(y))
            return
        try:
            cx, cy = self.position()
        except Exception:
            cx, cy = x, y
        for i in range(1, steps + 1):
            t = i / steps
            pdi.moveTo(int(cx + (x - cx) * t), int(cy + (y - cy) * t))
            time.sleep(0.004)

    def click(self, x, y, hold=0.06, steps=6):
        if not self.available:
            raise InputUnavailable(self.reason)
        pdi = self.pydirectinput
        self.move(x, y, steps=steps)
        pdi.mouseDown()
        time.sleep(max(0.02, hold))
        pdi.mouseUp()

    def key(self, name, hold=0.02):
        if not self.available:
            raise InputUnavailable(self.reason)
        pdi = self.pydirectinput
        if hasattr(pdi, "press"):
            pdi.press(name)
        else:
            pdi.keyDown(name)
            time.sleep(hold)
            pdi.keyUp(name)

    def hotkey(self, *keys, hold=0.02):
        if not self.available:
            raise InputUnavailable(self.reason)
        pdi = self.pydirectinput
        for k in keys:
            pdi.keyDown(k)
            time.sleep(hold)
        time.sleep(hold)
        for k in reversed(keys):
            pdi.keyUp(k)
            time.sleep(hold)

    def paste(self, text, verify=True, retries=6, restore=False):
        """Копирует текст в буфер и вставляет Ctrl+V. Возвращает True при успехе."""
        if not self.available:
            raise InputUnavailable(self.reason)
        old = None
        if restore:
            try:
                old = pyperclip.paste()
            except Exception:
                pass
        ok = False
        for _ in range(retries):
            try:
                pyperclip.copy(text)
                time.sleep(0.03)
                if not verify or pyperclip.paste() == text:
                    ok = True
                    break
            except Exception:
                time.sleep(0.05)
        if not ok:                                              # последняя попытка вслепую
            try:
                pyperclip.copy(text)
                time.sleep(0.06)
                ok = True
            except Exception:
                ok = False
        if ok:
            self.hotkey("ctrl", "v")
        if restore and ok:
            # даём игре забрать текст из буфера, прежде чем вернуть прежнее содержимое
            time.sleep(0.12)
            try:
                if old is not None and old != "":
                    pyperclip.copy(old)
            except Exception:
                pass
        return ok


INPUT = _Input()


# ----------------------------------------------------------------------------
# Конфигурация
# ----------------------------------------------------------------------------
COORD_FIELDS = [
    ("item_slot",       "👜 Слот предмета (выживший)"),
    ("addon1_slot",     "🔧 Слот аддона №1"),
    ("addon2_slot",     "🔧 Слот аддона №2"),
    ("slot1",           "🔮 Слот навыка 1"),
    ("slot2",           "🔮 Слот навыка 2"),
    ("slot3",           "🔮 Слот навыка 3"),
    ("slot4",           "🔮 Слот навыка 4"),
    ("search",          "🔍 Поисковая строка инвентаря"),
    ("clear",           "❌ Кнопка очистки поиска (необязательно)"),
    ("first_result",    "✅ 1-я иконка в результатах поиска"),
    ("char_search",     "🎭 Поиск персонажа (необязательно)"),
    ("ocr_region",      "🔎 Область имени результата для OCR (необязательно)"),
]

TIMING_DEFAULTS = {
    "search_settle":   (0.35, "Пауза после ввода поиска, сек (0.25–0.6)"),
    "after_slot_click":(0.45, "Пауза после клика по слоту, сек"),
    "hold":            (0.06, "Удержание кнопки мыши, сек"),
    "between_steps":   (0.25, "Пауза между шагами, сек"),
    "retries":         (2,    "Повторов поиска при неудаче"),
    "countdown":       (5,    "Обратный отсчёт, сек"),
    "move_steps":      (6,    "Шагов перемещения курсора (1 = мгновенно)"),
    "result_step":     (84,   "Шаг сетки выдачи, px (для result_index > 1)"),
}

OPTION_DEFAULTS = {
    "dry_run":         False,
    "use_clear_button":False,
    "verify_clipboard":True,
    "ocr_verify":      False,
    "restore_clipboard":True,
    "result_index":    1,      # 1..9 — какую иконку выдачи считать нужной
    "abort_key":       "f9",
    "select_char":     False,       # искать персонажа по имени и выбирать его
    "perk_mode":       "general",   # general | unique | mixed
    "respect_owned":   False,       # учитывать белые списки OWNED_*
    "addons_enabled":  True,
}


def default_config():
    cfg = {"coords": {}, "timings": {}, "options": {}, "owned": {}}
    for key, _ in COORD_FIELDS:
        cfg["coords"][key] = {"x": "", "y": ""}
    cfg["coords"]["ocr_region"].update({"w": "", "h": ""})
    for key, (val, _) in TIMING_DEFAULTS.items():
        cfg["timings"][key] = val
    cfg["options"] = dict(OPTION_DEFAULTS)
    cfg["owned"] = {"killers": [], "survivors": []}
    cfg["publish"] = {"nickname": "", "gh_token": ""}
    cfg["update"] = {"auto": True, "allow_branch": False, "skip_tag": ""}
    return cfg


def _migrate_legacy(path):
    """Старый dbd_randomizer_config.txt -> coords-словарь нового формата."""
    coords = {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                if "=" not in line:
                    continue
                key, val = line.split("=", 1)
                coords[key.strip()] = val.strip()
    except Exception:
        return {}, [], {}
    out, owned = {}, []
    for key, _ in COORD_FIELDS:
        out[key] = {"x": coords.get(f"{key}_x", ""), "y": coords.get(f"{key}_y", "")}
    out["ocr_region"].update({"w": coords.get("ocr_region_w", ""), "h": coords.get("ocr_region_h", "")})
    for cfg_key, owned_key in (("owned_killers", "killers"), ("owned_surv_chars", "survivors")):
        raw = coords.get(cfg_key, "")
        if raw:
            owned.append((owned_key, [x.strip() for x in raw.split(",") if x.strip()]))
    return out, owned, coords


def load_config():
    cfg = default_config()
    migrated = False
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
                user = json.load(fh)
            for section in ("coords", "timings", "options", "owned", "publish", "update"):
                if isinstance(user.get(section), dict):
                    if section == "coords":
                        for key, val in user[section].items():
                            if isinstance(val, dict):
                                cfg["coords"].setdefault(key, {"x": "", "y": ""}).update(val)
                    else:
                        cfg[section].update(user[section])
            return cfg, False
        except Exception:
            backup = CONFIG_FILE + ".broken"
            try:
                shutil.copy2(CONFIG_FILE, backup)
            except Exception:
                pass
            migrated = True
    if os.path.exists(LEGACY_CONFIG):
        coords, owned, raw = _migrate_legacy(LEGACY_CONFIG)
        if coords:
            cfg["coords"].update(coords)
            for key, names in owned:
                cfg["owned"][key] = names
            cfg["publish"]["nickname"] = raw.get("nickname", "")
            cfg["publish"]["gh_token"] = raw.get("gh_token", "")
            cfg["update"]["auto"] = raw.get("auto_update", "1") != "0"
            migrated = True
            try:
                os.replace(LEGACY_CONFIG, LEGACY_CONFIG + ".migrated")
            except Exception:
                pass
    return cfg, migrated


def save_config(cfg):
    """Атомарная запись: сначала временный файл, потом replace."""
    tmp = CONFIG_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_FILE)


# ----------------------------------------------------------------------------
# База данных (JSON поверх дефолтов из dbd_data.py)
# ----------------------------------------------------------------------------
def db_defaults():
    """Глубокая копия встроенной базы: правки в рантайме не должны менять dbd_data.py."""
    return {
        "version": DATA.VERSION,
        "killers": copy.deepcopy(DATA.KILLERS),
        "survivors": copy.deepcopy(DATA.SURVIVORS),
        "survivor_items": copy.deepcopy(DATA.SURVIVOR_ITEMS),
        "surv_common_perks": list(DATA.SURV_COMMON_PERKS),
        "killer_common_perks": list(DATA.KILLER_COMMON_PERKS),
        "owned": {
            "survivor_perks": list(DATA.OWNED_SURVIVOR_PERKS),
            "survivor_items": list(DATA.OWNED_SURVIVOR_ITEMS),
            "survivor_addons": list(DATA.OWNED_SURVIVOR_ADDONS),
            "killer_addons": list(DATA.OWNED_KILLER_ADDONS),
            "killer_perks": list(DATA.OWNED_KILLER_PERKS),
        },
    }


def load_db():
    db = db_defaults()
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as fh:
                user = json.load(fh)
            for section in ("killers", "survivors", "survivor_items",
                            "surv_common_perks", "killer_common_perks"):
                if user.get(section):
                    db[section] = user[section]
            if isinstance(user.get("owned"), dict):
                db["owned"].update(user["owned"])
            db["_loaded_from_file"] = True
        except Exception:
            db["_load_error"] = True
    else:
        try:
            dump_db(db)
        except Exception:
            pass
    return db


def dump_db(db):
    out = {k: v for k, v in db.items() if not k.startswith("_")}
    tmp = DB_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, DB_FILE)


# ----------------------------------------------------------------------------
# Чистая логика генерации (без tkinter — тестируется в --selftest)
# ----------------------------------------------------------------------------
NO_ADDONS = "🚫 аддон не подобран"
EMPTY = "—"


def _filter_owned(pool, owned, respect):
    """respect=False или пустой белый список -> считаем, что открыто всё.

    respect=True -> строго только то, что есть в белом списке; если совпадений нет,
    возвращаем пустой список (слоты останутся пустыми), а НЕ «всё подряд».
    """
    if not respect or not owned:
        return list(pool)
    allowed_set = set(owned)
    return [x for x in pool if x in allowed_set]


def _pick(pool, n):
    pool = list(dict.fromkeys(pool))          # убираем дубли, сохраняя порядок
    if len(pool) <= n:
        return pool[:]
    return random.sample(pool, n)


def _fill_perks(perks, pools, respect_owned=False):
    """Добирает навыки до 4 слотов, не допуская повторов.

    pools — список пулов в порядке приоритета (например, [уникальные, общие, всё вместе]).
    При respect_owned=True недостающие слоты остаются пустыми (EMPTY),
    чтобы автоэкипировка не тыкала в то, чего у вас нет.
    """
    perks = list(perks)
    if respect_owned:
        while len(perks) < 4:
            perks.append(EMPTY)
        return perks[:4]
    for pool in pools:
        if len(perks) >= 4:
            break
        candidates = [p for p in dict.fromkeys(pool) if p not in perks]
        for perk in _pick(candidates, 4 - len(perks)):
            perks.append(perk)
    return perks[:4]


def make_killer_build(db, available, perk_mode="general", respect_owned=False, addons_enabled=True):
    owned = db.get("owned", {})
    name = random.choice(sorted(available))
    info = db["killers"][name]

    if addons_enabled:
        addon_pool = _filter_owned(info.get("addons", []), owned.get("killer_addons"), respect_owned)
        addons = _pick(addon_pool, 2)
    else:
        addons = []
    while len(addons) < 2:
        addons.append(NO_ADDONS if not addons else EMPTY)


    unique = list(info.get("perks", []))
    common = list(db.get("killer_common_perks", []))
    if perk_mode == "unique":
        pool = _filter_owned(unique, owned.get("killer_perks"), respect_owned)
    elif perk_mode == "mixed":
        pool = _filter_owned(unique + common, owned.get("killer_perks"), respect_owned)
    else:
        pool = _filter_owned(common, owned.get("killer_perks"), respect_owned)
    perks = _pick(pool, 4)
    if len(perks) < 4:                        # уникальных всего 3 — добираем общими
        perks = _fill_perks(perks, [common, unique + common], respect_owned)


    return {
        "side": "KILLER",
        "char": name,
        "power_or_item": info.get("power", EMPTY),
        "power_is_item": False,
        "addons": addons,
        "perks": perks[:4],
    }


def make_survivor_build(db, available, perk_mode="general", respect_owned=False, addons_enabled=True):
    owned = db.get("owned", {})
    name = random.choice(sorted(available))

    categories = list(db["survivor_items"].keys())
    cat = random.choice(categories)
    entry = db["survivor_items"][cat]

    item_pool = _filter_owned(entry.get("items", []), owned.get("survivor_items"), respect_owned)
    item = random.choice(item_pool) if item_pool else EMPTY

    if addons_enabled:
        addon_pool = _filter_owned(entry.get("addons", []), owned.get("survivor_addons"), respect_owned)
        addons = _pick(addon_pool, 2)
        if not addons:
            addons = [NO_ADDONS if not entry.get("addons") else EMPTY]
    else:
        addons = [EMPTY]
    while len(addons) < 2:
        addons.append(EMPTY)

    unique = list(db["survivors"].get(name, []))
    common = list(db.get("surv_common_perks", []))
    if perk_mode == "unique":
        pool = _filter_owned(unique, owned.get("survivor_perks"), respect_owned)
    elif perk_mode == "mixed":
        pool = _filter_owned(unique + common, owned.get("survivor_perks"), respect_owned)
    else:
        pool = _filter_owned(common, owned.get("survivor_perks"), respect_owned)
    perks = _pick(pool, 4)
    if len(perks) < 4:
        perks = _fill_perks(perks, [common, unique + common], respect_owned)

    return {
        "side": "SURVIVOR",
        "char": name,
        "power_or_item": item,
        "category": cat,
        "power_is_item": True,
        "addons": addons,
        "perks": perks[:4],
    }


def build_to_text(b):
    if b["side"] == "KILLER":
        lines = [f"👹 Убийца: {b['char']}", f"⚡ Сила: {b['power_or_item']}  (не экипируется)"]
    else:
        lines = [f"👤 Выживший: {b['char']}",
                 f"📦 Предмет: {b['power_or_item']}  [{b.get('category', '')}]"]
    lines.append("🔧 Аддоны:")
    for a in b["addons"]:
        lines.append(f"   • {a}")
    lines.append("🔮 Навыки:")
    for i, p in enumerate(b["perks"], 1):
        lines.append(f"   {i}. {p}")
    return "\n".join(lines)


def build_to_clipboard_text(b):
    """Компактный вариант для копирования/чата."""
    head = b["char"]
    item = b["power_or_item"]
    addons = " + ".join(a for a in b["addons"] if a not in (EMPTY, NO_ADDONS)) or "без аддонов"
    perks = ", ".join(b["perks"])
    return f"{head} | {item} | {addons} | Перки: {perks}"


# ----------------------------------------------------------------------------
# Валидация базы
# ----------------------------------------------------------------------------
def _norm(s):
    return (s or "").strip().lower().replace("ё", "е")


def _entry_text(entry):
    """Текст из Entry; всё, что не строка (например, заглушка в тестах), -> ''."""
    try:
        val = entry.get()
    except Exception:
        return ""
    return val.strip() if isinstance(val, str) else ""


def validate_db(db):
    errors, warnings = [], []

    killers = db.get("killers", {})
    survivors = db.get("survivors", {})
    items = db.get("survivor_items", {})

    if len(killers) < 44:
        warnings.append(f"Убийц в базе: {len(killers)} (в игре 44 на патче {db.get('version')}).")
    if len(survivors) < 50:
        warnings.append(f"Выживших в базе: {len(survivors)}.")

    for name, info in killers.items():
        if not isinstance(info, dict):
            errors.append(f"[{name}] запись убийцы должна быть словарём")
            continue
        perks = info.get("perks", [])
        if len(perks) != 3:
            warnings.append(f"[{name}] навыков: {len(perks)} (ожидается 3)")
        if not info.get("addons"):
            warnings.append(f"[{name}] список аддонов пуст — автоэкипировка пропустит этот шаг")
        if not info.get("power"):
            errors.append(f"[{name}] не указана сила")
        dupes = {x for x in perks if perks.count(x) > 1}
        if dupes:
            errors.append(f"[{name}] дубли навыков: {', '.join(sorted(dupes))}")
        adds = info.get("addons", [])
        dupes = {x for x in adds if adds.count(x) > 1}
        if dupes:
            errors.append(f"[{name}] дубли аддонов: {', '.join(sorted(dupes))}")
        if info.get("_todo"):
            warnings.append(f"[{name}] TODO: {info['_todo']}")

    for name, perks in survivors.items():
        if len(perks) != 3:
            warnings.append(f"[{name}] (выж.) навыков: {len(perks)} (ожидается 3)")

    # одинаковые имена в разных списках -> поиск может выбрать не то
    def collect():
        bag = {}
        for kname, info in killers.items():
            for a in info.get("addons", []):
                bag.setdefault(_norm(a), set()).add(f"аддон {kname}")
        for cat, entry in items.items():
            for a in entry.get("addons", []):
                bag.setdefault(_norm(a), set()).add(f"аддон предмета «{cat}»")
            for it in entry.get("items", []):
                bag.setdefault(_norm(it), set()).add(f"предмет «{cat}»")
        for kname, info in killers.items():
            bag.setdefault(_norm(info.get("power", "")), set()).add(f"сила {kname}")
        return bag

    bag = collect()
    for key, where in sorted(bag.items()):
        if len(where) > 1:
            warnings.append(f"Одно имя в разных разделах: «{key}» -> {', '.join(sorted(where))}")

    # имена-префиксы: «Фонарик» находится и внутри «Маскарадный фонарик»
    names = sorted(bag.keys())
    for a in names:
        if len(a) < 5:
            continue
        for b in names:
            if a != b and a in b:
                warnings.append(f"Поиск по «{a}» может выдать «{b}» — проверьте порядок выдачи "
                                f"(или настройте result_index / OCR).")
                break

    # «подозрительные» переводы
    for kname, info in killers.items():
        for p in info.get("perks", []):
            if _norm(p).endswith(("ое", "ее")) and not _norm(p).startswith("порча"):
                warnings.append(f"[{kname}] навык «{p}» выглядит как прилагательное — сверьте с игрой")

    return errors, warnings


# ----------------------------------------------------------------------------
# Захват координат
# ----------------------------------------------------------------------------
class CoordinateGrabber:
    """Отдельное окно: ЛКМ — записать координату, Esc — отмена.

    Ссылка на объект ОБЯЗАТЕЛЬНО хранится у родителя (в v1 её съедал сборщик
    мусора, и окно иногда закрывалось само).
    """

    def __init__(self, parent, title="Захват координаты"):
        self.coords = None
        self.top = tk.Toplevel(parent)
        self.top.title(title)
        self.top.geometry("330x130")
        self.top.configure(bg="#1e1e1e")
        self.top.attributes("-topmost", True)
        self.top.resizable(False, False)
        tk.Label(self.top, text="🎯 Наведите мышь на нужную точку\nи кликните ЛКМ в этом окне.\nEsc — отмена",
                 bg="#1e1e1e", fg="#e0e0e0", font=("Segoe UI", 10), justify="center").pack(pady=10)
        self.lbl = tk.Label(self.top, text="x: —   y: —", bg="#1e1e1e", fg="#ff9500",
                            font=("Consolas", 11, "bold"))
        self.lbl.pack(pady=2)
        self.top.bind("<Button-1>", self._on_click)
        self.top.bind("<Motion>", self._on_motion)
        self.top.bind("<Escape>", lambda e: self.top.destroy())
        self.top.protocol("WM_DELETE_WINDOW", self.top.destroy)

    def _screen_pos(self):
        try:
            return self.top.winfo_pointerxy()          # физические пиксели
        except Exception:
            pass
        if INPUT.available:
            try:
                p = INPUT.position()
                return int(p[0]), int(p[1])
            except Exception:
                pass
        return None

    def _on_motion(self, _event):
        pos = self._screen_pos()
        if pos:
            self.lbl.config(text=f"x: {pos[0]}   y: {pos[1]}")

    def _on_click(self, _event):
        pos = self._screen_pos()
        if pos:
            self.coords = pos
        self.top.destroy()


# ----------------------------------------------------------------------------
# Диалог обновления: показывает, ЧТО именно будет записано на диск
# ----------------------------------------------------------------------------
class UpdateDialog:
    """Файлы уже скачаны и проверены, но на диск НЕ записаны — решение за пользователем."""

    def __init__(self, parent, upd, info):
        self.result = None
        self.upd, self.info = upd, info
        self.top = tk.Toplevel(parent)
        self.top.title(f"Доступно обновление {upd.get('tag', '')}")
        self.top.geometry("620x520")
        self.top.configure(bg="#1e1e1e")
        self.top.attributes("-topmost", True)
        self.top.transient(parent)
        self.top.grab_set()

        ttk.Label(self.top, text=f"Установлена v{APP_VERSION} → доступна {upd.get('tag', '')}",
                  font=("Segoe UI", 11, "bold"), foreground="#ff9500").pack(pady=(12, 4))
        ttk.Label(self.top, text=f"Источник: {GH.GITHUB_REPO} @ {upd.get('ref', '')}",
                  font=("Segoe UI", 8), foreground="#8e8e93").pack()

        notes = tk.Text(self.top, height=8, bg="#2c2c2c", fg="#e0e0e0", relief="flat",
                        wrap="word", font=("Segoe UI", 10))
        notes.pack(fill="both", expand=True, padx=14, pady=8)
        notes.insert("end", (upd.get("notes") or "").strip() or "Описание отсутствует.")
        notes.configure(state="disabled")

        ttk.Label(self.top, text="Будут заменены файлы (старые сохранятся как .bak):",
                  font=("Segoe UI", 9, "bold"), foreground="#e0e0e0").pack(anchor="w", padx=16)
        rows = tk.Text(self.top, height=len(info) + 1, bg="#232323", fg="#9be29b", relief="flat",
                       font=("Consolas", 9))
        rows.pack(fill="x", padx=14, pady=(2, 8))
        for item in info:
            rows.insert("end", f"  {item['name']:<22} {item['bytes']:>8} байт   sha256:{item['sha256'][:16]}\n")
        rows.configure(state="disabled")

        btns = ttk.Frame(self.top)
        btns.pack(fill="x", padx=14, pady=(0, 12))
        ttk.Button(btns, text="🔄 Обновить и перезапустить", style="Gen.TButton",
                   command=self._do_update).pack(side="left", expand=True, fill="x", padx=4)
        ttk.Button(btns, text="Позже", command=self._dismiss).pack(side="right", padx=4)
        self.top.protocol("WM_DELETE_WINDOW", self._dismiss)

    def _do_update(self):
        self.result = "restart"
        self.top.destroy()

    def _dismiss(self):
        self.result = None
        self.top.destroy()


# ----------------------------------------------------------------------------
# OCR-проверка (необязательно)
# ----------------------------------------------------------------------------
def ocr_read(x, y, w, h, lang="rus"):
    try:
        import pytesseract
        from PIL import ImageGrab
    except Exception:
        return None
    try:
        img = ImageGrab.grab(bbox=(int(x), int(y), int(x) + int(w), int(y) + int(h)))
        img = img.convert("L").point(lambda p: 0 if p < 140 else 255)
        txt = pytesseract.image_to_string(img, lang=lang)
        return " ".join(txt.split())
    except Exception:
        return None


# ----------------------------------------------------------------------------
# Приложение
# ----------------------------------------------------------------------------
class App:
    def __init__(self, root):
        self.root = root
        self.cfg, migrated = load_config()
        self.db = load_db()
        self.build = None
        self.community_builds = []
        self._updating = False
        self._pending_update = None
        self.abort = threading.Event()
        self.worker = None
        self.ui_q = queue.Queue()
        self._grabber = None                 # защита от сборщика мусора
        self._hotkey_handle = None
        self._char_widgets = {}
        self._coord_widgets = {}
        self._timing_widgets = {}
        self._option_vars = {}

        _set_dpi_awareness()
        root.title(f"DBD Ultimate Search Randomizer — SURV & KILLER v{APP_VERSION}")
        root.configure(bg="#121212")
        root.geometry("1080x780")
        root.minsize(900, 620)

        self._setup_style()
        self._build_ui()
        self._poll_ui_queue()
        self._register_abort_hotkey()

        root.protocol("WM_DELETE_WINDOW", self._on_close)
        if self.cfg["update"].get("auto", True):
            root.after(4000, self.periodic_update_check)
        if migrated:
            self.log("Конфигурация перенесена из старого dbd_randomizer_config.txt в JSON.")
        if self.db.get("_load_error"):
            self.log("⚠ dbd_database.json повреждён — используются встроенные данные.")
        if not INPUT.available:
            self.log(f"⚠ Автоматизация недоступна ({INPUT.reason}). Доступен «сухой прогон».")
        self.log(f"База: {len(self.db['killers'])} убийц, {len(self.db['survivors'])} выживших "
                 f"(версия {self.db.get('version')}).")

    # ---------------------------------------------------------------- стиль --
    def _setup_style(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")          # «default» на Windows игнорирует цвета
        except Exception:
            pass
        bg, fg, acc = "#121212", "#e6e6e6", "#ff9500"
        style.configure(".", background=bg, foreground=fg, font=("Segoe UI", 10), bordercolor="#2c2c2c")
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("TFrame", background=bg)
        style.configure("TLabelframe", background=bg, bordercolor="#2c2c2c")
        style.configure("TLabelframe.Label", background=bg, foreground=acc, font=("Segoe UI", 10, "bold"))
        style.configure("TNotebook", background=bg, borderwidth=0)
        style.configure("TNotebook.Tab", background="#232323", foreground="#9a9a9a", padding=(14, 6))
        style.map("TNotebook.Tab", background=[("selected", acc)], foreground=[("selected", "#121212")])
        style.configure("TCheckbutton", background=bg, foreground=fg)
        style.map("TCheckbutton", background=[("active", bg)])
        style.configure("TRadiobutton", background=bg, foreground=fg)
        style.map("TRadiobutton", background=[("active", bg)])
        style.configure("TButton", background="#2c2c2c", foreground="#ffffff", padding=5)
        style.map("TButton", background=[("active", "#3a3a3a")])
        style.configure("Gen.TButton", background=acc, foreground="#121212",
                        font=("Segoe UI", 12, "bold"), padding=10)
        style.map("Gen.TButton", background=[("active", "#ffb04d"), ("disabled", "#4a3a20")])
        style.configure("Equip.TButton", background="#34c759", foreground="#0d1a10",
                        font=("Segoe UI", 11, "bold"), padding=9)
        style.map("Equip.TButton", background=[("active", "#4cd964"), ("disabled", "#24402c")])
        style.configure("Stop.TButton", background="#ff3b30", foreground="#1a0d0c",
                        font=("Segoe UI", 11, "bold"), padding=9)
        style.map("Stop.TButton", background=[("active", "#ff6a5f")])
        style.configure("Vertical.TScrollbar", background="#2c2c2c", troughcolor=bg)

    # ------------------------------------------------------------- интерфейс --
    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        # --- переключатель стороны -------------------------------------------
        self.mode_var = tk.StringVar(value=self.cfg["options"].get("side", "KILLER"))
        top = ttk.Frame(self.root)
        top.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 2))
        ttk.Label(top, text="СТОРОНА:", font=("Segoe UI", 10, "bold")).pack(side="left")
        for text, value, color in (("👹 МАНЬЯКИ", "KILLER", "#ff6b60"),
                                   ("👤 ВЫЖИВАЮЩИЕ", "SURVIVOR", "#5ac8fa")):
            rb = tk.Radiobutton(top, text=text, variable=self.mode_var, value=value,
                                bg="#121212", fg=color, selectcolor="#1c1c1e",
                                activebackground="#121212", activeforeground=color,
                                font=("Segoe UI", 10, "bold"), command=self._on_mode_change)
            rb.pack(side="left", padx=12)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        self.tab_main = ttk.Frame(self.notebook)
        self.tab_chars = ttk.Frame(self.notebook)
        self.tab_coords = ttk.Frame(self.notebook)
        self.tab_builds = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_main, text=" 🎲 БИЛД ")
        self.notebook.add(self.tab_builds, text=" 🌍 БИЛДЫ СООБЩЕСТВА ")
        self.notebook.add(self.tab_chars, text=" 🎭 ПЕРСОНАЖИ ")
        self.notebook.add(self.tab_coords, text=" 🎯 КЛИКИ И ТАЙМИНГИ ")

        self._build_main_tab()
        self._build_builds_tab()
        self._build_chars_tab()
        self._build_coords_tab()

        # --- строка состояния -------------------------------------------------
        bottom = ttk.Frame(self.root)
        bottom.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))
        self.status = ttk.Label(bottom, text="Готово. Сгенерируйте билд.", foreground="#8e8e93",
                                font=("Segoe UI", 9), wraplength=760, justify="left")
        self.status.pack(side="left", fill="x", expand=True)
        self.btn_stop = ttk.Button(bottom, text="⏹ СТОП (F9)", style="Stop.TButton",
                                   command=self.request_abort, width=14)
        self.btn_stop.pack(side="right", padx=(8, 0))

    # ---- вкладка «Билд» ------------------------------------------------------
    def _build_main_tab(self):
        self.tab_main.columnconfigure(0, weight=3)
        self.tab_main.columnconfigure(1, weight=2)
        self.tab_main.rowconfigure(0, weight=1)
        self.tab_main.rowconfigure(1, weight=0)

        left = ttk.Frame(self.tab_main)
        left.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)

        box = ttk.LabelFrame(left, text=" ВАШ БИЛД ")
        box.grid(row=0, column=0, sticky="nsew")
        box.rowconfigure(0, weight=1)
        box.columnconfigure(0, weight=1)
        self.txt_build = tk.Text(box, bg="#181818", fg="#f0f0f0", insertbackground="#f0f0f0",
                                 font=("Consolas", 11), wrap="word", relief="flat", padx=12, pady=10,
                                 state="disabled")
        self.txt_build.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(box, orient="vertical", command=self.txt_build.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.txt_build.configure(yscrollcommand=sb.set)
        for tag, color, font in (("head", "#ff9500", ("Consolas", 12, "bold")),
                                 ("item", "#5ac8fa", ("Consolas", 11, "bold")),
                                 ("addon", "#e0e0e0", ("Consolas", 11)),
                                 ("perk", "#34c759", ("Consolas", 11)),
                                 ("warn", "#ffcc00", ("Consolas", 10, "italic"))):
            self.txt_build.tag_configure(tag, foreground=color, font=font)
        self._set_build_text("Нажмите «СГЕНЕРИРОВАТЬ».\n\n"
                             "1) Вкладка «ПЕРСОНАЖИ» — отметьте, что у вас открыто.\n"
                             "2) Вкладка «КЛИКИ И ТАЙМИНГИ» — укажите координаты.\n"
                             "3) В игре откройте меню снаряжения нужного персонажа.\n"
                             "4) Нажмите «ЭКИПИРОВАТЬ».")

        right = ttk.Frame(self.tab_main)
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=8)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(3, weight=1)

        opt = ttk.LabelFrame(right, text=" НАСТРОЙКИ ГЕНЕРАЦИИ ")
        opt.grid(row=0, column=0, sticky="ew")
        self.perk_mode_var = tk.StringVar(value=self.cfg["options"].get("perk_mode", "general"))
        for text, value, hint in (("Общие навыки (есть у всех)", "general", ""),
                                  ("Уникальные навыки персонажа", "unique", ""),
                                  ("Смешанные (3 своих + 1 общий и т.п.)", "mixed", "")):
            ttk.Radiobutton(opt, text=text, value=value, variable=self.perk_mode_var).pack(anchor="w", padx=8, pady=1)
        self.addons_var = tk.BooleanVar(value=self.cfg["options"].get("addons_enabled", True))
        ttk.Checkbutton(opt, text="Подбирать аддоны", variable=self.addons_var).pack(anchor="w", padx=8, pady=1)
        self.owned_var = tk.BooleanVar(value=self.cfg["options"].get("respect_owned", False))
        ttk.Checkbutton(opt, text="Только открытое у меня (белые списки в JSON)",
                        variable=self.owned_var).pack(anchor="w", padx=8, pady=(1, 6))

        btns = ttk.Frame(right)
        btns.grid(row=1, column=0, sticky="ew", pady=6)
        btns.columnconfigure(0, weight=1)
        self.btn_generate = ttk.Button(btns, text="🎲 СГЕНЕРИРОВАТЬ БИЛД", style="Gen.TButton",
                                       command=self.generate_build)
        self.btn_generate.grid(row=0, column=0, sticky="ew", pady=2)
        self.btn_equip = ttk.Button(btns, text="⚡ ЭКИПИРОВАТЬ В ИГРЕ", style="Equip.TButton",
                                    command=self.start_equip, state="disabled")
        self.btn_equip.grid(row=1, column=0, sticky="ew", pady=2)
        row2 = ttk.Frame(btns)
        row2.grid(row=2, column=0, sticky="ew", pady=2)
        row2.columnconfigure(0, weight=1)
        row2.columnconfigure(1, weight=1)
        ttk.Button(row2, text="📋 Копировать билд", command=self.copy_build).grid(row=0, column=0, sticky="ew", padx=(0, 3))
        ttk.Button(row2, text="🔁 Перегенерировать перки", command=self.reroll_perks).grid(row=0, column=1, sticky="ew", padx=(3, 0))
        self.btn_publish = ttk.Button(btns, text="🌍 ОПУБЛИКОВАТЬ БИЛД", command=self.publish_current_build)
        self.btn_publish.grid(row=3, column=0, sticky="ew", pady=2)

        run = ttk.LabelFrame(right, text=" ЗАПУСК АВТОМАТИЗАЦИИ ")
        run.grid(row=2, column=0, sticky="ew")
        self.dry_var = tk.BooleanVar(value=self.cfg["options"].get("dry_run", False))
        ttk.Checkbutton(run, text="Сухой прогон (без кликов, только лог)",
                        variable=self.dry_var).pack(anchor="w", padx=8, pady=1)
        self.ocr_var = tk.BooleanVar(value=self.cfg["options"].get("ocr_verify", False))
        ttk.Checkbutton(run, text="Проверять результат поиска (OCR, нужен pytesseract)",
                        variable=self.ocr_var).pack(anchor="w", padx=8, pady=1)
        self.selchar_var = tk.BooleanVar(value=self.cfg["options"].get("select_char", False))
        ttk.Checkbutton(run, text="Самому выбрать персонажа (нужна координата char_search)",
                        variable=self.selchar_var).pack(anchor="w", padx=8, pady=1)
        self.progress = ttk.Progressbar(run, mode="determinate", maximum=100)
        self.progress.pack(fill="x", padx=8, pady=(4, 8))

        logbox = ttk.LabelFrame(right, text=" ЖУРНАЛ ")
        logbox.grid(row=3, column=0, sticky="nsew", pady=(6, 0))
        logbox.rowconfigure(0, weight=1)
        logbox.columnconfigure(0, weight=1)
        self.txt_log = tk.Text(logbox, bg="#141414", fg="#b8b8b8", font=("Consolas", 9),
                               wrap="word", relief="flat", padx=6, pady=6, state="disabled", height=8)
        self.txt_log.grid(row=0, column=0, sticky="nsew")
        lsb = ttk.Scrollbar(logbox, orient="vertical", command=self.txt_log.yview)
        lsb.grid(row=0, column=1, sticky="ns")
        self.txt_log.configure(yscrollcommand=lsb.set)

    # ---- вкладка «Персонажи» -------------------------------------------------
    def _make_scrolled(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        canvas = tk.Canvas(frame, bg="#121212", highlightthickness=0)
        sb = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        def _wheel(event, target=None):
            delta = -1 if getattr(event, "num", 0) == 4 or getattr(event, "delta", 0) > 0 else 1
            canvas.yview_scroll(delta, "units")
            return "break"
        canvas.bind("<MouseWheel>", _wheel)
        canvas.bind("<Button-4>", _wheel)
        canvas.bind("<Button-5>", _wheel)
        for child in (inner, canvas):
            child.bind("<Enter>", lambda e, c=canvas: c.focus_set())
        return inner, canvas

    def _build_chars_tab(self):
        hint = ("Отметьте персонажей, которые у вас ОТКРЫТЫ — неотмеченные не выпадают.\n"
                "Имя должно совпадать с тем, что написано в игре (его же можно вбить в поиск персонажа).")
        ttk.Label(self.tab_chars, text=hint, foreground="#ff9500", justify="center",
                  font=("Segoe UI", 9, "italic")).pack(pady=(8, 2))

        toolbar = ttk.Frame(self.tab_chars)
        toolbar.pack(fill="x", padx=10, pady=4)
        ttk.Label(toolbar, text="Фильтр:").pack(side="left")
        self.char_filter = ttk.Entry(toolbar, width=24)
        self.char_filter.pack(side="left", padx=6)
        self.char_filter.bind("<KeyRelease>", lambda e: self._apply_char_filter())
        for text, cmd in (("Все", lambda: self._set_all_chars(True)),
                          ("Никого", lambda: self._set_all_chars(False)),
                          ("Инвертировать", lambda: self._set_all_chars(None)),
                          ("💾 Сохранить", self.save_owned_characters)):
            ttk.Button(toolbar, text=text, command=cmd).pack(side="left", padx=3)

        paned = ttk.Panedwindow(self.tab_chars, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=10, pady=4)

        lf_k = ttk.LabelFrame(paned, text=" 👹 МАНЬЯКИ ")
        paned.add(lf_k, weight=1)
        inner_k, _ = self._make_scrolled(lf_k)

        lf_s = ttk.LabelFrame(paned, text=" 👤 ВЫЖИВАЮЩИЕ ")
        paned.add(lf_s, weight=1)
        inner_s, _ = self._make_scrolled(lf_s)

        owned_k = set(self.cfg["owned"].get("killers") or [])
        owned_s = set(self.cfg["owned"].get("survivors") or [])
        for name in sorted(self.db["killers"].keys()):
            var = tk.BooleanVar(value=(name in owned_k) if owned_k else True)
            self._char_widgets[("K", name)] = (var, self._add_char_cb(inner_k, name, var, "#ff9500"))
        for name in sorted(self.db["survivors"].keys()):
            var = tk.BooleanVar(value=(name in owned_s) if owned_s else True)
            self._char_widgets[("S", name)] = (var, self._add_char_cb(inner_s, name, var, "#5ac8fa"))

        note = ("Подсказка: если снять все отметки и нажать «Сохранить», при следующем запуске "
                "снова будут отмечены все.")
        ttk.Label(self.tab_chars, text=note, foreground="#6e6e73",
                  font=("Segoe UI", 8, "italic")).pack(pady=(0, 8))

    def _add_char_cb(self, parent, name, var, color):
        cb = tk.Checkbutton(parent, text=name, variable=var, bg="#121212", fg="#dcdcdc",
                            selectcolor="#232323", activebackground="#121212",
                            activeforeground=color, anchor="w", font=("Segoe UI", 10),
                            highlightthickness=0)
        cb.pack(fill="x", padx=4, pady=1)
        return cb

    def _apply_char_filter(self):
        """Скрывает неподходящие чекбоксы и заново пакует видимые в алфавитном порядке."""
        needle = _norm(self.char_filter.get())
        for side in ("K", "S"):
            names = sorted(n for (s, n) in self._char_widgets if s == side)
            for name in names:
                _var, widget = self._char_widgets[(side, name)]
                if needle and needle not in _norm(name):
                    widget.pack_forget()
                else:
                    widget.pack(fill="x", padx=4, pady=1)

    def _set_all_chars(self, value):
        needle = _norm(self.char_filter.get())
        for (side, name), (var, _w) in self._char_widgets.items():
            if needle and needle not in _norm(name):
                continue
            if value is None:
                var.set(not var.get())
            else:
                var.set(bool(value))

    def save_owned_characters(self):
        killers = [n for (s, n), (v, _w) in self._char_widgets.items() if s == "K" and v.get()]
        survs = [n for (s, n), (v, _w) in self._char_widgets.items() if s == "S" and v.get()]
        self.cfg["owned"]["killers"] = sorted(killers)
        self.cfg["owned"]["survivors"] = sorted(survs)
        save_config(self.cfg)
        self.set_status(f"Сохранено: маньяков {len(killers)}, выживших {len(survs)}.", "#34c759")
        self.log(f"Сохранён список персонажей: {len(killers)} маньяков / {len(survs)} выживших.")

    # ---- вкладка «Клики и тайминги» -----------------------------------------
    def _build_coords_tab(self):
        self.tab_coords.columnconfigure(0, weight=3)
        self.tab_coords.columnconfigure(1, weight=2)
        self.tab_coords.rowconfigure(0, weight=1)

        # координаты
        leftf = ttk.LabelFrame(self.tab_coords, text=" КООРДИНАТЫ ЭКРАНА (пиксели) ")
        leftf.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)
        leftf.rowconfigure(0, weight=1)
        leftf.columnconfigure(0, weight=1)
        wrap = ttk.Frame(leftf)
        wrap.grid(row=0, column=0, sticky="nsew")
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)
        inner, _ = self._make_scrolled_grid(wrap)

        for key, desc in COORD_FIELDS:
            row = ttk.Frame(inner)
            row.pack(fill="x", padx=6, pady=2)
            ttk.Label(row, text=desc, width=42, anchor="w").pack(side="left")
            saved = self.cfg["coords"].get(key, {})
            entries = {}
            for axis in ("x", "y"):
                ent = tk.Entry(row, width=6, bg="#232323", fg="#ffffff", insertbackground="white",
                               relief="solid", bd=1, justify="center")
                ent.insert(0, str(saved.get(axis, "")))
                ent.pack(side="left", padx=2)
                entries[axis] = ent
            if key == "ocr_region":
                for axis in ("w", "h"):
                    ent = tk.Entry(row, width=6, bg="#232323", fg="#ffffff", insertbackground="white",
                                   relief="solid", bd=1, justify="center")
                    ent.insert(0, str(saved.get(axis, "")))
                    ent.pack(side="left", padx=2)
                    entries[axis] = ent
            self._coord_widgets[key] = entries
            ttk.Button(row, text="🎯 Клик", width=8,
                       command=lambda k=key: self.grab_coordinates(k)).pack(side="left", padx=6)
            if key == "ocr_region":
                ttk.Button(row, text="🔎 Область", width=10,
                           command=lambda: self.grab_ocr_region()).pack(side="left", padx=2)

        # тайминги + опции
        rightf = ttk.Frame(self.tab_coords)
        rightf.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=8)
        rightf.rowconfigure(2, weight=1)
        rightf.columnconfigure(0, weight=1)

        tf = ttk.LabelFrame(rightf, text=" ТАЙМИНГИ ")
        tf.grid(row=0, column=0, sticky="ew")
        for key, (default, desc) in TIMING_DEFAULTS.items():
            row = ttk.Frame(tf)
            row.pack(fill="x", padx=6, pady=2)
            ttk.Label(row, text=desc, anchor="w").pack(side="left", fill="x", expand=True)
            ent = tk.Entry(row, width=7, bg="#232323", fg="#ffffff", insertbackground="white",
                           relief="solid", bd=1, justify="center")
            ent.insert(0, str(self.cfg["timings"].get(key, default)))
            ent.pack(side="right")
            self._timing_widgets[key] = ent

        of = ttk.LabelFrame(rightf, text=" ПАРАМЕТРЫ КЛИКОВ ")
        of.grid(row=1, column=0, sticky="ew", pady=6)
        self._add_option(of, "use_clear_button", "Кликать «×» очистки перед поиском")
        self._add_option(of, "verify_clipboard", "Проверять буфер обмена перед вставкой")
        self._add_option(of, "restore_clipboard", "Восстанавливать буфер обмена после")
        row = ttk.Frame(of)
        row.pack(fill="x", padx=6, pady=3)
        ttk.Label(row, text="Номер иконки в выдаче (1–9):").pack(side="left")
        self._option_vars["result_index"] = tk.StringVar(value=str(self.cfg["options"].get("result_index", 1)))
        ttk.Entry(row, textvariable=self._option_vars["result_index"], width=4).pack(side="right")
        row = ttk.Frame(of)
        row.pack(fill="x", padx=6, pady=3)
        ttk.Label(row, text="Клавиша СТОП:").pack(side="left")
        self._option_vars["abort_key"] = tk.StringVar(value=str(self.cfg["options"].get("abort_key", "f9")))
        ttk.Entry(row, textvariable=self._option_vars["abort_key"], width=8).pack(side="right")

        sf = ttk.LabelFrame(rightf, text=" СЕРВИС ")
        sf.grid(row=2, column=0, sticky="nsew")
        for text, cmd in (("💾 Сохранить все настройки", self.save_settings),
                          ("🩺 Проверить базу данных", self.run_data_check),
                          ("📝 Открыть dbd_database.json", self.open_db_file),
                          ("🔄 Пересоздать dbd_database.json", self.reset_db_file),
                          ("🧪 Тестовый клик по «first_result»", self.test_click_result)):
            ttk.Button(sf, text=text, command=cmd).pack(fill="x", padx=6, pady=2)

        upf = ttk.LabelFrame(rightf, text=" 🔄 АВТООБНОВЛЕНИЕ ")
        upf.grid(row=3, column=0, sticky="ew", pady=(6, 0))
        self.auto_update_var = tk.BooleanVar(value=bool(self.cfg["update"].get("auto", True)))
        ttk.Checkbutton(upf, text="Проверять релизы GitHub (при запуске и каждые 30 мин)",
                        variable=self.auto_update_var,
                        command=self.toggle_auto_update).pack(anchor="w", padx=6, pady=2)
        self.allow_branch_var = tk.BooleanVar(value=bool(self.cfg["update"].get("allow_branch", False)))
        ttk.Checkbutton(upf, text="Брать файлы из main, если релизов нет (небезопасно)",
                        variable=self.allow_branch_var).pack(anchor="w", padx=6, pady=2)
        ttk.Button(upf, text="🔄 Проверить обновления сейчас",
                   command=lambda: self.check_for_updates(silent=False)).pack(fill="x", padx=6, pady=2)
        ttk.Label(upf, text=f"Версия v{APP_VERSION}. Файлы берутся из ТЕГА РЕЛИЗА, перед заменой "
                            f"показываются размер и SHA-256, старые версии сохраняются как .bak. "
                            f"Конфиг и токен не перезаписываются никогда.",
                  font=("Segoe UI", 8, "italic"), foreground="#8e8e93", justify="left",
                  wraplength=330).pack(anchor="w", padx=6, pady=(0, 6))

    def _make_scrolled_grid(self, parent):
        canvas = tk.Canvas(parent, bg="#121212", highlightthickness=0)
        sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        canvas.configure(yscrollcommand=sb.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")

        def _wheel(event):
            delta = -1 if getattr(event, "num", 0) == 4 or getattr(event, "delta", 0) > 0 else 1
            canvas.yview_scroll(delta, "units")
            return "break"
        canvas.bind("<MouseWheel>", _wheel)
        canvas.bind("<Button-4>", _wheel)
        canvas.bind("<Button-5>", _wheel)
        return inner, canvas

    def _add_option(self, parent, key, text):
        var = tk.BooleanVar(value=bool(self.cfg["options"].get(key, OPTION_DEFAULTS.get(key))))
        self._option_vars[key] = var
        ttk.Checkbutton(parent, text=text, variable=var).pack(anchor="w", padx=6, pady=2)

    # ---------------------------------------------------------------- утилиты --
    def log(self, message):
        self.ui_q.put(("log", str(message)))

    def set_status(self, text, color="#8e8e93"):
        self.ui_q.put(("status", (str(text), color)))

    def _poll_ui_queue(self):
        try:
            while True:
                kind, payload = self.ui_q.get_nowait()
                if kind == "log":
                    self._append_log(payload)
                elif kind == "status":
                    text, color = payload
                    self.status.config(text=text, foreground=color)
                elif kind == "progress":
                    self.progress["value"] = payload
                elif kind == "error":
                    messagebox.showerror("Ошибка", payload)
                elif kind == "warn":
                    messagebox.showwarning("Внимание", payload)
                elif kind == "info":
                    messagebox.showinfo("Готово", payload)
                elif kind == "builds":
                    self._on_builds_loaded(*payload)
                elif kind == "update":
                    self._show_update_dialog(*payload)
        except queue.Empty:
            pass
        self.root.after(70, self._poll_ui_queue)

    def _append_log(self, line):
        stamp = time.strftime("%H:%M:%S")
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", f"[{stamp}] {line}\n")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def _on_mode_change(self):
        self.cfg["options"]["side"] = self.mode_var.get()

    def _set_build_text(self, text):
        self.txt_build.configure(state="normal")
        self.txt_build.delete("1.0", "end")
        self.txt_build.insert("end", text)
        self.txt_build.configure(state="disabled")

    def _render_build(self):
        b = self.build
        self.txt_build.configure(state="normal")
        self.txt_build.delete("1.0", "end")
        if b.get("author"):
            self.txt_build.insert("end", f"🌍 билд сообщества от {b['author']}\n", "warn")
        if b["side"] == "KILLER":
            self.txt_build.insert("end", f"👹 Убийца: {b['char']}\n", "head")
            self.txt_build.insert("end", f"⚡ Сила: {b['power_or_item']}  (не экипируется)\n", "item")
        else:
            self.txt_build.insert("end", f"👤 Выживший: {b['char']}\n", "head")
            self.txt_build.insert("end", f"📦 Предмет: {b['power_or_item']}\n", "item")
            self.txt_build.insert("end", f"    категория: {b.get('category', '')}\n", "warn")
        self.txt_build.insert("end", "\n🔧 Аддоны:\n", "head")
        for a in b["addons"]:
            self.txt_build.insert("end", f"   • {a}\n", "addon")
        self.txt_build.insert("end", "\n🔮 Навыки:\n", "head")
        for i, p in enumerate(b["perks"], 1):
            self.txt_build.insert("end", f"   {i}. {p}\n", "perk")
        self.txt_build.configure(state="disabled")

    def get_coord(self, key):
        ent = self._coord_widgets.get(key)
        if not ent:
            return None
        try:
            return int(str(ent["x"].get()).strip()), int(str(ent["y"].get()).strip())
        except Exception:
            return None

    def get_ocr_region(self):
        ent = self._coord_widgets.get("ocr_region")
        if not ent:
            return None
        try:
            return (int(str(ent["x"].get()).strip()), int(str(ent["y"].get()).strip()),
                    int(str(ent["w"].get()).strip()), int(str(ent["h"].get()).strip()))
        except Exception:
            return None

    def timing(self, key):
        default = TIMING_DEFAULTS[key][0]
        try:
            val = float(str(self._timing_widgets[key].get()).strip().replace(",", "."))
        except Exception:
            return float(default)
        if key == "retries":
            return max(0, int(val))
        return max(0.0, val)

    def option(self, key):
        var = self._option_vars.get(key)
        if var is None:
            return self.cfg["options"].get(key, OPTION_DEFAULTS.get(key))
        val = var.get()
        if key == "result_index":
            try:
                return max(1, min(9, int(str(val).strip())))
            except Exception:
                return 1
        if key == "abort_key":
            return str(val).strip().lower() or "f9"
        return bool(val)

    def collect_settings(self):
        for key, entries in self._coord_widgets.items():
            for axis, ent in entries.items():
                self.cfg["coords"].setdefault(key, {})[axis] = ent.get().strip()
        for key, ent in self._timing_widgets.items():
            raw = ent.get().strip().replace(",", ".")
            try:
                self.cfg["timings"][key] = int(float(raw)) if key == "retries" else float(raw)
            except ValueError:
                pass
        for key, var in self._option_vars.items():
            val = var.get()
            if key == "result_index":
                try:
                    val = max(1, min(9, int(str(val).strip())))
                except Exception:
                    val = 1
            elif key == "abort_key":
                val = str(val).strip().lower() or "f9"
            else:
                val = bool(val)
            self.cfg["options"][key] = val
        self.cfg["options"]["side"] = self.mode_var.get()
        self.cfg["options"]["dry_run"] = bool(self.dry_var.get())
        self.cfg["options"]["ocr_verify"] = bool(self.ocr_var.get())
        self.cfg["options"]["perk_mode"] = self.perk_mode_var.get()
        self.cfg["options"]["select_char"] = bool(self.selchar_var.get())
        self.cfg["publish"]["nickname"] = _entry_text(self.nick_entry)
        self.cfg["publish"]["gh_token"] = _entry_text(self.token_entry)
        self.cfg["update"]["auto"] = bool(self.auto_update_var.get())
        self.cfg["update"]["allow_branch"] = bool(self.allow_branch_var.get())
        self.cfg["options"]["addons_enabled"] = bool(self.addons_var.get())
        self.cfg["options"]["respect_owned"] = bool(self.owned_var.get())

    def save_settings(self):
        self.collect_settings()
        save_config(self.cfg)
        self.set_status("Настройки сохранены.", "#34c759")
        self.log("Настройки (координаты, тайминги, опции) сохранены в dbd_randomizer_config.json")
        self._register_abort_hotkey()

    # ------------------------------------------------------- захват координат --
    def grab_coordinates(self, key):
        if self._grabber is not None:
            return
        self._grabber = CoordinateGrabber(self.root, f"Захват: {key}")
        self.root.wait_window(self._grabber.top)
        coords = self._grabber.coords
        self._grabber = None
        if not coords:
            return
        entries = self._coord_widgets[key]
        entries["x"].delete(0, "end")
        entries["x"].insert(0, str(coords[0]))
        entries["y"].delete(0, "end")
        entries["y"].insert(0, str(coords[1]))
        self.log(f"Координата «{key}» = {coords[0]}, {coords[1]}")

    def grab_ocr_region(self):
        """Два клика: левый верхний угол области, затем правый нижний."""
        if self._grabber is not None:
            return
        first = CoordinateGrabber(self.root, "OCR: левый верхний угол")
        self.root.wait_window(first.top)
        p1 = first.coords
        self._grabber = None
        if not p1:
            return
        self._grabber = CoordinateGrabber(self.root, "OCR: правый нижний угол")
        self.root.wait_window(self._grabber.top)
        p2 = self._grabber.coords
        self._grabber = None
        if not p2:
            return
        ent = self._coord_widgets["ocr_region"]
        for axis, value in (("x", min(p1[0], p2[0])), ("y", min(p1[1], p2[1])),
                            ("w", abs(p2[0] - p1[0])), ("h", abs(p2[1] - p1[1]))):
            ent[axis].delete(0, "end")
            ent[axis].insert(0, str(value))
        self.log(f"OCR-область: x={ent['x'].get()} y={ent['y'].get()} "
                 f"w={ent['w'].get()} h={ent['h'].get()}")

    def test_click_result(self):
        coord = self.get_coord("first_result")
        if not coord:
            messagebox.showwarning("Координаты", "Не задана координата «first_result».")
            return
        if self.dry_var.get():
            self.log(f"[DRY] тестовый клик по {coord}")
            return
        if not INPUT.available:
            messagebox.showerror("Автоматизация", INPUT.reason)
            return
        try:
            INPUT.click(coord[0], coord[1], hold=self.timing("hold"))
            self.log(f"Тестовый клик по {coord} выполнен.")
        except Exception as exc:
            messagebox.showerror("Ошибка", str(exc))

    # ------------------------------------------------------------- генерация --
    def available_characters(self, side):
        tag = "K" if side == "KILLER" else "S"
        names = self.db["killers"] if tag == "K" else self.db["survivors"]
        out = []
        for name in names:
            widget = self._char_widgets.get((tag, name))
            if widget is None or widget[0].get():
                out.append(name)
        return out

    def generate_build(self):
        side = self.mode_var.get()
        available = self.available_characters(side)
        if not available:
            messagebox.showwarning("Внимание", "Не отмечен ни один персонаж на вкладке «ПЕРСОНАЖИ».")
            return
        kwargs = dict(perk_mode=self.perk_mode_var.get(),
                      respect_owned=bool(self.owned_var.get()),
                      addons_enabled=bool(self.addons_var.get()))
        try:
            if side == "KILLER":
                self.build = make_killer_build(self.db, available, **kwargs)
            else:
                self.build = make_survivor_build(self.db, available, **kwargs)
        except Exception as exc:
            messagebox.showerror("Генерация", f"Не удалось собрать билд:\n{exc}")
            return
        self._render_build()
        self.btn_equip.config(state="normal")
        self.set_status("Билд готов. Откройте в игре меню снаряжения этого персонажа и жмите «ЭКИПИРОВАТЬ».",
                        "#34c759")
        self.log("Сгенерирован билд: " + build_to_clipboard_text(self.build))

    def reroll_perks(self):
        if not self.build:
            messagebox.showwarning("Внимание", "Сначала сгенерируйте билд.")
            return
        b = self.build
        if b["side"] == "KILLER":
            unique = list(self.db["killers"][b["char"]].get("perks", []))
            common = list(self.db.get("killer_common_perks", []))
        else:
            unique = list(self.db["survivors"].get(b["char"], []))
            common = list(self.db.get("surv_common_perks", []))
        mode = self.perk_mode_var.get()
        pool = unique if mode == "unique" else (unique + common if mode == "mixed" else common)
        perks = _pick(pool, 4)
        if len(perks) < 4:
            perks = _fill_perks(perks, [common, unique + common], bool(self.owned_var.get()))
        b["perks"] = perks
        self._render_build()
        self.log("Перки перегенерированы: " + ", ".join(b["perks"]))

    def copy_build(self):
        if not self.build:
            messagebox.showwarning("Внимание", "Сначала сгенерируйте билд.")
            return
        try:
            pyperclip.copy(build_to_clipboard_text(self.build))
            self.set_status("Билд скопирован в буфер обмена.", "#34c759")
        except Exception as exc:
            messagebox.showerror("Буфер обмена", str(exc))

    # ------------------------------------------------------- билды сообщества --
    def _build_builds_tab(self):
        top_bar = ttk.Frame(self.tab_builds)
        top_bar.pack(fill="x", padx=10, pady=(8, 2))
        ttk.Button(top_bar, text="🔄 Обновить список",
                   command=lambda: self.refresh_community_builds(manual=True)).pack(side="left")
        ttk.Button(top_bar, text="📋 Скопировать выбранный",
                   command=self.copy_selected_build).pack(side="left", padx=6)
        ttk.Button(top_bar, text="⚡ Экипировать выбранный", style="Equip.TButton",
                   command=self.equip_selected_build).pack(side="left", padx=6)
        self.lbl_builds_info = ttk.Label(top_bar, text="", foreground="#8e8e93",
                                         font=("Segoe UI", 9, "italic"))
        self.lbl_builds_info.pack(side="right")

        filt = ttk.Frame(self.tab_builds)
        filt.pack(fill="x", padx=10, pady=2)
        ttk.Label(filt, text="Фильтр:").pack(side="left")
        self.builds_filter_var = tk.StringVar(value="ВСЕ")
        for value, text in (("ВСЕ", "Все"), ("KILLER", "👹 Маньяки"), ("SURVIVOR", "👤 Выжившие")):
            rb = tk.Radiobutton(filt, text=text, variable=self.builds_filter_var, value=value,
                                bg="#121212", fg="#e0e0e0", selectcolor="#232323",
                                activebackground="#121212", activeforeground="#ffffff",
                                font=("Segoe UI", 9), command=self._render_builds_list)
            rb.pack(side="left", padx=4)
        ttk.Label(filt, text="Поиск:", font=("Segoe UI", 9)).pack(side="left", padx=(14, 2))
        self.builds_search_entry = tk.Entry(filt, width=22, bg="#232323", fg="#ffffff",
                                            insertbackground="white", bd=1, relief="solid")
        self.builds_search_entry.pack(side="left")
        self.builds_search_entry.bind("<KeyRelease>", lambda e: self._render_builds_list())

        list_frame = ttk.Frame(self.tab_builds)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        self.builds_tree = ttk.Treeview(list_frame, columns=("side", "author", "char", "main", "perks"),
                                        show="headings", height=12)
        for col, text, width, anch in (("side", "Сторона", 90, "center"), ("author", "Автор", 110, "w"),
                                       ("char", "Персонаж", 150, "w"), ("main", "Сила / Предмет", 190, "w"),
                                       ("perks", "Навыки", 360, "w")):
            self.builds_tree.heading(col, text=text)
            self.builds_tree.column(col, width=width, anchor=anch)
        tsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.builds_tree.yview)
        self.builds_tree.configure(yscrollcommand=tsb.set)
        self.builds_tree.pack(side="left", fill="both", expand=True)
        tsb.pack(side="right", fill="y")
        try:
            self.builds_tree.tag_configure("killer", foreground="#ff6961")
            self.builds_tree.tag_configure("survivor", foreground="#7fd4ff")
            self.builds_tree.tag_configure("mine", foreground="#ffd60a")
        except Exception:
            pass
        self.builds_tree.bind("<Double-1>", lambda e: self.copy_selected_build())
        self.builds_tree.bind("<<TreeviewSelect>>", lambda e: self._show_build_details())

        det = ttk.LabelFrame(self.tab_builds, text=" ДЕТАЛИ ВЫБРАННОГО БИЛДА ")
        det.pack(fill="x", padx=10, pady=(0, 5))
        self.lbl_build_details = ttk.Label(det, text="—", justify="left", font=("Consolas", 9),
                                           foreground="#e0e0e0")
        self.lbl_build_details.pack(anchor="w", padx=10, pady=5)

        sett = ttk.LabelFrame(self.tab_builds, text=" 🔑 НАСТРОЙКА ПУБЛИКАЦИИ ")
        sett.pack(fill="x", padx=10, pady=(0, 6))
        r1 = ttk.Frame(sett)
        r1.pack(fill="x", padx=8, pady=4)
        ttk.Label(r1, text="Ник для публикации:", width=26, anchor="w").pack(side="left")
        self.nick_entry = tk.Entry(r1, width=22, bg="#232323", fg="#ffffff",
                                   insertbackground="white", bd=1, relief="solid")
        self.nick_entry.insert(0, self.cfg["publish"].get("nickname", ""))
        self.nick_entry.pack(side="left", padx=4)
        r2 = ttk.Frame(sett)
        r2.pack(fill="x", padx=8, pady=4)
        ttk.Label(r2, text="Токен GitHub (Contents: Write):", width=26, anchor="w").pack(side="left")
        self.token_entry = tk.Entry(r2, width=44, show="*", bg="#232323", fg="#ffffff",
                                    insertbackground="white", bd=1, relief="solid")
        self.token_entry.insert(0, self.cfg["publish"].get("gh_token", ""))
        self.token_entry.pack(side="left", padx=4)
        self.show_token_var = tk.BooleanVar(value=False)
        tk.Checkbutton(r2, text="показать", variable=self.show_token_var, bg="#121212", fg="#8e8e93",
                       selectcolor="#232323", activebackground="#121212", font=("Segoe UI", 8),
                       command=self._toggle_token_visibility).pack(side="left")
        r3 = ttk.Frame(sett)
        r3.pack(fill="x", padx=8, pady=(2, 8))
        ttk.Button(r3, text="💾 Сохранить настройки", command=self.save_publish_settings).pack(side="left")
        ttk.Label(r3, text="Токен нужен только для ПУБЛИКАЦИИ. Хранится в вашем конфиге;\n"
                           "для чтения списка билдов токен не требуется.",
                  font=("Segoe UI", 8, "italic"), foreground="#8e8e93", justify="left").pack(side="left", padx=12)

        self.root.after(1500, lambda: self.refresh_community_builds(manual=False))

    def _toggle_token_visibility(self):
        self.token_entry.config(show="" if self.show_token_var.get() else "*")

    def save_publish_settings(self):
        self.cfg["publish"]["nickname"] = self.nick_entry.get().strip()
        self.cfg["publish"]["gh_token"] = self.token_entry.get().strip()
        save_config(self.cfg)
        self.set_status("Настройки публикации сохранены.", "#34c759")
        self.log("Сохранены ник и токен публикации (токен — только в локальном конфиге).")

    def refresh_community_builds(self, manual=False):
        threading.Thread(target=self._load_builds_worker, args=(manual,), daemon=True).start()

    def _load_builds_worker(self, manual):
        builds, online = GH.load_community_builds(APP_DIR)
        self.ui_q.put(("builds", (builds, online, manual)))

    def _on_builds_loaded(self, builds, online, manual):
        self.community_builds = builds if isinstance(builds, list) else []
        self._render_builds_list()
        if online:
            self.lbl_builds_info.config(text=f"Загружено из GitHub: {len(self.community_builds)}",
                                        foreground="#34c759")
        else:
            self.lbl_builds_info.config(text=f"Офлайн-кэш: {len(self.community_builds)} (нет связи с GitHub)",
                                        foreground="#ffcc00")
        self.log(f"Билды сообщества: {len(self.community_builds)} "
                 f"({'онлайн' if online else 'кэш'}).")
        if manual and not self.community_builds and online:
            self.ui_q.put(("info", "Пока никто ничего не опубликовал. "
                                   "Сгенерируйте билд и нажмите «Опубликовать»!"))

    def _filtered_builds(self):
        flt = self.builds_filter_var.get()
        try:
            q = self.builds_search_entry.get().strip().lower()
        except Exception:
            q = ""
        out = []
        for b in self.community_builds:
            if not isinstance(b, dict):
                continue
            if flt != "ВСЕ" and b.get("side") != flt:
                continue
            if q:
                blob = " ".join([str(b.get("char", "")), str(b.get("power_or_item", "")),
                                 str(b.get("author", "")),
                                 " ".join(map(str, b.get("perks", [])))]).lower()
                if q not in blob:
                    continue
            out.append(b)
        return out

    def _render_builds_list(self, keep_selection=False):
        tree = self.builds_tree
        selected = tree.selection()[0] if keep_selection and tree.selection() else None
        tree.delete(*tree.get_children())
        for i, b in enumerate(self._filtered_builds()):
            side_txt = "👹 Маньяк" if b.get("side") == "KILLER" else "👤 Выживший"
            perks = " | ".join(str(x) for x in b.get("perks", []))
            tag = "mine" if b.get("local") else ("killer" if b.get("side") == "KILLER" else "survivor")
            tree.insert("", "end", iid=str(i), tags=(tag,),
                        values=(side_txt, b.get("author", "—"), b.get("char", "—"),
                                b.get("power_or_item", "—"), perks))
        if selected is not None and tree.exists(selected):
            tree.selection_set(selected)

    def _selected_build(self):
        sel = self.builds_tree.selection()
        if not sel:
            return None
        try:
            idx = int(sel[0])
        except (TypeError, ValueError):
            return None
        filtered = self._filtered_builds()
        return filtered[idx] if 0 <= idx < len(filtered) else None

    def _show_build_details(self):
        b = self._selected_build()
        self.lbl_build_details.config(text=GH.format_build_text(b) if b else "—")

    def copy_selected_build(self):
        b = self._selected_build()
        if not b:
            self.ui_q.put(("warn", "Сначала выберите билд из списка (клик по строке)."))
            return
        try:
            pyperclip.copy(GH.format_build_text(b))
            self.set_status("Карточка билда скопирована в буфер обмена ✔", "#34c759")
        except Exception as exc:
            self.ui_q.put(("error", f"Не удалось скопировать: {exc}"))

    def equip_selected_build(self):
        b = self._selected_build()
        if not b:
            self.ui_q.put(("warn", "Сначала выберите билд из списка."))
            return
        addons = [a for a in (b.get("addons") or [])]
        while len(addons) < 2:
            addons.append(EMPTY)
        perks = [p for p in (b.get("perks") or []) if p and p != EMPTY]
        if len(perks) < 4:
            self.ui_q.put(("warn", "В билде меньше 4 навыков — автоэкипировка невозможна."))
            return
        side = b.get("side", "KILLER")
        self.mode_var.set(side)
        self.build = {
            "side": side,
            "char": b.get("char", ""),
            "power_or_item": b.get("power_or_item", EMPTY),
            "category": "",
            "power_is_item": side == "SURVIVOR",
            "addons": addons[:2],
            "perks": perks[:4],
            "author": b.get("author", "—"),
        }
        self._render_build()
        self.btn_equip.config(state="normal")
        self.notebook.select(self.tab_main)
        self.set_status(f"Билд от {self.build['author']} загружен. Откройте меню снаряжения "
                        f"и нажмите «ЭКИПИРОВАТЬ».", "#34c759")
        self.log(f"Загружен чужой билд: {GH.format_build_text(b).splitlines()[2]}")

    def publish_current_build(self):
        if not self.build:
            self.ui_q.put(("warn", "Сначала сгенерируйте билд на вкладке «БИЛД»."))
            return
        b = self.build
        if any(p == EMPTY for p in b["perks"]):
            self.ui_q.put(("warn", "В билде есть пустые слоты навыков — заполните их перед публикацией."))
            return
        author = str(self.cfg["publish"].get("nickname", "")).strip()
        if not author:
            author = simpledialog.askstring("Публикация", "Введите ваш ник (будет виден всем):",
                                            parent=self.root)
            if not author:
                return
            author = author.strip()[:30]
            self.cfg["publish"]["nickname"] = author
            try:
                self.nick_entry.delete(0, "end")
                self.nick_entry.insert(0, author)
            except Exception:
                pass
            save_config(self.cfg)
        token = GH.resolve_token(self.cfg)
        if not token:
            token = simpledialog.askstring("Публикация",
                                           "Введите токен GitHub (нужны права на запись в репозиторий).\n"
                                           "Сохранить навсегда можно во вкладке «БИЛДЫ»:",
                                           show="*", parent=self.root)
            if not token:
                return
            token = token.strip()
        addons = [EMPTY if a == NO_ADDONS else a for a in b["addons"]]
        payload = GH.make_build_payload(b["side"], b["char"], b["power_or_item"], addons,
                                        b["perks"], author)
        self.btn_publish.config(state="disabled")
        self.set_status("Публикуем билд на GitHub…", "#ffcc00")
        threading.Thread(target=self._publish_worker, args=(payload, token), daemon=True).start()

    def _publish_worker(self, payload, token):
        ok, msg = GH.publish_build_to_github(payload, token)

        def done():
            self.btn_publish.config(state="normal")
            if ok:
                self.set_status("🌍 " + msg, "#34c759")
                payload["local"] = True
                self.community_builds.insert(0, payload)
                self._render_builds_list()
                self.lbl_build_details.config(text=GH.format_build_text(payload))
                messagebox.showinfo("Публикация", msg)
            else:
                self.set_status("🔴 " + msg, "#ff3b30")
                self.log("Публикация не удалась: " + msg)
                messagebox.showerror("Публикация не удалась", msg)
        self.root.after(0, done)

    # ---------------------------------------------------------- автообновление --
    def periodic_update_check(self):
        if self.cfg["update"].get("auto", True):
            self.check_for_updates(silent=True)
        self.root.after(GH.UPDATE_CHECK_INTERVAL_MS, self.periodic_update_check)

    def check_for_updates(self, silent=False):
        if self._updating:
            return
        self._updating = True
        if not silent:
            self.set_status("Проверяю обновления на GitHub…", "#ffcc00")
        threading.Thread(target=self._update_worker, args=(silent,), daemon=True).start()

    def _update_worker(self, silent):
        try:
            token = GH.resolve_token(self.cfg)
            upd = GH.check_update(APP_VERSION, token=token,
                                  allow_branch=bool(self.cfg["update"].get("allow_branch", False)))
            if not upd:
                if not silent:
                    self.ui_q.put(("info", f"У вас уже установлена последняя версия (v{APP_VERSION})."))
                else:
                    self.log(f"Обновлений нет (текущая v{APP_VERSION}).")
                return
            if upd["tag"] == self.cfg["update"].get("skip_tag"):
                self.log(f"Обновление {upd['tag']} пропущено пользователем.")
                return
            bundle, info, missing = GH.download_update(upd["ref"], token=token)
            self.log(f"Найдено обновление {upd['tag']}: скачано и проверено файлов {len(bundle)}"
                     + (f"; в релизе нет: {', '.join(missing)}" if missing else ""))
            self.ui_q.put(("update", (upd, info, bundle)))
        except GH.UpdateError as exc:
            self.log(f"Обновление отклонено проверкой: {exc}")
            if not silent:
                self.ui_q.put(("error", f"Обновление НЕ установлено — проверка не пройдена:\n{exc}"))
        except Exception as exc:
            self.log(f"Проверка обновления не удалась: {exc!r}")
            if not silent:
                self.ui_q.put(("error", f"Проверка обновления не удалась:\n{exc}"))
        finally:
            self._updating = False

    def _show_update_dialog(self, upd, info, bundle):
        self._pending_update = (upd, info, bundle)
        dlg = UpdateDialog(self.root, upd, info)
        self.root.wait_window(dlg.top)
        if dlg.result == "restart":
            self.apply_and_restart(bundle)
        else:
            self.cfg["update"]["skip_tag"] = upd.get("tag", "")
            save_config(self.cfg)
            self.log(f"Обновление {upd.get('tag')} отложено (больше не предлагать эту версию).")
        self._pending_update = None

    def apply_and_restart(self, bundle):
        try:
            changed = GH.apply_update(bundle, APP_DIR)
        except GH.UpdateError as exc:
            messagebox.showerror("Обновление", str(exc))
            return
        if not changed:
            messagebox.showinfo("Обновление", "Файлы уже актуальны — заменять нечего.")
            return
        self.log("Обновлены файлы: " + ", ".join(changed) + " (старые версии — .bak)")
        try:
            subprocess.Popen([sys.executable, os.path.join(APP_DIR, "dbd_randomizer.py")], cwd=APP_DIR)
        except Exception as exc:
            messagebox.showerror("Перезапуск", f"Обновление установлено ({', '.join(changed)}), "
                                               f"но перезапустить не удалось:\n{exc}\n\nЗапустите программу вручную.")
            return
        self.abort.set()
        self.root.destroy()

    def toggle_auto_update(self):
        self.cfg["update"]["auto"] = bool(self.auto_update_var.get())
        save_config(self.cfg)
        self.log("Автопроверка обновлений: " + ("включена" if self.cfg["update"]["auto"] else "выключена"))

    # ----------------------------------------------------------- автоматизация --
    def _register_abort_hotkey(self):
        key = str(self.cfg["options"].get("abort_key", "f9")).lower()
        try:
            import keyboard
        except Exception:
            return
        try:
            if self._hotkey_handle is not None:
                keyboard.remove_hotkey(self._hotkey_handle)
        except Exception:
            pass
        try:
            self._hotkey_handle = keyboard.add_hotkey(key, self.request_abort)
        except Exception as exc:
            self.log(f"Не удалось назначить горячую клавишу {key}: {exc}")

    def request_abort(self):
        if not self.abort.is_set():
            self.abort.set()
            self.log("⏹ Получена команда СТОП.")
            self.set_status("Останавливаюсь…", "#ffcc00")

    def _sleep(self, seconds, abortable=True):
        end = time.time() + max(0.0, seconds)
        while time.time() < end:
            if abortable and self.abort.is_set():
                raise AbortError()
            time.sleep(min(0.05, max(0.0, end - time.time())))

    def _click(self, coord, label=""):
        if coord is None:
            raise RuntimeError(f"не задана координата {label}")
        if self.dry_var.get():
            self.log(f"[DRY] клик {label or ''} -> {coord}")
            return
        INPUT.click(coord[0], coord[1], hold=self.timing("hold"),
                    steps=int(self.timing("move_steps")))

    def _paste(self, text):
        if self.dry_var.get():
            self.log(f"[DRY] вставка текста: «{text}»")
            return True
        ok = INPUT.paste(text, verify=self.option("verify_clipboard"),
                         restore=self.option("restore_clipboard"))
        if not ok:
            self.log(f"⚠ Буфер обмена не принял текст «{text}» — вставка вслепую.")
        return ok

    def _ocr_matches(self, target):
        region = self.get_ocr_region()
        if not region or not self.option("ocr_verify"):
            return None
        text = ocr_read(*region)
        if not text:
            return None
        hit = _norm(target) in _norm(text)
        self.log(f"OCR: «{text[:60]}» -> {'совпало' if hit else 'НЕ совпало'} с «{target}»")
        return hit

    def search_and_select(self, target):
        """Клик по поиску -> вставка имени -> (проверка) -> клик по результату.

        Возвращает True, если элемент экипирован (или подтверждён OCR),
        False — если поиск, судя по всему, ничего не нашёл.
        """
        search = self.get_coord("search")
        result = self.get_coord("first_result")
        if search is None or result is None:
            raise RuntimeError("не заданы координаты search / first_result")
        settle = self.timing("search_settle")
        retries = max(0, int(self.timing("retries")))
        index = self.option("result_index")
        step = int(self.timing("result_step"))
        dry = self.dry_var.get()
        target_coord = result if index <= 1 else (result[0] + (index - 1) * step, result[1])

        for attempt in range(retries + 1):
            if self.abort.is_set():
                raise AbortError()
            if attempt:
                self.log(f"Повтор поиска «{target}» ({attempt}/{retries})…")

            self._click(search, "search")
            self._sleep(0.12)
            if self.option("use_clear_button"):
                self._click(self.get_coord("clear"), "clear")
                self._sleep(0.08)
                self._click(search, "search")
                self._sleep(0.08)
            if not dry:
                # Ctrl+A + Delete надёжнее кнопки «×»: работает и когда поле уже пустое
                INPUT.hotkey("ctrl", "a")
                self._sleep(0.03)
            self._paste(target)
            self._sleep(settle * (1.6 if attempt else 1.0))   # повтор — заведомо дольше

            checked = self._ocr_matches(target)
            if checked is False:
                if attempt < retries:
                    continue
                self.log(f"⚠ «{target}»: OCR не подтвердил результат — клик пропускается, "
                         f"проверьте имя в dbd_database.json.")
                return False

            self._click(target_coord, "first_result" if index <= 1 else f"result#{index}")
            self._sleep(0.15)
            return True
        return False

    def _equip_steps(self):
        b = self.build
        steps = []
        if self.selchar_var.get():
            steps.append(("char_search", b["char"], "персонаж"))
        if b["side"] == "SURVIVOR" and b.get("power_is_item"):
            if b["power_or_item"] not in (EMPTY,):
                steps.append(("item_slot", b["power_or_item"], "предмет"))
        for i, addon in enumerate(b["addons"], start=1):
            if addon in (EMPTY, NO_ADDONS):
                continue
            steps.append((f"addon{i}_slot", addon, f"аддон №{i}"))
        for i, perk in enumerate(b["perks"], start=1):
            if perk == EMPTY:
                continue
            steps.append((f"slot{i}", perk, f"навык {i}/4"))
        return steps

    def start_equip(self):
        if not self.build:
            messagebox.showwarning("Внимание", "Сначала сгенерируйте билд.")
            return
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Уже идёт", "Автоэкипировка уже запущена.")
            return
        self.collect_settings()

        steps = self._equip_steps()
        required = ["search", "first_result"] + [s[0] for s in steps]
        # «char_search» — это и слот, и поле поиска; координата одна
        missing = [r for r in dict.fromkeys(required) if self.get_coord(r) is None]
        if missing:
            messagebox.showerror("Координаты", "Не заданы координаты:\n" + "\n".join(f"• {m}" for m in missing))
            self.notebook.select(self.tab_coords)
            return
        if not self.dry_var.get() and not INPUT.available:
            messagebox.showerror("Автоматизация", f"Недоступен ввод: {INPUT.reason}\n"
                                                  "Включите «Сухой прогон», чтобы посмотреть план действий.")
            return
        if self.build["side"] == "KILLER":
            self.log("Режим МАНЬЯК: сила не экипируется — ставим только аддоны и навыки. "
                     "Персонажа выберите в игре сами.")

        save_config(self.cfg)
        self.abort.clear()
        self.btn_generate.config(state="disabled")
        self.btn_equip.config(state="disabled")
        self.worker = threading.Thread(target=self._run_automation, args=(steps,), daemon=True)
        self.worker.start()

    def _run_automation(self, steps):
        total = len(steps) + 1
        try:
            countdown = int(self.timing("countdown"))
            for i in range(countdown, 0, -1):
                if self.abort.is_set():
                    raise AbortError()
                self.set_status(f"⚠ Приготовьтесь: старт через {i} с… (СТОП — {self.option('abort_key').upper()})",
                                "#ffcc00")
                self.ui_q.put(("progress", (countdown - i) / max(1, total) * 100))
                time.sleep(1)

            mode = "СУХОЙ ПРОГОН" if self.dry_var.get() else "АВТО"
            self.log(f"=== {mode}: {total - 1} шаг(ов) ===")
            for done, (key, name, label) in enumerate(steps, start=1):
                if self.abort.is_set():
                    raise AbortError()
                self.set_status(f"{mode}: {label} — «{name}» ({done}/{len(steps)})", "#ff9500")
                self.log(f"→ {label}: кликаю слот «{key}»")
                self._click(self.get_coord(key), key)
                self._sleep(self.timing("after_slot_click"))
                ok = self.search_and_select(name)
                if not ok:
                    self.log(f"⚠ «{name}» — не подтверждено, продолжаю дальше.")
                self.ui_q.put(("progress", done / max(1, total) * 100))
                self._sleep(self.timing("between_steps"))

            self.set_status("🎉 Готово: билд экипирован.", "#34c759")
            self.log("=== Автоэкипировка завершена ===")
        except AbortError:
            self.set_status("⏹ Остановлено пользователем.", "#ffcc00")
            self.log("Остановлено пользователем.")
        except InputUnavailable as exc:
            self.set_status(f"🔴 Ввод недоступен: {exc}", "#ff3b30")
            self.ui_q.put(("error", f"Автоматизация недоступна:\n{exc}"))
        except Exception as exc:
            self.set_status(f"🔴 Ошибка: {exc}", "#ff3b30")
            self.log(f"Ошибка: {exc!r}")
            self.ui_q.put(("error", str(exc)))
        finally:
            self.ui_q.put(("progress", 100))
            self.root.after(0, lambda: (self.btn_generate.config(state="normal"),
                                        self.btn_equip.config(state="normal")))

    # ---------------------------------------------------------------- сервис --
    def run_data_check(self):
        errors, warnings = validate_db(self.db)
        text = [f"Проверка базы (версия {self.db.get('version')})",
                f"Убийц: {len(self.db['killers'])} | Выживших: {len(self.db['survivors'])} | "
                f"Категорий предметов: {len(self.db['survivor_items'])}",
                "",
                f"ОШИБКИ ({len(errors)}):"]
        text += [f"  ✖ {e}" for e in errors] or ["  — нет"]
        text += ["", f"ПРЕДУПРЕЖДЕНИЯ ({len(warnings)}):"]
        text += [f"  ⚠ {w}" for w in warnings[:120]] or ["  — нет"]
        if len(warnings) > 120:
            text.append(f"  … и ещё {len(warnings) - 120}")
        report = "\n".join(text)
        win = tk.Toplevel(self.root)
        win.title("Проверка базы данных")
        win.geometry("900x620")
        win.configure(bg="#121212")
        txt = tk.Text(win, bg="#141414", fg="#dcdcdc", font=("Consolas", 10), wrap="word",
                      relief="flat", padx=10, pady=10)
        txt.pack(fill="both", expand=True)
        txt.insert("end", report)
        txt.configure(state="disabled")
        ttk.Button(win, text="📋 Скопировать отчёт",
                   command=lambda: pyperclip.copy(report)).pack(pady=6)
        self.log(f"Проверка базы: ошибок {len(errors)}, предупреждений {len(warnings)}.")
        path = os.path.join(APP_DIR, "dbd_data_report.txt")
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(report + "\n")
        except Exception:
            pass

    def open_db_file(self):
        self.collect_settings()
        try:
            dump_db(self.db)
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось сохранить базу:\n{exc}")
            return
        try:
            os.startfile(DB_FILE)                       # Windows
        except Exception:
            filedialog.askopenfile(initialdir=APP_DIR, initialfile=os.path.basename(DB_FILE))

    def reset_db_file(self):
        if not messagebox.askyesno("Внимание", "Пересоздать dbd_database.json из встроенных данных?\n"
                                               "Ваши правки базы будут потеряны."):
            return
        if os.path.exists(DB_FILE):
            try:
                shutil.copy2(DB_FILE, DB_FILE + ".bak")
            except Exception:
                pass
        self.db = db_defaults()
        dump_db(self.db)
        self.log("dbd_database.json пересоздан (резервная копия — .bak). Перезапустите программу, "
                 "чтобы списки персонажей обновились.")
        messagebox.showinfo("Готово", "База пересоздана. Перезапустите программу.")

    def _on_close(self):
        self.abort.set()
        try:
            self.collect_settings()          # координаты, тайминги, ник, токен, автообновление
            self.save_owned_characters_silent()
            save_config(self.cfg)
        except Exception:
            pass
        self.root.destroy()

    def save_owned_characters_silent(self):
        killers = [n for (s, n), (v, _w) in self._char_widgets.items() if s == "K" and v.get()]
        survs = [n for (s, n), (v, _w) in self._char_widgets.items() if s == "S" and v.get()]
        self.cfg["owned"]["killers"] = sorted(killers)
        self.cfg["owned"]["survivors"] = sorted(survs)


class AbortError(Exception):
    pass


# ----------------------------------------------------------------------------
# --selftest: проверка базы и генератора без GUI
# ----------------------------------------------------------------------------
def selftest():
    print(f"DBD Randomizer selftest | app v{APP_VERSION} | база {DATA.VERSION}")
    db = load_db()
    errors, warnings = validate_db(db)
    print(f"  убийц: {len(db['killers'])}, выживших: {len(db['survivors'])}, "
          f"категорий предметов: {len(db['survivor_items'])}")
    print(f"  ошибок: {len(errors)}, предупреждений: {len(warnings)}")
    for e in errors:
        print("   ✖", e)
    for w in warnings[:15]:
        print("   ⚠", w)
    if len(warnings) > 15:
        print(f"   … ещё {len(warnings) - 15} предупреждений (кнопка «Проверить базу» в GUI)")

    random.seed(42)
    ok = True
    for side in ("KILLER", "SURVIVOR"):
        pool = sorted(db["killers"] if side == "KILLER" else db["survivors"])
        for mode in ("general", "unique", "mixed"):
            for _ in range(60):
                fn = make_killer_build if side == "KILLER" else make_survivor_build
                b = fn(db, pool, perk_mode=mode)
                need = 3 if mode == "unique" else 4
                if len(b["perks"]) != 4 or len(set(b["perks"])) != 4:
                    print("   ✖ перки:", side, mode, b["perks"]); ok = False
                if sum(1 for p in b["perks"] if p in (db["killers"].get(b["char"], {}) or {}).get("perks", [])
                       or p in db["survivors"].get(b["char"], [])) < min(need, 4) and mode == "unique":
                    print("   ✖ unique-режим потерял свои перки:", side, b["char"], b["perks"]); ok = False
                if len(b["addons"]) != 2:
                    print("   ✖ аддоны:", side, mode, b["addons"]); ok = False
    print("  генератор:", "OK" if ok else "ЕСТЬ ОШИБКИ")
    sample = make_killer_build(db, sorted(db["killers"]), perk_mode="mixed")
    print("\nПример билда:\n" + build_to_text(sample))
    return 0 if ok and not errors else 1


def main():
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    _load_tk()
    _set_dpi_awareness()
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
