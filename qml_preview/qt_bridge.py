"""Bridge the complete v2.28 legacy engine to a custom Qt Quick frontend.

The legacy Tk root is hidden; Qt is the only visible main window. This
compatibility bridge deliberately preserves the tested generation, database,
automation, OCR, community and settings implementations until each backend can
be extracted cleanly from Tk. Avoid Tk calls from worker threads.
"""
from __future__ import annotations

import copy
import os
import random
import re
import time

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot, QUrl
from PySide6.QtGui import QGuiApplication

import dbd_randomizer as core


def clean(value):
    """No emoji/pictographs in the new visible UI."""
    s = str(value or "")
    return re.sub(r"[\U0001F000-\U0001FFFF\u2600-\u27BF]", "", s).strip()


class QtBridge(QObject):
    perksChanged = Signal()
    roleChanged = Signal()
    modeChanged = Signal()
    statusChanged = Signal()
    optionsChanged = Signal()
    historyChanged = Signal()
    detailChanged = Signal()
    charactersChanged = Signal()
    skinsChanged = Signal()
    settingsChanged = Signal()
    communityChanged = Signal()
    iconVersionChanged = Signal()
    runningChanged = Signal()

    def __init__(self):
        super().__init__()
        core._load_tk()
        self.root = core.tk.Tk()
        self.root.withdraw()
        self.app = core.App(self.root)
        self.root.withdraw()
        self._locks = [False] * 4
        self._history = []
        self._status = "Готово. Генератор подключён к оригинальной базе."
        self._last_status = ""
        self._last_progress = -1
        self._running = False
        self._last_builds = -1
        self._icon_version = 0
        self._skin_character = next(iter(self.app.db.get("survivors", {})), "")
        self._skin_filter = ""
        self._selected_community = -1
        self._builder_side = "SURVIVOR"
        self._builder_char = ""
        self._builder_perks = [""] * 4
        self._builder_addons = [""] * 2
        self._builder_item = ""
        self._classes = {}
        self._clock = QTimer(self)
        self._clock.timeout.connect(self._pump)
        self._clock.start(45)

    def _pump(self):
        try:
            self.root.update()
        except core.tk.TclError:
            self._clock.stop()
            return
        try:
            t = clean(self.app.status.cget("text"))
            if t and t != self._last_status:
                self._last_status = t
                self._status = t
                self.statusChanged.emit()
            running = bool(self.app.worker and self.app.worker.is_alive())
            if running != self._running:
                self._running = running
                self.runningChanged.emit()
            n = len(self.app.community_builds)
            if n != self._last_builds:
                self._last_builds = n
                self.communityChanged.emit()
        except Exception:
            pass

    def _persist(self):
        self.app.collect_settings()
        core.save_config(self.app.cfg)

    @Property(str, notify=roleChanged)
    def role(self):
        return "killer" if self.app.mode_var.get() == "KILLER" else "survivor"

    @Property(str, notify=modeChanged)
    def mode(self):
        return self.app.perk_mode_var.get()

    @Property(str, notify=statusChanged)
    def status(self):
        return self._status

    @Property(bool, notify=runningChanged)
    def running(self):
        return self._running

    @Property("QVariantMap", notify=optionsChanged)
    def options(self):
        a = self.app
        return {
            "addons": bool(a.addons_var.get()),
            "appearance": bool(a.skin_var.get()),
            "challenge": bool(a.challenge_var.get()),
            "owned": bool(a.owned_var.get()),
            "classes": bool(a.class_var.get()),
            "dry": bool(a.dry_var.get()),
            "ocr": bool(a.ocr_var.get()),
            "select_char": bool(a.selchar_var.get()),
        }

    @Property("QVariantList", notify=perksChanged)
    def perks(self):
        names = (self.app.build or {}).get("perks") or []
        return [{
            "index": i + 1,
            "name": clean(names[i]) if i < len(names) else "Не выбран",
            "raw": names[i] if i < len(names) else "",
            "locked": self._locks[i],
            "filled": bool(i < len(names) and names[i] not in ("", core.EMPTY))
        } for i in range(4)]

    @Property("QVariantList", notify=historyChanged)
    def history(self):
        return self._history[:12]

    @Property("QVariantMap", notify=detailChanged)
    def detail(self):
        b = self.app.build or {}
        skin = b.get("skin") or {}
        challenge = b.get("challenge") or {}
        cls = b.get("class") or {}
        return {
            "char": clean(b.get("char", "")),
            "side": b.get("side", ""),
            "power": clean(b.get("power_or_item", "")),
            "category": clean(b.get("category", "")),
            "addons": [clean(x) for x in b.get("addons", [])],
            "skin": clean(skin.get("display", "")) if isinstance(skin, dict) else clean(skin),
            "challenge": clean(challenge.get("ru", "")) if isinstance(challenge, dict) else "",
            "challengeText": clean(challenge.get("text", "")) if isinstance(challenge, dict) else "",
            "class": clean(cls.get("ru", "")) if isinstance(cls, dict) else "",
            "hasBuild": bool(b),
        }

    @Property("QVariantList", notify=charactersChanged)
    def characters(self):
        result = []
        for (s, name), (var, _widget) in sorted(self.app._char_widgets.items(), key=lambda p: (p[0][0], p[0][1])):
            result.append({"name": name, "side": s, "owned": bool(var.get())})
        return result

    @Property("QVariantList", notify=skinsChanged)
    def skins(self):
        skins = getattr(core.SKINS, "CHAR_SKINS", {}) if core.SKINS else {}
        by_id = getattr(core.SKINS, "SKINS_BY_ID", {}) if core.SKINS else {}
        selected = set(self.app.cfg.get("skins", {}).get(self._skin_character, []))
        out = []
        for sid in skins.get(self._skin_character, []):
            item = by_id.get(sid, {})
            name = clean(item.get("name_ru") or item.get("name") or str(sid))
            if self._skin_filter and self._skin_filter.lower() not in name.lower():
                continue
            out.append({"id": int(sid), "name": name, "owned": sid in selected,
                        "rarity": clean(item.get("rarity_ru", ""))})
        return out

    @Property(str, notify=skinsChanged)
    def skinCharacter(self):
        return self._skin_character

    @Property("QVariantList", notify=communityChanged)
    def community(self):
        data = self.app.community_builds or []
        return [{"index": i, "title": clean(x.get("title") or x.get("char") or "Без названия"),
                 "author": clean(x.get("author", "")), "side": x.get("side", ""),
                 "character": clean(x.get("char", "")), "date": x.get("date", "")}
                for i, x in enumerate(data[:200]) if isinstance(x, dict)]

    @Property("QVariantList", notify=settingsChanged)
    def coordinates(self):
        out = []
        for key, label in core.COORD_FIELDS:
            entries = self.app._coord_widgets.get(key, {})
            out.append({"key": key, "title": clean(label),
                        "x": entries.get("x").get() if entries.get("x") else "",
                        "y": entries.get("y").get() if entries.get("y") else "",
                        "w": entries.get("w").get() if entries.get("w") else "",
                        "h": entries.get("h").get() if entries.get("h") else ""})
        return out

    @Property("QVariantList", notify=settingsChanged)
    def timings(self):
        return [{"key": k, "title": clean(desc), "value": entry.get()}
                for k, (_default, desc) in core.TIMING_DEFAULTS.items()
                for entry in [self.app._timing_widgets.get(k)] if entry]

    @Property("QVariantMap", notify=settingsChanged)
    def preferences(self):
        p = self.app.cfg.get("publish", {})
        return {"nickname": p.get("nickname", ""), "backend": p.get("backend", "github"),
                "firebase": p.get("firebase_url", "")}

    @Property(int, notify=iconVersionChanged)
    def iconVersion(self):
        return self._icon_version

    @Slot(str, result=str)
    def iconPath(self, key):
        path = self.app.icon_store.local_path(key)
        if path and self.app.icon_store.is_cached(key):
            return QUrl.fromLocalFile(path).toString()
        if key and self.app.icon_store.enabled:
            self.app.icon_store.request([key], on_ready=lambda _: self._request_icon_refresh())
        return ""

    def _request_icon_refresh(self):
        QTimer.singleShot(250, self._refresh_icons)

    def _refresh_icons(self):
        self._icon_version += 1
        self.iconVersionChanged.emit()

    @Slot(str)
    def setRole(self, role):
        if role not in ("killer", "survivor"):
            return
        self.app.mode_var.set("KILLER" if role == "killer" else "SURVIVOR")
        self.app._on_mode_change()
        self._locks = [False] * 4
        self.roleChanged.emit()
        self.perksChanged.emit()
        self._persist()

    @Slot(str)
    def setMode(self, value):
        if value not in ("mixed", "unique", "any", "general"):
            return
        self.app.perk_mode_var.set(value)
        self.modeChanged.emit()
        self._persist()

    @Slot(str)
    def toggleOption(self, key):
        mapping = {
            "addons": self.app.addons_var, "appearance": self.app.skin_var,
            "challenge": self.app.challenge_var, "owned": self.app.owned_var,
            "classes": self.app.class_var, "dry": self.app.dry_var,
            "ocr": self.app.ocr_var, "select_char": self.app.selchar_var
        }
        var = mapping.get(key)
        if var is None:
            return
        var.set(not bool(var.get()))
        self.optionsChanged.emit()
        self._persist()

    @Slot()
    def generate(self):
        try:
            self.app.generate_build()
            if not self.app.build:
                return
            self._locks = [False] * 4
            self._sync_build()
            text = clean(core.build_to_clipboard_text(self.app.build)).replace("\n", " / ")
            self._history.insert(0, text)
            self._history = self._history[:12]
            self.historyChanged.emit()
        except Exception as exc:
            self._set_error("Генерация: " + str(exc))

    def _sync_build(self):
        self.perksChanged.emit()
        self.detailChanged.emit()
        self._refresh_icons()

    @Slot(int)
    def toggleLock(self, index):
        if 0 <= index < 4 and self.perks[index]["filled"]:
            self._locks[index] = not self._locks[index]
            self.perksChanged.emit()

    @Slot(int)
    def reroll(self, index):
        b = self.app.build
        if not b or not 0 <= index < 4 or self._locks[index]:
            return
        try:
            current = list(b.get("perks", []))
            taken = set(current[:index] + current[index + 1:])
            pool = core.pick_perks(self.app.db, b["side"], b["char"],
                                   self.app.perk_mode_var.get(), bool(self.app.owned_var.get()),
                                   self.app.available_characters(b["side"]))
            possible = [p for p in pool if p not in taken and p not in (core.EMPTY,)]
            if not possible:
                possible = [p for p in core.all_unique_perks(self.app.db, b["side"])
                            if p not in taken]
            if possible:
                b["perks"][index] = random.choice(possible)
                self.app._render_build()
                self._sync_build()
        except Exception as exc:
            self._set_error(str(exc))

    @Slot()
    def rerollPerks(self):
        if not self.app.build:
            return
        old = list(self.app.build.get("perks", []))
        self.app.reroll_perks()
        used = set()
        fresh = self.app.build.get("perks", [])[:]
        for i, locked in enumerate(self._locks):
            if locked and i < len(old):
                fresh[i] = old[i]
                used.add(old[i])
        for i, perk in enumerate(fresh):
            if not self._locks[i] and perk in used:
                replacement = [p for p in core.all_unique_perks(self.app.db, self.app.build["side"])
                               if p not in fresh]
                if replacement:
                    fresh[i] = random.choice(replacement)
            used.add(fresh[i])
        self.app.build["perks"] = fresh
        self.app._render_build()
        self._sync_build()

    @Slot()
    def rerollChallenge(self):
        if self.app.build:
            self.app.reroll_challenge()
            self._sync_build()

    @Slot()
    def rollClasses(self):
        self._classes = {side: core.pick_class(side) for side in ("SURVIVOR", "KILLER")}
        self._set_error("Классы: " + " | ".join(clean((v or {}).get("ru", "—")) for v in self._classes.values()))

    @Slot()
    def copyBuild(self):
        if self.app.build:
            self.app.copy_build()
            self._status = "Билд скопирован."
            self.statusChanged.emit()

    @Slot()
    def equip(self):
        try:
            self.app.start_equip()
            self._running = bool(self.app.worker and self.app.worker.is_alive())
            self.runningChanged.emit()
        except Exception as exc:
            self._set_error(str(exc))

    @Slot()
    def stop(self):
        self.app.request_abort()
        self._status = "Остановка автоматизации запрошена."
        self.statusChanged.emit()

    @Slot(str)
    def placeholder(self, action):
        if action == "Автоэкипировка":
            self.equip()
        elif action == "STOP":
            self.stop()
        else:
            self._set_error(action + ": используйте соответствующий раздел.")

    def _set_error(self, message):
        self._status = clean(message)
        self.statusChanged.emit()

    @Slot(str, str)
    def setCharacter(self, name, side):
        key = ("K" if side in ("KILLER", "K") else "S", name)
        item = self.app._char_widgets.get(key)
        if not item:
            return
        item[0].set(not item[0].get())
        self.charactersChanged.emit()
        self.app.save_owned_characters_silent()
        self._persist()

    @Slot(str)
    def setSkinCharacter(self, name):
        if name in (getattr(core.SKINS, "CHAR_SKINS", {}) if core.SKINS else {}):
            self._skin_character = name
            self.skinsChanged.emit()

    @Slot(str)
    def filterSkins(self, term):
        self._skin_filter = term.strip()
        self.skinsChanged.emit()

    @Slot(int)
    def toggleSkin(self, skin_id):
        arr = self.app.cfg.setdefault("skins", {}).setdefault(self._skin_character, [])
        if skin_id in arr:
            arr.remove(skin_id)
        else:
            arr.append(skin_id)
        self._persist()
        self.skinsChanged.emit()

    @Slot()
    def refreshCommunity(self):
        self.app.refresh_community_builds(manual=True)
        self._set_error("Обновление списка билдов сообщества запущено.")

    @Slot(int)
    def copyCommunity(self, index):
        data = self.app.community_builds
        if 0 <= index < len(data):
            QGuiApplication.clipboard().setText(core.GH.format_build_text(data[index]))
            self._set_error("Билд сообщества скопирован.")

    @Slot(int)
    def useCommunity(self, index):
        data = self.app.community_builds
        if not 0 <= index < len(data):
            return
        entry = data[index]
        side = entry.get("side")
        b = {"side": side, "char": entry.get("char", ""),
             "power_or_item": entry.get("power_or_item", core.EMPTY),
             "power_is_item": side == "SURVIVOR",
             "addons": (entry.get("addons") or [])[:2],
             "perks": (entry.get("perks") or [])[:4],
             "skin": None, "forbidden": {}}
        if side not in ("SURVIVOR", "KILLER") or not b["char"] or len(b["perks"]) != 4:
            self._set_error("Некорректный билд сообщества.")
            return
        self.app.build = b
        self.app.mode_var.set(side)
        self._locks = [False] * 4
        self.app._render_build()
        self._sync_build()
        self.roleChanged.emit()
        self._set_error("Билд сообщества перенесён в карточку.")

    @Slot(str, str, str)
    def editCoord(self, key, axis, value):
        ent = self.app._coord_widgets.get(key, {}).get(axis)
        if ent is None:
            return
        ent.delete(0, "end")
        ent.insert(0, str(value))
        self.settingsChanged.emit()

    @Slot(str, str)
    def editTiming(self, key, value):
        ent = self.app._timing_widgets.get(key)
        if ent is not None:
            ent.delete(0, "end")
            ent.insert(0, str(value))
            self.settingsChanged.emit()

    @Slot()
    def saveSettings(self):
        self._persist()
        self._set_error("Настройки сохранены в dbd_randomizer_config.json.")

    @Slot()
    def copyLog(self):
        QGuiApplication.clipboard().setText(self.app.txt_log.get("1.0", "end"))
        self._set_error("Журнал скопирован.")

    @Slot()
    def clearLog(self):
        self.app._clear_log()

    @Property(str, notify=statusChanged)
    def logText(self):
        try:
            return clean(self.app.txt_log.get("1.0", "end"))[-3000:]
        except Exception:
            return ""

    @Slot()
    def close(self):
        self._clock.stop()
        try:
            self.app._on_close()
        except Exception:
            self.root.destroy()
