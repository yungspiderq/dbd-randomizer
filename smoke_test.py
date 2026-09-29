# -*- coding: utf-8 -*-
"""Головной (headless) смоук-тест GUI-логики: подменяем tkinter и бэкенд ввода.

Запуск:  python smoke_test.py
"""
import base64 as b64
import json
import os
import sys
import tempfile
import shutil
import time
import types
import unittest
import urllib.error
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import dbd_randomizer as R
import dbd_github as GH


def _fake_entry(value=""):
    ent = mock.MagicMock()
    ent.get.return_value = value
    return ent


def install_fake_tk():
    tk = types.ModuleType("tkinter")

    class Var:
        def __init__(self, *a, **kw):
            self._v = kw.get("value", a[0] if a else "")

        def get(self):
            return self._v

        def set(self, v):
            self._v = v

    tk.StringVar = tk.BooleanVar = tk.IntVar = Var
    tk.Tk = mock.MagicMock()
    tk.Toplevel = mock.MagicMock()
    tk.Canvas = mock.MagicMock(side_effect=lambda *a, **kw: mock.MagicMock())
    tk.Text = mock.MagicMock(side_effect=lambda *a, **kw: mock.MagicMock())
    tk.Label = mock.MagicMock(side_effect=lambda *a, **kw: mock.MagicMock())
    tk.Checkbutton = mock.MagicMock(side_effect=lambda *a, **kw: mock.MagicMock())
    tk.Button = mock.MagicMock(side_effect=lambda *a, **kw: mock.MagicMock())
    tk.Radiobutton = mock.MagicMock(side_effect=lambda *a, **kw: mock.MagicMock())
    tk.Frame = mock.MagicMock(side_effect=lambda *a, **kw: mock.MagicMock())
    tk.Entry = mock.MagicMock(side_effect=lambda *a, **kw: _fake_entry(kw.get("text", "")))
    tk.END = "end"
    tk.LEFT = tk.RIGHT = tk.TOP = tk.BOTTOM = "side"
    tk.X = tk.Y = tk.BOTH = tk.NSEW = tk.NW = "fill"
    tk.HORIZONTAL = tk.VERTICAL = "orient"
    tk.PhotoImage = mock.MagicMock(side_effect=lambda *a, **kw: mock.MagicMock())
    tk.TclError = Exception

    ttk = types.ModuleType("tkinter.ttk")
    for name in ("Style", "Frame", "Label", "Button", "Checkbutton", "Radiobutton",
                 "Entry", "Combobox", "Spinbox", "Notebook", "LabelFrame", "Scrollbar",
                 "Progressbar", "Panedwindow", "Treeview", "Separator", "Menubutton"):
        # каждый вызов конструктора виджета даёт НОВЫЙ мок (иначе все Label — один объект)
        setattr(ttk, name, mock.MagicMock(side_effect=lambda *a, **kw: mock.MagicMock()))
    messagebox = types.ModuleType("tkinter.messagebox")
    messagebox.showinfo = mock.MagicMock()
    messagebox.showerror = mock.MagicMock()
    messagebox.showwarning = mock.MagicMock()
    messagebox.askyesno = mock.MagicMock(return_value=True)
    filedialog = types.ModuleType("tkinter.filedialog")
    filedialog.askopenfile = mock.MagicMock()

    simpledialog = types.ModuleType("tkinter.simpledialog")
    simpledialog.askstring = mock.MagicMock(return_value="тестовый_ник")

    tk.ttk, tk.messagebox, tk.filedialog = ttk, messagebox, filedialog
    tk.simpledialog = simpledialog
    sys.modules["tkinter"] = tk
    sys.modules["tkinner.ttk".replace("tkinner", "tkinter")] = ttk
    sys.modules["tkinter.messagebox"] = messagebox
    sys.modules["tkinter.filedialog"] = filedialog
    sys.modules["tkinter.simpledialog"] = simpledialog
    return tk, ttk, messagebox, simpledialog


FAKE_TK, FAKE_TTK, FAKE_MB, FAKE_SD = install_fake_tk()
R._load_tk()


class FakeInput:
    available = True
    reason = ""

    def __init__(self):
        self.calls = []
        self.clip = ""

    def position(self):
        return (0, 0)

    def move(self, x, y, steps=6):
        self.calls.append(("move", x, y))

    def click(self, x, y, hold=0.06, steps=6):
        self.calls.append(("click", x, y))

    def key(self, name, hold=0.02):
        self.calls.append(("key", name))

    def hotkey(self, *keys, hold=0.02):
        self.calls.append(("hotkey", keys))

    def paste(self, text, verify=True, retries=6, restore=False):
        self.calls.append(("paste", text))
        self.clip = text
        return True


def make_app():
    root = mock.MagicMock()
    root.after = lambda *a, **kw: None          # без рекурсии polling'а
    app = R.App(root)
    app.icon_store.enabled = False              # тесты не ходят в интернет за иконками
    # подменяем виджеты координат/таймингов на управляемые заглушки
    app.timing = lambda key: float(R.TIMING_DEFAULTS[key][0]) if key != "retries" else 2
    return app


