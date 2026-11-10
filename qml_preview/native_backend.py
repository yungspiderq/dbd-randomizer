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
from dbd_icons_store import IconStore


def tidy(s):
    return re.sub(r"[\U0001F000-\U0001FFFF\u2600-\u27BF]", "", str(s or "")).strip()


class QtBridge(QObject):
    perksChanged = Signal()
    roleChanged = Signal()
    modeChanged = Signal()
    statusChanged = Signal()
    optionsChanged = Signal()
    advancedChanged = Signal()
    historyChanged = Signal()
    detailChanged = Signal()
    charactersChanged = Signal()
    skinsChanged = Signal()
    settingsChanged = Signal()
    communityChanged = Signal()
    iconVersionChanged = Signal()
    runningChanged = Signal()
    updateChanged = Signal()
    _wake = Signal()

    def __init__(self):
        super().__init__()
        self.cfg, migrated = core.load_config()
        self.db = core.load_db()
        self.build = None
        self._role = self.cfg["options"].get("side", "SURVIVOR")
        if self._role not in ("SURVIVOR", "KILLER"):
            self._role = "SURVIVOR"
        self._mode = self.cfg["options"].get("perk_mode", "mixed")
        self._locks = [False] * 4
        self._history = []
        self._status = "Загружены игровые данные v" + core.APP_VERSION
        self._log = []
        self._messages = queue.SimpleQueue()
        self._icon_version = 0
        self._icons = IconStore(core.ICONS_DIR, enabled=True)
        self._icon_pending = set()
        self._skin_character = next(iter(self.db["survivors"]), "")
        self._skin_filter = ""
        self._classes = {}
        self._community = []
        self._challenge = None
        self._running = False
        self._worker = None
        self._stop = threading.Event()
        self._hotkey_handle = None
        self._planned_equipped = None
        self._update_info = None
        self._update_text = ""
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
        for _ in range(80):
            try:
                item = self._messages.get_nowait()
            except queue.Empty:
                break
            kind = item[0]
            if kind == "status":
                self._status = item[1]
                self.statusChanged.emit()
                if item[2]:
                    self._log.append(time.strftime("%H:%M:%S") + "  " + item[1])
                    self._log = self._log[-250:]
                    self.statusChanged.emit()
            elif kind == "running":
                self._running = item[1]
                self.runningChanged.emit()
            elif kind == "community":
                self._community = item[1]
                self.communityChanged.emit()
            elif kind == "icons":
                self._icon_pending.discard(item[1])
                needs_icons = True
            elif kind == "update":
                self._update_info = item[1]
                self._update_text = item[2]
                self._update_busy = False
                self.updateChanged.emit()
            elif kind == "install":
                try:
                    qt_updater.install_staged(item[1])
                    self._notify("Обновление проверено. Завершаю приложение для установки.")
                    QGuiApplication.instance().quit()
                except Exception as e:
                    self._notify("Не удалось запустить установку: " + str(e))
                    self._update_busy = False
                    self.updateChanged.emit()
        if needs_icons:
            self._icon_version += 1
            self.iconVersionChanged.emit()

    def _save(self):
        self.cfg.setdefault("options", {})["side"] = self._role
        self.cfg["options"]["perk_mode"] = self._mode
        self.cfg.setdefault("owned", {})["killers"] = sorted(self._owned["K"]) or ["__none__"]
        self.cfg["owned"]["survivors"] = sorted(self._owned["S"]) or ["__none__"]
        core.save_config(self.cfg)

    def _option(self, key):
        return self.cfg["options"].get(key, core.OPTION_DEFAULTS.get(key))

    @Property(str, notify=roleChanged)
    def role(self):
        return "killer" if self._role == "KILLER" else "survivor"

    @Property(str, notify=modeChanged)
    def mode(self):
        return self._mode

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
            "focusgame": bool(self._option("focus_game")),
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
        return [{"name": name, "side": "K" if name in self.db["killers"] else "S",
                 "count": len(ids)}
                for name, ids in sorted(core.SKINS.CHAR_SKINS.items())
                if name in self.db["killers"] or name in self.db["survivors"]]

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
        return {"total": len(ids), "owned": sum(sid in owned for sid in ids)}

    @Property("QVariantList", notify=skinsChanged)
    def skins(self):
        if not core.SKINS:
            return []
        result = []
        owned = self._owned_skin_ids()
        for sid in self._skin_ids():
            info = core.SKINS.SKINS_BY_ID.get(sid) or {}
            name = tidy(info.get("name_ru") or info.get("name") or sid)
            english = tidy(info.get("name", ""))
            rarity = tidy(info.get("rarity_ru") or core.SKINS.RARITY_RU.get(info.get("rarity"), ""))
            typ = "Скин персонажа" if info.get("kind") == "coschar" else "Набор одежды"
            date = str(info.get("date") or "")
            search = core._norm(" ".join((str(sid), name, english, rarity, typ, date, self._skin_character)))
            if self._skin_filter and core._norm(self._skin_filter) not in search:
                continue
            result.append({"id": int(sid), "name": name, "english": english,
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
        path = self._icons.local_path(key)
        if path and self._icons.is_cached(key):
            return QUrl.fromLocalFile(path).toString()
        if key not in self._icon_pending and self._icons.enabled:
            self._icon_pending.add(key)
            self._icons.request([key], on_ready=lambda _: self._icon_downloaded(key))
        return ""

    def _icon_downloaded(self, key):
        self._messages.put(("icons", key))
        self._wake.emit()

    @Slot(str)
    def setRole(self, role):
        if role not in ("killer", "survivor"):
            return
        self._role = role.upper() if role == "KILLER" else ("KILLER" if role == "killer" else "SURVIVOR")
        self._locks = [False] * 4
        self.roleChanged.emit()
        self.perksChanged.emit()
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
            "restoreclipboard": "restore_clipboard", "focusgame": "focus_game",
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
            func = core.make_killer_build if self._role == "KILLER" else core.make_survivor_build
            self.build = func(self.db, names, **kw)
            if ch:
                self.build["challenge"] = ch
            if self._option("class_enabled"):
                self.build["class"] = core.pick_class(self._role)
            self._locks = [False] * 4
            self._sync()
            self._history.insert(0, tidy(core.build_to_clipboard_text(self.build)).replace("\n", " | "))
            self._history = self._history[:12]
            self.historyChanged.emit()
            self._save()
            self._notify("Билд готов: " + self.build["char"])
        except Exception as e:
            self._notify("Генерация: " + str(e))

    def _sync(self):
        self.perksChanged.emit()
        self.detailChanged.emit()
        self.iconVersionChanged.emit()

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
        allowed = [p for p in set(pool) if p not in existing]
        if self._option("respect_owned"):
            key = "killer_perks" if self.build["side"] == "KILLER" else "survivor_perks"
            whitelist = set(self.db.get("owned", {}).get(key) or [])
            if whitelist:
                allowed = [p for p in allowed if p in whitelist]
        if allowed:
            self.build["perks"][index] = random.choice(allowed)
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
        self._skin_filter = term.strip()
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
    def searchPerks(self, side, query):
        """Search all usable perks for the chosen role (including common perks)."""
        if side not in ("KILLER", "SURVIVOR"):
            return []
        source = core.all_unique_perks(self.db, side)
        source += list(self.db["killer_common_perks" if side == "KILLER" else "surv_common_perks"])
        needle = core._norm(query)
        names = sorted(set(source))
        selected = [name for name in names if needle in core._norm(name)]
        return [{"name": name} for name in selected[:90 if needle else 32]]

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

    @Slot(str, str, str, str, str, str, str, str, str)
    def buildCustom(self, side, char, item, a1, a2, p1, p2, p3, p4):
        chars = self.db["killers"] if side == "KILLER" else self.db["survivors"]
        if char not in chars:
            self._notify("Выберите существующего персонажа (точное имя).")
            return
        perks = [x.strip() for x in (p1,p2,p3,p4)]
        pool = set(core.all_unique_perks(self.db, side))
        pool.update(self.db["killer_common_perks" if side == "KILLER" else "surv_common_perks"])
        if len(set(perks)) != 4 or any(x not in pool for x in perks):
            self._notify("Нужно четыре разных настоящих навыка из базы.")
            return
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
                return
            if not item and any(a != core.EMPTY for a in selected_addons):
                self._notify("Для аддонов выжившего сначала выберите предмет.")
                return
            category = matches[0][0] if matches else ""
            power = item or core.EMPTY
            valid_addons = set(core._playable_addons(matches[0][1].get("addons", []))) if matches else set()
        chosen = [a for a in selected_addons if a != core.EMPTY]
        if len(set(chosen)) != len(chosen) or any(a not in valid_addons for a in chosen):
            self._notify("Аддоны должны быть разными и совместимыми с выбранной силой/предметом.")
            return
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
                controller.editCoord(key,"x",str(pos.x()))
                controller.editCoord(key,"y",str(pos.y()))
                controller.saveSettings()
                self.close()
            def keyPressEvent(self,event):
                if event.key()==Qt.Key_Escape:
                    self.close()
        self._overlay=Overlay()
        self._overlay.setGeometry(QGuiApplication.primaryScreen().geometry())
        self._overlay.showFullScreen()
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
        end=time.monotonic()+max(0.0,seconds)
        while time.monotonic()<end:
            if self._stop.is_set():
                raise core.AbortError()
            time.sleep(min(0.04,max(0.0,end-time.monotonic())))

    def _click(self,coord,label):
        if self._option("dry_run"):
            self._notify("DRY: клик "+label+" "+str(coord))
            return True
        params=dict(hold=self._timing("hold"),steps=int(self._timing("move_steps")),
                    step_delay=self._timing("move_step_delay"),settle=self._timing("hover_settle"),
                    wiggle=int(self._timing("wiggle")),verify=bool(self._option("hover_verify")))
        if core.INPUT.click(coord[0],coord[1],**params):
            return True
        if self._option("hover_retry"):
            params["steps"]=max(params["steps"],12)
            params["settle"]=max(params["settle"],0.25)
            return core.INPUT.click(coord[0],coord[1],**params)
        return False

    def _paste(self,text):
        if self._option("dry_run"):
            self._notify("DRY: ввод "+text)
            return True
        return core.INPUT.paste(text,verify=self._option("verify_clipboard"),
                                restore=self._option("restore_clipboard"))

    def _search_and_select(self,target):
        search=self._coord("search")
        result=self._coord("first_result")
        if not search or not result:
            raise ValueError("Координаты поиска не заданы.")
        idx=max(1,min(9,int(self._option("result_index") or 1)))
        step=int(self._timing("result_step"))
        dest=(result[0]+(idx-1)*step,result[1])
        for attempt in range(1+int(self._timing("retries"))):
            self._sleep(0)
            self._click(search,"search")
            self._sleep(0.12)
            if self._option("use_clear_button"):
                clear=self._coord("clear")
                if clear:
                    self._click(clear,"clear")
                    self._sleep(0.08)
                    self._click(search,"search")
                    self._sleep(0.08)
            if not self._option("dry_run"):
                core.INPUT.hotkey("ctrl","a")
                self._sleep(0.03)
            self._paste(target)
            self._sleep(self._timing("search_settle")*(1.6 if attempt else 1.0))
            region=self._ocr_region()
            if self._option("ocr_verify") and region and not self._option("dry_run"):
                ocr=core.ocr_read(*region)
                if ocr and core._norm(target) not in core._norm(ocr):
                    self._notify("OCR: результат не совпал для "+target)
                    continue
            self._click(dest,"result")
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
        if self._running:
            self._notify("Экипировка уже идёт.")
            return
        try:
            steps=self._equip_steps()
            needed=["search","first_result"]+[x[0] for x in steps]
            missing=[x for x in needed if not self._coord(x)]
            if missing:
                self._notify("Не заданы координаты: "+", ".join(dict.fromkeys(missing)))
                return
            if not self._option("dry_run") and not core.INPUT.available:
                self._notify("Ввод недоступен: "+core.INPUT.reason)
                return
            self._stop.clear()
            self._messages.put(("running",True))
            self._wake.emit()
            self._worker=threading.Thread(target=self._automate,args=(steps,),daemon=True)
            self._worker.start()
        except Exception as e:
            self._notify("Подготовка экипировки: "+str(e))

    def _automate(self,steps):
        try:
            for i in range(int(self._timing("countdown")),0,-1):
                self._notify("Старт через "+str(i)+" сек. Стоп: F9")
                self._sleep(1)
            if not self._option("dry_run") and self._option("focus_game"):
                ok,why=core.INPUT.focus_game()
                self._notify("Фокус игры: "+str(why))
            for i,(key,name,label) in enumerate(steps,1):
                self._sleep(0)
                self._notify("Экипировка "+str(i)+"/"+str(len(steps))+": "+label+" / "+name)
                self._click(self._coord(key),key)
                self._sleep(self._timing("after_slot_click"))
                ok=self._search_and_select(name)
                if not ok:
                    self._click(self._coord(key),key)
                    self._sleep(self._timing("after_slot_click"))
                    ok=self._search_and_select(name)
                if not ok:
                    self._notify("Не подтверждён: "+name)
                self._sleep(self._timing("between_steps"))
            if not self._option("dry_run"):
                self.cfg.setdefault("last_equipped",{})[self.build["side"]]=self._planned_equipped
                self._save()
            self._notify("Экипировка завершена.")
        except core.AbortError:
            self._notify("Автоматизация остановлена.")
            if not self._option("dry_run"):
                self.cfg.setdefault("last_equipped",{})[self.build["side"]]=None
                self._save()
        except Exception as e:
            self._notify("Ошибка экипировки: "+str(e))
            if not self._option("dry_run") and self.build:
                self.cfg.setdefault("last_equipped",{})[self.build["side"]]=None
                self._save()
        finally:
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
                staged = qt_updater.stage(info, os.path.dirname(sys.executable))
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
        self._save()
