"""Native Qt backend for DBD Randomizer. No Tk window or Tk variables.

Business rules and game data reuse functions from dbd_randomizer.py; the Qt
backend handles state, persistence, background networking and game UI automation.
"""
from __future__ import annotations

import os
import queue
import random
import re
import sys
import threading
import time
import traceback
from urllib.parse import urlsplit

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot, QUrl, Qt
from PySide6.QtGui import QGuiApplication, QPainter, QColor, QCursor, QDesktopServices
from PySide6.QtWidgets import QWidget

import dbd_randomizer as core
import qt_updater
from addon_effects import AddonEffectLibrary
from rotation_engine import RotationState, make_rotated_build
from perk_cards import perk_info, reconcile_pins
from stats_engine import BuildStatistics
from favorites import FavoriteBuilds
from appearance import SCALES, THEMES, normalize as normalize_appearance, palette as appearance_palette, write_to_options
from dbd_icons_store import IconStore
from icon_queue import IconDownloadQueue


def tidy(s):
    return re.sub(r"[\U0001F000-\U0001FFFF\u2600-\u27BF]", "", str(s or "")).strip()


class QtBridge(QObject):
    perksChanged = Signal()
    buildRevisionChanged = Signal()
    roleChanged = Signal()
    modeChanged = Signal()
    rotationChanged = Signal()
    statusChanged = Signal()
    optionsChanged = Signal()
    advancedChanged = Signal()
    historyChanged = Signal()
    statisticsChanged = Signal()
    favoritesChanged = Signal()
    appearanceChanged = Signal()
    detailChanged = Signal()
    charactersChanged = Signal()
    skinsChanged = Signal()
    settingsChanged = Signal()
    communityChanged = Signal()
    iconVersionChanged = Signal()
    addonEffectChanged = Signal()
    runningChanged = Signal()
    updateChanged = Signal()
    _wake = Signal()

    def __init__(self):
        super().__init__()
        self.cfg, migrated = core.load_config()
        self._appearance = normalize_appearance(self.cfg.get("options", {}))
        self.db = core.load_db()
        self.build = None
        self._role = self.cfg["options"].get("side", "SURVIVOR")
        if self._role not in ("SURVIVOR", "KILLER"):
            self._role = "SURVIVOR"
        self._mode = self.cfg["options"].get("perk_mode", "mixed")
        self._rotation = RotationState(self.cfg["options"].get("rotation_state"))
        self._rotation_enabled = bool(self.cfg["options"].get("rotation_enabled", False))
        self._statistics = BuildStatistics(self.cfg["options"].get("statistics_v1"))
        self._favorites = FavoriteBuilds(self.cfg["options"].get("favorite_builds_v1"),
                                         empty=core.EMPTY, no_addons=core.NO_ADDONS)
        self._favorite_search = ""
        self._favorite_side = "ALL"
        self._favorite_collection = "Все коллекции"
        self._statistics_side = self._role
        self._statistics_group = "characters"
        self._statistics_period = 0
        self._stats_population_cache = {}
        self._locks = [False] * 4
        self._build_revision = 0
        self._history = []
        self._status = ("Ядро " + core.APP_VERSION + " · Qt " + qt_updater.CURRENT_TAG)
        self._log = []
        self._messages = queue.SimpleQueue()
        self._icon_version = 0
        # Coalesce icon download bursts into a single redraw for the QML catalogs.
        self._icon_refresh = QTimer(self)
        self._icon_refresh.setSingleShot(True)
        self._icon_refresh.setInterval(120)
        self._icon_refresh.timeout.connect(self._flush_icons)
        self._icons = IconStore(core.ICONS_DIR, enabled=True)
        self._icon_pending = set()
        self._icon_urls = {}
        self._icon_queue = IconDownloadQueue(self._icons, self._icon_processed, workers=3)
        self._addon_catalog = AddonEffectLibrary(core.APP_DIR, on_change=self._effects_updated)
        self._selected_addon = {"side": "", "character": "", "category": "", "name": ""}
        self._skin_character = next(iter(self.db["survivors"]), "")
        self._skin_filter = ""
        self._skin_name_filter = "all"
        self._classes = {}
        self._community = []
        self._challenge = None
        self._running = False
        self._worker = None
        self._stop = threading.Event()
        self._hotkey_handle = None
        self._target_window = None
        self._equip_side = None
        self._planned_equipped = None
        self._update_info = None
        self._update_text = qt_updater.last_install_error(
            os.path.dirname(sys.executable)
        ) or ("Установлена версия " + qt_updater.CURRENT_TAG)
        self._update_busy = False
        self._owned = {}
        for side, key in (("K", "killers"), ("S", "survivors")):
            all_chars = list(self.db["killers" if side == "K" else "survivors"])
            stored = self.cfg.get("owned", {}).get(key) or []
            # Legacy empty list means all; "__none__" is an explicit empty selection.
            self._owned[side] = (set(stored) & set(all_chars)) if stored else set(all_chars)
        self._wake.connect(self._drain)
        self._tick = QTimer(self)
        self._tick.timeout.connect(self._drain)
        self._tick.start(80)
        self._hotkey()
        if migrated:
            self._save()

    def _notify(self, message, log=True):
        self._messages.put(("status", tidy(message), log))
        self._wake.emit()

    def _drain(self):
        needs_icons = False
        # Coalesce burst notifications to avoid redundant QML bindings.
        status_dirty = False
        update_dirty = False
        for _ in range(80):
            try:
                item = self._messages.get_nowait()
            except queue.Empty:
                break
            kind = item[0]
            if kind == "status":
                self._status = item[1]
                status_dirty = True
                if item[2]:
                    self._log.append(time.strftime("%H:%M:%S") + "  " + item[1])
                    self._log = self._log[-250:]
            elif kind == "running":
                self._running = item[1]
                self.runningChanged.emit()
            elif kind == "community":
                self._community = item[1]
                self.communityChanged.emit()
            elif kind == "icons":
                self._icon_pending.discard(item[1])
                needs_icons = needs_icons or bool(item[2])
            elif kind == "effects":
                self.addonEffectChanged.emit()
            elif kind == "update_progress":
                # Progress is not a terminal result: do not clear _update_busy
                # or _update_info before the verified archive is installed.
                self._update_text = item[1]
                update_dirty = True
            elif kind == "update":
                self._update_info = item[1]
                self._update_text = item[2]
                self._update_busy = False
                update_dirty = True
            elif kind == "install":
                try:
                    qt_updater.install_staged(item[1])
                    self._update_text = "Обновление проверено. Закрываю приложение для установки…"
                    self.updateChanged.emit()
                    self._notify("Обновление проверено. Завершаю приложение для установки.")
                    QGuiApplication.instance().quit()
                except Exception as e:
                    self._notify("Не удалось запустить установку: " + str(e))
                    self._update_busy = False
                    self.updateChanged.emit()
        if status_dirty:
            self.statusChanged.emit()
        if update_dirty:
            self.updateChanged.emit()
        if needs_icons and not self._icon_refresh.isActive():
            self._icon_refresh.start()

    def _flush_icons(self):
        self._icon_version += 1
        self.iconVersionChanged.emit()

    def _save(self):
        self.cfg.setdefault("options", {})["side"] = self._role
        self.cfg["options"]["perk_mode"] = self._mode
        self.cfg["options"]["rotation_enabled"] = self._rotation_enabled
        self.cfg["options"]["rotation_state"] = self._rotation.serialize()
        self.cfg["options"]["statistics_v1"] = self._statistics.serialize()
        self.cfg["options"]["favorite_builds_v1"] = self._favorites.serialize()
        write_to_options(self.cfg["options"], self._appearance)
        self.cfg.setdefault("owned", {})["killers"] = sorted(self._owned["K"]) or ["__none__"]
        self.cfg["owned"]["survivors"] = sorted(self._owned["S"]) or ["__none__"]
        core.save_config(self.cfg)

    def _option(self, key):
        return self.cfg["options"].get(key, core.OPTION_DEFAULTS.get(key))

    @Property(str, notify=appearanceChanged)
    def appearanceTheme(self):
        return self._appearance["theme"]

    @Property(float, notify=appearanceChanged)
    def appearanceScale(self):
        return self._appearance["scale"]

    @Property(bool, notify=appearanceChanged)
    def animationsEnabled(self):
        return self._appearance["animations"]

    @Property("QVariantMap", notify=appearanceChanged)
    def appearancePalette(self):
        return appearance_palette(self._appearance["theme"])

    @Slot(str)
    def setAppearanceTheme(self, value):
        if value not in THEMES or value == self._appearance["theme"]:
            return
        self._appearance["theme"] = value
        self._save()
        self.appearanceChanged.emit()

    @Slot(float)
    def setAppearanceScale(self, value):
        if not any(abs(value - permitted) < 0.001 for permitted in SCALES):
            return
        value = min(SCALES, key=lambda x: abs(x - value))
        if value == self._appearance["scale"]:
            return
        self._appearance["scale"] = value
        self._save()
        self.appearanceChanged.emit()

    @Slot()
    def resetAppearance(self):
        self._appearance = normalize_appearance({})
        self._save()
        self.appearanceChanged.emit()

    @Slot(bool)
    def setAnimationsEnabled(self, enabled):
        if enabled == self._appearance["animations"]:
            return
        self._appearance["animations"] = enabled
        self._save()
        self.appearanceChanged.emit()

    @Property(str, notify=roleChanged)
    def role(self):
        return "killer" if self._role == "KILLER" else "survivor"

    @Property(str, notify=modeChanged)
    def mode(self):
        return self._mode

    @Property(str, notify=statisticsChanged)
    def statisticsSide(self):
        return self._statistics_side

    @Property(str, notify=statisticsChanged)
    def statisticsGroup(self):
        return self._statistics_group

    @Property(int, notify=statisticsChanged)
    def statisticsPeriod(self):
        return self._statistics_period

    @Slot(int)
    def setStatisticsPeriod(self, days):
        if days not in (0, 1, 7, 30):
            return
        if self._statistics_period != days:
            self._statistics_period = days
            self.statisticsChanged.emit()

    def _statistics_population(self):
        side = self._statistics_side
        group = self._statistics_group
        key = (side, group)
        if key in self._stats_population_cache:
            return self._stats_population_cache[key]
        result = self._build_statistics_population(side, group)
        self._stats_population_cache[key] = result
        return result

    def _build_statistics_population(self, side, group):
        if group == "characters":
            return list(self.db["killers" if side == "KILLER" else "survivors"])
        if group == "perks":
            return list(set(core.all_unique_perks(self.db, side)) |
                        set(self.db["killer_common_perks" if side == "KILLER" else "surv_common_perks"]))
        if group == "addons":
            if side == "KILLER":
                return list({x for entry in self.db["killers"].values()
                             for x in core._playable_addons(entry.get("addons", []))})
            return list({x for entry in self.db["survivor_items"].values()
                         for x in core._playable_addons(entry.get("addons", []))})
        if group == "items" and side == "SURVIVOR":
            return list({x for entry in self.db["survivor_items"].values()
                         for x in entry.get("items", [])})
        return []

    @Property("QVariantMap", notify=statisticsChanged)
    def statistics(self):
        side = self._statistics_side
        pool = self._statistics_population()
        population = list(self.db["killers" if side == "KILLER" else "survivors"])
        days = self._statistics_period
        return {
            "overview": self._statistics.overview_period(side, population, days),
            "top": self._statistics.summary_period(side, self._statistics_group, pool,
                                                    days=days, limit=12, order="top"),
            "least": self._statistics.summary_period(side, self._statistics_group, pool,
                                                      days=days, limit=12, order="least"),
            "stale": self._statistics.summary(side, self._statistics_group, pool,
                                               limit=12, order="stale"),
            "recent": self._statistics.recent_period(side, days, 28),
            "group": self._statistics_group,
            "side": side,
            "period": days,
            "sampleSize": len(pool)
        }

    @Slot(str)
    def setStatisticsSide(self, side):
        if side not in ("SURVIVOR", "KILLER"):
            return
        if self._statistics_side != side:
            self._statistics_side = side
            if side == "KILLER" and self._statistics_group == "items":
                self._statistics_group = "characters"
            self.statisticsChanged.emit()

    @Slot(str)
    def setStatisticsGroup(self, group):
        if group not in ("characters", "perks", "addons", "items"):
            return
        if group == "items" and self._statistics_side == "KILLER":
            return
        if self._statistics_group != group:
            self._statistics_group = group
            self.statisticsChanged.emit()

    @Slot()
    def resetStatistics(self):
        self._statistics.reset(self._statistics_side)
        self.statisticsChanged.emit()
        self._save()
        self._notify("Статистика выбранной стороны очищена. История ротации сохранена.")

    @Slot()
    def copyStatistics(self):
        view = self.statistics
        overview = view["overview"]
        labels = {"characters":"Персонажи", "perks":"Навыки", "addons":"Аддоны", "items":"Предметы"}
        periods = {0: "Всё время", 1: "Сегодня", 7: "7 дней", 30: "30 дней"}
        lines = [
            "Статистика DBD Randomizer — " + ("Маньяки" if view["side"] == "KILLER" else "Выжившие"),
            "Период: " + periods.get(view["period"], "Всё время"),
            "Генераций: " + str(overview["generated"]) + " (обычный " +
            str(overview["classic"]) + ", ротация " + str(overview["balanced"]) + ")",
            "Разных персонажей: " + str(overview["seen"]) + " / " + str(overview["total"]),
            "Категория: " + labels.get(view["group"], ""),
        ]
        for index, row in enumerate(view["top"], 1):
            if row["count"]:
                lines.append(str(index) + ". " + row["name"] + " — " + str(row["count"]))
        QGuiApplication.clipboard().setText("\n".join(lines))
        self._notify("Статистика скопирована.")

    @Property(bool, notify=rotationChanged)
    def rotationEnabled(self):
        return self._rotation_enabled

    @Property("QVariantMap", notify=rotationChanged)
    def rotationStats(self):
        return self._rotation.info(self._role, self.available_characters(self._role))

    @Slot(bool)
    def setRotationEnabled(self, enabled):
        enabled = bool(enabled)
        if self._rotation_enabled == enabled:
            return
        self._rotation_enabled = enabled
        self._save()
        self.rotationChanged.emit()
        self._notify("Ротация включена: шанс повторов снижен." if enabled else
                     "Обычный случайный режим включён.")

    @Slot()
    def resetRotation(self):
        self._rotation.reset(self._role)
        self._save()
        self.rotationChanged.emit()
        self._notify("История ротации для выбранной стороны очищена.")

    @Property(str, notify=statusChanged)
    def status(self):
        return self._status

    @Property(str, notify=statusChanged)
    def logText(self):
        return "\n".join(self._log[-60:])

    @Property(bool, notify=runningChanged)
    def running(self):
        return self._running

    @Property("QVariantMap", notify=optionsChanged)
    def options(self):
        return {
            "addons": bool(self._option("addons_enabled")),
            "appearance": bool(self._option("skin_enabled")),
            "challenge": bool(self._option("challenge_enabled")),
            "owned": bool(self._option("respect_owned")),
            "classes": bool(self._option("class_enabled")),
            "dry": bool(self._option("dry_run")),
            "ocr": bool(self._option("ocr_verify")),
            "select_char": bool(self._option("select_char"))
        }

    @Property("QVariantMap", notify=advancedChanged)
    def advanced(self):
        return {
            "clear": bool(self._option("use_clear_button")),
            "verifyclipboard": bool(self._option("verify_clipboard")),
            "restoreclipboard": bool(self._option("restore_clipboard")),
            "hoververify": bool(self._option("hover_verify")),
            "hoverretry": bool(self._option("hover_retry")),
            "resultIndex": str(self._option("result_index") or 1),
            "abortKey": str(self._option("abort_key") or "f9"),
            "challengeDiff": str(self._option("challenge_diff") or "any"),
        }

    @Property("QVariantList", notify=perksChanged)
    def perks(self):
        names = self.build.get("perks", []) if self.build else []
        return [{"index": i+1, "name": tidy(names[i]) if i < len(names) else "Не выбран",
                 "raw": names[i] if i < len(names) else "",
                 "locked": self._locks[i],
                 "filled": i < len(names) and names[i] not in ("", core.EMPTY)}
                for i in range(4)]

    @Property(int, notify=buildRevisionChanged)
    def buildRevision(self):
        return self._build_revision

    @Property(int, notify=perksChanged)
    def lockedCount(self):
        if not self.build:
            return 0
        return sum(bool(p["locked"]) for p in self.perks if p["filled"])

    @Slot(int, result="QVariantMap")
    def perkInfo(self, index):
        if not self.build or not 0 <= index < 4:
            return {"slot": index + 1, "name": "Не выбран", "owner": "",
                    "kind": "Пустой слот", "locked": False, "filled": False}
        raw = self.perks[index]
        info = perk_info(self.db, self.build["side"], raw["raw"], empty=core.EMPTY)
        return {**info, "slot": index + 1, "locked": raw["locked"],
                "filled": raw["filled"], "side": self.build["side"]}

    @Slot()
    def openPerkReference(self):
        # The current database stores perk names and ownership, but no verified
        # in-game perk effects. Open the real reference page rather than guessing.
        QDesktopServices.openUrl(QUrl("https://deadbydaylight.wiki.gg/wiki/Perks"))

    @Slot(bool)
    def setAllPerkLocks(self, locked):
        if not self.build:
            return
        filled = self.perks
        changed = False
        for i in range(4):
            target = bool(locked) and filled[i]["filled"]
            if self._locks[i] != target:
                self._locks[i] = target
                changed = True
        if changed:
            self.perksChanged.emit()

    @Property(int, notify=favoritesChanged)
    def favoriteCount(self):
        return self._favorites.count

    @Property("QVariantList", notify=favoritesChanged)
    def favorites(self):
        return self._favorites.list(self._favorite_search, self._favorite_side,
                                    self._favorite_collection)

    @Property("QVariantList", notify=favoritesChanged)
    def favoriteCollections(self):
        return self._favorites.collections()

    @Property(str, notify=favoritesChanged)
    def favoriteSide(self):
        return self._favorite_side

    @Property(str, notify=favoritesChanged)
    def favoriteCollection(self):
        return self._favorite_collection

    @Slot(str)
    def setFavoriteSearch(self, text):
        self._favorite_search = str(text or "")[:180]
        self.favoritesChanged.emit()

    @Slot(str)
    def setFavoriteSide(self, side):
        if side not in ("ALL", "KILLER", "SURVIVOR"):
            return
        self._favorite_side = side
        self.favoritesChanged.emit()

    @Slot(str)
    def setFavoriteCollection(self, name):
        if name not in self._favorites.collections():
            name = "Все коллекции"
        self._favorite_collection = name
        self.favoritesChanged.emit()

    @Slot(str, str, str, result=bool)
    def saveFavorite(self, title, collection, note):
        if not self.build:
            self._notify("Сначала создайте билд для сохранения.")
            return False
        try:
            ident = self._favorites.add(self.build, title, collection, note)
            self._save()
            self.favoritesChanged.emit()
            self._notify("Билд сохранён в избранное: " +
                         self._favorites.get(ident)["title"])
            return True
        except (ValueError, TypeError) as exc:
            self._notify("Не удалось сохранить билд: " + str(exc))
            return False

    @Slot(str, str, str, str, result=bool)
    def editFavorite(self, ident, title, collection, note):
        if not self._favorites.update(ident, title, collection, note):
            self._notify("Сохранённый билд не найден.")
            return False
        if self._favorite_collection not in self._favorites.collections():
            self._favorite_collection = "Все коллекции"
        self._save()
        self.favoritesChanged.emit()
        self._notify("Название и заметки сохранены.")
        return True

    @Slot(str, result=bool)
    def deleteFavorite(self, ident):
        if not self._favorites.delete(ident):
            self._notify("Билд уже отсутствует в избранном.")
            return False
        if self._favorite_collection not in self._favorites.collections():
            self._favorite_collection = "Все коллекции"
        self._save()
        self.favoritesChanged.emit()
        self._notify("Билд удалён из избранного.")
        return True

    @Slot(str, result=bool)
    def loadFavorite(self, ident):
        try:
            build = self._favorites.restore(ident, self.db, core)
        except (ValueError, TypeError) as exc:
            self._notify("Не удалось открыть сохранённый билд: " + str(exc))
            return False
        self.build = build
        self._role = build["side"]
        self._locks = [False] * 4
        self.roleChanged.emit()
        self.rotationChanged.emit()
        self._sync()
        # Reopening a saved build is not a fresh random roll; do not change
        # either rotation weights or generation statistics.
        self._save()
        self._notify("Загружен сохранённый билд: " + build["char"])
        return True

    @Slot(str)
    def copyFavorite(self, ident):
        try:
            build = self._favorites.restore(ident, self.db, core)
        except (ValueError, TypeError) as exc:
            self._notify("Нельзя скопировать устаревший билд: " + str(exc))
            return
        QGuiApplication.clipboard().setText(core.build_to_clipboard_text(build))
        self._notify("Сохранённый билд скопирован.")

    @Property("QVariantList", notify=historyChanged)
    def history(self):
        return self._history[:12]

    @Property("QVariantMap", notify=detailChanged)
    def detail(self):
        b = self.build or {}
        skin, challenge, cl = b.get("skin") or {}, b.get("challenge") or {}, b.get("class") or {}
        forbidden = b.get("forbidden") or {}
        restrictions = []
        for key, label in (("item", "Предмет"), ("addons", "Аддоны"), ("perks", "Навыки")):
            if forbidden.get(key):
                restrictions.append(label + " запрещены условием челленджа"
                                    if key != "item" else "Предмет запрещён условием челленджа")
        addon_names = list(b.get("addons") or [])
        addon_details = [
            {"slot": i + 1,
             "name": tidy(addon_names[i]) if i < len(addon_names) else "Не выбран",
             "raw": addon_names[i] if i < len(addon_names) else "",
             "filled": i < len(addon_names) and addon_names[i] not in (None, "", core.EMPTY, core.NO_ADDONS),
             "disabled": bool(forbidden.get("addons"))}
            for i in range(2)
        ]
        challenge_data = challenge if isinstance(challenge, dict) else {}
        difficulty = (getattr(core.DATA, "CHALLENGE_DIFFS", {}) or {}).get(challenge_data.get("diff"), "")
        return {"char": tidy(b.get("char", "")), "side": b.get("side", ""),
                "power": tidy(b.get("power_or_item", "")), "category": tidy(b.get("category", "")),
                "addons": [tidy(x) for x in addon_names],
                "addonDetails": addon_details,
                "skin": tidy(skin.get("display") or skin.get("name")) if isinstance(skin, dict) else tidy(skin),
                "challenge": tidy(challenge_data.get("ru")),
                "challengeText": tidy(challenge_data.get("text")),
                "challengeWhy": tidy(challenge_data.get("why")),
                "challengeDifficulty": tidy(difficulty),
                "challengeRestrictions": restrictions,
                "class": tidy(cl.get("ru")) if isinstance(cl, dict) else "",
                "hasBuild": bool(b)}

    @Property("QVariantList", notify=charactersChanged)
    def characters(self):
        return [{"side": side, "name": name, "owned": name in self._owned[side]}
                for side, pool in (("K", self.db["killers"]), ("S", self.db["survivors"]))
                for name in sorted(pool)]

    @Property("QVariantList", notify=skinsChanged)
    def skinCharacters(self):
        if not core.SKINS:
            return []
        result = []
        for name, ids in sorted(core.SKINS.CHAR_SKINS.items()):
            if name not in self.db["killers"] and name not in self.db["survivors"]:
                continue
            local = sum(bool((core.SKINS.SKINS_BY_ID.get(sid) or {}).get("name_ru"))
                        for sid in ids)
            result.append({"name": name,
                           "side": "K" if name in self.db["killers"] else "S",
                           "count": len(ids), "translated": local,
                           "missingRussian": len(ids) - local})
        return result

    def _skin_ids(self):
        return list(core.SKINS.CHAR_SKINS.get(self._skin_character, [])) if core.SKINS else []

    def _owned_skin_ids(self):
        ids = self._skin_ids()
        saved = self.cfg.get("skins", {}).get(self._skin_character)
        return set(ids) if saved is None else set(saved)

    @Property("QVariantMap", notify=skinsChanged)
    def skinStats(self):
        ids = self._skin_ids()
        owned = self._owned_skin_ids()
        translated = sum(bool((core.SKINS.SKINS_BY_ID.get(sid) or {}).get("name_ru"))
                         for sid in ids) if core.SKINS else 0
        return {"total": len(ids), "owned": sum(sid in owned for sid in ids),
                "translated": translated, "missingRussian": len(ids) - translated}

    @Property(str, notify=skinsChanged)
    def skinNameFilter(self):
        return self._skin_name_filter

    @Property("QVariantList", notify=skinsChanged)
    def skins(self):
        if not core.SKINS:
            return []
        result = []
        owned = self._owned_skin_ids()
        source_labels = {
            "piece": "Сопоставлено по элементам",
            "manual": "Ручное подтверждение",
            "coschar": "Сопоставлено по набору",
            "previous": "Сохранено из прошлой базы",
            "file": "Русская вики (по изображению)",
        }
        for sid in self._skin_ids():
            info = core.SKINS.SKINS_BY_ID.get(sid) or {}
            russian = tidy(info.get("name_ru") or "")
            has_russian = bool(russian)
            if self._skin_name_filter == "ru" and not has_russian:
                continue
            if self._skin_name_filter == "missing" and has_russian:
                continue
            name = russian or tidy(info.get("name") or sid)
            english = tidy(info.get("name", ""))
            rarity = tidy(info.get("rarity_ru") or core.SKINS.RARITY_RU.get(info.get("rarity"), ""))
            typ = "Скин персонажа" if info.get("kind") == "coschar" else "Набор одежды"
            date = str(info.get("date") or "")
            search = core._norm(" ".join((str(sid), name, english, rarity, typ, date, self._skin_character)))
            if self._skin_filter and core._norm(self._skin_filter) not in search:
                continue
            provenance = str(info.get("name_ru_from") or ("file" if has_russian else ""))
            result.append({"id": int(sid), "name": name, "english": english,
                           "russian": russian, "hasRussian": has_russian,
                           "russianSource": source_labels.get(provenance, "Источник не указан")
                               if has_russian else "Русское название пока не найдено",
                           "owned": sid in owned, "rarity": rarity, "type": typ, "date": date})
        return result

    @Property(str, notify=skinsChanged)
    def skinCharacter(self):
        return self._skin_character

    @Property("QVariantList", notify=communityChanged)
    def community(self):
        return [{"index": i, "title": tidy(x.get("title") or x.get("char") or "Без названия"),
                 "author": tidy(x.get("author", "")), "side": x.get("side", ""),
                 "character": tidy(x.get("char", "")), "date": x.get("date", "")}
                for i, x in enumerate(self._community) if isinstance(x, dict)]

    @Property("QVariantList", notify=settingsChanged)
    def coordinates(self):
        cfg = self.cfg["coords"]
        return [{"key": k, "title": tidy(label),
                 "x": str(cfg.get(k, {}).get("x", "")), "y": str(cfg.get(k, {}).get("y", "")),
                 "w": str(cfg.get(k, {}).get("w", "")), "h": str(cfg.get(k, {}).get("h", ""))}
                for k, label in core.COORD_FIELDS]

    @Property("QVariantList", notify=settingsChanged)
    def timings(self):
        return [{"key": k, "title": tidy(label), "value": str(self.cfg["timings"].get(k, val))}
                for k, (val, label) in core.TIMING_DEFAULTS.items()]

    @Property("QVariantMap", notify=settingsChanged)
    def preferences(self):
        p = self.cfg.get("publish", {})
        return {"nickname": p.get("nickname", ""), "backend": p.get("backend", "firebase"),
                "firebase": p.get("firebase_url", "")}

    @Property(int, notify=iconVersionChanged)
    def iconVersion(self):
        return self._icon_version

    @Slot(str, result=str)
    def iconPath(self, key):
        if not key or key in (core.EMPTY, core.NO_ADDONS):
            return ""
        known = self._icon_urls.get(key)
        if known:
            return known
        path = self._icons.local_path(key)
        if path and self._icons.is_cached(key):
            url = QUrl.fromLocalFile(path).toString()
            self._icon_urls[key] = url
            return url
        if key not in self._icon_pending and self._icon_queue.request(key):
            self._icon_pending.add(key)
        return ""

    def _icon_processed(self, key, success):
        # Executed on one of the three worker threads, never directly update Qt.
        self._messages.put(("icons", key, success))
        self._wake.emit()

    def _effects_updated(self):
        self._messages.put(("effects",))
        self._wake.emit()

    @Property("QVariantMap", notify=addonEffectChanged)
    def addonEffect(self):
        chosen = self._selected_addon
        return self._addon_catalog.get(
            chosen["side"], chosen["character"], chosen["category"], chosen["name"]
        )

    @Slot(str, str, str, str)
    def selectAddonEffect(self, side, character, category, name):
        if not name or name in (core.EMPTY, core.NO_ADDONS):
            return
        if side not in ("KILLER", "SURVIVOR"):
            return
        self._selected_addon = {"side": side, "character": character,
                                "category": category, "name": name}
        self.addonEffectChanged.emit()
        self._addon_catalog.refresh_async()

    @Slot()
    def openAddonSource(self):
        if self._selected_addon["name"]:
            QDesktopServices.openUrl(QUrl(self.addonEffect["source"]))

    @Slot(str)
    def setRole(self, role):
        if role not in ("killer", "survivor"):
            return
        self._role = role.upper() if role == "KILLER" else ("KILLER" if role == "killer" else "SURVIVOR")
        self._locks = [False] * 4
        self.roleChanged.emit()
        self.perksChanged.emit()
        self.rotationChanged.emit()
        self._save()

    @Slot(str)
    def setMode(self, value):
        if value not in ("mixed", "unique", "any", "general"):
            return
        self._mode = value
        self.modeChanged.emit()
        self._save()

    @Slot(str)
    def toggleOption(self, key):
        names = {"addons": "addons_enabled", "appearance": "skin_enabled",
                 "challenge": "challenge_enabled", "owned": "respect_owned",
                 "classes": "class_enabled", "dry": "dry_run", "ocr": "ocr_verify",
                 "select_char": "select_char"}
        opt = names.get(key)
        if opt:
            self.cfg["options"][opt] = not bool(self._option(opt))
            self.optionsChanged.emit()
            self._save()

    @Slot(str)
    def toggleAdvanced(self, name):
        options = {
            "clear": "use_clear_button", "verifyclipboard": "verify_clipboard",
            "restoreclipboard": "restore_clipboard",
            "hoververify": "hover_verify", "hoverretry": "hover_retry"
        }
        key = options.get(name)
        if key:
            self.cfg["options"][key] = not bool(self._option(key))
            self._save()
            self.advancedChanged.emit()

    @Slot(str, str)
    def setAdvanced(self, name, value):
        if name == "resultIndex":
            try:
                self.cfg["options"]["result_index"] = max(1,min(9,int(value)))
            except ValueError:
                self._notify("Номер иконки должен быть от 1 до 9.")
                return
        elif name == "challengeDiff":
            if value not in ("any", "easy", "medium", "hard"):
                return
            self.cfg["options"]["challenge_diff"] = value
        elif name == "abortKey":
            if not re.fullmatch(r"f(?:[1-9]|1[0-2])", value.lower()):
                self._notify("Выберите безопасную клавишу F1–F12.")
                return
            self.cfg["options"]["abort_key"] = value.lower()
            try:
                if self._hotkey_handle is not None:
                    import keyboard
                    keyboard.remove_hotkey(self._hotkey_handle)
                self._hotkey_handle = None
                self._hotkey()
            except Exception:
                pass
        else:
            return
        self._save()
        self.advancedChanged.emit()

    def available_characters(self, side):
        k = "K" if side == "KILLER" else "S"
        return sorted(self._owned[k])

    def challenge_diff_value(self):
        val = self._option("challenge_diff")
        return dict(core.CHALLENGE_DIFFS).get(val, "any")

    @Slot()
    def generate(self):
        self._generate()

    def _generate(self, preset_challenge=None):
        try:
            names = self.available_characters(self._role)
            if not names:
                raise ValueError("Отметьте хотя бы одного персонажа этой стороны.")
            ch = preset_challenge
            if ch is None and self._option("challenge_enabled"):
                hist = self.cfg.get("challenge_history", [])
                ch = core.pick_challenge(self._role, self.challenge_diff_value(), avoid=hist)
                if ch:
                    self.cfg["challenge_history"] = [ch["ru"]] + [x for x in hist if x != ch["ru"]][:11]
            fx = core.challenge_fx(ch, self._role, self.cfg) if ch else {}
            kw = dict(perk_mode=self._mode, respect_owned=bool(self._option("respect_owned")),
                      addons_enabled=bool(self._option("addons_enabled")),
                      skin_enabled=bool(self._option("skin_enabled")),
                      owned_skins=self.cfg.get("skins", {}), fx=fx)
            self.build_before_generation = self.build
            if self._rotation_enabled:
                self.build = make_rotated_build(core, self.db, self._role, names, self._rotation, **kw)
            else:
                func = core.make_killer_build if self._role == "KILLER" else core.make_survivor_build
                self.build = func(self.db, names, **kw)
            if ch:
                self.build["challenge"] = ch
            if self._option("class_enabled"):
                self.build["class"] = core.pick_class(self._role)
            self._locks, dropped_pins = reconcile_pins(
                self.db, self.build_before_generation, self._locks, self.build,
                respect_owned=bool(self._option("respect_owned")), empty=core.EMPTY)
            if self._rotation_enabled:
                self._rotation.record_build(self.build, core.EMPTY, core.NO_ADDONS)
                self.rotationChanged.emit()
            self._statistics.record_build(self.build, balanced=self._rotation_enabled,
                                          empty=core.EMPTY, no_addons=core.NO_ADDONS)
            self.statisticsChanged.emit()
            self._sync()
            self._history.insert(0, tidy(core.build_to_clipboard_text(self.build)).replace("\n", " | "))
            self._history = self._history[:12]
            self.historyChanged.emit()
            self._save()
            self._notify("Билд готов: " + self.build["char"] +
                         (". Несовместимых закреплений снято: " + str(dropped_pins)
                          if dropped_pins else ""))
        except Exception as e:
            self._notify("Генерация: " + str(e))

    def _sync(self):
        self.perksChanged.emit()
        self.detailChanged.emit()
        # Perk QML bindings update separately; avoid reloading every icon.
        self._build_revision += 1
        self.buildRevisionChanged.emit()

    @Slot(int)
    def toggleLock(self, index):
        if 0 <= index < 4 and self.perks[index]["filled"]:
            self._locks[index] = not self._locks[index]
            self.perksChanged.emit()

    @Slot(int)
    def reroll(self, index):
        if not self.build or not 0 <= index < 4 or self._locks[index]:
            return
        pool = core.all_unique_perks(self.db, self.build["side"])
        pool += self.db["killer_common_perks" if self.build["side"] == "KILLER" else "surv_common_perks"]
        existing = {p for i,p in enumerate(self.build["perks"]) if i != index}
        forbidden = set((self.build.get("fx") or {}).get("ban_perks") or ())
        allowed = [p for p in sorted(set(pool)) if p not in existing and p not in forbidden]
        challenge_mode = (self.build.get("fx") or {}).get("perk_pool")
        if challenge_mode == "common":
            allowed = [p for p in allowed if p in self.db["killer_common_perks" if self.build["side"] == "KILLER" else "surv_common_perks"]]
        elif challenge_mode == "own":
            source = self.db["killers"] if self.build["side"] == "KILLER" else self.db["survivors"]
            info = source.get(self.build["char"], [])
            own = info.get("perks", []) if isinstance(info, dict) else info
            allowed = [p for p in allowed if p in own]
        if self._option("respect_owned"):
            key = "killer_perks" if self.build["side"] == "KILLER" else "survivor_perks"
            whitelist = set(self.db.get("owned", {}).get(key) or [])
            if whitelist:
                allowed = [p for p in allowed if p in whitelist]
        if allowed:
            if self._rotation_enabled:
                former = self.build["perks"][index]
                if len(allowed) > 1 and former in allowed:
                    allowed = [p for p in allowed if p != former]
                chosen = self._rotation.select(self.build["side"], "perks", allowed)[0]
                self._rotation.record(self.build["side"], "perks", [chosen])
                self.rotationChanged.emit()
                self._save()
            else:
                chosen = random.choice(allowed)
            self.build["perks"][index] = chosen
            self._statistics.record_perk_reroll(self.build["side"], self.build["char"], chosen,
                                                balanced=self._rotation_enabled, empty=core.EMPTY)
            self.statisticsChanged.emit()
            self._save()
            self._sync()

    @Slot()
    def rerollPerks(self):
        if not self.build:
            return
        for i in range(4):
            if not self._locks[i]:
                self.reroll(i)

    @Slot()
    def rerollChallenge(self):
        if not self.build:
            return
        ch = core.reroll_challenge(self.build["side"], self.challenge_diff_value(),
                                   avoid={(self.build.get("challenge") or {}).get("ru", "")})
        if ch:
            self._generate(preset_challenge=ch)

    @Slot()
    def copyBuild(self):
        if not self.build:
            self._notify("Сначала создайте билд.")
            return
        QGuiApplication.clipboard().setText(core.build_to_clipboard_text(self.build))
        self._notify("Билд скопирован.")

    @Slot(str, str)
    def setCharacter(self, name, side):
        key = "K" if side in ("K", "KILLER") else "S"
        pool = self.db["killers" if key == "K" else "survivors"]
        if name not in pool:
            return
        selected = self._owned[key]
        if name in selected:
            selected.remove(name)
        else:
            selected.add(name)
        self.charactersChanged.emit()
        self._save()

    @Slot(str, str, str)
    def setCharactersBulk(self, side, action, search):
        """All, none, invert, scoped to the visible search for the selected side."""
        side = side.upper()
        if side not in ("K", "S") or action not in ("all", "none", "invert"):
            return
        pool = self.db["killers"] if side == "K" else self.db["survivors"]
        term = core._norm(search)
        matching = [name for name in pool if term in core._norm(name)]
        selected = self._owned[side]
        for name in matching:
            if action == "all":
                selected.add(name)
            elif action == "none":
                selected.discard(name)
            elif name in selected:
                selected.remove(name)
            else:
                selected.add(name)
        self._save()
        self.charactersChanged.emit()
        self._notify("Выбор сохранён: " + ("маньяки" if side == "K" else "выжившие") + ", " + str(len(selected)) + " из " + str(len(pool)))

    @Slot(str)
    def setSkinCharacter(self, name):
        if core.SKINS and name in core.SKINS.CHAR_SKINS:
            self._skin_character = name
            self.skinsChanged.emit()

    @Slot()
    def nextSkinCharacter(self):
        options = list(core.SKINS.CHAR_SKINS) if core.SKINS else []
        if options:
            self.setSkinCharacter(options[(options.index(self._skin_character) + 1) % len(options)]
                                  if self._skin_character in options else options[0])

    @Slot(str)
    def filterSkins(self, term):
        term = term.strip()
        if self._skin_filter != term:
            self._skin_filter = term
            self.skinsChanged.emit()

    @Slot(str)
    def setSkinNameFilter(self, value):
        if value not in ("all", "ru", "missing"):
            return
        if self._skin_name_filter != value:
            self._skin_name_filter = value
            self.skinsChanged.emit()

    @Slot(int)
    def toggleSkin(self, sid):
        if sid not in self._skin_ids():
            return
        owned = self._owned_skin_ids()
        if sid in owned:
            owned.remove(sid)
        else:
            owned.add(sid)
        self.cfg.setdefault("skins", {})[self._skin_character] = sorted(owned)
        self._save()
        self.skinsChanged.emit()

    @Slot(str)
    def setSkinsOwned(self, action):
        if action not in ("all", "none", "invert"):
            return
        ids = self._skin_ids()
        owned = self._owned_skin_ids()
        if action == "all":
            owned = set(ids)
        elif action == "none":
            owned.clear()
        else:
            owned = set(ids) - owned
        self.cfg.setdefault("skins", {})[self._skin_character] = sorted(owned)
        self._save()
        self.skinsChanged.emit()
        self._notify("Внешность: выбрано " + str(len(owned)) + " из " + str(len(ids)))

    @Slot(result=int)
    def randomSkinId(self):
        owned = self._owned_skin_ids()
        candidates = [sid for sid in self._skin_ids() if sid in owned]
        if not candidates:
            self._notify("Нет выбранных наборов для этого персонажа.")
            return -1
        return int(random.choice(candidates))

    @Slot()
    def rollClasses(self):
        self._classes = {side: core.pick_class(side) for side in ("SURVIVOR", "KILLER")}
        self.detailChanged.emit()
        self._notify("Классы 2v8 обновлены.")

    @Property("QVariantList", notify=detailChanged)
    def classDetails(self):
        return [{"side": s, "title": tidy((v or {}).get("ru", "—")),
                 "skills": tidy("; ".join(x.get("text", "") for x in (v or {}).get("skills", [])))}
                for s,v in self._classes.items()]

    @Slot()
    def copyClass(self):
        QGuiApplication.clipboard().setText(core.classes_to_text(list(self._classes.items())))
        self._notify("Классы скопированы.")

    @Slot(str, str, result="QVariantList")
    def searchCharacters(self, side, query):
        """Return real characters for the custom build picker; empty query is limited."""
        pool = self.db["killers"] if side == "KILLER" else self.db["survivors"]
        needle = core._norm(query)
        names = [name for name in sorted(pool) if not needle or needle in core._norm(name)]
        return [{"name": name} for name in names[:75]]

    @Slot(str, str, result="QVariantList")
    @Slot(str, str, str, str, result="QVariantList")
    def searchPerks(self, side, query, category="all", character=""):
        """Search actual role perks with verified ownership and category filters."""
        if side not in ("KILLER", "SURVIVOR"):
            return []
        common = set(self.db["killer_common_perks" if side == "KILLER" else "surv_common_perks"])
        chars = self.db["killers" if side == "KILLER" else "survivors"]
        names = set(core.all_unique_perks(self.db, side)) | common
        if category == "common":
            names &= common
        elif category == "unique":
            names -= common
        elif category == "character":
            spec = chars.get(character)
            if spec is None:
                return []
            names &= set(spec.get("perks", []) if isinstance(spec, dict) else spec)
        elif category != "all":
            return []
        owners = {}
        for hero, spec in chars.items():
            for name in (spec.get("perks", []) if isinstance(spec, dict) else spec):
                owners.setdefault(name, []).append(hero)
        needle = core._norm(query or "")
        filtered = [name for name in sorted(names)
                    if not needle or needle in core._norm(name)
                    or needle in core._norm(" ".join(owners.get(name, [])))]
        return [{
            "name": name,
            "owner": ", ".join(owners.get(name, [])),
            "kind": "Общий навык" if name in common else "Уникальный навык",
            "common": name in common,
        } for name in filtered[:90 if needle else 48]]

    @Slot(str, result="QVariantList")
    def searchItems(self, query):
        """Search actual survivor items, preserving their generator category."""
        needle = core._norm(query)
        matches = [
            {"name": name, "category": category}
            for category, data in sorted(self.db["survivor_items"].items())
            for name in data.get("items", [])
            if not needle or needle in core._norm(name)
        ]
        return matches[:80 if needle else 25]

    @Slot(str, str, str, str, result="QVariantList")
    def searchAddons(self, side, character, item, query):
        """Use the same addon pools as the existing generator, not made-up suggestions."""
        if side == "KILLER":
            addons = list(self.db["killers"].get(character, {}).get("addons", []))
        elif side == "SURVIVOR":
            categories = self.db["survivor_items"]
            eligible = [v for v in categories.values()
                        if item and item in v.get("items", [])]
            addons = [a for category in eligible for a in category.get("addons", [])]
        else:
            return []
        needle = core._norm(query)
        names = [name for name in sorted(set(core._playable_addons(addons)))
                 if not needle or needle in core._norm(name)]
        return [{"name": name} for name in names[:75 if needle else 30]]

    @Slot(str, str, str, str, str, str, str, str, str, result=bool)
    def buildCustom(self, side, char, item, a1, a2, p1, p2, p3, p4):
        chars = self.db["killers"] if side == "KILLER" else self.db["survivors"]
        if char not in chars:
            self._notify("Выберите существующего персонажа (точное имя).")
            return False
        perks = [x.strip() for x in (p1,p2,p3,p4)]
        pool = set(core.all_unique_perks(self.db, side))
        pool.update(self.db["killer_common_perks" if side == "KILLER" else "surv_common_perks"])
        if len(set(perks)) != 4 or any(x not in pool for x in perks):
            self._notify("Нужно четыре разных настоящих навыка из базы.")
            return False
        item = item.strip()
        selected_addons = [x.strip() or core.EMPTY for x in (a1, a2)]
        if side == "KILLER":
            valid_addons = set(core._playable_addons(chars[char].get("addons", [])))
            power = chars[char].get("power", core.EMPTY)
            category = ""
        else:
            matches = [
                (cat, spec) for cat, spec in self.db["survivor_items"].items()
                if item in spec.get("items", [])
            ] if item else []
            if item and not matches:
                self._notify("Выберите настоящий предмет выжившего из каталога.")
                return False
            if not item and any(a != core.EMPTY for a in selected_addons):
                self._notify("Для аддонов выжившего сначала выберите предмет.")
                return False
            category = matches[0][0] if matches else ""
            power = item or core.EMPTY
            valid_addons = set(core._playable_addons(matches[0][1].get("addons", []))) if matches else set()
        chosen = [a for a in selected_addons if a != core.EMPTY]
        if len(set(chosen)) != len(chosen) or any(a not in valid_addons for a in chosen):
            self._notify("Аддоны должны быть разными и совместимыми с выбранной силой/предметом.")
            return False
        self.build = {"side": side, "char": char,
                      "power_or_item": power,
                      "category": category,
                      "power_is_item": side=="SURVIVOR",
                      "addons": selected_addons,
                      "perks": perks, "forbidden": {}, "skin": None}
        self._role = side
        self._locks = [False]*4
        self._sync()
        self.roleChanged.emit()
        self._notify("Пользовательский билд готов.")
        return True

    @Slot()
    def refreshCommunity(self):
        def load():
            try:
                build_list, _online = core.GH.load_community_builds(core.APP_DIR)
                firebase = core.GH.load_firebase_builds(base=self.cfg["publish"].get("firebase_url")
                                                         or core.GH.FIREBASE_BASE_DEFAULT)
                if isinstance(firebase, list):
                    build_list = list(firebase) + list(build_list or [])
                self._messages.put(("community", list(build_list or [])))
                self._wake.emit()
                self._notify("Билды сообщества загружены.")
            except Exception as e:
                self._notify("Ошибка загрузки сообщества: " + str(e))
        threading.Thread(target=load, daemon=True).start()

    @Slot(int)
    def useCommunity(self, index):
        if not 0 <= index < len(self._community):
            return
        item = self._community[index]
        perks = list(item.get("perks") or [])
        side = item.get("side")
        if side not in ("SURVIVOR","KILLER") or len(perks)!=4:
            self._notify("Невозможно загрузить неполный билд.")
            return
        self.build = {
            "side": side, "char": item.get("char",""), "perks":perks,
            "addons": (list(item.get("addons") or []) + [core.EMPTY]*2)[:2],
            "power_or_item":item.get("power_or_item",core.EMPTY),
            "power_is_item":side=="SURVIVOR", "skin":None,"forbidden":{}
        }
        self._role = side
        self._locks = [False]*4
        self.roleChanged.emit()
        self._sync()
        self._notify("Билд сообщества загружен.")

    @Slot(int)
    def copyCommunity(self, index):
        if 0 <= index < len(self._community):
            QGuiApplication.clipboard().setText(core.GH.format_build_text(self._community[index]))
            self._notify("Билд сообщества скопирован.")

    @Slot(str, str)
    def setPublishPref(self, key, value):
        if key in ("nickname", "firebase_url") and len(value) <= 300:
            self.cfg.setdefault("publish", {})[key] = value
            self._save()
            self.settingsChanged.emit()

    @Slot()
    def publishCurrent(self):
        if not self.build:
            self._notify("Сначала сгенерируйте билд.")
            return
        if any(x in (core.EMPTY, "") for x in self.build["perks"]):
            self._notify("Невозможно опубликовать неполный билд.")
            return
        info=self.cfg.get("publish", {})
        nick=(info.get("nickname") or "").strip()
        if not nick:
            self._notify("Укажите ник в настройках публикации.")
            return
        b=self.build
        skin=b.get("skin") or {}
        skin_name=skin.get("display","") if isinstance(skin,dict) else str(skin)
        payload=core.GH.make_build_payload(
            b["side"],b["char"],b.get("power_or_item",""),
            b.get("addons",[]),b["perks"],nick,skin=skin_name)
        def upload():
            try:
                # Preferred anonymous Firebase publish avoids sharing GitHub tokens.
                url=info.get("firebase_url") or core.GH.FIREBASE_BASE_DEFAULT
                ok,msg=core.GH.publish_build_firebase(payload,base=url)
                if ok:
                    self._messages.put(("community",[payload]+self._community))
                    self._wake.emit()
                self._notify(msg)
            except Exception as e:
                self._notify("Публикация: "+str(e))
        threading.Thread(target=upload,daemon=True).start()

    @Slot(str, str, str)
    def editCoord(self, key, axis, value):
        if key not in self.cfg["coords"] or axis not in ("x","y","w","h"):
            return
        self.cfg["coords"][key][axis] = value.strip()[:10]

    @Slot(str,str)
    def editTiming(self, key, value):
        if key in core.TIMING_DEFAULTS:
            try:
                number=float(value.replace(",","."))
                self.cfg["timings"][key] = max(0,int(number)) if key=="retries" else max(0.0,number)
            except ValueError:
                self._notify("Некорректный тайминг: "+key)

    @Slot()
    def saveSettings(self):
        self._save()
        self.settingsChanged.emit()
        self._notify("Настройки сохранены.")

    @Slot(str)
    def captureCoord(self, key):
        if key not in self.cfg["coords"]:
            return
        controller=self
        class Overlay(QWidget):
            def __init__(self):
                super().__init__(None,Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint|Qt.Tool)
                self.setAttribute(Qt.WA_TranslucentBackground)
                self.setCursor(Qt.CrossCursor)
                self.setFocusPolicy(Qt.StrongFocus)
            def paintEvent(self,_):
                p=QPainter(self)
                p.fillRect(self.rect(),QColor(12,18,27,60))
                p.setPen(QColor(240,89,83))
                p.drawText(20,40,"Щёлкните по нужному месту · Esc — отмена")
            def mousePressEvent(self,_):
                pos=QCursor.pos()
                try:
                    x,y=core.INPUT.position()
                except Exception:
                    x,y=pos.x(),pos.y()
                controller.editCoord(key,"x",str(x))
                controller.editCoord(key,"y",str(y))
                controller.saveSettings()
                self.close()
            def keyPressEvent(self,event):
                if event.key()==Qt.Key_Escape:
                    self.close()
        self._overlay=Overlay()
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        self._overlay.setGeometry(screen.geometry())
        self._overlay.show()
        self._overlay.activateWindow()

    @Slot()
    def dataCheck(self):
        def check():
            problems,warnings=core.validate_db(self.db)
            self._notify("База: ошибок "+str(len(problems))+", предупреждений "+str(len(warnings)))
        threading.Thread(target=check,daemon=True).start()

    @Slot()
    def copyLog(self):
        QGuiApplication.clipboard().setText(self.logText)
        self._notify("Журнал скопирован.")

    @Slot()
    def clearLog(self):
        self._log=[]
        self.statusChanged.emit()

    def _hotkey(self):
        if sys.platform != "win32":
            return
        try:
            import keyboard
            key=str(self._option("abort_key") or "f9").lower()
            self._hotkey_handle=keyboard.add_hotkey(key,self.stop)
        except Exception as e:
            self._notify("Горячая клавиша недоступна: "+str(e))

    def _coord(self,key):
        value=self.cfg["coords"].get(key,{})
        try:
            return int(value["x"]),int(value["y"])
        except (KeyError,ValueError,TypeError):
            return None

    def _outside_desktop(self, keys, extra=()):
        """Report impossible physical coordinates, supporting multi-monitor layouts."""
        if sys.platform != "win32":
            return []
        try:
            api = core.ctypes.windll.user32
            left, top = int(api.GetSystemMetrics(76)), int(api.GetSystemMetrics(77))
            width, height = int(api.GetSystemMetrics(78)), int(api.GetSystemMetrics(79))
            if width <= 0 or height <= 0:
                return []
            invalid = []
            points = [(key, self._coord(key)) for key in dict.fromkeys(keys)]
            points.extend(extra)
            for key, point in points:
                if point is not None and not (
                    left <= point[0] < left + width and top <= point[1] < top + height
                ):
                    invalid.append(key)
            return invalid
        except Exception:
            return []

    def _ocr_region(self):
        val=self.cfg["coords"].get("ocr_region",{})
        try:
            x,y,w,h=(int(val[a]) for a in ("x","y","w","h"))
            return (x,y,w,h) if w>0 and h>0 else None
        except (KeyError,ValueError,TypeError):
            return None

    def _timing(self,k):
        val=self.cfg["timings"].get(k,core.TIMING_DEFAULTS[k][0])
        try:
            return max(0,float(val))
        except (ValueError,TypeError):
            return core.TIMING_DEFAULTS[k][0]

    def _sleep(self,seconds):
        # A zero-second pause is still a cancellation checkpoint.
        if self._stop.is_set():
            raise core.AbortError()
        end=time.monotonic()+max(0.0,seconds)
        while time.monotonic()<end:
            if self._stop.is_set():
                raise core.AbortError()
            time.sleep(min(0.04,max(0.0,end-time.monotonic())))
        if self._stop.is_set():
            raise core.AbortError()

    def _capture_target_window(self):
        """Lock onto the window manually focused after the countdown."""
        if self._option("dry_run"):
            return
        hwnd = core.INPUT.foreground_window()
        if not hwnd or core.INPUT.is_own_window(hwnd):
            raise RuntimeError(
                "Переключитесь в окно DBD во время отсчёта. "
                "Игровое окно не выбрано; клики не выполнялись."
            )
        self._target_window = hwnd
        self._notify("Выбрано активное окно вручную; поиск процесса DBD отключён.")

    def _assert_input_ready(self):
        if self._stop.is_set():
            raise core.AbortError()
        if self._option("dry_run"):
            return
        if not self._target_window or core.INPUT.foreground_window() != self._target_window:
            raise RuntimeError(
                "Активное окно изменилось — автоэкипировка остановлена, "
                "чтобы не нажимать в другом приложении."
            )

    def _click(self,coord,label):
        self._assert_input_ready()
        if self._option("dry_run"):
            self._notify("DRY: клик "+label+" "+str(coord))
            return True
        params=dict(guard=self._assert_input_ready,hold=self._timing("hold"),steps=int(self._timing("move_steps")),
                    step_delay=self._timing("move_step_delay"),settle=self._timing("hover_settle"),
                    wiggle=int(self._timing("wiggle")),verify=bool(self._option("hover_verify")))
        if core.INPUT.click(coord[0],coord[1],**params):
            return True
        if self._option("hover_retry"):
            self._assert_input_ready()
            params["steps"]=max(params["steps"],12)
            params["settle"]=max(params["settle"],0.25)
            return core.INPUT.click(coord[0],coord[1],**params)
        return False

    def _paste(self,text):
        self._assert_input_ready()
        if self._option("dry_run"):
            self._notify("DRY: ввод "+text)
            return True
        return core.INPUT.paste(text,verify=self._option("verify_clipboard"),
                                restore=self._option("restore_clipboard"),
                                guard=self._assert_input_ready)

    def _result_target(self):
        """Physical position of the selected search result icon."""
        first = self._coord("first_result")
        if first is None:
            return None
        index = max(1, min(9, int(self._option("result_index") or 1)))
        step = int(self._timing("result_step"))
        return first[0] + (index - 1) * step, first[1]

    def _search_and_select(self,target):
        search=self._coord("search")
        result=self._result_target()
        if not search or not result:
            raise ValueError("Координаты поиска не заданы.")
        dest=result
        verify_ocr = bool(self._option("ocr_verify")) and not self._option("dry_run")
        region = self._ocr_region() if verify_ocr else None
        if verify_ocr and region is None:
            raise ValueError("Включена OCR-проверка, но область OCR не настроена.")
        for attempt in range(1+int(self._timing("retries"))):
            self._sleep(0)
            if not self._click(search,"search"):
                continue
            self._sleep(0.12)
            if self._option("use_clear_button"):
                clear=self._coord("clear")
                if clear:
                    if not self._click(clear,"clear"):
                        continue
                    self._sleep(0.08)
                    if not self._click(search,"search"):
                        continue
                    self._sleep(0.08)
            if not self._option("dry_run"):
                self._assert_input_ready()
                core.INPUT.hotkey("ctrl","a",guard=self._assert_input_ready)
                self._sleep(0.03)
            if not self._paste(target):
                continue
            self._sleep(self._timing("search_settle")*(1.6 if attempt else 1.0))
            if verify_ocr:
                self._assert_input_ready()
                ocr=core.ocr_read(*region)
                self._sleep(0)  # F9 may have been pressed during slow OCR
                if not ocr:
                    self._notify("OCR: текст не распознан для "+target)
                    continue
                if core._norm(target) not in core._norm(ocr):
                    self._notify("OCR: результат не совпал для "+target)
                    continue
            if not self._click(dest,"result"):
                continue
            self._sleep(0.15)
            return True
        return False

    def _equip_steps(self):
        b=self.build
        if not b:
            raise ValueError("Сначала сгенерируйте билд.")
        steps=[]
        if self._option("select_char"):
            steps.append(("char_search",b["char"],"персонаж"))
        forbid=b.get("forbidden") or {}
        if b["side"]=="SURVIVOR" and b.get("power_is_item") and not forbid.get("item") and b.get("power_or_item") not in (core.EMPTY,None):
            steps.append(("item_slot",b["power_or_item"],"предмет"))
        prev=self.cfg.get("last_equipped",{}).get(b["side"]) or {}
        def plan(names,n,tracked,prefix,label):
            current=list(tracked or [])[:n]+[None]*n
            current=current[:n]
            for i,name in enumerate(names[:n],1):
                if name in (core.EMPTY,core.NO_ADDONS,"",None):
                    continue
                previous=current.index(name)+1 if name in current else 0
                if previous==i:
                    continue
                if previous:
                    steps.append((prefix(previous),name,"снять "+label))
                    current[previous-1]=None
                steps.append((prefix(i),name,label+" "+str(i)))
                current[i-1]=name
            return current
        addons=[None,None] if forbid.get("addons") else plan(b.get("addons",[]),2,prev.get("addons"),lambda i:"addon"+str(i)+"_slot","аддон")
        perks=[None]*4 if forbid.get("perks") else plan(b.get("perks",[]),4,prev.get("perks"),lambda i:"slot"+str(i),"навык")
        self._planned_equipped={"perks":perks,"addons":addons,"char":b.get("char")}
        return steps

    @Slot()
    def equip(self):
        # The Qt event loop may not process queued 'running' signals until
        # after another button click. Reserve the slot synchronously.
        if self._running or (self._worker is not None and self._worker.is_alive()):
            self._notify("Экипировка уже идёт.")
            return
        try:
            steps=self._equip_steps()
            if not steps:
                self._notify("Экипировка не требуется: нет действий для отправки.")
                return
            needed=["search","first_result"]+[x[0] for x in steps]
            missing=[x for x in needed if not self._coord(x)]
            if missing:
                self._notify("Не заданы координаты: "+", ".join(dict.fromkeys(missing)))
                return
            if not self._option("dry_run") and not core.INPUT.available:
                self._notify("Ввод недоступен: "+core.INPUT.reason)
                return
            if not self._option("dry_run"):
                outside = self._outside_desktop(needed, extra=[("result_index", self._result_target())])
                if outside:
                    self._notify("Координаты вне границ экрана: " + ", ".join(outside) +
                                 ". Проверьте разрешение и настройте позиции заново.")
                    return
                if self._option("ocr_verify") and self._ocr_region() is None:
                    self._notify("OCR включён, но область распознавания не задана.")
                    return
            self._equip_side = self.build["side"]
            self._stop.clear()
            self._running = True
            self.runningChanged.emit()
            self._worker=threading.Thread(target=self._automate,args=(steps,),daemon=True)
            self._worker.start()
        except Exception as e:
            self._running = False
            self.runningChanged.emit()
            self._notify("Подготовка экипировки: "+str(e))

    def _automate(self,steps):
        # Preserve the initiating build side if the UI changes during countdown.
        side = self._equip_side or (self.build or {}).get("side")
        try:
            self._target_window = None
            dry_run = bool(self._option("dry_run"))
            countdown = int(self._timing("countdown"))
            if not dry_run:
                countdown = max(3, countdown)  # time to Alt-Tab into DBD
            for i in range(countdown,0,-1):
                self._notify(
                    "Переключитесь в DBD вручную! Старт через "
                    +str(i)+" сек. Стоп: "
                    +str(self._option("abort_key") or "F9").upper()
                )
                self._sleep(1)
            self._capture_target_window()
            self._assert_input_ready()
            for i,(key,name,label) in enumerate(steps,1):
                self._sleep(0)
                self._notify("Экипировка "+str(i)+"/"+str(len(steps))+": "+label+" / "+name)
                ok=False
                for attempt in range(2):
                    if not self._click(self._coord(key),key):
                        continue
                    self._sleep(self._timing("after_slot_click"))
                    if self._search_and_select(name):
                        ok=True
                        break
                if not ok:
                    raise RuntimeError("Не удалось выбрать: "+name)
                self._sleep(self._timing("between_steps"))
            if not self._option("dry_run"):
                # A successful click only proves that input was sent, NOT that the
                # game equipped the item. Never cache an unverified screen state.
                self.cfg.setdefault("last_equipped",{})[side]=None
                self._save()
            self._notify("Команды отправлены. Подтвердите результат в игре; состояние не сохранено как проверенное.")
        except core.AbortError:
            self._notify("Автоматизация остановлена.")
            if not self._option("dry_run"):
                self.cfg.setdefault("last_equipped",{})[side]=None
                self._save()
        except Exception as e:
            self._notify("Ошибка экипировки: "+str(e))
            if not self._option("dry_run") and self.build:
                self.cfg.setdefault("last_equipped",{})[side]=None
                self._save()
        finally:
            self._target_window = None
            self._equip_side = None
            self._messages.put(("running",False))
            self._wake.emit()

    @Slot()
    def stop(self):
        self._stop.set()
        self._notify("Запрошена остановка.")

    @Slot(str)
    def placeholder(self,action):
        if action=="STOP":
            self.stop()
        elif action=="Автоэкипировка":
            self.equip()
        else:
            self._notify("Действие пока недоступно: "+action)

    @Property(str, constant=True)
    def installedVersion(self):
        return qt_updater.CURRENT_TAG

    @Property(str, notify=updateChanged)
    def updateText(self):
        return self._update_text

    @Property(bool, notify=updateChanged)
    def updateAvailable(self):
        return self._update_info is not None

    @Property(bool, notify=updateChanged)
    def updateBusy(self):
        return self._update_busy

    @Slot()
    def checkUpdate(self):
        if self._update_busy:
            return
        self._update_busy = True
        self.updateChanged.emit()
        self._notify("Проверяю релизы Qt на GitHub…")
        def work():
            try:
                info = qt_updater.check()
                msg = ("Найдено обновление " + info["tag"]) if info else (
                    "Установлена актуальная версия " + qt_updater.CURRENT_TAG)
                self._messages.put(("update", info, msg))
                self._wake.emit()
            except Exception as e:
                self._messages.put(("update", None, "Проверка не удалась: " + str(e)))
                self._wake.emit()
        threading.Thread(target=work, daemon=True).start()

    @Slot()
    def installUpdate(self):
        if not self._update_info or self._update_busy:
            return
        info = dict(self._update_info)
        if not getattr(sys, "frozen", False):
            QDesktopServices.openUrl(QUrl(info["url"]))
            return
        self._update_busy = True
        self.updateChanged.emit()
        self._notify("Скачиваю обновление; текущая версия продолжает работать.")
        def work():
            try:
                def progress(message):
                    self._messages.put(("update_progress", message))
                    self._wake.emit()
                staged = qt_updater.stage(
                    info, os.path.dirname(sys.executable), progress=progress
                )
                self._messages.put(("install", staged))
                self._wake.emit()
            except Exception as e:
                self._messages.put(("update", info, "Не удалось скачать: " + str(e)))
                self._wake.emit()
        threading.Thread(target=work, daemon=True).start()

    @Slot()
    def returnToLegacy(self):
        self._notify("В этой Qt-версии нет скрытого окна Tkinter. Используйте настройки Qt.")

    @Slot()
    def close(self):
        self._icon_queue.close()
        self.stop()
        if self._worker:
            self._worker.join(timeout=1.0)
        try:
            if self._hotkey_handle is not None:
                import keyboard
                keyboard.remove_hotkey(self._hotkey_handle)
        except Exception:
            pass
        self._tick.stop()
        self._icon_refresh.stop()
        self._save()
