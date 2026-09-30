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
import re
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
    import dbd_icons as ICONS
    from dbd_icons_store import IconStore, pil_available
    try:
        import dbd_skins as SKINS
    except ImportError:                   # старая папка после апдейта: работаем без скинов
        SKINS = None
except ImportError:                       # запуск из другой директории
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import dbd_data as DATA
    import dbd_github as GH
    import dbd_icons as ICONS
    from dbd_icons_store import IconStore, pil_available
    try:
        import dbd_skins as SKINS
    except ImportError:
        SKINS = None

if getattr(sys, "frozen", False):                 # сборка PyInstaller: файлы рядом с .exe
    APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
APP_VERSION = GH.APP_VERSION
ICONS_DIR = os.path.join(APP_DIR, "icons_cache")
ICON_SIZE = 34
CONFIG_FILE = os.path.join(APP_DIR, "dbd_randomizer_config.json")
LEGACY_CONFIG = os.path.join(APP_DIR, "dbd_randomizer_config.txt")
DB_FILE = os.path.join(APP_DIR, "dbd_database.json")
BACKEND_NAME = "pydirectinput"            # DirectInput нужен для полноэкранного DBD

# ----------------------------------------------------------------------------
# Windows: DPI awareness ДО создания окон, иначе координаты мыши и координаты
# игры разъезжаются при масштабе != 100%.
# ----------------------------------------------------------------------------
def _set_dark_titlebar(window):
    """Windows 10/11: тёмная рамка окна, чтобы приложение не выглядело «наполовину»."""
    if os.name != "nt":
        return
    try:
        window.update_idletasks()
        frame = window.wm_frame()
        hwnd = int(frame, 16) if frame else 0
        if not hwnd:
            return
        hwnd = ctypes.windll.user32.GetParent(hwnd) or hwnd
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        value = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value))
    except Exception:
        pass


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


class IconCombo:
    """Комбобокс с иконками: кнопка-поле (иконка + текст) и выпадающий Toplevel
    со списком «иконка + название» и строкой поиска. Значения уникальны в группе
    через колбэк on_select. API совместим с тем, что использует конструктор:
    get()/set()/configure(values=...)/pack()/grid()."""

    def __init__(self, master, app, values=(), on_select=None, width=28):
        self.app = app
        self._values = list(values)
        self._value = ""
        self.on_select = on_select
        self._popup = None
        self.frame = tk.Frame(master, bg="#1c232c", highlightbackground="#2a323d",
                              highlightthickness=1)
        self.icon = tk.Label(self.frame, bg="#1c232c", width=20, height=20)
        self.icon.pack(side="left", padx=(6, 4), pady=3)
        self.text = tk.Label(self.frame, bg="#1c232c", fg="#dfe5ea", anchor="w",
                             font=("Segoe UI", 9), width=width, justify="left")
        self.text.pack(side="left", fill="x", expand=True, pady=3)
        self.btn = tk.Button(self.frame, text="▾", bg="#1c232c", fg="#8d99a6",
                             activebackground="#333c48", activeforeground="#e6ebf0",
                             relief="flat", bd=0, font=("Segoe UI", 8),
                             command=self.toggle)
        self.btn.pack(side="right", fill="y", padx=(0, 2))
        for w in (self.frame, self.icon, self.text):
            w.bind("<Button-1>", lambda _e: self.toggle())
        self.set("")          # иначе иконка-лейбл остаётся без картинки и
                              # height=20 трактуется Tk как 20 СТРОК текста

    # -- API ------------------------------------------------------------------
    def get(self):
        return self._value

    def set(self, value):
        self._value = value or ""
        self.text.config(text=self._value if self._value else "— не выбрано —",
                         fg="#dfe5ea" if self._value else "#56606c")
        self.icon.config(image=self.app._icon_photo(self._value or None, 20), text="")

    def configure(self, values=None, **kw):
        if values is not None:
            self._values = list(values)
            if self._value and self._value not in self._values:
                self.set("")
        if kw:
            self.frame.config(**kw)
        return self

    config = configure

    def pack(self, *a, **kw):
        self.frame.pack(*a, **kw)
        return self

    def grid(self, *a, **kw):
        self.frame.grid(*a, **kw)
        return self

    # -- попап ------------------------------------------------------------------
    def toggle(self):
        if self._popup is not None:
            self._close()
            return
        self._open()

    def _open(self):
        self._close()
        top = tk.Toplevel(self.app.root)
        self._popup = top
        top.overrideredirect(True)
        top.configure(bg="#2a323d")
        top.withdraw()
        self.app.root.update_idletasks()
        x = self.frame.winfo_rootx()
        y = self.frame.winfo_rooty() + self.frame.winfo_height() + 2
        top.geometry(f"340x300+{x}+{y}")
        top.deiconify()

        search = tk.Entry(top, bg="#1c232c", fg="#e6ebf0", insertbackground="#e6ebf0",
                          bd=0, relief="flat", highlightthickness=1,
                          highlightbackground="#2a323d", font=("Segoe UI", 9))
        search.pack(fill="x", padx=6, pady=6)
        search.focus_set()

        canvas = tk.Canvas(top, bg="#151a21", highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(top, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg="#151a21")
        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=(0, 6))
        sb.pack(side="right", fill="y", pady=6)
        self._rows = {}

        def _wheel(event):
            canvas.yview_scroll(-1 if getattr(event, "delta", 0) > 0 or
                                getattr(event, "num", 0) == 4 else 1, "units")
            return "break"

        def fill(needle=""):
            for w in inner.winfo_children():
                w.destroy()
            self._rows.clear()
            needle = _norm(needle)
            shown = [v for v in self._values if not needle or needle in _norm(v)]
            for v in shown:
                row = tk.Frame(inner, bg="#151a21")
                row.pack(fill="x")
                img = tk.Label(row, bg="#151a21", width=20, height=20)
                img.pack(side="left", padx=(6, 6), pady=3)
                lbl = tk.Label(row, text=v, bg="#151a21", fg="#dfe5ea", anchor="w",
                               font=("Segoe UI", 9))
                lbl.pack(side="left", fill="x", expand=True, pady=3)
                img.config(image=self.app._icon_photo(v, 20))
                self._rows[v] = img
                for w in (row, img, lbl):
                    w.bind("<Button-1>", lambda _e, val=v: self._choose(val))
                    w.bind("<MouseWheel>", _wheel)
                    w.bind("<Button-4>", _wheel)
                    w.bind("<Button-5>", _wheel)
                    w.bind("<Enter>", lambda e, w=row: w.config(bg="#1c232c"))
                    w.bind("<Leave>", lambda e, w=row: w.config(bg="#151a21"))
            canvas.configure(scrollregion=canvas.bbox("all"))
            if shown:
                self.app._request_icons(shown)

        def on_key(_e=None):
            fill(search.get())
        search.bind("<KeyRelease>", on_key)
        search.bind("<Escape>", lambda _e: self._close())
        search.bind("<Down>", lambda _e: "break")
        fill("")

        for w in (canvas, inner):
            w.bind("<MouseWheel>", _wheel)
            w.bind("<Button-4>", _wheel)
            w.bind("<Button-5>", _wheel)
        top.bind("<FocusOut>", lambda _e: self._close())

    def _choose(self, value):
        self._close()
        self.set(value)
        if self.on_select:
            self.on_select(self, value)

    def _close(self):
        if self._popup is not None:
            try:
                self._popup.destroy()
            except Exception:
                pass
            self._popup = None

    def refresh_icon(self):
        """Вызывается, когда иконки докачались фоном."""
        if self._value:
            self.set(self._value)
        for name, img in getattr(self, "_rows", {}).items():
            img.config(image=self.app._icon_photo(name, 20))


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
    "perk_mode":       "mixed",     # mixed | unique | general
    "respect_owned":   False,       # учитывать белые списки OWNED_*
    "addons_enabled":  True,
    "skin_enabled":    True,        # подбирать набор одежды к билду
}


# Ревизия пространства id в dbd_skins.py: v2.11.0 перешла с «скинов персонажей»
# (p.cosChars, 1..111) на полную базу наборов (p.outfits, id 1..2996) + сдвиг
# COSCHAR_ID_OFFSET для скинов персонажей. Старые отметки владения при другой
# ревизии указывали бы на другие наборы, поэтому они сбрасываются (см. load_config).
SKINS_SCHEMA = 2


def default_config():
    cfg = {"coords": {}, "timings": {}, "options": {}, "owned": {}}
    for key, _ in COORD_FIELDS:
        cfg["coords"][key] = {"x": "", "y": ""}
    cfg["coords"]["ocr_region"].update({"w": "", "h": ""})
    for key, (val, _) in TIMING_DEFAULTS.items():
        cfg["timings"][key] = val
    cfg["options"] = dict(OPTION_DEFAULTS)
    cfg["owned"] = {"killers": [], "survivors": []}
    cfg["skins"] = {}                      # char -> список id имеющихся наборов
    cfg["skins_schema"] = SKINS_SCHEMA     # ревизия id наборов (dbd_skins.py)
    cfg["publish"] = {"nickname": "", "gh_token": "", "backend": "github", "firebase_url": ""}
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
            if isinstance(user.get("skins"), dict):
                # v2.10.x хранил id «скинов персонажей» (1..111): с v2.11 полная база
                # наборов использует те же числа для других записей — старые отметки
                # означали бы чужие наборы, поэтому при смене ревизии они сбрасываются.
                if user.get("skins_schema") == SKINS_SCHEMA:
                    cfg["skins"] = user["skins"]
                    cfg["skins_schema"] = SKINS_SCHEMA
                elif user["skins"]:
                    migrated = True
            for section in ("coords", "timings", "options", "owned", "publish", "update"):
                if isinstance(user.get(section), dict):
                    if section == "coords":
                        for key, val in user[section].items():
                            if isinstance(val, dict):
                                cfg["coords"].setdefault(key, {"x": "", "y": ""}).update(val)
                    else:
                        cfg[section].update(user[section])
            cfg, mig = _migrate_options(cfg)
            return cfg, migrated or mig
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
    cfg, extra = _migrate_options(cfg)
    return cfg, migrated or extra


def _migrate_options(cfg):
    """v2.1 и старше: дефолтом был режим «общие навыки», из-за чего падали только
    общие перки. Один раз переводим сохранённый конфиг на честный дефолт «mixed».
    Явный выбор пользователя после этого не затирается (флаг остаётся в конфиге).
    """
    opts = cfg.setdefault("options", {})
    if opts.get("perk_mode_mixed_default_v22"):
        return cfg, False
    opts["perk_mode_mixed_default_v22"] = True
    if opts.get("backend") == "anon":            # kvdb умер (нужна карта) -> firebase
        opts["backend"] = "firebase"
    if opts.get("perk_mode") == "general":
        opts["perk_mode"] = "mixed"
        return cfg, True
    return cfg, False


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


def all_unique_perks(db, side):
    """Все уникальные навыки стороны (свои + чужие) — для режима «уникальные»."""
    out = []
    src = db["killers"].values() if side == "KILLER" else db["survivors"].values()
    for entry in src:
        out.extend(entry.get("perks", []) if isinstance(entry, dict) else entry)
    return list(dict.fromkeys(out))


def pick_perks(db, side, char, perk_mode="mixed", respect_owned=False, available=None):
    """Ровно 4 навыка без повторов по режиму:

    ``general`` — только общие (есть у всех);
    ``mixed``   — 3 своих уникальных + 1 общий;
    ``unique``  — 3 своих уникальных + 1 уникальный любого другого персонажа;
    ``any``     — полностью случайные 4 из всех навыков стороны.

    ``available`` — список отмеченных персонажей (вкладка «ПЕРСОНАЖИ»): чужие
    уникальные навыки в режимах ``unique``/``mixed``/``any`` берутся только из
    него, чтобы генератор не предлагал перки неоткрытых персонажей.

    При respect_owned=True каждый подпул фильтруется белым списком, а недостающие
    слоты остаются EMPTY (автоэкипировка не будет тыкать в то, чего нет).
    """
    if side == "KILLER":
        unique = list(db["killers"].get(char, {}).get("perks", []))
        common = list(db.get("killer_common_perks", []))
        owned = db.get("owned", {}).get("killer_perks")
    else:
        unique = list(db["survivors"].get(char, []))
        common = list(db.get("surv_common_perks", []))
        owned = db.get("owned", {}).get("survivor_perks")
    foreign = [p for p in all_unique_perks(db, side)
               if p not in unique and p not in set(common)]
    if available is not None:
        # чужие уникальные берём ТОЛЬКО у отмеченных персонажей
        src_chars = db["killers"] if side == "KILLER" else db["survivors"]
        allowed = set()
        for name in available:
            entry = src_chars.get(name)
            if entry is None:
                continue
            allowed.update(entry.get("perks", []) if isinstance(entry, dict) else entry)
        foreign = [p for p in foreign if p in allowed]

    if perk_mode == "any":
        stages = ((common + unique + foreign, 4),)
    elif perk_mode == "unique":
        stages = ((unique, len(unique)), (foreign, 4), (common, 4))
    elif perk_mode == "mixed":
        stages = ((unique, len(unique)), (common, 4), (foreign, 4))
    else:
        stages = ((common, 4), (unique, 4), (foreign, 4))

    perks = []
    for pool, take in stages:
        if len(perks) >= 4:
            break
        candidates = _filter_owned([p for p in dict.fromkeys(pool) if p not in perks],
                                   owned, respect_owned)
        perks += _pick(candidates, min(take, 4 - len(perks)))
    return _fill_perks(perks, [], respect_owned) if respect_owned else perks[:4]


