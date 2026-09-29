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
    tk.Canvas = mock.MagicMock()
    tk.Text = mock.MagicMock()
    tk.Label = mock.MagicMock()
    tk.Checkbutton = mock.MagicMock()
    tk.Button = mock.MagicMock()
    tk.Radiobutton = mock.MagicMock()
    tk.Frame = mock.MagicMock()
    tk.Entry = mock.MagicMock(side_effect=lambda *a, **kw: _fake_entry(kw.get("text", "")))
    tk.END = "end"
    tk.LEFT = tk.RIGHT = tk.TOP = tk.BOTTOM = "side"
    tk.X = tk.Y = tk.BOTH = tk.NSEW = tk.NW = "fill"
    tk.HORIZONTAL = tk.VERTICAL = "orient"
    tk.TclError = Exception

    ttk = types.ModuleType("tkinter.ttk")
    for name in ("Style", "Frame", "Label", "Button", "Checkbutton", "Radiobutton",
                 "Entry", "Notebook", "LabelFrame", "Scrollbar", "Progressbar", "Panedwindow",
                 "Treeview"):
        setattr(ttk, name, mock.MagicMock())
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
            for mode in ("general", "unique", "mixed"):
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

    def test_store_disabled_is_safe(self):
        import tempfile
        st = R.IconStore(tempfile.mkdtemp(), enabled=False)
        self.assertIsNone(st.fetch_one("Надежда"))
        self.assertFalse(st.is_cached("Надежда"))
        st.request(["Надежда"], on_ready=lambda r: None)      # не должно падать
        self.assertEqual(st.missing([]), [])


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
