"""Fast headless regression tests for the native Qt backend."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QSignalSpy, QTest
import dbd_randomizer as core
import native_backend
import qt_updater


class QtBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qtapp = QApplication.instance() or QApplication(["dbd-qt-test"])

    def setUp(self):
        self.cfg = core.default_config()
        self.cfg["options"]["skin_enabled"] = False
        self.cfg["timings"]["countdown"] = 0
        self.cfg["timings"]["search_settle"] = 0
        self.cfg["timings"]["after_slot_click"] = 0
        self.cfg["timings"]["between_steps"] = 0
        for val in self.cfg["coords"].values():
            val["x"] = "100"
            val["y"] = "100"
        self.patches = [
            patch.object(core, "load_config", return_value=(self.cfg, False)),
            patch.object(core, "load_db", side_effect=core.db_defaults),
            patch.object(core, "save_config"),
            patch.object(native_backend.QtBridge, "_hotkey"),
            patch.object(native_backend, "IconStore"),
            patch.object(core, "_load_tk", side_effect=AssertionError("Tk should not load")),
        ]
        for p in self.patches:
            p.start()
        self.bridge = native_backend.QtBridge()

    def tearDown(self):
        self.bridge.close()
        for p in reversed(self.patches):
            p.stop()

    def test_installed_version_is_not_stuck_at_beta12(self):
        self.assertEqual(self.bridge.installedVersion, qt_updater.CURRENT_TAG)
        self.assertIn(qt_updater.CURRENT_TAG, self.bridge.updateText)

    def test_installer_error_is_shown_at_startup(self):
        with patch.object(qt_updater, "last_install_error",
                          return_value="Предыдущее обновление не установилось: Access denied"):
            another = native_backend.QtBridge()
            try:
                self.assertIn("Access denied", another.updateText)
            finally:
                another.close()

    def test_native_backend_no_tk_and_both_roles(self):
        self.assertEqual(self.bridge.role, "survivor")
        self.bridge.generate()
        self.assertEqual(len(self.bridge.build["perks"]), 4)
        self.assertEqual(len(self.bridge.perks), 4)
        self.bridge.setRole("killer")
        self.bridge.generate()
        self.assertEqual(self.bridge.build["side"], "KILLER")
        self.assertEqual(len(self.bridge.build["addons"]), 2)

    def test_icon_batching_emits_once_for_a_download_burst(self):
        spy = QSignalSpy(self.bridge.iconVersionChanged)
        for i in range(40):
            self.bridge._messages.put(("icons", "icon_" + str(i), True))
        self.bridge._drain()
        self.assertEqual(self.bridge.iconVersion, 0)
        self.assertEqual(spy.count(), 0)
        QTest.qWait(175)
        self.assertEqual(self.bridge.iconVersion, 1)
        self.assertEqual(spy.count(), 1)
        self.bridge._messages.put(("icons", "broken_icon", False))
        self.bridge._drain()
        QTest.qWait(175)
        self.assertEqual(spy.count(), 1, "Failed images must not refresh every thumbnail")
        self.bridge._messages.put(("icons", "next_success", True))
        self.bridge._drain()
        QTest.qWait(175)
        self.assertEqual(spy.count(), 2)

    def test_status_burst_emits_one_qml_refresh(self):
        status_spy = QSignalSpy(self.bridge.statusChanged)
        update_spy = QSignalSpy(self.bridge.updateChanged)
        for i in range(25):
            self.bridge._messages.put(("status", "status-" + str(i), True))
            self.bridge._messages.put(("update_progress", str(i) + "%"))
        self.bridge._drain()
        self.assertEqual(status_spy.count(), 1)
        self.assertEqual(update_spy.count(), 1)
        self.assertEqual(self.bridge.status, "status-24")
        self.assertEqual(self.bridge.updateText, "24%")
        self.assertEqual(len(self.bridge._log), 25)

    def test_generating_and_rerolling_do_not_reload_all_catalog_icons(self):
        icon_spy = QSignalSpy(self.bridge.iconVersionChanged)
        build_spy = QSignalSpy(self.bridge.buildRevisionChanged)
        self.bridge.generate()
        self.assertEqual(icon_spy.count(), 0)
        self.assertGreaterEqual(build_spy.count(), 1)
        self.bridge.rerollPerks()
        self.assertEqual(icon_spy.count(), 0)
        self.assertGreater(build_spy.count(), 1)

    def test_selected_result_is_preflight_checked_before_input(self):
        self.bridge.generate()
        self.bridge.cfg["options"]["dry_run"] = False
        self.bridge.cfg["options"]["result_index"] = 9
        self.bridge.cfg["timings"]["result_step"] = 84
        self.assertEqual(self.bridge._result_target(), (772, 100))
        def fake_desktop(keys, extra=()):
            self.assertIn("first_result", keys)
            self.assertEqual(extra, [("result_index", (772, 100))])
            return ["result_index"]
        with patch.object(self.bridge, "_outside_desktop", side_effect=fake_desktop), \
             patch.object(core.INPUT, "available", True), \
             patch.object(self.bridge, "_automate") as automate:
            self.bridge.equip()
            automate.assert_not_called()
            self.assertFalse(self.bridge.running)

    def test_ocr_without_region_aborts_before_countdown(self):
        self.bridge.generate()
        self.bridge.cfg["options"]["dry_run"] = False
        self.bridge.cfg["options"]["ocr_verify"] = True
        self.bridge.cfg["coords"]["ocr_region"] = {"x": "", "y": "", "w": "", "h": ""}
        with patch.object(self.bridge, "_outside_desktop", return_value=[]), \
             patch.object(core.INPUT, "available", True), \
             patch.object(self.bridge, "_automate") as automate:
            self.bridge.equip()
            automate.assert_not_called()
            self.assertFalse(self.bridge.running)

    def test_equip_side_is_snapshot_even_if_current_build_changes(self):
        self.bridge.generate()
        self.bridge.cfg["options"]["dry_run"] = False
        self.bridge._equip_side = "KILLER"
        self.bridge.build["side"] = "SURVIVOR"
        with patch.object(self.bridge, "_sleep"), \
             patch.object(self.bridge, "_click", return_value=True), \
             patch.object(self.bridge, "_search_and_select", return_value=True), \
             patch.object(core.INPUT, "foreground_window", return_value=501), \
             patch.object(core.INPUT, "is_own_window", return_value=False):
            self.bridge._automate([("slot1", "sample", "perk")])
        self.assertIn("KILLER", self.bridge.cfg["last_equipped"])
        self.assertNotIn("SURVIVOR", self.bridge.cfg["last_equipped"])
        self.assertIsNone(self.bridge._equip_side)

    def test_settings_mode_and_character_filter(self):
        self.bridge.setMode("any")
        self.assertEqual(self.bridge.mode, "any")
        self.bridge.toggleOption("dry")
        self.assertTrue(self.bridge.options["dry"])
        s = next(x["name"] for x in self.bridge.characters if x["side"] == "S")
        self.bridge.setCharacter(s, "S")
        self.assertNotIn(s, self.bridge.available_characters("SURVIVOR"))

    def test_live_appearance_controls_persist_without_changing_game_options(self):
        self.assertEqual(self.bridge.appearanceTheme, "crimson")
        self.assertEqual(self.bridge.appearanceScale, 1.0)
        self.assertTrue(self.bridge.animationsEnabled)
        original_mode = self.bridge.mode
        original_rotation = self.bridge.rotationEnabled
        self.bridge.setAppearanceTheme("frost")
        self.assertEqual(self.bridge.appearanceTheme, "frost")
        self.assertEqual(self.bridge.appearancePalette["accent"], "#4298e5")
        self.bridge.setAppearanceScale(1.2)
        self.assertAlmostEqual(self.bridge.appearanceScale, 1.2)
        self.bridge.setAnimationsEnabled(False)
        self.assertFalse(self.bridge.animationsEnabled)
        self.assertEqual(self.cfg["options"]["qt_theme"], "frost")
        self.assertAlmostEqual(self.cfg["options"]["qt_scale"], 1.2)
        self.assertFalse(self.cfg["options"]["qt_animations"])
        self.assertEqual(self.bridge.mode, original_mode)
        self.assertEqual(self.bridge.rotationEnabled, original_rotation)

    def test_appearance_rejects_unsupported_values_and_reset_keeps_favorites(self):
        self.bridge.generate()
        self.assertTrue(self.bridge.saveFavorite("appearance fixture", "", ""))
        self.bridge.setAppearanceTheme("violet")
        self.bridge.setAppearanceScale(0.9)
        self.bridge.setAnimationsEnabled(False)
        self.bridge.setAppearanceTheme("fake")
        self.bridge.setAppearanceScale(20.0)
        self.assertEqual(self.bridge.appearanceTheme, "violet")
        self.assertEqual(self.bridge.appearanceScale, 0.9)
        self.assertEqual(self.bridge.favoriteCount, 1)
        self.bridge.resetAppearance()
        self.assertEqual(self.bridge.appearanceTheme, "crimson")
        self.assertEqual(self.bridge.appearanceScale, 1.0)
        self.assertTrue(self.bridge.animationsEnabled)
        self.assertEqual(self.bridge.favoriteCount, 1)
        self.assertEqual(self.bridge.statistics["overview"]["generated"], 1)

    def test_balanced_mode_is_opt_in_and_persists(self):
        self.assertFalse(self.bridge.rotationEnabled)
        self.bridge.generate()
        self.assertEqual(self.bridge.rotationStats["seen"], 0)
        self.bridge.setRotationEnabled(True)
        self.assertTrue(self.bridge.rotationEnabled)
        self.bridge.generate()
        self.assertEqual(self.bridge.rotationStats["seen"], 1)
        self.assertTrue(self.cfg["options"]["rotation_enabled"])
        self.assertIn("rotation_state", self.cfg["options"])
        self.assertGreater(self.cfg["options"]["rotation_state"]["SURVIVOR"]["characters"]["counts"][self.bridge.build["char"]], 0)
        self.bridge.setRotationEnabled(False)
        self.assertFalse(self.bridge.rotationEnabled)
        self.assertEqual(self.bridge.rotationStats["seen"], 1)

    def test_rotation_side_isolation_and_confirmation_reset_backend(self):
        self.bridge.setRotationEnabled(True)
        self.bridge.generate()
        self.assertEqual(self.bridge.rotationStats["seen"], 1)
        self.bridge.setRole("killer")
        self.assertEqual(self.bridge.rotationStats["seen"], 0)
        self.bridge.generate()
        self.assertEqual(self.bridge.rotationStats["seen"], 1)
        self.bridge.resetRotation()
        self.assertEqual(self.bridge.rotationStats["seen"], 0)
        self.bridge.setRole("survivor")
        self.assertEqual(self.bridge.rotationStats["seen"], 1)

    def test_balanced_mode_reroll_uses_weighted_perk_history(self):
        self.bridge.setRotationEnabled(True)
        self.bridge.generate()
        before = list(self.bridge.build["perks"])
        self.bridge.reroll(0)
        after = self.bridge.build["perks"]
        self.assertEqual(len(after), 4)
        self.assertNotEqual(after[0], before[0])
        self.assertEqual(len(set(after)), 4)

    def test_perk_details_owner_common_and_safe_reference(self):
        self.bridge.setRole("killer")
        self.bridge.generate()
        info = self.bridge.perkInfo(0)
        self.assertTrue(info["filled"])
        self.assertEqual(info["name"], self.bridge.perks[0]["name"])
        self.assertIn(info["kind"], ("Уникальный навык", "Общий навык"))
        self.assertTrue(info["found"])
        self.assertEqual(info["slot"], 1)

    def test_pinned_perks_survive_full_generate_and_have_no_duplicates(self):
        self.bridge.setRole("killer")
        self.bridge.generate()
        selected = self.bridge.perks[0]["name"]
        revision = self.bridge.buildRevision
        self.bridge.toggleLock(0)
        self.assertEqual(revision, self.bridge.buildRevision)
        self.bridge.generate()
        self.assertGreater(self.bridge.buildRevision, revision)
        self.assertEqual(self.bridge.perks[0]["name"], selected)
        self.assertTrue(self.bridge.perks[0]["locked"])
        names = [p["name"] for p in self.bridge.perks if p["filled"]]
        self.assertEqual(len(names), len(set(names)))

    def test_bulk_lock_and_unlock_affects_only_filled_slots(self):
        self.bridge.generate()
        self.bridge.setAllPerkLocks(True)
        self.assertEqual(self.bridge.lockedCount, 4)
        original = [p["name"] for p in self.bridge.perks]
        self.bridge.rerollPerks()
        self.assertEqual(original, [p["name"] for p in self.bridge.perks])
        self.bridge.setAllPerkLocks(False)
        self.assertEqual(self.bridge.lockedCount, 0)

    def test_new_challenge_can_release_incompatible_pinned_perks(self):
        self.bridge.setRole("killer")
        self.bridge.generate()
        self.bridge.setAllPerkLocks(True)
        dropping = {"side": "KILLER", "diff": 1, "ru": "Тестовое ограничение",
                    "text": "Без перков", "fx": {"drop": ["perks"]}}
        self.bridge._generate(preset_challenge=dropping)
        self.assertEqual(self.bridge.lockedCount, 0)
        self.assertTrue(self.bridge.build["forbidden"]["perks"])

    def test_period_selector_matches_saved_current_day_and_cannot_modify_role(self):
        self.bridge.generate()
        self.bridge.setStatisticsPeriod(1)
        self.assertEqual(self.bridge.statisticsPeriod, 1)
        self.assertEqual(self.bridge.statistics["period"], 1)
        self.assertEqual(self.bridge.statistics["overview"]["generated"], 1)
        self.assertEqual(self.bridge.role, "survivor")
        self.bridge.setStatisticsPeriod(7)
        self.assertEqual(self.bridge.statistics["overview"]["generated"], 1)
        self.bridge.setStatisticsPeriod(30)
        self.assertEqual(self.bridge.statistics["overview"]["generated"], 1)
        self.bridge.setStatisticsPeriod(100)
        self.assertEqual(self.bridge.statisticsPeriod, 30)
        self.bridge.setStatisticsPeriod(0)
        self.assertEqual(self.bridge.statistics["overview"]["generated"], 1)

    def test_icon_path_uses_bounded_worker_queue(self):
        self.assertEqual(self.bridge._icon_queue.worker_count, 3)
        self.assertEqual(self.bridge._icon_queue.pending_count, 0)
        self.assertEqual(self.bridge.iconPath(""), "")
        with patch.object(self.bridge._icons, "local_path", return_value=None), \
             patch.object(self.bridge._icons, "is_cached", return_value=False), \
             patch.object(self.bridge._icons, "filename", return_value=None):
            self.assertEqual(self.bridge.iconPath("a deliberately unknown nonexistent icon"), "")

    def test_statistics_tracks_both_modes_and_perk_rerolls(self):
        self.bridge.generate()
        overview = self.bridge.statistics["overview"]
        self.assertEqual(overview["generated"], 1)
        self.assertEqual(overview["classic"], 1)
        self.bridge.setRotationEnabled(True)
        self.bridge.generate()
        overview = self.bridge.statistics["overview"]
        self.assertEqual(overview["generated"], 2)
        self.assertEqual(overview["balanced"], 1)
        self.assertEqual(len(self.bridge.statistics["recent"]), 2)
        self.bridge.reroll(0)
        self.assertEqual(self.bridge.statistics["overview"]["generated"], 2)
        self.assertEqual(self.bridge.statistics["overview"]["rerolls"], 1)
        self.assertIn("statistics_v1", self.cfg["options"])

    def test_statistics_side_and_category_independent_from_build(self):
        self.bridge.generate()
        self.bridge.setStatisticsSide("KILLER")
        self.assertEqual(self.bridge.statisticsSide, "KILLER")
        self.assertEqual(self.bridge.role, "survivor")
        self.assertEqual(self.bridge.statistics["overview"]["generated"], 0)
        self.bridge.setStatisticsGroup("perks")
        self.assertEqual(self.bridge.statisticsGroup, "perks")
        self.bridge.setStatisticsGroup("items")
        self.assertEqual(self.bridge.statisticsGroup, "perks")
        self.bridge.setStatisticsSide("SURVIVOR")
        self.bridge.setStatisticsGroup("items")
        self.assertEqual(self.bridge.statisticsGroup, "items")
        self.assertTrue(self.bridge.statistics["top"])

    def test_reset_statistics_does_not_reset_rotation(self):
        self.bridge.setRotationEnabled(True)
        self.bridge.generate()
        assert self.bridge.rotationStats["seen"] == 1
        self.bridge.resetStatistics()
        self.assertEqual(self.bridge.statistics["overview"]["generated"], 0)
        self.assertEqual(self.bridge.rotationStats["seen"], 1)
        self.assertTrue(self.bridge.rotationEnabled)

    def test_favorites_save_restore_does_not_count_as_new_roll(self):
        self.bridge.generate()
        build = self.bridge.build
        self.assertTrue(self.bridge.saveFavorite("Сильный билд", "Тестовая коллекция", "Заметка"))
        self.assertEqual(self.bridge.favoriteCount, 1)
        self.assertIn("favorite_builds_v1", self.cfg["options"])
        ident = self.bridge.favorites[0]["id"]
        self.bridge.setRotationEnabled(True)
        self.bridge.generate()
        before_stats = self.bridge.statistics["overview"]["generated"]
        before_rotate = self.bridge.rotationStats["generated"]
        self.bridge.setAllPerkLocks(True)
        self.assertTrue(self.bridge.loadFavorite(ident))
        self.assertEqual(self.bridge.build["perks"], build["perks"])
        self.assertEqual(self.bridge.build["addons"], build["addons"])
        self.assertEqual(self.bridge.lockedCount, 0)
        self.assertEqual(self.bridge.statistics["overview"]["generated"], before_stats)
        self.assertEqual(self.bridge.rotationStats["generated"], before_rotate)

    def test_favorites_filter_edit_and_remove(self):
        self.bridge.generate()
        self.assertTrue(self.bridge.saveFavorite("Мои перки", "Сборки", "На ремонт"))
        self.assertTrue(self.bridge.saveFavorite("Второй билд", "Проверка", "Что-то"))
        self.assertEqual(self.bridge.favoriteCount, 2)
        self.bridge.setFavoriteSearch("ремонт")
        self.assertEqual(len(self.bridge.favorites), 1)
        self.bridge.setFavoriteSearch("")
        self.bridge.setFavoriteSide("KILLER")
        self.assertEqual(len(self.bridge.favorites), 0)
        self.bridge.setFavoriteSide("SURVIVOR")
        self.assertEqual(len(self.bridge.favorites), 2)
        self.bridge.setFavoriteCollection("Сборки")
        self.assertEqual(len(self.bridge.favorites), 1)
        ident = self.bridge.favorites[0]["id"]
        self.assertTrue(self.bridge.editFavorite(ident, "Новое имя", "Любимые", "Описание"))
        self.assertEqual(self.bridge.favoriteCollection, "Все коллекции")
        self.assertTrue(self.bridge.deleteFavorite(ident))
        self.assertEqual(self.bridge.favoriteCount, 1)
        self.assertFalse(self.bridge.loadFavorite(ident))

    def test_favorites_validation_rejects_missing_character_without_modifying_build(self):
        self.bridge.generate()
        self.assertTrue(self.bridge.saveFavorite("Для теста", "", ""))
        ident = self.bridge.favorites[0]["id"]
        original = self.bridge.build
        import copy
        self.bridge.db = copy.deepcopy(self.bridge.db)
        del self.bridge.db["survivors"][original["char"]]
        self.assertFalse(self.bridge.loadFavorite(ident))
        self.assertIs(self.bridge.build, original)

    def test_lock_and_reroll(self):
        self.bridge.generate()
        self.bridge.toggleLock(0)
        original = self.bridge.perks[0]["name"]
        self.bridge.rerollPerks()
        self.assertEqual(self.bridge.perks[0]["name"], original)

    def test_dry_run_never_changes_equipped_tracking(self):
        self.bridge.generate()
        self.bridge.toggleOption("dry")
        self.bridge.equip()
        self.bridge._worker.join(timeout=12)
        self.assertFalse(self.bridge._worker.is_alive())
        self.assertEqual(self.bridge.cfg.get("last_equipped", {}), {})

    def test_concurrent_equip_clicks_do_not_start_two_workers(self):
        self.bridge.generate()
        self.bridge.toggleOption("dry")
        import threading
        release = threading.Event()
        entered = threading.Event()
        def slow_automate(steps):
            entered.set()
            release.wait(timeout=5)
            self.bridge._messages.put(("running", False))
            self.bridge._wake.emit()
        with patch.object(self.bridge, "_automate", side_effect=slow_automate) as worker:
            self.bridge.equip()
            self.assertTrue(entered.wait(timeout=3))
            self.bridge.equip()
            self.assertEqual(worker.call_count, 1)
            release.set()
            self.bridge._worker.join(timeout=5)

    def test_search_does_not_claim_success_when_input_fails(self):
        self.bridge._target_window = 501
        self.bridge.generate()
        self.bridge.cfg["options"]["dry_run"] = False
        self.bridge.cfg["options"]["ocr_verify"] = False
        self.bridge.cfg["timings"]["retries"] = 0
        self.bridge.cfg["timings"]["search_settle"] = 0
        with patch.object(self.bridge, "_sleep"), patch.object(self.bridge, "_click", return_value=False):
            self.assertFalse(self.bridge._search_and_select("example"))
        with patch.object(self.bridge, "_sleep"), patch.object(self.bridge, "_click", return_value=True), \
             patch.object(self.bridge, "_paste", return_value=False), \
             patch.object(core.INPUT, "foreground_window", return_value=501), \
             patch.object(core.INPUT, "hotkey"):
            self.assertFalse(self.bridge._search_and_select("example"))

    def test_failed_equip_resets_cached_state(self):
        self.bridge.generate()
        self.bridge.cfg["options"]["dry_run"] = False
        self.bridge.cfg.setdefault("last_equipped", {})[self.bridge.build["side"]] = {"perks": ["old"]}
        self.bridge._planned_equipped = {"perks": ["new"]}
        with patch.object(self.bridge, "_sleep"), patch.object(self.bridge, "_click", return_value=False), \
             patch.object(self.bridge, "_search_and_select") as search:
            self.bridge._automate([("slot1", "example", "навык")])
            search.assert_not_called()
        self.assertIsNone(self.bridge.cfg["last_equipped"][self.bridge.build["side"]])

    def test_manual_target_capture_accepts_any_external_window(self):
        self.bridge.cfg["options"]["dry_run"] = False
        with patch.object(core.INPUT, "foreground_window", return_value=501), \
             patch.object(core.INPUT, "is_own_window", return_value=False):
            self.bridge._capture_target_window()
            self.assertEqual(self.bridge._target_window, 501)
            self.bridge._assert_input_ready()

    def test_manual_target_rejects_own_window_and_missing_foreground(self):
        self.bridge.cfg["options"]["dry_run"] = False
        for hwnd, is_own in ((None, True), (300, True)):
            with self.subTest(hwnd=hwnd), \
                 patch.object(core.INPUT, "foreground_window", return_value=hwnd), \
                 patch.object(core.INPUT, "is_own_window", return_value=is_own):
                with self.assertRaisesRegex(RuntimeError, "Переключитесь"):
                    self.bridge._capture_target_window()
                self.assertIsNone(self.bridge._target_window)

    def test_manual_target_blocks_all_steps_when_own_window_active(self):
        self.bridge.generate()
        self.bridge.cfg["options"]["dry_run"] = False
        with patch.object(core.INPUT, "foreground_window", return_value=300), \
             patch.object(core.INPUT, "is_own_window", return_value=True), \
             patch.object(self.bridge, "_click") as click, \
             patch.object(self.bridge, "_sleep"):
            self.bridge._automate([("slot1", "example", "навык")])
            click.assert_not_called()
        self.assertIsNone(self.bridge.cfg.get("last_equipped", {})[self.bridge.build["side"]])

    def test_foreground_loss_aborts_before_second_click(self):
        self.bridge.generate()
        self.bridge.cfg["options"]["dry_run"] = False
        self.bridge.cfg["options"]["hover_retry"] = False
        # Captured HWND -> preflight -> first click -> switched before next click.
        with patch.object(core.INPUT, "foreground_window",
                          side_effect=[501, 501, 501, 777]), \
             patch.object(core.INPUT, "is_own_window", return_value=False), \
             patch.object(core.INPUT, "click", return_value=True) as click, \
             patch.object(self.bridge, "_search_and_select", return_value=True), \
             patch.object(self.bridge, "_sleep"):
            self.bridge._automate([
                ("slot1", "first", "навык 1"),
                ("slot2", "second", "навык 2"),
            ])
            self.assertEqual(click.call_count, 1)
        self.assertIsNone(self.bridge.cfg.get("last_equipped", {})[self.bridge.build["side"]])

    def test_foreground_guard_blocks_paste_and_click(self):
        self.bridge.cfg["options"]["dry_run"] = False
        self.bridge._target_window = 501
        with patch.object(core.INPUT, "foreground_window", return_value=777), \
             patch.object(core.INPUT, "click") as click, \
             patch.object(core.INPUT, "paste") as paste:
            with self.assertRaisesRegex(RuntimeError, "изменилось"):
                self.bridge._click((100, 100), "slot1")
            with self.assertRaisesRegex(RuntimeError, "изменилось"):
                self.bridge._paste("example")
            click.assert_not_called()
            paste.assert_not_called()

    def test_focus_loss_during_cursor_travel_does_not_click(self):
        from unittest.mock import MagicMock
        pointer = MagicMock()
        checkpoints = [0]
        def guard():
            checkpoints[0] += 1
            if checkpoints[0] >= 3:
                raise RuntimeError("focus lost during movement")
        with patch.object(core.INPUT, "available", True), \
             patch.object(core.INPUT, "pydirectinput", pointer), \
             patch.object(core.INPUT, "position", return_value=(0, 0)):
            with self.assertRaisesRegex(RuntimeError, "focus lost"):
                core.INPUT.click(300, 300, steps=8, step_delay=0,
                                 wiggle=0, settle=0, verify=False, guard=guard)
        pointer.mouseDown.assert_not_called()
        pointer.mouseUp.assert_not_called()

    def test_mouse_release_and_modifier_release_on_focus_loss(self):
        from unittest.mock import MagicMock
        pointer = MagicMock()
        with patch.object(core.INPUT, "available", True), \
             patch.object(core.INPUT, "pydirectinput", pointer), \
             patch.object(core.INPUT, "position", return_value=(1, 1)):
            points = [0]
            def guard_click():
                points[0] += 1
                if points[0] >= 5:
                    raise RuntimeError("lost focus while mouse held")
            with self.assertRaisesRegex(RuntimeError, "lost focus"):
                core.INPUT.click(1, 1, steps=1, step_delay=0, wiggle=0,
                                 settle=0, verify=False, hold=0, guard=guard_click)
            pointer.mouseDown.assert_called_once()
            pointer.mouseUp.assert_called_once()
            pointer.reset_mock()
            keys = [0]
            def guard_key():
                keys[0] += 1
                if keys[0] >= 2:
                    raise RuntimeError("focus changed while ctrl held")
            with self.assertRaisesRegex(RuntimeError, "focus changed"):
                core.INPUT.hotkey("ctrl", "a", hold=0, guard=guard_key)
            pointer.keyDown.assert_called_once_with("ctrl")
            pointer.keyUp.assert_called_once_with("ctrl")

    def test_invalid_screen_coordinates_prevent_worker_start(self):
        self.bridge.generate()
        self.bridge.cfg["options"]["dry_run"] = False
        with patch.object(self.bridge, "_outside_desktop", return_value=["slot1"]), \
             patch.object(core.INPUT, "available", True), \
             patch.object(self.bridge, "_automate") as worker:
            self.bridge.equip()
            worker.assert_not_called()
            self.assertFalse(self.bridge.running)

    @unittest.skipUnless(sys.platform == "win32", "Win32 HWND required")
    def test_own_window_is_identified_by_current_process_id(self):
        from unittest.mock import MagicMock
        api = MagicMock()
        def set_pid(_hwnd, ptr):
            core.ctypes.cast(ptr, core.ctypes.POINTER(core.ctypes.c_ulong)).contents.value = os.getpid()
            return 1
        api.GetWindowThreadProcessId.side_effect = set_pid
        with patch.object(core.ctypes.windll, "user32", api):
            self.assertTrue(core.INPUT.is_own_window(501))
        self.assertTrue(core.INPUT.is_own_window(0))  # no HWND is never a safe target

    def test_zero_duration_sleep_is_still_interruptible(self):
        self.bridge.stop()
        with self.assertRaises(core.AbortError):
            self.bridge._sleep(0)
        with self.assertRaises(core.AbortError):
            self.bridge._sleep(-1)

    def test_stop_mid_step_prevents_search(self):
        self.bridge.generate()
        self.bridge.cfg["options"]["dry_run"] = True
        self.bridge._stop.clear()
        def click_then_stop(coord, key):
            self.bridge.stop()
            return True
        with patch.object(self.bridge, "_click", side_effect=click_then_stop), \
             patch.object(self.bridge, "_search_and_select") as search:
            self.bridge._automate([("slot1", "example", "навык")])
            search.assert_not_called()
        self.assertTrue(self.bridge._stop.is_set())
        self.assertEqual(self.bridge.cfg.get("last_equipped", {}), {})

    def test_ocr_requires_region_and_readable_match(self):
        self.bridge._target_window = 501
        self.bridge.cfg["options"]["dry_run"] = False
        self.bridge.cfg["options"]["ocr_verify"] = True
        self.bridge.cfg["timings"]["retries"] = 0
        self.bridge.cfg["coords"].pop("ocr_region", None)
        with self.assertRaisesRegex(ValueError, "OCR"):
            self.bridge._search_and_select("example")
        self.bridge.cfg["coords"]["ocr_region"] = {
            "x": "100", "y": "100", "w": "260", "h": "70"
        }
        with patch.object(core.INPUT, "foreground_window", return_value=501), \
             patch.object(self.bridge, "_sleep"), \
             patch.object(self.bridge, "_click", return_value=True) as click, \
             patch.object(self.bridge, "_paste", return_value=True), \
             patch.object(core.INPUT, "hotkey"), \
             patch.object(core, "ocr_read", return_value=None):
            self.assertFalse(self.bridge._search_and_select("example"))
            self.assertEqual(click.call_count, 1)  # search field, not result

    def test_stop_during_ocr_never_clicks_result(self):
        self.bridge._target_window = 501
        self.bridge.cfg["options"]["dry_run"] = False
        self.bridge.cfg["options"]["ocr_verify"] = True
        self.bridge.cfg["timings"]["retries"] = 0
        self.bridge.cfg["coords"]["ocr_region"] = {
            "x": "100", "y": "100", "w": "260", "h": "70"
        }
        def read_and_cancel(*args):
            self.bridge.stop()
            return "example"
        with patch.object(core.INPUT, "foreground_window", return_value=501), \
             patch.object(self.bridge, "_click", return_value=True) as click, \
             patch.object(self.bridge, "_paste", return_value=True), \
             patch.object(core.INPUT, "hotkey"), \
             patch.object(core, "ocr_read", side_effect=read_and_cancel):
            with self.assertRaises(core.AbortError):
                self.bridge._search_and_select("example")
            self.assertEqual(click.call_count, 1)

    def test_character_panels_and_filtered_bulk_actions(self):
        entries = self.bridge.characters
        self.assertTrue(any(c["side"] == "K" for c in entries))
        self.assertTrue(any(c["side"] == "S" for c in entries))
        self.bridge.setCharactersBulk("K", "none", "")
        self.assertFalse(self.bridge.available_characters("KILLER"))
        self.assertEqual(self.cfg["owned"]["killers"], ["__none__"])
        self.bridge.setCharactersBulk("K", "all", "")
        self.assertTrue(self.bridge.available_characters("KILLER"))
        target = next(c["name"] for c in self.bridge.characters if c["side"] == "S")
        self.bridge.setCharactersBulk("S", "none", target)
        match = next(c for c in self.bridge.characters if c["side"] == "S" and c["name"] == target)
        self.assertFalse(match["owned"])

    def test_skin_gallery_default_and_bulk_ownership(self):
        if not core.SKINS:
            self.skipTest("No skins database")
        names = self.bridge.skinCharacters
        self.assertTrue(names)
        first = next((x for x in names if x["side"] == "S" and x["count"] > 0), None)
        self.assertIsNotNone(first)
        self.bridge.setSkinCharacter(first["name"])
        stats = self.bridge.skinStats
        self.assertEqual(stats["owned"], stats["total"])
        first_skin = self.bridge.skins[0]
        self.assertIn("rarity", first_skin)
        self.assertIn("date", first_skin)
        self.assertIn("type", first_skin)
        self.bridge.toggleSkin(first_skin["id"])
        self.assertEqual(self.bridge.skinStats["owned"], stats["total"]-1)
        self.bridge.setSkinsOwned("none")
        self.assertEqual(self.bridge.skinStats["owned"], 0)
        self.assertEqual(self.bridge.randomSkinId(), -1)
        self.bridge.setSkinsOwned("all")
        self.assertEqual(self.bridge.skinStats["owned"], stats["total"])
        self.assertIn(self.bridge.randomSkinId(), [x["id"] for x in self.bridge.skins])

    def test_skin_localization_coverage_and_filters_preserve_ownership(self):
        if not core.SKINS:
            self.skipTest("No skins database")
        candidate = next((x for x in self.bridge.skinCharacters
                          if x["translated"] > 0 and x["missingRussian"] > 0), None)
        self.assertIsNotNone(candidate)
        self.bridge.setSkinCharacter(candidate["name"])
        stats = self.bridge.skinStats
        self.assertEqual(stats["translated"] + stats["missingRussian"], stats["total"])
        self.assertEqual(stats["owned"], stats["total"])
        self.assertEqual(self.bridge.skinNameFilter, "all")
        self.assertEqual(len(self.bridge.skins), stats["total"])
        self.bridge.setSkinNameFilter("ru")
        translated = self.bridge.skins
        self.assertEqual(len(translated), stats["translated"])
        self.assertTrue(all(row["hasRussian"] and row["russian"]
                            and row["russianSource"] for row in translated))
        self.assertTrue(all(row["english"] for row in translated))
        self.bridge.setSkinNameFilter("missing")
        missing = self.bridge.skins
        self.assertEqual(len(missing), stats["missingRussian"])
        self.assertTrue(all(not row["hasRussian"] and not row["russian"]
                            and row["english"] == row["name"] for row in missing))
        self.bridge.filterSkins(missing[0]["english"])
        self.assertIn(missing[0]["id"], [row["id"] for row in self.bridge.skins])
        self.bridge.filterSkins("")
        self.bridge.setSkinNameFilter("not-a-filter")
        self.assertEqual(self.bridge.skinNameFilter, "missing")
        self.assertEqual(self.bridge.skinStats["owned"], stats["total"])
        self.bridge.setSkinNameFilter("all")
        self.assertEqual(len(self.bridge.skins), stats["total"])
        # Filtration is visual only; random draw still uses ownership selections.
        self.assertIn(self.bridge.randomSkinId(),
                      [row["id"] for row in self.bridge.skins])

    def test_skin_character_coverage_totals_match_global_catalog(self):
        if not core.SKINS:
            self.skipTest("No skins database")
        rows = self.bridge.skinCharacters
        self.assertTrue(rows)
        self.assertTrue(all(x["translated"] + x["missingRussian"] == x["count"]
                            for x in rows))
        self.assertEqual(sum(x["count"] for x in rows), len(core.SKINS.SKINS_BY_ID))
        self.assertEqual(sum(x["translated"] for x in rows),
                         sum(bool(v.get("name_ru")) for v in core.SKINS.SKINS_BY_ID.values()))

    def test_addons_have_real_names_and_two_labeled_slots(self):
        self.bridge.setRole("killer")
        self.bridge.generate()
        meta = self.bridge.detail
        self.assertEqual(len(meta["addonDetails"]), 2)
        for pos, addon in enumerate(meta["addonDetails"], 1):
            self.assertEqual(addon["slot"], pos)
            self.assertEqual(addon["raw"], self.bridge.build["addons"][pos - 1])
            self.assertEqual(addon["name"], self.bridge.build["addons"][pos - 1].strip())
            self.assertIsInstance(addon["filled"], bool)

    def test_full_challenge_rule_difficulty_and_equipment_restrictions(self):
        challenge = next(ch for ch in core.DATA.CHALLENGES
                         if ch.get("side") == "SURVIVOR"
                         and "item" in ch.get("fx", {}).get("drop", ()))
        self.bridge._generate(preset_challenge=challenge)
        metadata = self.bridge.detail
        self.assertEqual(metadata["challenge"], challenge["ru"])
        self.assertEqual(metadata["challengeText"], challenge["text"])
        self.assertEqual(metadata["challengeWhy"], challenge["why"])
        self.assertEqual(metadata["challengeDifficulty"], core.DATA.CHALLENGE_DIFFS[challenge["diff"]])
        self.assertTrue(any("Предмет" in part for part in metadata["challengeRestrictions"]))

    def test_visual_catalogs_match_generator_pools(self):
        chars = self.bridge.searchCharacters("KILLER", "")
        self.assertGreater(len(chars), 0)
        self.assertIn(chars[0]["name"], self.bridge.db["killers"])
        self.assertTrue(self.bridge.searchPerks("SURVIVOR", ""))
        killer = chars[0]["name"]
        result = self.bridge.searchAddons("KILLER", killer, "", "")
        playable = set(core._playable_addons(self.bridge.db["killers"][killer]["addons"]))
        self.assertTrue(all(x["name"] in playable for x in result))
        self.assertFalse(self.bridge.searchPerks("UNKNOWN", ""))

    def test_perk_builder_catalog_filters_and_owners(self):
        killer = next(iter(self.bridge.db["killers"]))
        owned = set(self.bridge.db["killers"][killer]["perks"])
        by_hero = self.bridge.searchPerks("KILLER", "", "character", killer)
        self.assertTrue(by_hero)
        self.assertTrue(all(row["name"] in owned for row in by_hero))
        self.assertTrue(all(key in by_hero[0] for key in ("name", "owner", "kind", "common")))
        self.assertEqual(self.bridge.searchPerks("KILLER", "", "character", "invalid"), [])
        self.assertEqual(self.bridge.searchPerks("KILLER", "", "invalid", killer), [])
        common = self.bridge.searchPerks("SURVIVOR", "", "common", "")
        self.assertTrue(common)
        self.assertTrue(all(row["common"] for row in common))
        unique = self.bridge.searchPerks("SURVIVOR", "", "unique", "")
        self.assertTrue(unique)
        self.assertTrue(all(not row["common"] for row in unique))
        name = unique[0]["name"]
        result = self.bridge.searchPerks("SURVIVOR", name, "unique", "")
        self.assertIn(name, [row["name"] for row in result])
        self.assertFalse(self.bridge.searchPerks("UNKNOWN", "", "all", ""))

    def test_item_picker_and_addon_compatibility(self):
        items = self.bridge.searchItems("")
        self.assertTrue(items)
        item = items[0]
        category = self.bridge.db["survivor_items"][item["category"]]
        self.assertIn(item["name"], category["items"])
        suggestions = self.bridge.searchAddons("SURVIVOR", "", item["name"], "")
        expected = set(core._playable_addons(category.get("addons", [])))
        self.assertTrue(all(row["name"] in expected for row in suggestions))
        self.assertEqual(self.bridge.searchAddons("SURVIVOR", "", "", ""), [])
        self.bridge.buildCustom("SURVIVOR",
                                next(iter(self.bridge.db["survivors"])),
                                "", "Несуществующий аддон", "",
                                *[x["name"] for x in self.bridge.searchPerks("SURVIVOR", "")[:4]])
        self.assertIsNone(self.bridge.build)

    def test_invalid_custom_build_rejected(self):
        self.bridge.buildCustom("SURVIVOR", "nonexistent", "", "", "", "x", "x", "x", "x")
        self.assertIsNone(self.bridge.build)

    def test_selected_addon_effect_shows_real_summary_and_source(self):
        with patch.object(self.bridge._addon_catalog, "refresh_async") as refresh:
            self.bridge.selectAddonEffect("KILLER", "Охотник", "", "Радужный камень")
            refresh.assert_called_once()
        data = self.bridge.addonEffect
        self.assertEqual(data["name"], "Радужный камень")
        self.assertTrue(data["verified"])
        self.assertIn("30", data["effect"])
        self.assertEqual(data["english"], "Iridescent Stone")
        self.assertTrue(data["source"].startswith("https://deadbydaylight.wiki.gg/"))
        self.bridge._addon_catalog.categories["Iridescent Stone"] = ["EffectDuration"]
        self.assertIn("длительность эффекта", self.bridge.addonEffect["categories"])

    def test_addon_without_checked_description_never_has_invented_claim(self):
        with patch.object(self.bridge._addon_catalog, "refresh_async"):
            self.bridge.selectAddonEffect("KILLER", "Охотник", "", "Несуществующая запись")
        data = self.bridge.addonEffect
        self.assertFalse(data["verified"])
        self.assertFalse(data["effect"])

    def test_addon_notes_cover_other_killers_and_survivors(self):
        examples = [
            ("KILLER", "Свинья", "", "Видеокассета"),
            ("KILLER", "Кошмар", "", "Садовые грабли"),
            ("KILLER", "Хороший парень", "", "Жесткая шляпа"),
            ("SURVIVOR", "", "Фонарики", "Батарейка"),
            ("SURVIVOR", "", "Аптечки", "Медицинские ножницы"),
            ("SURVIVOR", "", "Ящики с инструментами", "Катушка проволоки"),
            ("SURVIVOR", "", "Ключи", "Уникальное обручальное кольцо"),
        ]
        for side, char, category, name in examples:
            with self.subTest(name=name):
                with patch.object(self.bridge._addon_catalog, "refresh_async"):
                    self.bridge.selectAddonEffect(side, char, category, name)
                effect = self.bridge.addonEffect
                self.assertTrue(effect["verified"])
                self.assertTrue(effect["effect"])
                self.assertTrue(effect["english"])
                self.assertIn("wiki.gg", effect["source"])

    def test_wiki_effect_tags_render_as_broad_mechanic_not_false_specific_claim(self):
        with patch.object(self.bridge._addon_catalog, "refresh_async"):
            self.bridge.selectAddonEffect("SURVIVOR", "", "Фонарики", "Сверхмощная батарейка")
        english = self.bridge.addonEffect["english"]
        self.bridge._addon_catalog.categories[english] = ["Charges", "ActionTime"]
        entry = self.bridge.addonEffect
        self.assertIn("заряды", entry["summary"])
        self.assertIn("время действия", entry["summary"])
        self.assertFalse(entry["verified"])
        self.assertEqual(entry["effect"], "")

    def test_all_survivor_addon_groups_have_english_lookup(self):
        from tools.addon_names_ru_en import ITEM_ADDON_RU_EN
        self.assertGreaterEqual(len(ITEM_ADDON_RU_EN), 6)
        for category, names in ITEM_ADDON_RU_EN.items():
            with self.subTest(category=category):
                self.assertTrue(names)
                ru, english = next(iter(names.items()))
                entry = self.bridge._addon_catalog.get("SURVIVOR", "", category, ru)
                self.assertEqual(entry["english"], english)
                self.assertTrue(entry["source"].startswith("https://"))

    def test_custom_build_validation_reports_success_to_ui(self):
        survivor = next(iter(self.bridge.db["survivors"]))
        perks = [row["name"] for row in self.bridge.searchPerks("SURVIVOR", "")[:4]]
        self.assertEqual(len(perks), 4)
        self.assertTrue(self.bridge.buildCustom("SURVIVOR", survivor, "", "", "", *perks))
        self.assertEqual(self.bridge.build["char"], survivor)
        self.assertFalse(self.bridge.buildCustom("SURVIVOR", "invalid survivor", "", "", "", *perks))

    def test_updater_progress_keeps_busy_flag_and_release(self):
        info = {"tag": "v2.28.0-qt-beta.18"}
        self.bridge._update_info = info
        self.bridge._update_busy = True
        self.bridge._messages.put(("update_progress", "Скачивание обновления: 40%"))
        self.bridge._drain()
        self.assertEqual(self.bridge.updateText, "Скачивание обновления: 40%")
        self.assertTrue(self.bridge.updateBusy)
        self.assertTrue(self.bridge.updateAvailable)
        self.assertIs(self.bridge._update_info, info)

    def test_future_updates_use_explicit_semver(self):
        self.assertLess(qt_updater._key("v2.28.0-qt-beta.14"), qt_updater._key("v2.28.0-qt-beta.15"))
        self.assertIsNone(qt_updater._key("v2.28.0"))
        with self.assertRaises(ValueError):
            qt_updater._get("https://attacker.example/test")


if __name__ == "__main__":
    unittest.main()