def pick_skin(char, owned_skins=None):
    """Случайный набор одежды персонажа из имеющихся (пустой список = все)."""
    ids = (getattr(SKINS, "CHAR_SKINS", {}) or {}).get(char) or []
    if not ids:
        return None
    owned = (owned_skins or {}).get(char)
    if owned is not None:                  # ключ есть: пустой список = ничего нет
        ids = [i for i in ids if i in set(owned)]
    if not ids:
        return None
    sid = random.choice(ids)
    info = (getattr(SKINS, "SKINS_BY_ID", {}) or {}).get(sid, {})
    return {"id": sid, "name": info.get("name", "?"),
            "display": info.get("name_ru") or info.get("name", "?")}


def make_killer_build(db, available, perk_mode="mixed", respect_owned=False,
                      addons_enabled=True, skin_enabled=True, owned_skins=None):
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


    perks = pick_perks(db, "KILLER", name, perk_mode, respect_owned, available)

    return {
        "side": "KILLER",
        "char": name,
        "power_or_item": info.get("power", EMPTY),
        "power_is_item": False,
        "addons": addons,
        "perks": perks[:4],
        "skin": pick_skin(name, owned_skins) if skin_enabled else None,
    }


def make_survivor_build(db, available, perk_mode="mixed", respect_owned=False,
                        addons_enabled=True, skin_enabled=True, owned_skins=None):
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

    perks = pick_perks(db, "SURVIVOR", name, perk_mode, respect_owned, available)

    return {
        "side": "SURVIVOR",
        "char": name,
        "power_or_item": item,
        "category": cat,
        "power_is_item": True,
        "addons": addons,
        "perks": perks[:4],
        "skin": pick_skin(name, owned_skins) if skin_enabled else None,
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
    skin = b.get("skin")
    if isinstance(skin, dict) and skin:
        lines.append(f"👗 Внешность (случайный набор): "
                     f"{skin.get('display') or skin.get('name', '?')}")
    elif isinstance(skin, str) and skin.strip():
        lines.append(f"👗 Внешность: {skin.strip()}")
    return "\n".join(lines)


def build_to_clipboard_text(b):
    """Компактный вариант для копирования/чата."""
    head = b["char"]
    if (b.get("title") or "").strip():
        head = f"«{b['title'].strip()}» — {head}"
    item = b["power_or_item"]
    addons = " + ".join(a for a in b["addons"] if a not in (EMPTY, NO_ADDONS)) or "без аддонов"
    perks = ", ".join(b["perks"])
    skin = (f" | 👗 {b['skin'].get('display') or b['skin']['name']}"
            if b.get("skin") else "")
    return f"{head} | {item} | {addons} | Перки: {perks}{skin}"


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
        self.top.configure(bg="#151a21")
        self.top.attributes("-topmost", True)
        self.top.resizable(False, False)
        tk.Label(self.top, text="🎯 Наведите мышь на нужную точку\nи кликните ЛКМ в этом окне.\nEsc — отмена",
                 bg="#151a21", fg="#e6ebf0", font=("Segoe UI", 10), justify="center").pack(pady=10)
        self.lbl = tk.Label(self.top, text="x: —   y: —", bg="#151a21", fg="#e5534b",
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
        self.top.configure(bg="#151a21")
        self.top.attributes("-topmost", True)
        self.top.transient(parent)
        self.top.grab_set()

        ttk.Label(self.top, text=f"Установлена v{APP_VERSION} → доступна {upd.get('tag', '')}",
                  font=("Segoe UI", 11, "bold"), foreground="#e5534b").pack(pady=(12, 4))
        ttk.Label(self.top, text=f"Источник: {GH.GITHUB_REPO} @ {upd.get('ref', '')}",
                  font=("Segoe UI", 8), foreground="#8d99a6").pack()

        notes = tk.Text(self.top, height=8, bg="#2a323d", fg="#e6ebf0", relief="flat",
                        wrap="word", font=("Segoe UI", 10))
        notes.pack(fill="both", expand=True, padx=14, pady=8)
        notes.insert("end", (upd.get("notes") or "").strip() or "Описание отсутствует.")
        notes.configure(state="disabled")

        ttk.Label(self.top, text="Будут заменены файлы (старые сохранятся как .bak):",
                  font=("Segoe UI", 9, "bold"), foreground="#e6ebf0").pack(anchor="w", padx=16)
        rows = tk.Text(self.top, height=len(info) + 1, bg="#1c232c", fg="#7ee2a8", relief="flat",
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
        self.icon_store = IconStore(ICONS_DIR, enabled=True)
        self._photos = {}
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
        root.configure(bg="#0e1116")
        try:
            sw = max(640, int(root.winfo_screenwidth()))
            sh = max(480, int(root.winfo_screenheight()))
        except Exception:
            sw, sh = 1280, 800
        root.geometry(f"{min(1120, sw - 60)}x{min(800, sh - 90)}")
        root.minsize(min(900, sw - 20), min(620, sh - 20))

        self._setup_style()
        _set_dark_titlebar(root)
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
        if self.icon_store.enabled:
            have, total = self.icon_store.stats()
            self.log(f"Иконки навыков: {have}/{total} в кэше; карта покрывает "
                     f"{len(ICONS.PERK_ICONS)} навыков. Недостающие докачаются при показе билда.")
        else:
            self.log("⚠ Pillow не установлен — карточка билда будет без иконок "
                     "(pip install Pillow).")

    # ---------------------------------------------------------------- стиль --
    def _setup_style(self):
        """Дизайн-система v2.6: тёмный «туман», кровавый акцент, боковая навигация."""
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")          # «default» на Windows игнорирует цвета
        except Exception:
            pass
        bg, panel, surface = "#0e1116", "#151a21", "#1c232c"
        line, fg, muted = "#2a323d", "#e6ebf0", "#8d99a6"
        acc, killer, surv = "#e5534b", "#ff7b72", "#58a6ff"
        ok, warn, danger = "#3fb950", "#e3b341", "#f85149"
        F = "Segoe UI"
        style.configure(".", background=bg, foreground=fg, font=(F, 10), bordercolor=line)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("Muted.TLabel", background=bg, foreground=muted, font=(F, 9))
        style.configure("Head.TLabel", background=bg, foreground=fg, font=(F, 13, "bold"))
        style.configure("Panel.TLabel", background=panel, foreground=fg)
        style.configure("PanelMuted.TLabel", background=panel, foreground=muted, font=(F, 9))
        style.configure("TFrame", background=bg)
        style.configure("Panel.TFrame", background=panel)
        style.configure("TLabelframe", background=panel, bordercolor=line, relief="flat")
        style.configure("TLabelframe.Label", background=panel, foreground=muted,
                        font=(F, 9, "bold"))
        # Навигация слева: notebook с вертикальными вкладками
        style.configure("TNotebook", background=bg, borderwidth=0, tabmargins=(0, 8, 8, 0))
        style.configure("TNotebook.Tab", background=bg, foreground=muted,
                        padding=(16, 12), font=(F, 10, "bold"), borderwidth=0)
        style.map("TNotebook.Tab",
                  background=[("selected", surface), ("active", "#161b22")],
                  foreground=[("selected", fg), ("active", fg)])
        style.configure("TCheckbutton", background=panel, foreground=fg, font=(F, 10))
        style.map("TCheckbutton", background=[("active", panel)],
                  indicatorcolor=[("selected", acc), ("!selected", "#39424e")])
        style.configure("TRadiobutton", background=panel, foreground=fg, font=(F, 10))
        style.map("TRadiobutton", background=[("active", panel)],
                  indicatorcolor=[("selected", acc), ("!selected", "#39424e")])
        style.configure("TButton", background=surface, foreground=fg, padding=(10, 6),
                        bordercolor=line, font=(F, 10))
        style.map("TButton", background=[("active", "#333c48"), ("disabled", "#161b22")],
                  foreground=[("disabled", "#56606c")])
        style.configure("Gen.TButton", background=acc, foreground="#ffffff",
                        font=(F, 12, "bold"), padding=(14, 10), bordercolor=acc)
        style.map("Gen.TButton", background=[("active", "#f0716a"), ("disabled", "#4d2622")],
                  foreground=[("disabled", "#8d99a6")])
        style.configure("Equip.TButton", background=ok, foreground="#0f2b18",
                        font=(F, 11, "bold"), padding=(12, 8), bordercolor=ok)
        style.map("Equip.TButton", background=[("active", "#56d364"), ("disabled", "#1f4d2e")])
        style.configure("Stop.TButton", background="#2b1110", foreground=danger,
                        font=(F, 11, "bold"), padding=(12, 8), bordercolor=danger)
        style.map("Stop.TButton", background=[("active", "#3d1512")])
        # Поля ввода
        for name in ("TEntry", "TCombobox", "TSpinbox"):
            style.configure(name, fieldbackground=surface, foreground=fg,
                            insertcolor=fg, bordercolor=line, lightcolor=line,
                            darkcolor=line, padding=(8, 5), arrowcolor=muted)
            style.map(name, fieldbackground=[("focus", "#202834"), ("disabled", "#161b22")],
                      bordercolor=[("focus", acc)],
                      foreground=[("disabled", "#56606c")])
        self.root.option_add("*TCombobox*Listbox.background", surface)
        self.root.option_add("*TCombobox*Listbox.foreground", fg)
        self.root.option_add("*TCombobox*Listbox.selectBackground", acc)
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        # Список билдов сообщества
        style.configure("Treeview", background=panel, fieldbackground=panel, foreground=fg,
                        bordercolor=line, lightcolor=line, darkcolor=line,
                        rowheight=30, font=(F, 9))
        style.configure("Treeview.Heading", background=surface, foreground=muted,
                        bordercolor=line, relief="flat", font=(F, 9, "bold"))
        style.map("Treeview", background=[("selected", "#26364a")],
                  foreground=[("selected", "#79c0ff")])
        style.map("Treeview.Heading", background=[("active", "#232b36")])
        # Полосы прокрутки и прогресс
        for orient in ("Vertical", "Horizontal"):
            style.configure(f"{orient}.TScrollbar", background=surface, troughcolor=bg,
                            bordercolor=bg, arrowcolor=muted, lightcolor=surface,
                            darkcolor=surface, gripcolor="#39424e")
            style.map(f"{orient}.TScrollbar",
                      background=[("active", "#39424e"), ("disabled", "#161b22")])
        style.configure("TProgressbar", troughcolor=surface, background=acc,
                        bordercolor=surface, lightcolor=acc, darkcolor=acc)
        style.configure("Horizontal.TProgressbar", troughcolor=surface, background=acc)
        style.configure("TPanedwindow", background=bg)
        style.configure("Sash", sashthickness=8, gripcolor="#39424e", background=line)
        style.configure("TSeparator", background=line)
        style.configure("TMenubutton", background=bg, foreground=fg, arrowcolor=muted)
        style.configure("Toolbutton", background=surface, foreground=fg)
        style.map("Toolbutton", background=[("active", "#333c48")])
        self._pal = dict(bg=bg, panel=panel, surface=surface, line=line, fg=fg,
                         muted=muted, acc=acc, killer=killer, surv=surv,
                         ok=ok, warn=warn, danger=danger)

    # ------------------------------------------------------------- интерфейс --
    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        # --- шапка: лого, название, переключатель стороны --------------------
        pal = self._pal
        head = tk.Frame(self.root, bg=pal["panel"], height=58,
                        highlightbackground=pal["line"], highlightthickness=1)
        head.grid(row=0, column=0, columnspan=2, sticky="ew")
        head.grid_propagate(False)
        tk.Label(head, text="☠", bg=pal["panel"], fg=pal["acc"],
                 font=("Segoe UI", 20, "bold")).pack(side="left", padx=(16, 0))
        ttl = tk.Frame(head, bg=pal["panel"])
        ttl.pack(side="left", padx=(10, 0))
        tk.Label(ttl, text="DBD ULTIMATE SEARCH RANDOMIZER", bg=pal["panel"],
                 fg=pal["fg"], font=("Segoe UI", 11, "bold"), anchor="w").pack(anchor="w")
        tk.Label(ttl, text=f"SURV & KILLER · v{APP_VERSION}", bg=pal["panel"],
                 fg=pal["muted"], font=("Segoe UI", 8), anchor="w").pack(anchor="w")
        self.mode_var = tk.StringVar(value=self.cfg["options"].get("side", "KILLER"))
        seg = tk.Frame(head, bg=pal["panel"])
        seg.pack(side="right", padx=16)
        for text, value, color in (("👹 МАНЬЯКИ", "KILLER", pal["killer"]),
                                   ("👤 ВЫЖИВАЮЩИЕ", "SURVIVOR", pal["surv"])):
            rb = tk.Radiobutton(seg, text=text, variable=self.mode_var, value=value,
                                bg=pal["surface"], fg=color, selectcolor=pal["panel"],
                                activebackground=pal["surface"], activeforeground=color,
                                font=("Segoe UI", 9, "bold"), command=self._on_mode_change,
                                relief="flat", bd=0, highlightthickness=1,
                                highlightbackground=pal["line"], padx=10, pady=3)
            rb.pack(side="left", padx=(0, 6))

        pal = self._pal
        self.root.columnconfigure(0, weight=0, minsize=218)
        self.root.columnconfigure(1, weight=1)
        self.nav = tk.Frame(self.root, bg="#0b0e12", width=218)
        self.nav.grid(row=1, column=0, sticky="ns")
        self.nav.grid_propagate(False)
        tk.Label(self.nav, text="НАВИГАЦИЯ", bg="#0b0e12", fg="#56606c",
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=20, pady=(16, 6))
        self._page = "main"
        self._nav_items = {}
        for key, icon, text in (("main", "🎲", "БИЛД"), ("maker", "🛠", "КОНСТРУКТОР"),
                                ("builds", "🌍", "БИЛДЫ СООБЩЕСТВА"),
                                ("chars", "🎭", "ПЕРСОНАЖИ"),
                                ("skins", "👗", "ВНЕШНОСТЬ"),
                                ("coords", "🎯", "КЛИКИ И ТАЙМИНГИ")):
            self._nav_items[key] = self._add_nav_item(key, icon, text)
        tk.Frame(self.nav, bg="#2a323d", height=1).pack(fill="x", padx=16, pady=(10, 8))
        tk.Label(self.nav, text="F5 билд · F6 перки · F7 копия", bg="#0b0e12",
                 fg="#56606c", font=("Segoe UI", 8), anchor="w",
                 justify="left").pack(anchor="w", padx=20)
        self.content = tk.Frame(self.root, bg=pal["bg"])
        self.content.grid(row=1, column=1, sticky="nsew")
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)
        self.tab_main = ttk.Frame(self.content)
        self.tab_maker = ttk.Frame(self.content)
        self.tab_builds = ttk.Frame(self.content)
        self.tab_chars = ttk.Frame(self.content)
        self.tab_skins = ttk.Frame(self.content)
        self.tab_coords = ttk.Frame(self.content)
        for fr in (self.tab_main, self.tab_maker, self.tab_builds,
                   self.tab_chars, self.tab_skins, self.tab_coords):
            fr.grid(row=0, column=0, sticky="nsew")

        self._build_main_tab()
        self._build_maker_tab()
        self._build_builds_tab()
        self._build_chars_tab()
        self._build_skins_tab()
        self._build_coords_tab()
        self._show_page("main")
        for key, fn in (("<F5>", self.generate_build), ("<F6>", self.reroll_perks),
                        ("<F7>", self.copy_build)):
            self.root.bind(key, lambda _e, f=fn: f())

        # --- строка состояния -------------------------------------------------
        tk.Frame(self.root, bg=pal["line"], height=1).grid(row=2, column=0,
                                                            columnspan=2, sticky="ew")
        bottom = ttk.Frame(self.root)
        bottom.grid(row=3, column=0, columnspan=2, sticky="ew", padx=12, pady=(6, 8))
        self.status_dot = tk.Label(bottom, text="●", fg="#56606c",
                                   font=("Segoe UI", 10))
        self.status_dot.pack(side="left", padx=(0, 6))
        self.status = ttk.Label(bottom, text="Готово. Сгенерируйте билд.", foreground="#8d99a6",
                                font=("Segoe UI", 9), wraplength=760, justify="left")
        self.status.pack(side="left", fill="x", expand=True)
        self.btn_stop = ttk.Button(bottom, text="⏹ СТОП (F9)", style="Stop.TButton",
                                   command=self.request_abort, width=14)
        self.btn_stop.pack(side="right", padx=(8, 0))

    def _add_nav_item(self, key, icon, text):
        pal = self._pal
        wrap = tk.Frame(self.nav, bg="#0b0e12")
        wrap.pack(fill="x")
        bar = tk.Frame(wrap, bg="#0b0e12", width=3)
        bar.pack(side="left", fill="y")
        lbl = tk.Label(wrap, text=f"{icon}   {text}", bg="#0b0e12", fg=pal["muted"],
                       font=("Segoe UI", 10, "bold"), anchor="w", padx=17, pady=10)
        lbl.pack(side="left", fill="x", expand=True)

        def enter(_e=None):
            if self._page != key:
                wrap.config(bg="#161b22"); bar.config(bg="#161b22")

        def leave(_e=None):
            if self._page != key:
                wrap.config(bg="#0b0e12"); bar.config(bg="#0b0e12")

        def click(_e=None):
            self._show_page(key)
        for w in (wrap, bar, lbl):
            w.bind("<Enter>", enter)
            w.bind("<Leave>", leave)
            w.bind("<Button-1>", click)
        return wrap, bar, lbl

    def _show_page(self, key):
        pal = self._pal
        self._page = key
        for k, (wrap, bar, lbl) in self._nav_items.items():
            active = (k == key)
            wrap.config(bg=pal["panel"] if active else "#0b0e12")
            bar.config(bg=pal["acc"] if active else "#0b0e12")
            lbl.config(bg=pal["panel"] if active else "#0b0e12",
                       fg=pal["fg"] if active else pal["muted"])
        {"main": self.tab_main, "maker": self.tab_maker, "builds": self.tab_builds,
         "chars": self.tab_chars, "skins": self.tab_skins,
         "coords": self.tab_coords}[key].tkraise()

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
        self._build_card(box)

        right = ttk.Frame(self.tab_main)
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=8)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(3, weight=1)

        opt = ttk.LabelFrame(right, text=" НАСТРОЙКИ ГЕНЕРАЦИИ ")
        opt.grid(row=0, column=0, sticky="ew")
        self.perk_mode_var = tk.StringVar(value=self.cfg["options"].get("perk_mode", "general"))
        for text, value, hint in (("Смешанные: 3 своих + 1 общий", "mixed", ""),
                                  ("Уникальные: 3 своих + 1 чужой уникальный", "unique", ""),
                                  ("Случайные: любые 4 из всех навыков", "any", ""),
                                  ("Общие: только навыки, которые есть у всех", "general", "")):
            ttk.Radiobutton(opt, text=text, value=value, variable=self.perk_mode_var).pack(anchor="w", padx=8, pady=1)
        self.addons_var = tk.BooleanVar(value=self.cfg["options"].get("addons_enabled", True))
        ttk.Checkbutton(opt, text="Подбирать аддоны", variable=self.addons_var).pack(anchor="w", padx=8, pady=1)
        self.skin_var = tk.BooleanVar(value=self.cfg["options"].get("skin_enabled", True))
        ttk.Checkbutton(opt, text="👗 Внешность: случайный набор у выпавшего персонажа",
                        variable=self.skin_var).pack(anchor="w", padx=8, pady=1)
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
        self.txt_log = tk.Text(logbox, bg="#0b0e12", fg="#aab4bf", font=("Consolas", 9),
                               wrap="word", relief="flat", padx=6, pady=6, state="disabled", height=8)
        self.txt_log.grid(row=0, column=0, sticky="nsew")
        lsb = ttk.Scrollbar(logbox, orient="vertical", command=self.txt_log.yview)
        lsb.grid(row=0, column=1, sticky="ns")
        self.txt_log.configure(yscrollcommand=lsb.set)
        jbar = tk.Frame(logbox, bg=self._pal["panel"])
        jbar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=4, pady=(4, 4))
        ttk.Button(jbar, text="🧹 очистить", width=11,
                   command=self._clear_log).pack(side="right")
        ttk.Button(jbar, text="📋 копия", width=9,
                   command=self._copy_log).pack(side="right", padx=(0, 4))

    # ---- карточка билда с иконками -------------------------------------------
    def _build_card(self, parent):
        canvas = tk.Canvas(parent, bg="#0e1116", highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        self.card = tk.Frame(canvas, bg="#151a21", highlightbackground="#2a323d",
                             highlightthickness=1)
        win = canvas.create_window((0, 0), window=self.card, anchor="nw")
        self.card.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width - 2))
        canvas.configure(yscrollcommand=sb.set)
        canvas.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=6)
        sb.grid(row=0, column=1, sticky="ns", pady=6)

        def _wheel(event):
            canvas.yview_scroll(-1 if getattr(event, "delta", 0) > 0 or
                                getattr(event, "num", 0) == 4 else 1, "units")
            return "break"
        for w in (canvas, self.card):
            w.bind("<MouseWheel>", _wheel)
            w.bind("<Button-4>", _wheel)
            w.bind("<Button-5>", _wheel)

        pad = dict(bg="#151a21")
        self.card_stripe = tk.Frame(self.card, bg="#e5534b", height=3)
        self.card_stripe.pack(fill="x")

        head = tk.Frame(self.card, **pad)
        head.pack(fill="x", padx=16, pady=(14, 4))
        self.card_char_img = tk.Label(head, bg="#1c232c", width=ICON_SIZE + 14,
                                      height=ICON_SIZE + 14, highlightbackground="#2a323d",
                                      highlightthickness=1)
        self.card_char_img.pack(side="left", padx=(0, 10))
        col = tk.Frame(head, **pad)
        col.pack(side="left", fill="x", expand=True)
        self.card_char = tk.Label(col, anchor="w", fg="#e6ebf0", bg="#151a21",
                                  font=("Segoe UI", 15, "bold"))
        self.card_char.pack(fill="x")
        self.card_sub = tk.Label(col, anchor="w", fg="#7d8894", bg="#151a21",
                                 font=("Segoe UI", 9, "italic"))
        self.card_sub.pack(fill="x")
        self.card_author = tk.Label(head, anchor="e", fg="#e3b341", bg="#151a21",
                                    font=("Segoe UI", 9, "italic"), wraplength=150,
                                    justify="right")
        self.card_author.pack(side="right", padx=(8, 0))
        row_skin = tk.Frame(self.card, **pad)
        row_skin.pack(fill="x", padx=16, pady=(6, 0))
        self.card_skin_img = tk.Label(row_skin, bg="#151a21", width=24, height=24)
        self.card_skin_img.pack(side="left", padx=(0, 8))
        self.card_skin = tk.Label(row_skin, anchor="w", fg="#8d99a6", bg="#151a21",
                                  font=("Segoe UI", 9, "italic"))
        self.card_skin.pack(side="left", fill="x", expand=True)

        self.card_hint = tk.Label(self.card, justify="left", anchor="w", fg="#8d99a6",
                                  font=("Segoe UI", 10), wraplength=430, **pad)
        self.card_hint.pack(fill="x", padx=16, pady=(8, 4))

        self._card_section("⚡ СИЛА / ПРЕДМЕТ")
        tile = self._tile(self.card, wrap=360)
        tile[0].pack(fill="x", padx=16, pady=2)
        self.card_main_img, self.card_main = tile[1], tile[2]
        self.card_main.config(fg="#e5534b", font=("Segoe UI", 10, "bold"))

        self._card_section("🔧 АДДОНЫ")
        arow = tk.Frame(self.card, **pad)
        arow.pack(fill="x", padx=16, pady=2)
        arow.columnconfigure(0, weight=1)
        arow.columnconfigure(1, weight=1)
        self.card_addons = []
        for i in range(2):
            tile = self._tile(arow, wrap=150)
            tile[0].grid(row=0, column=i, sticky="nsew",
                         padx=(0 if i == 0 else 3, 3 if i == 0 else 0))
            self.card_addons.append((tile[1], tile[2]))

        self._card_section("🔮 НАВЫКИ")
        self.card_perks = []
        for _ in range(4):
            tile = self._tile(self.card, wrap=360)
            tile[0].pack(fill="x", padx=16, pady=2)
            tile[2].config(fg="#3fb950")
            self.card_perks.append((tile[1], tile[2]))

        bar = tk.Frame(self.card, **pad)
        bar.pack(fill="x", padx=16, pady=(10, 14))
        self.lbl_icons = tk.Label(bar, fg="#7d8894", bg="#151a21", font=("Segoe UI", 8),
                                  anchor="w", justify="left")
        self.lbl_icons.pack(side="left", fill="x", expand=True)
        self.btn_icons = tk.Button(bar, text="⬇ Все иконки", bg="#1c232c", fg="#e6ebf0",
                                   activebackground="#333c48", activeforeground="#ffffff",
                                   relief="flat", bd=0, font=("Segoe UI", 8), padx=10, pady=3,
                                   command=self.download_all_icons)
        self.btn_icons.pack(side="right")
        self._update_icon_hint()
        self._set_build_text(None)

    def _tile(self, parent, wrap=340):
        """Плитка слота: рамка, иконка слева, текст справа."""
        frame = tk.Frame(parent, bg="#1c232c", highlightbackground="#2a323d",
                         highlightthickness=1)
        img = tk.Label(frame, bg="#1c232c", width=ICON_SIZE, height=ICON_SIZE)
        img.pack(side="left", padx=(8, 8), pady=6)
        txt = tk.Label(frame, anchor="w", fg="#dfe5ea", bg="#1c232c",
                       font=("Segoe UI", 10), wraplength=wrap, justify="left")
        txt.pack(side="left", fill="x", expand=True, padx=(0, 10), pady=6)
        return frame, img, txt

    def _card_section(self, text):
        row = tk.Frame(self.card, bg="#151a21")
        row.pack(fill="x", padx=14, pady=(14, 4))
        tk.Label(row, text=text, anchor="w", fg="#8d99a6", bg="#151a21",
                 font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Frame(row, bg="#2a323d", height=1).pack(side="left", fill="x",
                                                    expand=True, padx=(10, 0), pady=(0, 4))

    def _update_icon_hint(self):
        have, total = self.icon_store.stats()
        if not self.icon_store.enabled:
            self.lbl_icons.config(text="Иконки недоступны (нужна библиотека Pillow: "
                                       "pip install Pillow)")
            self.btn_icons.config(state="disabled")
            return
        self.lbl_icons.config(text=f"Иконок в кэше: {have} из {total} · "
                                   f"докaчиваются автоматически в {os.path.basename(ICONS_DIR)}/")

    def _placeholder_photo(self, size):
        """Тёмный квадрат нужного размера в пикселях. ВАЖНО: без картинки Tk
        считает height Label'а в СТРОКАХ текста — плитки разъезжаются."""
        key = ("-", size)
        if key in self._photos:
            return self._photos[key]
        photo = None
        try:
            from PIL import Image, ImageTk
            photo = ImageTk.PhotoImage(Image.new("RGBA", (size, size), (44, 52, 64, 255)))
        except Exception:
            try:
                photo = tk.PhotoImage(width=size, height=size)
            except Exception:
                return None
        self._photos[key] = photo
        return photo

    def _icon_photo(self, name, size=ICON_SIZE):
        """PhotoImage иконки ИЛИ плейсхолдер: никогда None при живом Tk."""
        key = (name or "-", size)
        if key in self._photos:
            return self._photos[key]
        photo = None
        if self.icon_store.enabled and name and name not in (EMPTY, NO_ADDONS):
            try:
                from PIL import Image, ImageTk
                img = None
                path = self.icon_store.local_path(name)
                if path and os.path.getsize(path) > 400:
                    img = Image.open(path).convert("RGBA")
                if img is not None:
                    photo = ImageTk.PhotoImage(img.resize((size, size), Image.LANCZOS))
            except Exception:
                photo = None
        if photo is None:
            return self._placeholder_photo(size)
        self._photos[key] = photo
        return photo

    def _request_icons(self, names):
        if not self.icon_store.enabled:
            return
        self.icon_store.request(names, on_ready=lambda ready: self.ui_q.put(("icons", ready)))

    def _on_icons_ready(self, ready):
        self._photos.clear()               # сбрасываем заглушки
        self._update_icon_hint()
        if self.build:
            self._render_build()
        self._refresh_char_icons()
        self._show_build_details()
        for cb in self._mk_combos():
            cb.refresh_icon()
        self._refresh_skin_icons()

    def download_all_icons(self):
        if not self.icon_store.enabled:
            messagebox.showwarning("Иконки", "Нужна библиотека Pillow: pip install Pillow")
            return
        self.btn_icons.config(state="disabled")
        self.lbl_icons.config(text="Скачиваю иконки…")
        self.log("Начата массовая загрузка иконок с wiki.gg…")

        def work():
            try:
                done, todo = self.icon_store.fetch_all()
                self.ui_q.put(("log", f"Иконки: докачано {done} из {todo}."))
            except Exception as exc:
                self.ui_q.put(("log", f"Загрузка иконок прервана: {exc}"))
            finally:
                self.ui_q.put(("icons_done", None))
        threading.Thread(target=work, daemon=True).start()

    def _on_icons_done(self, _):
        self.btn_icons.config(state="normal")
        self._photos.clear()
        self._update_icon_hint()
        if self.build:
            self._render_build()
        self._refresh_char_icons()
        self._show_build_details()
        for cb in self._mk_combos():
            cb.refresh_icon()

    # ---- вкладка «Конструктор» ----------------------------------------------
    def _build_maker_tab(self):
        top = ttk.Frame(self.tab_maker)
        top.pack(fill="x", padx=10, pady=(8, 2))
        ttk.Label(top, text="Соберите билд вручную: название, описание, персонаж, аддоны и навыки. "
                            "Готовый билд можно положить в карточку, скопировать, экипировать или опубликовать.",
                  foreground="#e5534b", font=("Segoe UI", 9, "italic"),
                  justify="left", wraplength=940).pack(fill="x")

        box = ttk.LabelFrame(self.tab_maker, text=" ПАСПОРТ БИЛДА ")
        box.pack(fill="x", padx=10, pady=4)
        r = ttk.Frame(box)
        r.pack(fill="x", padx=8, pady=(6, 2))
        ttk.Label(r, text="Название:", width=10, anchor="w").pack(side="left")
        self.mk_title = tk.Entry(r, width=52, bg="#1c232c", fg="#e6ebf0",
                                 insertbackground="#e6ebf0", bd=1, relief="flat", highlightthickness=1, highlightbackground="#2a323d")
        self.mk_title.pack(side="left", padx=4)
        r2 = ttk.Frame(box)
        r2.pack(fill="x", padx=8, pady=(0, 6))
        ttk.Label(r2, text="Описание:", width=10, anchor="w").pack(side="left")
        self.mk_desc = tk.Text(r2, height=3, bg="#1c232c", fg="#e6ebf0",
                               insertbackground="#e6ebf0", bd=1, relief="solid",
                               font=("Segoe UI", 9), wrap="word")
        self.mk_desc.pack(side="left", fill="x", expand=True, padx=4)

        sel = ttk.LabelFrame(self.tab_maker, text=" СОСТАВ ")
        sel.pack(fill="both", expand=True, padx=10, pady=4)
        sel.columnconfigure(0, weight=1)
        sel.columnconfigure(1, weight=1)
        mk_left = ttk.Frame(sel)
        mk_left.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=6)
        mk_right = ttk.Frame(sel)
        mk_right.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=6)
        for fr in (mk_left, mk_right):
            fr.columnconfigure(0, weight=1)
        row = ttk.Frame(mk_left)
        row.grid(row=0, column=0, sticky="ew")
        ttk.Label(row, text="Сторона:", width=10, anchor="w").pack(side="left")
        self.mk_side_var = tk.StringVar(value="KILLER")
        for text, value, color in (("👹 Маньяк", "KILLER", "#ff7b72"),
                                   ("👤 Выживший", "SURVIVOR", "#58a6ff")):
            tk.Radiobutton(row, text=text, variable=self.mk_side_var, value=value,
                           bg="#0e1116", fg=color, selectcolor="#1c232c",
                           activebackground="#0e1116", activeforeground=color,
                           font=("Segoe UI", 9, "bold"),
                           command=self._mk_on_side).pack(side="left", padx=8)

        self.mk_row_char = ttk.Frame(mk_left)
        self.mk_row_char.grid(row=1, column=0, sticky="ew", pady=2)
        ttk.Label(self.mk_row_char, text="Персонаж:", width=10, anchor="w").pack(side="left")
        self.mk_char = ttk.Combobox(self.mk_row_char, state="readonly", width=22)
        self.mk_char.pack(side="left", padx=4)
        self.mk_char.bind("<<ComboboxSelected>>", lambda e: self._mk_on_char())
        self.mk_power_lbl = ttk.Label(self.mk_row_char, text="", foreground="#e5534b",
                                      font=("Segoe UI", 9))
        self.mk_power_lbl.pack(side="left", padx=10)

        self.mk_row_item = ttk.Frame(mk_left)
        self.mk_row_item.grid(row=2, column=0, sticky="ew", pady=2)
        self.mk_row_item.grid_remove()
        ttk.Label(self.mk_row_item, text="Категория:", width=10, anchor="w").pack(side="left")
        self.mk_cat = ttk.Combobox(self.mk_row_item, state="readonly", width=18)
        self.mk_cat.pack(side="left", padx=4)
        self.mk_cat.bind("<<ComboboxSelected>>", lambda e: self._mk_on_cat())
        ttk.Label(self.mk_row_item, text="Предмет:").pack(side="left", padx=(10, 2))
        self.mk_item = IconCombo(self.mk_row_item, self, width=24)
        self.mk_item.pack(side="left", padx=4)

        self.mk_row_addons = ttk.Frame(mk_right)
        self.mk_row_addons.grid(row=0, column=0, sticky="ew", pady=2)
        ttk.Label(self.mk_row_addons, text="Аддоны:", width=10, anchor="w").pack(side="left")
        self.mk_addons = []
        for _ in range(2):
            cb = IconCombo(self.mk_row_addons, self, width=24,
                           on_select=lambda src_cb, _v, g=None: self._mk_dedupe(
                               self.mk_addons if g is None else g, src_cb, _v))
            cb.pack(side="left", padx=4)
            self.mk_addons.append(cb)

        mk_perk_box = ttk.LabelFrame(mk_right, text=" НАВЫКИ ")
        mk_perk_box.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        mk_perk_box.columnconfigure(0, weight=1)
        self.mk_perks = []
        for i in range(4):
            prow = ttk.Frame(mk_perk_box)
            prow.pack(fill="x", padx=8, pady=2)
            ttk.Label(prow, text=f"Навык {i + 1}:", width=10, anchor="w").pack(side="left")
            cb = IconCombo(prow, self, width=38,
                           on_select=lambda src_cb, _v: self._mk_dedupe(self.mk_perks, src_cb, _v))
            cb.pack(side="left", padx=4)
            self.mk_perks.append(cb)

        btns = ttk.Frame(self.tab_maker)
        btns.pack(fill="x", padx=10, pady=(4, 10))
        ttk.Button(btns, text="🎲 Случайные перки",
                   command=self._mk_random_perks).pack(side="left", padx=3)
        ttk.Button(btns, text="👁 В карточку",
                   command=lambda: self._mk_to_card(False)).pack(side="left", padx=3)
        ttk.Button(btns, text="📋 Копировать", command=self._mk_copy).pack(side="left", padx=3)
        ttk.Button(btns, text="⚡ Экипировать", style="Equip.TButton",
                   command=self._mk_equip).pack(side="left", padx=3)
        ttk.Button(btns, text="🌍 Опубликовать", command=self._mk_publish).pack(side="left", padx=3)
        self._mk_on_side()

    # -- вспомогательные для конструктора --------------------------------------
    def _mk_chars(self):
        names = self.db["killers"] if self.mk_side_var.get() == "KILLER" else self.db["survivors"]
        return sorted(names)

    def _mk_perk_pool(self, available=None):
        side = self.mk_side_var.get()
        common = (self.db.get("killer_common_perks") if side == "KILLER"
                  else self.db.get("surv_common_perks"))
        uniques = all_unique_perks(self.db, side)
        if available is not None:
            src_chars = self.db["killers"] if side == "KILLER" else self.db["survivors"]
            allowed = set()
            for name in available:
                entry = src_chars.get(name)
                if entry is None:
                    continue
                allowed.update(entry.get("perks", []) if isinstance(entry, dict) else entry)
            uniques = [p for p in uniques if p in allowed]
        return list(dict.fromkeys(list(common) + uniques))

    def _mk_addon_pool(self):
        side, char = self.mk_side_var.get(), self.mk_char.get()
        if side == "KILLER":
            return list(self.db["killers"].get(char, {}).get("addons", []))
        return list(self.db["survivor_items"].get(self.mk_cat.get(), {}).get("addons", []))

    def _mk_on_side(self):
        chars = self._mk_chars()
        self.mk_char.configure(values=chars)
        if self.mk_char.get() not in chars:
            self.mk_char.set(chars[0] if chars else "")
        if self.mk_side_var.get() == "SURVIVOR":
            cats = sorted(self.db["survivor_items"])
            self.mk_cat.configure(values=cats)
            if self.mk_cat.get() not in cats:
                self.mk_cat.set(cats[0] if cats else "")
            self.mk_row_item.grid()
        else:
            self.mk_row_item.grid_remove()
        self._mk_on_char()

    def _mk_on_char(self):
        side, char = self.mk_side_var.get(), self.mk_char.get()
        pool = self._mk_perk_pool()
        for cb in self.mk_perks:
            cb.configure(values=pool)
        if side == "KILLER":
            self.mk_power_lbl.config(text=f"⚡ {self.db['killers'].get(char, {}).get('power', '')}")
        else:
            self.mk_power_lbl.config(text="")
            self._mk_on_cat()
            return
        self._mk_fill_addons()

    def _mk_on_cat(self):
        cat = self.mk_cat.get()
        items = list(self.db["survivor_items"].get(cat, {}).get("items", []))
        self.mk_item.configure(values=items)
        if self.mk_item.get() not in items:
            self.mk_item.set(items[0] if items else "")
        self._mk_fill_addons()

    def _mk_fill_addons(self):
        pool = self._mk_addon_pool()
        for cb in self.mk_addons:
            cur = cb.get()
            cb.configure(values=pool)
            if cur not in pool:
                cb.set("")

    def _mk_dedupe(self, group, src, value):
        """Не даёт выбрать один и тот же перк/аддон дважды: дубли сбрасываются."""
        if not value:
            return
        for other in group:
            if other is not src and other.get() == value:
                other.set("")

    def _mk_combos(self):
        return [self.mk_item] + list(self.mk_addons) + list(self.mk_perks)

    def _mk_random_perks(self):
        pool = self._mk_perk_pool(self.available_characters(self.mk_side_var.get()))
        for cb, perk in zip(self.mk_perks, _pick(pool, 4)):
            cb.set(perk)

    def _mk_collect(self):
        char = self.mk_char.get().strip()
        if not char:
            messagebox.showwarning("Конструктор", "Выберите персонажа.")
            return None
        side = self.mk_side_var.get()
        if side == "KILLER":
            power = self.db["killers"].get(char, {}).get("power", EMPTY)
            cat = ""
        else:
            power = self.mk_item.get().strip() or EMPTY
            cat = self.mk_cat.get()
        perks = [cb.get().strip() for cb in self.mk_perks]
        if len(perks) < 4 or any(not p for p in perks) or len(set(perks)) < 4:
            messagebox.showwarning("Конструктор",
                                   "Заполните 4 РАЗНЫХ навыка (или нажмите «🎲 Случайные перки»).")
            return None
        addons = [cb.get().strip() or EMPTY for cb in self.mk_addons]
        if addons[0] != EMPTY and addons[0] == addons[1]:
            messagebox.showwarning("Конструктор", "Аддоны не должны повторяться.")
            return None
        return {
            "side": side,
            "char": char,
            "power_or_item": power,
            "category": cat,
            "power_is_item": side == "SURVIVOR",
            "addons": addons[:2],
            "perks": perks[:4],
            "title": self.mk_title.get().strip()[:60],
            "description": self.mk_desc.get("1.0", "end").strip()[:300],
        }

    def _mk_to_card(self, equip):
        b = self._mk_collect()
        if not b:
            return
        self.build = b
        self._render_build()
        self.btn_equip.config(state="normal")
        self._show_page("main")
        if equip:
            self.start_equip()

    def _mk_copy(self):
        b = self._mk_collect()
        if not b:
            return
        try:
            pyperclip.copy(build_to_clipboard_text(b))
            self.set_status("Билд из конструктора скопирован.", "#3fb950")
        except Exception as exc:
            messagebox.showerror("Буфер обмена", str(exc))

    def _mk_equip(self):
        self._mk_to_card(True)

    def _mk_publish(self):
        b = self._mk_collect()
        if not b:
            return
        self.build = b
        self._render_build()
        self.publish_current_build()

    def _on_backend_change(self):
        if not getattr(self, "backend_var", None):
            return
        if self.backend_var.get() == "firebase":
            hint = ("Без токена: билд дописывается в общую Firebase-базу проекта владельца "
                    "(create-only). URL базы можно сменить выше.")
            if not self.firebase_entry.get().strip() and GH.FIREBASE_BASE_DEFAULT:
                self.firebase_entry.insert(0, GH.FIREBASE_BASE_DEFAULT)
        else:
            hint = ("Через GitHub Contents API: нужен токен с правом Contents: Write "
                    "(вкладка хранит его локально).")
        self.lbl_backend_hint.config(text=hint)

    # ---- вкладка «Внешность» -------------------------------------------------
    def _build_skins_tab(self):
        if SKINS is None:
            ttk.Label(self.tab_skins,
                      text="Модуль внешности (dbd_skins.py) не найден в этой папке.\n"
                           "Скачайте dbd_skins.py из последнего релиза рядом с программой "
                           "или обновите приложение целиком / возьмите свежий EXE.",
                      foreground="#e5534b", font=("Segoe UI", 10),
                      justify="left").pack(padx=16, pady=16)
            self._sk_widgets = {}
            return
        top = ttk.Frame(self.tab_skins)
        top.pack(fill="x", padx=10, pady=(8, 2))
        ttk.Label(top, text="Персонаж:").pack(side="left")
        chars = sorted(getattr(SKINS, "CHAR_SKINS", {}))
        self.sk_char = ttk.Combobox(top, state="readonly", width=24, values=chars)
        self.sk_char.pack(side="left", padx=6)
        self.sk_char.bind("<<ComboboxSelected>>", lambda e: self._sk_on_char())
        ttk.Button(top, text="🎲 Случайный набор", command=self._sk_random).pack(side="left", padx=4)
        ttk.Button(top, text="Все", command=lambda: self._sk_set_all(True)).pack(side="left", padx=3)
        ttk.Button(top, text="Никого", command=lambda: self._sk_set_all(False)).pack(side="left", padx=3)
        ttk.Button(top, text="💾 Сохранить", command=self._sk_save).pack(side="left", padx=3)
        self.sk_count = ttk.Label(top, text="", foreground="#8d99a6", font=("Segoe UI", 9))
        self.sk_count.pack(side="right")
        all_skins = getattr(SKINS, "SKINS_BY_ID", {}) or {}
        total, chars_n = len(all_skins), len(getattr(SKINS, "CHAR_SKINS", {}) or {})
        n_ru = sum(1 for i in all_skins.values() if i.get("name_ru"))
        if n_ru >= total:
            names_note = "Все названия — русские."
        elif n_ru:
            names_note = (f"Русские названия: {n_ru} из {total} — сняты с русской вики "
                          "(статьи «(наборы одежды)» и «(кастомизация)»). У остальных "
                          "показаны английские: на русской вики их нет. Чтобы закрыть "
                          "остаток официальными именами из русского клиента, заполните "
                          "tools/skin_names_missing.csv и запустите tools/ru_names_missing.py "
                          "+ tools/resolve_skins.py.")
        else:
            names_note = ("Названия английские: русские имена снимаются с русской вики "
                          "(tools/fetch_ru_skins.py), таблица пока пуста.")
        ttk.Label(self.tab_skins,
                  text=f"База внешности: {total} записей у {chars_n} персонажей "
                       f"(данные wiki.gg, патч {getattr(SKINS, 'GAME_VERSION', '?')}). "
                       "Отметьте наборы, которые у вас есть: неотмеченные не выпадают в билдах "
                       "и в «🎲 Случайный набор». ★ — скин персонажа (отдельная модель/голос), "
                       f"остальные — наборы одежды. {names_note}",
                  foreground="#e5534b", font=("Segoe UI", 9, "italic"),
                  justify="left", wraplength=940).pack(fill="x", padx=10, pady=(0, 4))
        body = ttk.Frame(self.tab_skins)
        body.pack(fill="both", expand=True, padx=10, pady=4)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        prev = ttk.LabelFrame(body, text=" ПРЕВЬЮ ")
        prev.grid(row=0, column=0, sticky="ns", padx=(0, 6))
        self.sk_img = tk.Label(prev, bg="#151a21", width=110, height=110,
                               highlightbackground="#2a323d", highlightthickness=1)
        self.sk_img.pack(padx=10, pady=(10, 6))
        self.sk_name = tk.Label(prev, text="—", bg="#151a21", fg="#e6ebf0",
                                font=("Segoe UI", 11, "bold"), wraplength=190)
        self.sk_name.pack(padx=8)
        self.sk_meta = tk.Label(prev, text="", bg="#151a21", fg="#8d99a6",
                                font=("Segoe UI", 9), wraplength=190)
        self.sk_meta.pack(padx=8, pady=(2, 10))
        listf = ttk.LabelFrame(body, text=" НАБОРЫ ПЕРСОНАЖА ")
        listf.grid(row=0, column=1, sticky="nsew")
        self.sk_inner, _ = self._make_scrolled(listf)
        self._sk_widgets = {}
        if self.sk_char.get() not in chars:
            self.sk_char.set(chars[0] if chars else "")
        self._sk_on_char()

    def _sk_on_char(self):
        char = self.sk_char.get()
        ids = (getattr(SKINS, "CHAR_SKINS", {}) or {}).get(char, [])
        for w in self.sk_inner.winfo_children():
            w.destroy()
        self._sk_widgets = {}
        owned = (self.cfg.get("skins") or {}).get(char)
        owned_set = set(owned) if owned is not None else None
        for sid in ids:
            info = (getattr(SKINS, "SKINS_BY_ID", {}) or {}).get(sid, {})
            var = tk.BooleanVar(value=True if owned_set is None else sid in owned_set)
            row = tk.Frame(self.sk_inner, bg="#0e1116")
            row.pack(fill="x", padx=4, pady=1)
            img = tk.Label(row, bg="#0e1116", width=26, height=26)
            img.pack(side="left", padx=(2, 6))
            img.config(image=self._icon_photo(f"skin:{sid}", 26))
            cb = tk.Checkbutton(row, text=self._sk_label(sid, info), variable=var,
                                bg="#0e1116", fg="#dfe5ea", selectcolor="#1c232c",
                                activebackground="#0e1116", anchor="w",
                                font=("Segoe UI", 10), highlightthickness=0,
                                command=lambda s=sid: self._sk_preview_id(s))
            cb.pack(side="left", fill="x", expand=True)
            self._sk_widgets[sid] = (var, img)
        self._update_sk_count()
        self._request_icons([f"skin:{i}" for i in ids])
        self._sk_preview_id(ids[0] if ids else None)

    @staticmethod
    def _sk_name(info, sid=None):
        """Имя набора для показа: русское (из tools/skin_names_ru.py), иначе английское."""
        return info.get("name_ru") or info.get("name") or (f"набор №{sid}" if sid else "?")

    @classmethod
    def _sk_label(cls, sid, info):
        """Подпись набора в списке: «★ имя» для скинов персонажей (отдельная модель)."""
        name = cls._sk_name(info, sid)
        return ("★ " + name) if info.get("kind") == "coschar" else name

    @staticmethod
    def _sk_meta_text(char, info):
        """Строка под превью: персонаж, редкость, тип и дата выхода набора."""
        parts = [char]
        rar = info.get("rarity_ru") or (getattr(SKINS, "RARITY_RU", {}) or {}).get(info.get("rarity"))
        if rar:
            parts.append(rar)
        parts.append("скин персонажа" if info.get("kind") == "coschar" else "набор одежды")
        date = str(info.get("date") or "")
        if re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", date):
            parts.append("вышел " + date)
        return " · ".join(parts)

    def _sk_preview_id(self, sid):
        char = self.sk_char.get()
        info = (getattr(SKINS, "SKINS_BY_ID", {}) or {}).get(sid) if sid is not None else None
        if not info:
            self.sk_img.config(image=self._icon_photo(None, 110), text="")
            self.sk_name.config(text="—")
            self.sk_meta.config(text="")
            return
        self.sk_img.config(image=self._icon_photo(f"skin:{sid}", 110), text="")
        shown = self._sk_name(info, sid)
        if info.get("name_ru") and info.get("name"):
            shown = f"{info['name_ru']}\n({info['name']})"
        self.sk_name.config(text=shown)
        self.sk_meta.config(text=self._sk_meta_text(char, info))
        self._request_icons([f"skin:{sid}"])

    def _sk_random(self):
        ids = [sid for sid, (var, _i) in self._sk_widgets.items() if var.get()]
        if not ids:
            messagebox.showwarning("Внешность",
                                   "У этого персонажа не отмечен ни один набор.")
            return
        self._sk_preview_id(random.choice(ids))
        self.set_status("Случайный набор показан в превью.", "#3fb950")

    def _sk_set_all(self, value):
        for var, _i in self._sk_widgets.values():
            var.set(value)
        self._update_sk_count()

    def _update_sk_count(self):
        total = len(self._sk_widgets)
        on = sum(1 for var, _i in self._sk_widgets.values() if var.get())
        self.sk_count.config(text=f"отмечено {on}/{total}")

    def _sk_save(self):
        char = self.sk_char.get()
        ids = sorted(sid for sid, (var, _i) in self._sk_widgets.items() if var.get())
        self.cfg.setdefault("skins", {})[char] = ids
        save_config(self.cfg)
        self.set_status(f"Сохранено: у «{char}» отмечено наборов: {len(ids)}.", "#3fb950")
        self.log(f"Список наборов сохранён: {char} -> {len(ids)}.")

    def _refresh_skin_icons(self):
        for sid, (_var, img) in getattr(self, "_sk_widgets", {}).items():
            img.config(image=self._icon_photo(f"skin:{sid}", 26))
        if getattr(self, "sk_img", None) is not None and self.build and self.build.get("skin"):
            self.card_skin_img.config(
                image=self._icon_photo(f"skin:{self.build['skin'].get('id')}", 24), text="")

    # ---- вкладка «Персонажи» -------------------------------------------------
    def _make_scrolled(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        canvas = tk.Canvas(frame, bg="#0e1116", highlightthickness=0)
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
        ttk.Label(self.tab_chars, text=hint, foreground="#e5534b", justify="center",
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

        self._char_icons = {}
        self._lf_k, self._lf_s = lf_k, lf_s
        owned_k = set(self.cfg["owned"].get("killers") or [])
        owned_s = set(self.cfg["owned"].get("survivors") or [])
        for name in sorted(self.db["killers"].keys()):
            var = tk.BooleanVar(value=(name in owned_k) if owned_k else True)
            self._char_widgets[("K", name)] = (var, self._add_char_cb(inner_k, "K", name, var, "#ff7b72"))
        for name in sorted(self.db["survivors"].keys()):
            var = tk.BooleanVar(value=(name in owned_s) if owned_s else True)
            self._char_widgets[("S", name)] = (var, self._add_char_cb(inner_s, "S", name, var, "#58a6ff"))
        self._update_char_counts()
        self._request_icons([n for (_s, n) in self._char_widgets])   # портреты фоном

        note = ("Подсказка: если снять все отметки и нажать «Сохранить», при следующем запуске "
                "снова будут отмечены все.")
        ttk.Label(self.tab_chars, text=note, foreground="#7d8894",
                  font=("Segoe UI", 8, "italic")).pack(pady=(0, 8))

    def _add_char_cb(self, parent, side, name, var, color):
        row = tk.Frame(parent, bg="#0e1116")
        row.pack(fill="x", padx=4, pady=1)
        img = tk.Label(row, bg="#0e1116", width=22, height=22)
        img.pack(side="left", padx=(2, 6))
        cb = tk.Checkbutton(row, text=name, variable=var, bg="#0e1116", fg="#dfe5ea",
                            selectcolor="#1c232c", activebackground="#0e1116",
                            activeforeground=color, anchor="w", font=("Segoe UI", 10),
                            highlightthickness=0, command=self._update_char_counts)
        cb.pack(side="left", fill="x", expand=True)
        self._char_icons[(side, name)] = img
        img.config(image=self._icon_photo(name, 22))
        return row

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
        self.set_status(f"Сохранено: маньяков {len(killers)}, выживших {len(survs)}.", "#3fb950")
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
                ent = tk.Entry(row, width=6, bg="#1c232c", fg="#ffffff", insertbackground="#e6ebf0",
                               relief="solid", bd=1, justify="center")
                ent.insert(0, str(saved.get(axis, "")))
                ent.pack(side="left", padx=2)
                entries[axis] = ent
            if key == "ocr_region":
                for axis in ("w", "h"):
                    ent = tk.Entry(row, width=6, bg="#1c232c", fg="#ffffff", insertbackground="#e6ebf0",
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
            ent = tk.Entry(row, width=7, bg="#1c232c", fg="#ffffff", insertbackground="#e6ebf0",
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
                  font=("Segoe UI", 8, "italic"), foreground="#8d99a6", justify="left",
                  wraplength=330).pack(anchor="w", padx=6, pady=(0, 6))

    def _make_scrolled_grid(self, parent):
        canvas = tk.Canvas(parent, bg="#0e1116", highlightthickness=0)
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

    def set_status(self, text, color="#8d99a6"):
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
                    if getattr(self, "status_dot", None):
                        self.status_dot.config(fg=color)
                elif kind == "progress":
                    self.progress["value"] = payload
                elif kind == "error":
                    messagebox.showerror("Ошибка", payload)
                elif kind == "warn":
                    messagebox.showwarning("Внимание", payload)
                elif kind == "info":
                    messagebox.showinfo("Готово", payload)
                elif kind == "icons":
                    self._on_icons_ready(payload)
                elif kind == "icons_done":
                    self._on_icons_done(payload)
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

    def _clear_log(self):
        self.txt_log.configure(state="normal")
        self.txt_log.delete("1.0", "end")
        self.txt_log.configure(state="disabled")

    def _copy_log(self):
        try:
            pyperclip.copy(self.txt_log.get("1.0", "end").strip())
            self.set_status("Журнал скопирован.", "#3fb950")
        except Exception as exc:
            messagebox.showerror("Буфер обмена", str(exc))

    def _on_mode_change(self):
        self.cfg["options"]["side"] = self.mode_var.get()

    def _set_build_text(self, text):
        """Пустое состояние карточки: подсказка вместо билда."""
        self.card_hint.config(text=text or "")
        filler = "" if text else "—"
        self.card_author.config(text="")
        self.card_char.config(text="Билд не сгенерирован" if text else filler)
        self.card_main.config(text="")
        self.card_sub.config(text="")
        self.card_char_img.config(image=self._icon_photo(None, ICON_SIZE + 12), text="")
        self.card_main_img.config(image=self._icon_photo(None, ICON_SIZE), text="")
        self.card_skin_img.config(image=self._icon_photo(None, 24), text="")
        self.card_skin.config(text="" if text else "—", fg="#56606c")
        for img, lbl in self.card_addons:
            img.config(image=self._icon_photo(None, ICON_SIZE), text="")
            lbl.config(text=filler, fg="#56606c")
        for img, lbl in self.card_perks:
            img.config(image=self._icon_photo(None, ICON_SIZE), text="")
            lbl.config(text=filler, fg="#56606c")

    def _render_build(self):
        b = self.build
        if not b:
            return
        title = (b.get("title") or "").strip()
        desc = (b.get("description") or "").strip()
        self.card_hint.config(text=desc)
        head = ""
        if b.get("author"):
            head = f"🌍 билд сообщества от {b['author']}"
        elif title or desc:
            head = "🛠 собрано в конструкторе"
        if title:
            head = (head + " · " if head else "") + f"«{title}»"
        self.card_author.config(text=head)
        self.card_stripe.config(bg=self._pal["killer"] if b["side"] == "KILLER"
                                else self._pal["surv"])
        skin = b.get("skin")
        if skin:
            shown = skin.get("display") or skin.get("name") or str(skin)
            label = "👗 Внешность (случайный набор)" if isinstance(skin, dict) else "👗 Внешность"
            self.card_skin.config(text=f"{label}: {shown}", fg="#8d99a6")
            self.card_skin_img.config(
                image=self._icon_photo(f"skin:{skin.get('id')}", 24), text="")
            want_skin = [f"skin:{skin.get('id')}"]
        else:
            self.card_skin.config(text="", fg="#56606c")
            self.card_skin_img.config(image=self._icon_photo(None, 24), text="")
            want_skin = []
        if b["side"] == "KILLER":
            self.card_char.config(text=f"👹 {b['char']}", fg="#ff7b72")
            self.card_main.config(text=f"⚡ {b['power_or_item']}")
            self.card_sub.config(text="сила убийцы не экипируется — ставятся только аддоны и навыки")
        else:
            self.card_char.config(text=f"👤 {b['char']}", fg="#58a6ff")
            self.card_main.config(text=f"📦 {b['power_or_item']}")
            self.card_sub.config(text=f"категория: {b.get('category', '')}")

        for img_label, name in ((self.card_char_img, b["char"]),
                                (self.card_main_img, b["power_or_item"])):
            sz = ICON_SIZE if img_label is self.card_main_img else ICON_SIZE + 12
            img_label.config(image=self._icon_photo(
                name if name and name not in (EMPTY, NO_ADDONS) else None, sz), text="")
        want_extra = [n for n in (b["char"], b["power_or_item"])
                      if n and n not in (EMPTY, NO_ADDONS)]

        want_addons = []
        for (img, lbl), addon in zip(self.card_addons, list(b["addons"]) + ["", ""]):
            if not addon or addon == EMPTY:
                img.config(image=self._icon_photo(None, ICON_SIZE), text="")
                lbl.config(text="   •  —", fg="#56606c")
                continue
            if addon == NO_ADDONS:
                img.config(image=self._icon_photo(None, ICON_SIZE), text="")
                lbl.config(text="   •  🚫 аддон не подобран", fg="#7d8894")
                continue
            img.config(image=self._icon_photo(addon, ICON_SIZE), text="")
            lbl.config(text=f"   •  {addon}", fg="#dfe5ea")
            want_addons.append(addon)

        want = []
        for i, (img, lbl) in enumerate(self.card_perks):
            perk = b["perks"][i] if i < len(b["perks"]) else EMPTY
            if not perk or perk == EMPTY:
                img.config(image=self._icon_photo(None, ICON_SIZE), text="")
                lbl.config(text=f"{i + 1}.  —  (слот пуст)", fg="#56606c")
                continue
            img.config(image=self._icon_photo(perk, ICON_SIZE), text="")
            lbl.config(text=f"{i + 1}.  {perk}", fg="#3fb950")
            want.append(perk)
        self._request_icons(want + want_addons + want_extra + want_skin)

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
        if getattr(self, "backend_var", None):
            self.cfg["publish"]["backend"] = self.backend_var.get()
            self.cfg["publish"]["firebase_url"] = self.firebase_entry.get().strip()
        self.cfg["update"]["auto"] = bool(self.auto_update_var.get())
        self.cfg["update"]["allow_branch"] = bool(self.allow_branch_var.get())
        self.cfg["options"]["addons_enabled"] = bool(self.addons_var.get())
        self.cfg["options"]["skin_enabled"] = bool(self.skin_var.get())
        self.cfg["options"]["respect_owned"] = bool(self.owned_var.get())

    def save_settings(self):
        self.collect_settings()
        save_config(self.cfg)
        self.set_status("Настройки сохранены.", "#3fb950")
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
                      addons_enabled=bool(self.addons_var.get()),
                      skin_enabled=bool(self.skin_var.get()),
                      owned_skins=self.cfg.get("skins", {}))
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
                        "#3fb950")
        self.log("Сгенерирован билд: " + build_to_clipboard_text(self.build))
        _sk = self.build.get("skin")
        if isinstance(_sk, dict) and _sk:
            _info = (getattr(SKINS, "SKINS_BY_ID", {}) or {}).get(_sk.get("id"), {})
            _n = len((getattr(SKINS, "CHAR_SKINS", {}) or {}).get(self.build["char"], []))
            self.log(f"👗 Внешность: случайный набор «{_sk.get('display') or _sk.get('name')}» "
                     f"из {_n or '?'} у «{self.build['char']}»"
                     + (f" (редкость: {_info['rarity_ru']})" if _info.get("rarity_ru") else ""))

    def reroll_perks(self):
        if not self.build:
            messagebox.showwarning("Внимание", "Сначала сгенерируйте билд.")
            return
        b = self.build
        b["perks"] = pick_perks(self.db, b["side"], b["char"],
                                self.perk_mode_var.get(), bool(self.owned_var.get()),
                                self.available_characters(b["side"]))
        self._render_build()
        self.log("Перки перегенерированы: " + ", ".join(b["perks"]))

    def copy_build(self):
        if not self.build:
            messagebox.showwarning("Внимание", "Сначала сгенерируйте билд.")
            return
        try:
            pyperclip.copy(build_to_clipboard_text(self.build))
            self.set_status("Билд скопирован в буфер обмена.", "#3fb950")
        except Exception as exc:
            messagebox.showerror("Буфер обмена", str(exc))

    # ------------------------------------------------------- билды сообщества --
    def _bind_wheel_region(self, region, canvas):
        """Колесо мыши над любой частью региона листает страницу."""
        def _wheel(event):
            canvas.yview_scroll(-1 if getattr(event, "delta", 0) > 0 or
                                getattr(event, "num", 0) == 4 else 1, "units")
            return "break"

        def walk(w):
            w.bind("<MouseWheel>", _wheel)
            w.bind("<Button-4>", _wheel)
            w.bind("<Button-5>", _wheel)
            for c in w.winfo_children():
                walk(c)
        walk(region)
        for w in (canvas, region):
            w.bind("<MouseWheel>", _wheel)
            w.bind("<Button-4>", _wheel)
            w.bind("<Button-5>", _wheel)

    def _build_builds_tab(self):
        page = tk.Canvas(self.tab_builds, bg="#0e1116", highlightthickness=0, bd=0)
        psb = ttk.Scrollbar(self.tab_builds, orient="vertical", command=page.yview)
        page_inner = tk.Frame(page, bg="#0e1116")
        win = page.create_window((0, 0), window=page_inner, anchor="nw")
        page_inner.bind("<Configure>", lambda e: page.configure(scrollregion=page.bbox("all")))
        page.bind("<Configure>", lambda e: page.itemconfigure(win, width=e.width))
        page.configure(yscrollcommand=psb.set)
        page.pack(side="left", fill="both", expand=True)
        psb.pack(side="right", fill="y")
        self._builds_page = page_inner
        top_bar = ttk.Frame(page_inner)
        top_bar.pack(fill="x", padx=10, pady=(8, 2))
        ttk.Button(top_bar, text="🔄 Обновить список",
                   command=lambda: self.refresh_community_builds(manual=True)).pack(side="left")
        ttk.Button(top_bar, text="📋 Скопировать выбранный",
                   command=self.copy_selected_build).pack(side="left", padx=6)
        ttk.Button(top_bar, text="⚡ Экипировать выбранный", style="Equip.TButton",
                   command=self.equip_selected_build).pack(side="left", padx=6)
        self.lbl_builds_info = ttk.Label(top_bar, text="", foreground="#8d99a6",
                                         font=("Segoe UI", 9, "italic"))
        self.lbl_builds_info.pack(side="right")

        filt = ttk.Frame(page_inner)
        filt.pack(fill="x", padx=10, pady=2)
        ttk.Label(filt, text="Фильтр:").pack(side="left")
        self.builds_filter_var = tk.StringVar(value="ВСЕ")
        for value, text in (("ВСЕ", "Все"), ("KILLER", "👹 Маньяки"), ("SURVIVOR", "👤 Выжившие")):
            rb = tk.Radiobutton(filt, text=text, variable=self.builds_filter_var, value=value,
                                bg="#0e1116", fg="#e6ebf0", selectcolor="#1c232c",
                                activebackground="#0e1116", activeforeground="#ffffff",
                                font=("Segoe UI", 9), command=self._render_builds_list)
            rb.pack(side="left", padx=4)
        ttk.Label(filt, text="Поиск:", font=("Segoe UI", 9)).pack(side="left", padx=(14, 2))
        self.builds_search_entry = tk.Entry(filt, width=22, bg="#1c232c", fg="#e6ebf0",
                                            insertbackground="#e6ebf0", bd=1, relief="flat", highlightthickness=1, highlightbackground="#2a323d")
        self.builds_search_entry.pack(side="left")
        self.builds_search_entry.bind("<KeyRelease>", lambda e: self._render_builds_list())

        list_frame = ttk.Frame(page_inner)
        list_frame.pack(fill="x", padx=10, pady=5)
        self.builds_tree = ttk.Treeview(list_frame,
                                        columns=("side", "author", "title", "char", "main", "perks"),
                                        show="headings", height=9)
        for col, text, width, anch in (("side", "Сторона", 84, "center"), ("author", "Автор", 96, "w"),
                                       ("title", "Название", 130, "w"),
                                       ("char", "Персонаж", 130, "w"),
                                       ("main", "Сила / Предмет", 160, "w"),
                                       ("perks", "Навыки", 320, "w")):
            self.builds_tree.heading(col, text=text)
            self.builds_tree.column(col, width=width, anchor=anch)
        tsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.builds_tree.yview)
        self.builds_tree.configure(yscrollcommand=tsb.set)
        self.builds_tree.pack(side="left", fill="both", expand=True)
        tsb.pack(side="right", fill="y")
        try:
            self.builds_tree.tag_configure("killer", foreground="#ff7b72")
            self.builds_tree.tag_configure("survivor", foreground="#79c0ff")
            self.builds_tree.tag_configure("mine", foreground="#e3b341")
            self.builds_tree.tag_configure("even", background="#151a21")
            self.builds_tree.tag_configure("odd", background="#12171f")
        except Exception:
            pass
        self.builds_tree.bind("<Double-1>", lambda e: self.copy_selected_build())
        self.builds_tree.bind("<<TreeviewSelect>>", lambda e: self._show_build_details())

        det = ttk.LabelFrame(page_inner, text=" ДЕТАЛИ ВЫБРАННОГО БИЛДА ")
        det.pack(fill="x", padx=10, pady=(0, 5))
        inner = tk.Frame(det, bg="#151a21", highlightbackground="#2a323d",
                         highlightthickness=1)
        inner.pack(fill="x", padx=8, pady=8)
        self.det_stripe = tk.Frame(inner, bg="#e5534b", height=2)
        self.det_stripe.pack(fill="x")
        head = tk.Frame(inner, bg="#151a21")
        head.pack(fill="x", padx=10, pady=(8, 2))
        self.det_char_img = tk.Label(head, bg="#151a21", width=30, height=30)
        self.det_char_img.pack(side="left", padx=(0, 8))
        self.det_title = tk.Label(head, anchor="w", fg="#e6ebf0", bg="#151a21",
                                  font=("Segoe UI", 11, "bold"))
        self.det_title.pack(side="left", fill="x", expand=True)
        self.det_meta = tk.Label(head, anchor="e", fg="#8d99a6", bg="#151a21",
                                 font=("Segoe UI", 8, "italic"))
        self.det_meta.pack(side="right")
        self.det_desc = tk.Label(inner, anchor="w", fg="#8d99a6", bg="#151a21",
                                 font=("Segoe UI", 9, "italic"), justify="left",
                                 wraplength=760)
        self.det_desc.pack(fill="x", padx=10, pady=(0, 4))
        self.det_rows = []
        tile = self._tile(inner, wrap=520)
        tile[0].pack(fill="x", padx=10, pady=2)
        self.det_rows.append((tile[1], tile[2]))
        arow = tk.Frame(inner, bg="#151a21")
        arow.pack(fill="x", padx=10, pady=2)
        arow.columnconfigure(0, weight=1)
        arow.columnconfigure(1, weight=1)
        for i in range(2):
            tile = self._tile(arow, wrap=250)
            tile[0].grid(row=0, column=i, sticky="nsew",
                         padx=(0 if i == 0 else 3, 3 if i == 0 else 0))
            self.det_rows.append((tile[1], tile[2]))
        for _ in range(4):
            tile = self._tile(inner, wrap=520)
            tile[0].pack(fill="x", padx=10, pady=2)
            tile[2].config(fg="#3fb950")
            self.det_rows.append((tile[1], tile[2]))
        tk.Frame(inner, bg="#151a21", height=6).pack(fill="x")

        sett = ttk.LabelFrame(page_inner, text=" 🔑 НАСТРОЙКА ПУБЛИКАЦИИ ")
        sett.pack(fill="x", padx=10, pady=(0, 6))
        r1 = ttk.Frame(sett)
        r1.pack(fill="x", padx=8, pady=4)
        ttk.Label(r1, text="Ник для публикации:", width=26, anchor="w").pack(side="left")
        self.nick_entry = tk.Entry(r1, width=22, bg="#1c232c", fg="#e6ebf0",
                                   insertbackground="#e6ebf0", bd=1, relief="flat", highlightthickness=1, highlightbackground="#2a323d")
        self.nick_entry.insert(0, self.cfg["publish"].get("nickname", ""))
        self.nick_entry.pack(side="left", padx=4)
        r2 = ttk.Frame(sett)
        r2.pack(fill="x", padx=8, pady=4)
        ttk.Label(r2, text="Токен GitHub (Contents: Write):", width=26, anchor="w").pack(side="left")
        self.token_entry = tk.Entry(r2, width=44, show="*", bg="#1c232c", fg="#e6ebf0",
                                    insertbackground="#e6ebf0", bd=1, relief="flat", highlightthickness=1, highlightbackground="#2a323d")
        self.token_entry.insert(0, self.cfg["publish"].get("gh_token", ""))
        self.token_entry.pack(side="left", padx=4)
        self.show_token_var = tk.BooleanVar(value=False)
        tk.Checkbutton(r2, text="показать", variable=self.show_token_var, bg="#0e1116", fg="#8d99a6",
                       selectcolor="#1c232c", activebackground="#0e1116", font=("Segoe UI", 8),
                       command=self._toggle_token_visibility).pack(side="left")
        rbx = ttk.LabelFrame(sett, text=" КАК ПУБЛИКОВАТЬ ")
        rbx.pack(fill="x", padx=8, pady=(6, 2))
        self.backend_var = tk.StringVar(value=self.cfg["publish"].get("backend", "github"))
        tk.Radiobutton(rbx, text="GitHub (нужен токен)", variable=self.backend_var,
                       value="github", bg="#0e1116", fg="#e6ebf0", selectcolor="#1c232c",
                       activebackground="#0e1116", activeforeground="#ffffff",
                       font=("Segoe UI", 9), anchor="w",
                       command=self._on_backend_change).pack(fill="x", padx=8, pady=(4, 0))
        tk.Radiobutton(rbx, text="Облако Firebase (БЕЗ токена)",
                       variable=self.backend_var, value="firebase", bg="#0e1116", fg="#e6ebf0",
                       selectcolor="#1c232c", activebackground="#0e1116",
                       activeforeground="#ffffff", font=("Segoe UI", 9), anchor="w",
                       command=self._on_backend_change).pack(fill="x", padx=8)
        brow = ttk.Frame(rbx)
        brow.pack(fill="x", padx=8, pady=(0, 6))
        ttk.Label(brow, text="URL БД:", font=("Segoe UI", 8)).pack(side="left")
        self.firebase_entry = tk.Entry(brow, width=44, bg="#1c232c", fg="#e6ebf0",
                                       insertbackground="#e6ebf0", bd=1, relief="flat", highlightthickness=1, highlightbackground="#2a323d")
        self.firebase_entry.insert(0, self.cfg["publish"].get("firebase_url", "")
                                   or GH.FIREBASE_BASE_DEFAULT)
        self.firebase_entry.pack(side="left", padx=4, fill="x", expand=True)
        self.lbl_backend_hint = ttk.Label(rbx, text="", foreground="#8d99a6",
                                          font=("Segoe UI", 8), justify="left", wraplength=380)
        self.lbl_backend_hint.pack(fill="x", padx=8, pady=(0, 6))
        self._on_backend_change()

        r3 = ttk.Frame(sett)
        r3.pack(fill="x", padx=8, pady=(2, 8))
        ttk.Button(r3, text="💾 Сохранить настройки", command=self.save_publish_settings).pack(side="left")
        ttk.Label(r3, text="Токен нужен только для ПУБЛИКАЦИИ. Хранится в вашем конфиге;\n"
                           "для чтения списка билдов токен не требуется.",
                  font=("Segoe UI", 8, "italic"), foreground="#8d99a6", justify="left").pack(side="left", padx=12)

        self._bind_wheel_region(page_inner, page)
        self.builds_tree.bind("<MouseWheel>", lambda e: (
            self.builds_tree.yview_scroll(-1 if getattr(e, "delta", 0) > 0 or
                                          getattr(e, "num", 0) == 4 else 1, "units"),
            "break")[1])
        for seq in ("<Button-4>", "<Button-5>"):
            self.builds_tree.bind(seq, lambda e: (
                self.builds_tree.yview_scroll(-1 if e.num == 4 else 1, "units"), "break")[1])
        self.root.after(1500, lambda: self.refresh_community_builds(manual=False))

    def _refresh_char_icons(self):
        """Подставляет портреты в строки вкладки «Персонажи», когда они докачались."""
        for (_side, _name), lbl in getattr(self, "_char_icons", {}).items():
            lbl.config(image=self._icon_photo(_name, 22), text="")

    def _update_char_counts(self):
        for side, lf in (("K", getattr(self, "_lf_k", None)),
                         ("S", getattr(self, "_lf_s", None))):
            if lf is None:
                continue
            total = sum(1 for (s, _n) in self._char_widgets if s == side)
            on = sum(1 for (s, _n), (var, _w) in self._char_widgets.items()
                     if s == side and var.get())
            emoji = "👹" if side == "K" else "👤"
            name = "МАНЬЯКИ" if side == "K" else "ВЫЖИВАЮЩИЕ"
            lf.config(text=f" {emoji} {name} · {on}/{total} ")

    def _toggle_token_visibility(self):
        self.token_entry.config(show="" if self.show_token_var.get() else "*")

    def save_publish_settings(self):
        self.cfg["publish"]["nickname"] = self.nick_entry.get().strip()
        self.cfg["publish"]["gh_token"] = self.token_entry.get().strip()
        self.cfg["publish"]["backend"] = self.backend_var.get()
        self.cfg["publish"]["firebase_url"] = self.firebase_entry.get().strip()
        save_config(self.cfg)
        self.set_status("Настройки публикации сохранены.", "#3fb950")
        self.log("Сохранены ник и токен публикации (токен — только в локальном конфиге).")

    def refresh_community_builds(self, manual=False):
        threading.Thread(target=self._load_builds_worker, args=(manual,), daemon=True).start()

    def _load_builds_worker(self, manual):
        builds, online = GH.load_community_builds(APP_DIR)
        builds = list(builds or [])
        base = self.firebase_url()
        anon = GH.load_firebase_builds(base=base) if base else None
        if anon:
            have = {b.get("id") for b in builds if isinstance(b, dict)}
            builds += [b for b in anon if isinstance(b, dict) and b.get("id") not in have]
            online = True
        self.ui_q.put(("builds", (builds, online, manual)))

    def firebase_url(self):
        return (str(self.cfg["publish"].get("firebase_url") or "").strip()
                or GH.FIREBASE_BASE_DEFAULT)

    def _on_builds_loaded(self, builds, online, manual):
        self.community_builds = builds if isinstance(builds, list) else []
        self._render_builds_list()
        if online:
            self.lbl_builds_info.config(text=f"Загружено из GitHub: {len(self.community_builds)}",
                                        foreground="#3fb950")
        else:
            self.lbl_builds_info.config(text=f"Офлайн-кэш: {len(self.community_builds)} (нет связи с GitHub)",
                                        foreground="#e3b341")
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
            tree.insert("", "end", iid=str(i), tags=(tag, "odd" if i % 2 else "even"),
                        values=(side_txt, b.get("author", "—"), b.get("title") or "—",
                                b.get("char", "—"), b.get("power_or_item", "—"), perks))
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
        pal = self._pal
        b = self._selected_build()
        if not getattr(self, "det_rows", None):
            return
        if not b:
            self.det_title.config(text="Выберите билд в списке", fg=pal["muted"])
            self.det_meta.config(text="")
            self.det_desc.config(text="")
            self.det_char_img.config(image=self._icon_photo(None, 30), text="")
            for img, txt in self.det_rows:
                img.config(image=self._icon_photo(None, 24), text="")
                txt.config(text="—", fg="#56606c")
            return
        side = b.get("side", "KILLER")
        color = pal["killer"] if side == "KILLER" else pal["surv"]
        self.det_stripe.config(bg=color)
        self.det_title.config(text=(b.get("title") or b.get("char") or "Билд"), fg=color)
        self.det_meta.config(text=f"{b.get('author', '—')} · {b.get('date', '')}")
        self.det_desc.config(text=(b.get("description") or "").strip())
        self.det_char_img.config(image=self._icon_photo(b.get("char") or None, 30), text="")
        values = ([b.get("power_or_item", "")] + list(b.get("addons") or [])
                  + list(b.get("perks") or []))
        names = [b.get("char", "")]
        for (img, txt), val in zip(self.det_rows, values + [""] * 7):
            if not val or val in (EMPTY, NO_ADDONS, "—"):
                img.config(image=self._icon_photo(None, 24), text="")
                txt.config(text="—", fg="#56606c")
                continue
            img.config(image=self._icon_photo(val, 24), text="")
            txt.config(text=val, fg="#dfe5ea")
            names.append(val)
        self._request_icons([n for n in names if n])

    def copy_selected_build(self):
        b = self._selected_build()
        if not b:
            self.ui_q.put(("warn", "Сначала выберите билд из списка (клик по строке)."))
            return
        try:
            pyperclip.copy(GH.format_build_text(b))
            self.set_status("Карточка билда скопирована в буфер обмена ✔", "#3fb950")
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
        self._show_page("main")
        self.set_status(f"Билд от {self.build['author']} загружен. Откройте меню снаряжения "
                        f"и нажмите «ЭКИПИРОВАТЬ».", "#3fb950")
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
        backend = self.backend_var.get() if getattr(self, "backend_var", None) else \
            self.cfg["publish"].get("backend", "github")
        token, base = None, self.firebase_url()
        if backend != "firebase":
            token = GH.resolve_token(self.cfg)
            if not token:
                token = simpledialog.askstring("Публикация",
                                               "Введите токен GitHub (нужны права на запись в репозиторий).\n"
                                               "Сохранить навсегда можно во вкладке «БИЛДЫ».\n"
                                               "Хотите публиковать БЕЗ токена? Отмените ввод и выберите\n"
                                               "«Облако Firebase» в настройках вкладки «БИЛДЫ».",
                                               show="*", parent=self.root)
                if not token:
                    return
                token = token.strip()
        addons = [EMPTY if a == NO_ADDONS else a for a in b["addons"]]
        payload = GH.make_build_payload(b["side"], b["char"], b["power_or_item"], addons,
                                        b["perks"], author,
                                        title=b.get("title", ""),
                                        description=b.get("description", ""),
                                        skin=((b.get("skin") or {}).get("display")
                                              or (b.get("skin") or {}).get("name", ""))
                                        if isinstance(b.get("skin"), dict)
                                        else (b.get("skin") or ""))
        self.btn_publish.config(state="disabled")
        self.set_status("Публикуем билд…", "#e3b341")
        threading.Thread(target=self._publish_worker,
                         args=(payload, token, base), daemon=True).start()

    def _publish_worker(self, payload, token, base=None):
        if token:
            ok, msg = GH.publish_build_to_github(payload, token)
        else:
            ok, msg = GH.publish_build_firebase(payload, base=base or self.firebase_url())

        def done():
            self.btn_publish.config(state="normal")
            if ok:
                self.set_status("🌍 " + msg, "#3fb950")
                payload["local"] = True
                self.community_builds.insert(0, payload)
                self._render_builds_list()
                self.lbl_build_details.config(text=GH.format_build_text(payload))
                messagebox.showinfo("Публикация", msg)
            else:
                self.set_status("🔴 " + msg, "#f85149")
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
        if getattr(sys, "frozen", False):
            msg = (f"У вас EXE-сборка v{APP_VERSION}: обновления приходят готовым "
                   "DBDRandomizer.exe в Releases на GitHub (автозамена файлов работает "
                   "только в Python-версии).")
            if silent:
                self.log(msg)
            else:
                self.ui_q.put(("info", msg))
            return
        self._updating = True
        if not silent:
            self.set_status("Проверяю обновления на GitHub…", "#e3b341")
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
            self.set_status("Останавливаюсь…", "#e3b341")

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
            self._show_page("coords")
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
                                "#e3b341")
                self.ui_q.put(("progress", (countdown - i) / max(1, total) * 100))
                time.sleep(1)

            mode = "СУХОЙ ПРОГОН" if self.dry_var.get() else "АВТО"
            self.log(f"=== {mode}: {total - 1} шаг(ов) ===")
            for done, (key, name, label) in enumerate(steps, start=1):
                if self.abort.is_set():
                    raise AbortError()
                self.set_status(f"{mode}: {label} — «{name}» ({done}/{len(steps)})", "#e5534b")
                self.log(f"→ {label}: кликаю слот «{key}»")
                self._click(self.get_coord(key), key)
                self._sleep(self.timing("after_slot_click"))
                ok = self.search_and_select(name)
                if not ok:
                    self.log(f"⚠ «{name}» — не подтверждено, продолжаю дальше.")
                self.ui_q.put(("progress", done / max(1, total) * 100))
                self._sleep(self.timing("between_steps"))

            self.set_status("🎉 Готово: билд экипирован.", "#3fb950")
            self.log("=== Автоэкипировка завершена ===")
        except AbortError:
            self.set_status("⏹ Остановлено пользователем.", "#e3b341")
            self.log("Остановлено пользователем.")
        except InputUnavailable as exc:
            self.set_status(f"🔴 Ввод недоступен: {exc}", "#f85149")
            self.ui_q.put(("error", f"Автоматизация недоступна:\n{exc}"))
        except Exception as exc:
            self.set_status(f"🔴 Ошибка: {exc}", "#f85149")
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
        win.configure(bg="#0e1116")
        txt = tk.Text(win, bg="#0b0e12", fg="#dfe5ea", font=("Consolas", 10), wrap="word",
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
    if SKINS is not None:
        _all = getattr(SKINS, "SKINS_BY_ID", {}) or {}
        with_img = sum(1 for i in _all.values() if i.get("file"))
        with_ru = sum(1 for i in _all.values() if i.get("name_ru"))
        print(f"  внешность: {len(_all)} наборов у {len(getattr(SKINS, 'CHAR_SKINS', {}))} "
              f"персонажей, превью у {with_img}, RU-названий {with_ru} "
              f"(патч {getattr(SKINS, 'GAME_VERSION', '?')})")
    else:
        print("  внешность: модуль dbd_skins.py не найден")
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
        for mode in ("general", "unique", "mixed", "any"):
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


def _emergency_report(exc_text):
    """pythonw молча умирает без консоли: пишем лог и показываем MessageBox."""
    try:
        with open(os.path.join(APP_DIR, "dbd_crash.log"), "w", encoding="utf-8") as fh:
            fh.write(exc_text)
    except OSError:
        pass
    try:
        if os.name == "nt":
            ctypes.windll.user32.MessageBoxW(
                0, "DBD Randomizer не смог запуститься:\n\n" + exc_text[:1200] +
                "\n\nПолный лог: dbd_crash.log рядом с программой.\n"
                "Частая причина после обновления: не хватает файла модуля —\n"
                "скачайте dbd_skins.py из релиза или возьмите свежий EXE/ZIP.",
                "Ошибка запуска DBD Randomizer", 0x10)
        else:
            sys.stderr.write(exc_text)
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        _emergency_report(traceback.format_exc())
        sys.exit(1)