class TestConfig(unittest.TestCase):
    def test_defaults_have_all_coord_fields(self):
        cfg = R.default_config()
        for key, _ in R.COORD_FIELDS:
            self.assertIn(key, cfg["coords"])

    def test_legacy_migration(self):
        path = os.path.join(HERE, "_legacy_test.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("search_x=100\nsearch_y = 200\nowned_killers=Охотник, Дух\n")
        coords, owned, raw = R._migrate_legacy(path)
        os.remove(path)
        self.assertEqual(coords["search"]["x"], "100")
        self.assertEqual(coords["search"]["y"], "200")
        self.assertEqual(dict(owned)["killers"], ["Охотник", "Дух"])

    def test_legacy_migration_carries_publish_settings(self):
        path = os.path.join(HERE, "_legacy_test2.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("search_x=1\nnickname=SpiderQ\ngh_token=ghp_fake\nauto_update=0\n")
        _coords, _owned, raw = R._migrate_legacy(path)
        os.remove(path)
        self.assertEqual(raw["nickname"], "SpiderQ")
        self.assertEqual(raw["gh_token"], "ghp_fake")
        self.assertEqual(raw["auto_update"], "0")

    def test_save_load_roundtrip(self):
        cfg = R.default_config()
        cfg["coords"]["search"] = {"x": "11", "y": "22"}
        R.save_config(cfg)
        loaded, _ = R.load_config()
        self.assertEqual(loaded["coords"]["search"]["x"], "11")


class TestGeneration(unittest.TestCase):
    def setUp(self):
        self.db = R.db_defaults()

    def test_all_modes_produce_valid_builds(self):
        for side in ("KILLER", "SURVIVOR"):
            pool = sorted(self.db["killers"] if side == "KILLER" else self.db["survivors"])
            for mode in ("general", "unique", "mixed", "any"):
                fn = R.make_killer_build if side == "KILLER" else R.make_survivor_build
                for _ in range(200):
                    b = fn(self.db, pool, perk_mode=mode, addons_enabled=True)
                    self.assertEqual(len(b["perks"]), 4, b)
                    self.assertEqual(len(set(b["perks"])), 4, b)
                    self.assertEqual(len(b["addons"]), 2, b)
                    self.assertNotEqual(b["addons"][0], b["addons"][1], b)
                    self.assertTrue(b["char"] in pool)

    def test_single_character_pool(self):
        b = R.make_killer_build(self.db, ["Охотник"], perk_mode="unique")
        self.assertEqual(b["char"], "Охотник")
        self.assertEqual(len(b["perks"]), 4)

    def test_addons_disabled(self):
        b = R.make_survivor_build(self.db, ["Мэг Томас"], addons_enabled=False)
        self.assertEqual(b["addons"], [R.EMPTY, R.EMPTY])

    def test_empty_addon_category_is_marked(self):
        b = R.make_survivor_build(self.db, ["Мэг Томас"])
        if b["category"] == "Хлопушки":
            self.assertEqual(b["addons"][0], R.NO_ADDONS)
        self.assertEqual(len(b["addons"]), 2)

    def test_respect_owned_pads_with_empty(self):
        db = R.db_defaults()
        db["owned"]["killer_perks"] = ["Барбекю и чили", "Тиннитус"]
        b = R.make_killer_build(db, ["Каннибал"], perk_mode="mixed", respect_owned=True)
        # у Каннибала из белого списка только «Барбекю и чили» -> остальные слоты пустые
        self.assertEqual(b["perks"][0], "Барбекю и чили")
        self.assertEqual(b["perks"][1:], [R.EMPTY, R.EMPTY, R.EMPTY])

    def test_respect_owned_lists(self):
        db = R.db_defaults()
        owned = ["Барбекю и чили", "Тиннитус", "Нокаут", "Коварство", "Шепоты"]
        db["owned"]["killer_perks"] = owned
        b = R.make_killer_build(db, sorted(db["killers"]), perk_mode="mixed", respect_owned=True)
        real = [p for p in b["perks"] if p != R.EMPTY]
        self.assertTrue(set(real) <= set(owned), b["perks"])
        self.assertEqual(len(b["perks"]), 4)

    def test_build_text_and_clipboard(self):
        b = R.make_survivor_build(self.db, ["Дуайт Фэйрфилд"])
        self.assertIn("Выживший", R.build_to_text(b))
        self.assertIn("Перки:", R.build_to_clipboard_text(b))


class TestIcons(unittest.TestCase):
    """Карта иконок обязана покрывать все навыки из базы — иначе в UI будут дырки."""

    def setUp(self):
        self.db = R.db_defaults()
        self.icons = R.ICONS.PERK_ICONS

    def test_every_perk_has_icon(self):
        names = set()
        for info in self.db["killers"].values():
            names.update(info.get("perks", []))
        for perks in self.db["survivors"].values():
            names.update(perks)
        names.update(self.db["killer_common_perks"])
        names.update(self.db["surv_common_perks"])
        missing = sorted(n for n in names if n and n not in self.icons)
        self.assertEqual(missing, [], f"нет иконок для: {missing}")

    def test_no_orphan_icons(self):
        names = set()
        for info in self.db["killers"].values():
            names.update(info.get("perks", []))
        for perks in self.db["survivors"].values():
            names.update(perks)
        names.update(self.db["killer_common_perks"])
        names.update(self.db["surv_common_perks"])
        orphans = sorted(k for k in self.icons if k not in names)
        self.assertLessEqual(len(orphans), 3, f"иконки без навыка в базе: {orphans}")

    def test_urls_are_wiki_png(self):
        self.assertTrue(R.ICONS.ICON_BASE.startswith("https://deadbydaylight.wiki.gg/"))
        for name, fname in self.icons.items():
            self.assertTrue(fname.lower().endswith(".png"), (name, fname))
            self.assertNotIn(" ", fname, (name, fname))

    def test_every_addon_has_icon(self):
        """Аддоны из базы обязаны иметь иконки; исключение — полностью удалённые
        из игры (их нет даже в таблице wiki.gg)."""
        removed = {
            "Переливчатый кирпич", "Свеча зажигания", "Ржавая цепь", "Универсальная смазка",
            "Маленькая отвертка", "Глубокая гравировка", "Белый шумовой генератор",
            "Крепкая швейная игла", "Тяжелый ремень", "Ржавый щипцы", "Смолистое яблоко",
            "Палитра", "Растворитель", "Кисть", "Живописная прихоть",
        }
        icons = getattr(R.ICONS, "ADDON_ICONS", {})
        names = []
        for info in self.db["killers"].values():
            names += info.get("addons", [])
        for entry in self.db["survivor_items"].values():
            names += entry.get("addons", [])
        missing = sorted({n for n in names if n and n not in icons} - removed)
        self.assertEqual(missing, [], f"нет иконок для аддонов: {missing}")
        coverage = len([n for n in set(names) if n in icons]) / max(1, len(set(names)))
        self.assertGreaterEqual(coverage, 0.95, f"покрытие иконками аддонов {coverage:.0%}")

    def test_addon_icons_are_wiki_png(self):
        icons = getattr(R.ICONS, "ADDON_ICONS", {})
        self.assertGreater(len(icons), 500)
        for name, fname in icons.items():
            self.assertTrue(fname.lower().endswith(".png"), (name, fname))
            self.assertNotIn(" ", fname, (name, fname))

    def test_character_power_item_icons_coverage(self):
        """Портреты/силы/предметы покрыты иконками; исключения — контент, у которого
        на вики физически нет файлов (новые убийцы K38+ и две старыми карты)."""
        icons = R.ICONS
        miss_s = [k for k in self.db["survivors"] if k not in icons.SURVIVOR_PORTRAITS]
        miss_p = [self.db["killers"][k]["power"] for k in self.db["killers"]
                  if self.db["killers"][k]["power"] not in icons.POWER_ICONS]
        miss_i = [i for v in self.db["survivor_items"].values() for i in v["items"]
                  if i not in icons.ITEM_ICONS]
        miss_k = [k for k in self.db["killers"]
                  if k not in icons.KILLER_SPRITE["ports"]
                  and k not in getattr(icons, "KILLER_PORTRAITS", {})]
        self.assertEqual(miss_s, [])
        self.assertEqual(set(miss_p), {"Одноглазый ужас", "Страх Фазбера", "Плоть без тела"})
        self.assertEqual(set(miss_i), {"Небрежная карта", "Карта с подписями"})
        self.assertEqual(miss_k, [])          # все 44 маньяка с портретами

    def test_sprite_filename_and_crop(self):
        import os, tempfile
        from PIL import Image
        st = R.IconStore(tempfile.mkdtemp(), enabled=True)
        if not st.enabled:
            self.skipTest("Pillow недоступен")
        self.assertEqual(st.filename("Охотник"),
                         "KP_%03d.png" % R.ICONS.KILLER_SPRITE["ports"]["Охотник"])
        meta = {"url": "http://127.0.0.1:9/sprite.png", "size": 8, "cols": 2,
                "ports": {"Охотник": 3}}            # фейковый спрайт: pos 3 -> ряд 1, колонка 0
        im = Image.new("RGBA", (32, 32), (10, 20, 30, 255))
        for x in range(0, 8):
            for y in range(8, 16):
                im.putpixel((x, y), (255, 0, 0, 255))
        for y in range(32):                                  # шум: файл > MIN_SIZE
            for x in range(16, 32):
                im.putpixel((x, y), ((x * 7 + y * 13) % 256, x % 256, y % 256, 255))
        im.save(os.path.join(st.cache_dir, "KillerPortraitsSprite.png"), compress_level=0)
        path = st._fetch_killer_portrait("Охотник", meta)           # сеть не нужна: спрайт на диске
        self.assertTrue(path and os.path.exists(path))
        crop = Image.open(path)
        self.assertEqual(crop.size, (8, 8))
        self.assertEqual(crop.getpixel((0, 0))[:3], (255, 0, 0))

    def test_filename_keeps_preencoded_percent(self):
        import tempfile
        st = R.IconStore(tempfile.mkdtemp(), enabled=True)
        fn = st.filename("Добивание")          # IconPerks_coupDeGr%C3%A2ce.png
        self.assertIn("%C3%A2", fn)
        self.assertNotIn("%25", fn)            # без двойного экранирования

    def test_stats_count_perks_and_addons(self):
        import tempfile
        st = R.IconStore(tempfile.mkdtemp(), enabled=True)
        if not st.enabled:
            self.skipTest("Pillow недоступен")
        have, total = st.stats()
        self.assertEqual(total, len(R.ICONS.PERK_ICONS) + len(R.ICONS.ADDON_ICONS)
                         + len(R.ICONS.SURVIVOR_PORTRAITS)
                         + len(getattr(R.ICONS, "KILLER_PORTRAITS", {}))
                         + len(R.ICONS.POWER_ICONS) + len(R.ICONS.ITEM_ICONS)
                         + len(R.ICONS.KILLER_SPRITE["ports"]))
        self.assertEqual(have, 0)

    def test_store_resolves_addon_icons(self):
        import tempfile
        st = R.IconStore(tempfile.mkdtemp(), enabled=True)
        if not st.enabled:
            self.skipTest("Pillow недоступен")
        self.assertIsNotNone(st.filename("Точильный камень"))       # аддон Охотника
        self.assertIsNotNone(st.filename("Батарейка"))             # аддон фонарика
        self.assertTrue(st.is_cached("Точильный камень") is False)  # ещё не скачана
        self.assertIn("Точильный камень", st.missing(["Точильный камень"]))

    def test_store_disabled_is_safe(self):
        import tempfile
        st = R.IconStore(tempfile.mkdtemp(), enabled=False)
        self.assertIsNone(st.fetch_one("Надежда"))
        self.assertFalse(st.is_cached("Надежда"))
        st.request(["Надежда"], on_ready=lambda r: None)      # не должно падать
        self.assertEqual(st.missing([]), [])


class TestPublishBackend(unittest.TestCase):
    """v2.5.1: способ публикации обязан сохраняться любой кнопкой сохранения."""

    def test_collect_settings_persists_backend(self):
        app = make_app()
        app.backend_var.set("firebase")
        app.firebase_entry.get = lambda *a: "https://example.firebaseio.com"
        app.collect_settings()
        self.assertEqual(app.cfg["publish"]["backend"], "firebase")
        self.assertEqual(app.cfg["publish"]["firebase_url"], "https://example.firebaseio.com")
        app.backend_var.set("github")
        app.collect_settings()
        self.assertEqual(app.cfg["publish"]["backend"], "github")

    def test_frozen_mode_skips_self_update(self):
        import sys
        app = make_app()
        sys.frozen = True                       # изображаем EXE-сборку
        try:
            app.check_for_updates(silent=True)  # не должно ходить в сеть и падать
            self.assertFalse(app._updating)
        finally:
            del sys.frozen


class TestBuildPassport(unittest.TestCase):
    """v2.3: название/описание билда и анонимная публикация без токена."""

    def test_payload_carries_title_and_description(self):
        p = R.GH.make_build_payload("KILLER", "Охотник", "Медвежий капкан",
                                    ["Точильный камень", "Смоляная бутылка"],
                                    ["Нетерпимость", "Зверская сила", "Пугающее присутствие",
                                     "Шепоты"], "SpiderQ", title="Онрё", description="Ловите.")
        self.assertEqual(p["title"], "Онрё")
        self.assertEqual(p["description"], "Ловите.")
        p2 = R.GH.make_build_payload("KILLER", "Охотник", "Медвежий капкан", [], [], "x")
        self.assertNotIn("title", p2)
        self.assertNotIn("description", p2)

    def test_title_and_description_are_capped(self):
        p = R.GH.make_build_payload("KILLER", "Охотник", "x", [], [], "x",
                                    title="Ы" * 100, description="А" * 500)
        self.assertLessEqual(len(p["title"]), 60)
        self.assertLessEqual(len(p["description"]), 300)

    def test_format_build_text_shows_passport(self):
        b = {"side": "KILLER", "char": "Охотник", "power_or_item": "Медвежий капкан",
             "addons": ["Точильный камень", "Смоляная бутылка"],
             "perks": ["Нетерпимость", "Зверская сила", "Пугающее присутствие", "Шепоты"],
             "author": "SpiderQ", "title": "Онрё", "description": "Ловите."}
        txt = R.GH.format_build_text(b)
        self.assertIn("Название: Онрё", txt)
        self.assertIn("Описание: Ловите.", txt)
        old = R.GH.format_build_text({k: v for k, v in b.items() if k not in ("title", "description")})
        self.assertNotIn("Название:", old)          # старые билды читаются как раньше

    def test_publish_firebase_fails_gracefully_offline(self):
        ok, msg = R.GH.publish_build_firebase({"id": "x-1"}, base="http://127.0.0.1:9", tries=1)
        self.assertFalse(ok)
        self.assertTrue(msg)

    def test_publish_firebase_without_base_explains(self):
        ok, msg = R.GH.publish_build_firebase({"id": "x-1"}, base="")
        self.assertFalse(ok)
        self.assertIn("не настроен", msg)

    def test_parse_firebase_drops_garbage(self):
        data = {"a": {"id": "1", "char": "Охотник"},
                "b": {"author": "selftest", "char": "test"},      # без id — мусор
                "c": {"id": "2"},                                  # без char — мусор
                "d": "str",
                "e": {"id": "0", "char": "Мэг Томас"}}
        got = R.GH._parse_firebase(data)
        self.assertEqual([b["id"] for b in got], ["1", "0"])       # свежие сверху по id
        self.assertEqual(R.GH._parse_firebase(None), [])
        self.assertEqual(R.GH._parse_firebase([1, 2]), [])

    def test_load_firebase_offline_is_none(self):
        self.assertIsNone(R.GH.load_firebase_builds(base="http://127.0.0.1:9"))
        self.assertIsNone(R.GH.load_firebase_builds(base=""))


class TestPerkModes(unittest.TestCase):
    """v2.2: режим «mixed» обязан давать своих перков, а не только общие."""

    def setUp(self):
        self.db = R.db_defaults()

    def test_default_mode_is_mixed(self):
        self.assertEqual(R.OPTION_DEFAULTS["perk_mode"], "mixed")

    def _own(self, side, char):
        if side == "KILLER":
            return set(self.db["killers"][char].get("perks", []))
        return set(self.db["survivors"][char])

    def test_mixed_gives_three_own_plus_common(self):
        for side, chars in (("KILLER", self.db["killers"]), ("SURVIVOR", self.db["survivors"])):
            common = set(self.db["killer_common_perks" if side == "KILLER"
                                 else "surv_common_perks"])
            for char in list(chars)[:12]:
                b = (R.make_killer_build if side == "KILLER" else R.make_survivor_build)(
                    self.db, [char], perk_mode="mixed")
                own = self._own(side, char)
                self.assertEqual(len(b["perks"]), 4)
                self.assertEqual(len(set(b["perks"])), 4)
                self.assertEqual(len(own & set(b["perks"])), min(3, len(own)), b["perks"])
                self.assertTrue(set(b["perks"]) <= own | common |
                                set(R.all_unique_perks(self.db, side)))
                # ровно один добивающий слот занят общим навыком (свои не в счёт:
                # в базе Сенобита «Мертвая хватка» дублируется в общем списке)
                self.assertEqual(len((set(b["perks"]) - own) & common), 1, b["perks"])

    def test_unique_gives_three_own_plus_foreign_unique(self):
        pool = sorted(self.db["killers"])
        common = set(self.db["killer_common_perks"])
        seen_chars = set()
        for _ in range(40):
            b = R.make_killer_build(self.db, pool, perk_mode="unique")
            own = self._own("KILLER", b["char"])          # персонаж билда, не цикла
            seen_chars.add(b["char"])
            self.assertEqual(len(own & set(b["perks"])), 3, b["perks"])
            rest = (set(b["perks"]) - own).pop()
            self.assertNotIn(rest, common, b["perks"])    # 4-й — чужой уникальный
        self.assertGreater(len(seen_chars), 5)

    def test_any_mode_draws_from_whole_pool(self):
        import random
        random.seed(3)
        all_k = (set(self.db["killer_common_perks"]) |
                 set(R.all_unique_perks(self.db, "KILLER")))
        saw_common = saw_foreign = False
        own = self._own("KILLER", "Каннибал")
        pool = sorted(self.db["killers"])
        for _ in range(60):
            b = R.make_killer_build(self.db, pool, perk_mode="any")
            self.assertEqual(len(set(b["perks"])), 4)
            self.assertTrue(set(b["perks"]) <= all_k, b["perks"])
            common = set(self.db["killer_common_perks"])
            saw_common = saw_common or bool(set(b["perks"]) & common)
            saw_foreign = saw_foreign or bool(set(b["perks"]) - own - common)
        self.assertTrue(saw_common and saw_foreign, "режим any не перемешивает весь пул")

    def test_modes_respect_checked_characters(self):
        """Чужие уникальные перки берутся ТОЛЬКО у отмеченных персонажей."""
        import random
        random.seed(5)
        avail = ["Каннибал", "Охотник"]
        allowed = (set(self.db["killers"]["Каннибал"]["perks"])
                   | set(self.db["killers"]["Охотник"]["perks"])
                   | set(self.db["killer_common_perks"]))
        for mode in ("any", "unique", "mixed"):
            for _ in range(40):
                b = R.make_killer_build(self.db, avail, perk_mode=mode)
                self.assertTrue(set(b["perks"]) <= allowed, (mode, b["perks"]))
        # выжившие тоже
        avail_s = ["Мэг Томас", "Дуайт Фэйрфилд"]
        allowed_s = (set(self.db["survivors"]["Мэг Томас"])
                     | set(self.db["survivors"]["Дуайт Фэйрфилд"])
                     | set(self.db["surv_common_perks"]))
        for _ in range(40):
            b = R.make_survivor_build(self.db, avail_s, perk_mode="any")
            self.assertTrue(set(b["perks"]) <= allowed_s, b["perks"])

    def test_general_is_common_only(self):
        b = R.make_killer_build(self.db, ["Каннибал"], perk_mode="general")
        self.assertTrue(set(b["perks"]) <= set(self.db["killer_common_perks"]), b["perks"])

    def test_legacy_config_with_general_is_migrated_once(self):
        import json, os, tempfile
        tmp = tempfile.mkdtemp()
        cfg_file = os.path.join(tmp, "dbd_randomizer_config.json")
        old_cfg = R.default_config()
        old_cfg["options"]["perk_mode"] = "general"
        with open(cfg_file, "w", encoding="utf-8") as fh:
            json.dump(old_cfg, fh)
        saved = (R.CONFIG_FILE, R.DB_FILE)
        R.CONFIG_FILE = cfg_file
        R.DB_FILE = os.path.join(tmp, "dbd_database.json")
        try:
            cfg, migrated = R.load_config()
            self.assertTrue(migrated)
            self.assertEqual(cfg["options"]["perk_mode"], "mixed")
            R.save_config(cfg)
            cfg2, migrated2 = R.load_config()
            self.assertFalse(migrated2)
            cfg2["options"]["perk_mode"] = "general"     # явный выбор пользователя
            R.save_config(cfg2)
            cfg3, _ = R.load_config()
            self.assertEqual(cfg3["options"]["perk_mode"], "general")   # не затираем
        finally:
            R.CONFIG_FILE, R.DB_FILE = saved


class TestValidation(unittest.TestCase):
    def test_no_errors_on_shipped_db(self):
        errors, warnings = R.validate_db(R.db_defaults())
        self.assertEqual(errors, [], errors)
        self.assertTrue(warnings)  # предупреждения о коллизиях имён ожидаются

    def test_detects_duplicates_and_bad_shapes(self):
        db = R.db_defaults()
        db["killers"]["Тестовый"] = {"power": "", "addons": ["А", "А"], "perks": ["П", "П"]}
        errors, _ = R.validate_db(db)
        joined = "\n".join(errors)
        self.assertIn("дубли аддонов", joined)
        self.assertIn("дубли навыков", joined)
        self.assertIn("не указана сила", joined)


class TestAutomation(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.fake = FakeInput()
        self._orig_input = R.INPUT
        R.INPUT = self.fake
        self.app._paste = lambda text: self.fake.paste(text)
        self.app._coord_values = {}

    def tearDown(self):
        R.INPUT = self._orig_input

    def _set_coords(self):
        values = {"search": (10, 20), "clear": (30, 20), "first_result": (500, 300),
                  "item_slot": (100, 400), "addon1_slot": (140, 400), "addon2_slot": (180, 400),
                  "slot1": (220, 400), "slot2": (260, 400), "slot3": (300, 400), "slot4": (340, 400)}
        self.app.get_coord = lambda key: values.get(key)

    def test_search_and_select_types_name(self):
        self._set_coords()
        self.app.dry_var.set(False)
        self.app._option_vars["result_index"] = mock.MagicMock(get=lambda: "1")
        self.app.option = lambda key: {"result_index": 1, "use_clear_button": False,
                                       "verify_clipboard": True, "ocr_verify": False,
                                       "abort_key": "f9"}.get(key, False)
        self.app._sleep = lambda s, abortable=True: None
        ok = self.app.search_and_select("Барбекю и чили")
        self.assertTrue(ok)
        kinds = [c[0] for c in self.fake.calls]
        self.assertIn("paste", kinds)
        self.assertIn("click", kinds)
        pasted = [c[1] for c in self.fake.calls if c[0] == "paste"]
        self.assertEqual(pasted, ["Барбекю и чили"])

    def test_equip_steps_killer_skips_power(self):
        self.app.build = {"side": "KILLER", "char": "Охотник", "power_or_item": "Медвежий капкан",
                          "power_is_item": False, "addons": ["Точильный камень", "Кофейная гуща"],
                          "perks": ["А", "Б", "В", "Г"]}
        steps = self.app._equip_steps()
        self.assertEqual([s[0] for s in steps],
                         ["addon1_slot", "addon2_slot", "slot1", "slot2", "slot3", "slot4"])

    def test_equip_steps_survivor_includes_item(self):
        self.app.build = {"side": "SURVIVOR", "char": "Мэг Томас", "power_or_item": "Фонарик",
                          "category": "Фонарики", "power_is_item": True,
                          "addons": ["Батарейка", R.NO_ADDONS], "perks": ["А", "Б", "В", "Г"]}
        steps = self.app._equip_steps()
        self.assertEqual(steps[0][0], "item_slot")
        self.assertNotIn("addon2_slot", [s[0] for s in steps])

    def test_run_automation_clicks_everything(self):
        self._set_coords()
        self.app.dry_var.set(False)
        self.app.option = lambda key: {"result_index": 1, "use_clear_button": True,
                                       "verify_clipboard": True, "ocr_verify": False,
                                       "abort_key": "f9"}.get(key, False)
        self.app._sleep = lambda s, abortable=True: None
        self.app.timing = lambda key: 0.0 if key != "retries" else 1
        self.app.build = {"side": "SURVIVOR", "char": "Мэг Томас", "power_or_item": "Фонарик",
                          "category": "Фонарики", "power_is_item": True,
                          "addons": ["Батарейка", "Сверхмощная батарейка"],
                          "perks": ["Адреналин", "Надежда", "Дежавю", "Спринтер"]}
        steps = self.app._equip_steps()
        self.app._run_automation(steps)
        clicks = [c for c in self.fake.calls if c[0] == "click"]
        pastes = [c[1] for c in self.fake.calls if c[0] == "paste"]
        self.assertEqual(len(pastes), 7)          # предмет + 2 аддона + 4 перка
        self.assertIn("Фонарик", pastes)
        self.assertIn("Адреналин", pastes)
        self.assertTrue(len(clicks) >= 7)

    def test_abort_stops_immediately(self):
        self._set_coords()
        self.app.dry_var.set(False)
        self.app.option = lambda key: {"result_index": 1, "abort_key": "f9"}.get(key, False)
        self.app.timing = lambda key: 0.0 if key != "retries" else 1
        self.app.build = {"side": "KILLER", "char": "Охотник", "power_or_item": "Медвежий капкан",
                          "power_is_item": False, "addons": ["А1", "А2"], "perks": ["П1", "П2", "П3", "П4"]}
        self.app.abort.set()
        self.app._run_automation(self.app._equip_steps())
        self.assertEqual([c for c in self.fake.calls if c[0] == "click"], [])

    def test_ocr_mismatch_skips_click(self):
        self._set_coords()
        self.app.dry_var.set(False)
        self.app.option = lambda key: {"result_index": 1, "use_clear_button": False,
                                       "verify_clipboard": True, "ocr_verify": True,
                                       "abort_key": "f9"}.get(key, False)
        self.app._sleep = lambda s, abortable=True: None
        self.app.timing = lambda key: 0.0 if key != "retries" else 2
        self.app._ocr_matches = lambda target: False
        self.fake.calls.clear()
        self.assertFalse(self.app.search_and_select("Такого предмета нет"))
        self.assertEqual([c for c in self.fake.calls if c[0] == "click" and c[1] == 500], [])

    def test_select_char_adds_step(self):
        self.app.selchar_var.set(True)
        self.app.build = {"side": "KILLER", "char": "Охотник", "power_or_item": "Медвежий капкан",
                          "power_is_item": False, "addons": [R.EMPTY, R.EMPTY],
                          "perks": ["А", "Б", "В", "Г"]}
        steps = self.app._equip_steps()
        self.assertEqual(steps[0], ("char_search", "Охотник", "персонаж"))
        self.app.selchar_var.set(False)
        self.assertNotIn("char_search", [s[0] for s in self.app._equip_steps()])

    def test_missing_coords_reported(self):
        self.app.build = {"side": "SURVIVOR", "char": "Мэг", "power_or_item": "Фонарик",
                          "category": "Фонарики", "power_is_item": True,
                          "addons": ["Батарейка", R.EMPTY], "perks": ["А", "Б", "В", "Г"]}
        self.app.get_coord = lambda key: None
        self.app.collect_settings = lambda: None
        self.app.start_equip()
        self.assertTrue(FAKE_MB.showerror.called)
        args = FAKE_MB.showerror.call_args[0]
        self.assertIn("search", args[1])


# ===========================================================================
# Сетевой слой: билды сообщества и автообновление
# ===========================================================================
V11_BUILD = {                       # реальный формат v1.1.x из community_builds.json
    "id": "1790625850-3178", "app_version": "1.1.0", "date": "29.09.2026",
    "author": "yungspider", "side": "KILLER", "char": "Онрё",
    "power_or_item": "Шквал ужаса",
    "addons": ["Монтажный пульт", "Хлипкая игрушка"],
    "perks": ["Порча: кара", "Рычаг влияния", "Порча: игрушка", "Неистовство"],
}


class TestGithubHelpers(unittest.TestCase):
    def test_version_tuple(self):
        self.assertEqual(GH.version_tuple("v1.1.1"), (1, 1, 1))
        self.assertGreater(GH.version_tuple("2.0.0"), GH.version_tuple("v1.1.1"))
        self.assertEqual(GH.version_tuple("мусор"), (0,))

    def test_payload_schema_matches_v11(self):
        payload = GH.make_build_payload("KILLER", "Онрё", "Шквал ужаса",
                                        ["А", "Б"], ["1", "2", "3", "4"], "yungspider")
        self.assertEqual(set(payload), set(V11_BUILD))
        self.assertEqual(len(payload["id"].split("-")), 2)
        self.assertLessEqual(len(payload["author"]), 30)

    def test_payload_pads_addons(self):
        payload = GH.make_build_payload("SURVIVOR", "Мэг", "Фонарик", ["А"], ["1", "2", "3", "4"], "x")
        self.assertEqual(payload["addons"], ["А", "—"])

    def test_format_build_text(self):
        text = GH.format_build_text(V11_BUILD)
        self.assertIn("=== DBD БИЛД 👹 ===", text)
        self.assertIn("Автор: yungspider", text)
        self.assertIn("Сила: Шквал ужаса", text)
        self.assertIn("4. Неистовство", text)
        self.assertIn("Предмет:", GH.format_build_text(dict(V11_BUILD, side="SURVIVOR")))

    def test_resolve_token_priority(self):
        os.environ["DBD_UPDATE_TOKEN"] = "env-token"
        try:
            self.assertEqual(GH.resolve_token({"publish": {"gh_token": "cfg"}}), "env-token")
        finally:
            del os.environ["DBD_UPDATE_TOKEN"]
        self.assertEqual(GH.resolve_token({"publish": {"gh_token": "cfg"}}), "cfg")
        self.assertEqual(GH.resolve_token({"gh_token": "old-flat"}), "old-flat")
        self.assertEqual(GH.resolve_token({}), "")


class TestPublish(unittest.TestCase):
    def setUp(self):
        self._get, self._req = GH._http_get, GH._http_request
        self.sent = []

    def tearDown(self):
        GH._http_get, GH._http_request = self._get, self._req

    def _http404(self, url, timeout=8, headers=None):
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

    def _existing(self, builds):
        body = json.dumps({"content": b64.b64encode(
            json.dumps(builds, ensure_ascii=False).encode()).decode(), "sha": "abc123"})

        def fake(url, timeout=8, headers=None):
            return body.encode()
        return fake

    def test_no_token(self):
        ok, msg = GH.publish_build_to_github(V11_BUILD, "")
        self.assertFalse(ok)
        self.assertIn("токен", msg.lower())

    def test_creates_file_when_absent(self):
        GH._http_get = self._http404
        GH._http_request = lambda url, data=None, **kw: self.sent.append((url, data, kw)) or b"{}"
        ok, msg = GH.publish_build_to_github(V11_BUILD, "tok")
        self.assertTrue(ok, msg)
        self.assertEqual(self.sent[0][2].get("method"), "POST")
        self.assertNotIn("sha", self.sent[0][1])

    def test_updates_with_sha(self):
        GH._http_get = self._existing([{"id": "other", "char": "Дух"}])
        GH._http_request = lambda url, data=None, **kw: self.sent.append((url, data, kw)) or b"{}"
        ok, msg = GH.publish_build_to_github(V11_BUILD, "tok")
        self.assertTrue(ok, msg)
        self.assertEqual(self.sent[0][2].get("method"), "PUT")
        self.assertEqual(self.sent[0][1]["sha"], "abc123")

    def test_duplicate_id_is_noop(self):
        GH._http_get = self._existing([dict(V11_BUILD)])
        GH._http_request = lambda url, data=None, **kw: self.sent.append(url) or b"{}"
        ok, msg = GH.publish_build_to_github(V11_BUILD, "tok")
        self.assertTrue(ok)
        self.assertIn("уже опубликован", msg)
        self.assertEqual(self.sent, [])          # ничего не писали

    def test_max_limit_enforced(self):
        GH._http_get = self._existing([{"id": f"x{i}"} for i in range(GH.MAX_COMMUNITY_BUILDS)])
        captured = {}

        def fake_req(url, data=None, **kw):
            captured["data"] = data
            return b"{}"
        GH._http_request = fake_req
        ok, _ = GH.publish_build_to_github(V11_BUILD, "tok")
        self.assertTrue(ok)
        written = json.loads(b64.b64decode(captured["data"]["content"]).decode())
        self.assertEqual(len(written), GH.MAX_COMMUNITY_BUILDS)
        self.assertEqual(written[0]["id"], V11_BUILD["id"])   # новый в начале

    def test_auth_errors_explained(self):
        for code, needle in ((401, "недействителен"), (403, "нет прав")):
            GH._http_get = self._existing([])

            def boom(url, data=None, **kw):
                raise urllib.error.HTTPError(url, code, "err", {}, None)
            GH._http_request = boom
            ok, msg = GH.publish_build_to_github(V11_BUILD, "tok")
            self.assertFalse(ok)
            self.assertIn(needle, msg)


class TestUpdateSafety(unittest.TestCase):
    GOOD = {"dbd_randomizer.py": b"def main():\n    pass\n" + b"x = 1\n" * 40,
            "dbd_data.py": b"KILLERS = {}\n" + b"# pad\n" * 40,
            "dbd_github.py": b'APP_VERSION = "9.9.9"\n' + b"# pad\n" * 40,
            "dbd_icons.py": b"PERK_ICONS = {}\n" + b"# pad\n" * 40,
            "dbd_icons_store.py": b"class IconStore:\n    pass\n" + b"# pad\n" * 40,
            "requirements.txt": b"pyautogui\npyperclip\npydirectinput\n"}

    def test_good_bundle_passes(self):
        info = GH._verify_bundle(self.GOOD)
        self.assertEqual(len(info), len(self.GOOD))
        for item in info:
            self.assertEqual(len(item["sha256"]), 64)
            self.assertGreater(item["bytes"], 0)

    def test_rejects_tiny_file(self):
        bad = dict(self.GOOD, **{"requirements.txt": b"x"})
        with self.assertRaises(GH.UpdateError):
            GH._verify_bundle(bad)

    def test_rejects_missing_marker(self):
        bad = dict(self.GOOD, **{"dbd_data.py": b"something = 1\n" * 40})
        with self.assertRaises(GH.UpdateError) as ctx:
            GH._verify_bundle(bad)
        self.assertIn("маркер", str(ctx.exception))

    def test_rejects_broken_python(self):
        bad = dict(self.GOOD, **{"dbd_data.py": b"KILLERS = {\n" + b"# pad\n" * 40})
        with self.assertRaises(GH.UpdateError) as ctx:
            GH._verify_bundle(bad)
        self.assertIn("синтаксическая", str(ctx.exception))

    def test_apply_update_writes_and_backs_up(self):
        tmp = tempfile.mkdtemp()
        try:
            with open(os.path.join(tmp, "dbd_randomizer.py"), "w") as fh:
                fh.write("old content")
            cfg = os.path.join(tmp, "dbd_randomizer_config.json")
            with open(cfg, "w") as fh:
                fh.write('{"coords": {"secret": "не трогать"}}')
            changed = GH.apply_update(self.GOOD, tmp)
            self.assertIn("dbd_randomizer.py", changed)
            self.assertEqual(open(os.path.join(tmp, "dbd_randomizer.py"), "rb").read(),
                             self.GOOD["dbd_randomizer.py"])
            self.assertEqual(open(os.path.join(tmp, "dbd_randomizer.py.bak")).read(), "old content")
            self.assertIn("secret", open(cfg).read())       # конфиг не тронут
            self.assertEqual(GH.apply_update(self.GOOD, tmp), [])   # второй раз менять нечего
        finally:
            shutil.rmtree(tmp)

    def test_check_update_ignores_same_or_older(self):
        orig_rel, orig_file = GH.get_latest_release_info, GH._get_remote_file_b64
        try:
            GH.get_latest_release_info = lambda token=None: ("v2.0.0", "notes")
            GH._get_remote_file_b64 = lambda *a, **kw: (None, None)
            self.assertIsNone(GH.check_update("2.0.0"))       # та же версия
            self.assertIsNone(GH.check_update("3.1.0"))       # новее релиза
            upd = GH.check_update("1.1.1")
            self.assertEqual(upd["ref"], "v2.0.0")            # качаем из ТЕГА, не из main

            GH.get_latest_release_info = lambda token=None: None
            self.assertIsNone(GH.check_update("1.0.0"))       # без allow_branch main не трогаем

            remote = b'APP_VERSION = "1.2.3"\n' + b"# pad\n" * 40
            GH._get_remote_file_b64 = lambda *a, **kw: (remote, "sha")
            self.assertIsNone(GH.check_update("1.0.0"))                       # всё ещё нельзя
            upd = GH.check_update("1.0.0", allow_branch=True)                 # явное разрешение
            self.assertEqual(upd["ref"], "main")
            self.assertEqual(upd["tag"], "v1.2.3")
        finally:
            GH.get_latest_release_info, GH._get_remote_file_b64 = orig_rel, orig_file

    def test_download_update_requires_all_files(self):
        orig = GH._get_remote_file_b64
        try:
            good = dict(self.GOOD)
            GH._get_remote_file_b64 = lambda path, token=None, ref="main": (good.get(path), "sha")
            bundle, info, missing = GH.download_update("v9.9.9")
            self.assertEqual(len(bundle), 6)
            self.assertEqual(len(info), 6)
            self.assertEqual(missing, [])

            # релиз в формате v1.x (только главный файл) — допустим, но помечается
            # релиз v2.x, в котором не хватает обязательного модуля, -> отказ
            partial = {k: v for k, v in good.items() if k != "dbd_icons.py"}
            GH._get_remote_file_b64 = lambda path, token=None, ref="main": (partial.get(path), "sha")
            with self.assertRaises(GH.UpdateError):
                GH.download_update("v2.0.0")

            # нет даже главного файла — обновление отклоняется
            GH._get_remote_file_b64 = lambda path, token=None, ref="main": (None, None)
            with self.assertRaises(GH.UpdateError):
                GH.download_update("v9.9.9")
        finally:
            GH._get_remote_file_b64 = orig


def drain(app):
    while not app.ui_q.empty():
        app.ui_q.get_nowait()


class TestCommunityBuildsUI(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        drain(self.app)

    def test_equip_foreign_v11_build(self):
        self.app._selected_build = lambda: dict(V11_BUILD)
        self.app.equip_selected_build()
        b = self.app.build
        self.assertEqual(b["side"], "KILLER")
        self.assertEqual(b["char"], "Онрё")
        self.assertEqual(b["power_or_item"], "Шквал ужаса")
        self.assertEqual(b["addons"], ["Монтажный пульт", "Хлипкая игрушка"])
        self.assertEqual(b["perks"], V11_BUILD["perks"])
        self.assertFalse(b["power_is_item"])          # у маньяка сила не экипируется
        self.assertEqual(b["author"], "yungspider")
        steps = self.app._equip_steps()
        self.assertNotIn("item_slot", [s[0] for s in steps])
        self.assertEqual(len(steps), 6)               # 2 аддона + 4 перка

    def test_equip_survivor_build_sets_item_step(self):
        self.app._selected_build = lambda: dict(V11_BUILD, side="SURVIVOR", char="Мэг Томас",
                                                power_or_item="Фонарик")
        self.app.equip_selected_build()
        self.assertTrue(self.app.build["power_is_item"])
        self.assertEqual(self.app._equip_steps()[0][0], "item_slot")

    def test_equip_rejects_short_build(self):
        drain(self.app)
        self.app._selected_build = lambda: dict(V11_BUILD, perks=["один", "два"])
        self.app.build = None
        self.app.equip_selected_build()
        self.assertIsNone(self.app.build)
        kind, payload = self.app.ui_q.get_nowait()
        self.assertEqual(kind, "warn")
        self.assertIn("меньше 4 навыков", payload)

    def test_details_card_fills_rows(self):
        drain(self.app)
        self.app._selected_build = lambda: dict(V11_BUILD, title="Онрё",
                                                description="Описание билда")
        self.app._show_build_details()
        self.assertEqual(self.app.det_title.config.call_args.kwargs["text"], "Онрё")
        self.assertEqual(self.app.det_desc.config.call_args.kwargs["text"], "Описание билда")
        texts = [txt.config.call_args.kwargs.get("text") for _i, txt in self.app.det_rows]
        self.assertIn("Шквал ужаса", texts)
        self.assertIn(V11_BUILD["perks"][0], texts)
        self.app._selected_build = lambda: None
        self.app._show_build_details()
        self.assertEqual(self.app.det_rows[0][1].config.call_args.kwargs["text"], "—")

    def test_maker_combos_start_with_placeholder_icon(self):
        app = make_app()
        for cb in list(app.mk_perks) + list(app.mk_addons) + [app.mk_item]:
            img_kw = cb.icon.config.call_args.kwargs.get("image")
            self.assertTrue(img_kw not in (None, ""),
                            "IconCombo создан без плейсхолдера — плитка растянется")

    def test_maker_dedupe_perks(self):
        app = make_app()
        g = app.mk_perks
        g[0].set("Нетерпимость")
        g[1].set("Нетерпимость")
        app._mk_dedupe(g, g[1], "Нетерпимость")
        self.assertEqual(g[0].get(), "")          # дубль сброшен у ДРУГОГО поля
        self.assertEqual(g[1].get(), "Нетерпимость")

    def test_maker_rejects_same_addons(self):
        app = make_app()
        drain(app)
        app.mk_char.set("Охотник")
        app._mk_on_char()
        app.mk_addons[0].set("Точильный камень")
        app.mk_addons[1].set("Точильный камень")
        for cb in app.mk_perks:
            cb.set("Нетерпимость")
        app.mk_perks[1].set("Зверская сила")
        app.mk_perks[2].set("Пугающее присутствие")
        app.mk_perks[3].set("Шепоты")
        self.assertIsNone(app._mk_collect())      # одинаковые аддоны отклоняются

    def test_char_counts_update(self):
        app = make_app()
        var, _w = app._char_widgets[("K", "Охотник")]
        var.set(False)
        app._update_char_counts()
        self.assertIn("43/44", app._lf_k.config.call_args.kwargs["text"])
        var.set(True)
        app._update_char_counts()
        self.assertIn("44/44", app._lf_k.config.call_args.kwargs["text"])

    def test_publish_requires_generated_build(self):
        drain(self.app)
        self.app.build = None
        self.app.publish_current_build()
        kind, payload = self.app.ui_q.get_nowait()
        self.assertEqual(kind, "warn")
        self.assertIn("сгенерируйте", payload)

    def test_publish_rejects_empty_slots(self):
        drain(self.app)
        self.app.build = {"side": "KILLER", "char": "Охотник", "power_or_item": "Медвежий капкан",
                          "power_is_item": False, "addons": ["А", "Б"],
                          "perks": ["П1", "П2", R.EMPTY, R.EMPTY]}
        self.app.publish_current_build()
        kind, payload = self.app.ui_q.get_nowait()
        self.assertEqual(kind, "warn")
        self.assertIn("пустые слоты", payload)

    def test_filtered_builds(self):
        self.app.community_builds = [
            dict(V11_BUILD),
            dict(V11_BUILD, id="2", side="SURVIVOR", char="Мэг Томас", author="SpiderQ"),
            "не словарь",
        ]
        self.app.builds_filter_var.set("ВСЕ")
        self.app.builds_search_entry = mock.MagicMock(get=lambda: "")
        self.assertEqual(len(self.app._filtered_builds()), 2)
        self.app.builds_filter_var.set("SURVIVOR")
        self.assertEqual([b["char"] for b in self.app._filtered_builds()], ["Мэг Томас"])
        self.app.builds_filter_var.set("ВСЕ")
        self.app.builds_search_entry = mock.MagicMock(get=lambda: "spiderq")
        self.assertEqual(len(self.app._filtered_builds()), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
