"""Local, bounded, validated favorites library for Qt builds.

Persists inside options.favorite_builds_v1 of the existing config. It deliberately
stores only equipment, character and appearance, not executable scripts,
automation settings, challenge constraints or account credentials.
"""
from __future__ import annotations

from datetime import datetime
import copy
import re
import uuid

MAX_FAVORITES = 180
TITLE_MAX = 72
COLLECTION_MAX = 48
NOTE_MAX = 240
TEXT_MAX = 180


def _text(value, limit):
    return value.strip()[:limit] if isinstance(value, str) else ""


def _equipment(values, count, empty):
    if not isinstance(values, (list, tuple)):
        raise ValueError("Слоты снаряжения должны быть списком.")
    if len(values) != count:
        raise ValueError("Неверное количество слотов снаряжения.")
    if any(not isinstance(name, str) or len(name) > TEXT_MAX for name in values):
        raise ValueError("Название предмета слишком длинное или повреждено.")
    return [name or empty for name in values]


def _skin(raw):
    if isinstance(raw, str):
        return _text(raw, TEXT_MAX)
    if isinstance(raw, dict):
        data = {}
        for key in ("name", "display"):
            if isinstance(raw.get(key), str):
                data[key] = _text(raw[key], TEXT_MAX)
        if type(raw.get("id")) is int and 0 <= raw["id"] <= 100000:
            data["id"] = raw["id"]
        return data or None
    return None


def snapshot(build, empty="", no_addons=""):
    if not isinstance(build, dict) or build.get("side") not in ("KILLER", "SURVIVOR"):
        raise ValueError("Сначала создайте настоящий билд.")
    side = build["side"]
    char = _text(build.get("char"), TEXT_MAX)
    if not char:
        raise ValueError("Нет выбранного персонажа.")
    perks = _equipment(build.get("perks"), 4, empty)
    addons = _equipment(build.get("addons"), 2, empty)
    clean_perks = [p for p in perks if p != empty]
    clean_addons = [a for a in addons if a not in (empty, no_addons)]
    if len(clean_perks) != len(set(clean_perks)) or len(clean_addons) != len(set(clean_addons)):
        raise ValueError("В билде есть повторяющиеся перки или аддоны.")
    return {
        "side": side,
        "char": char,
        "power_or_item": _text(build.get("power_or_item"), TEXT_MAX) or empty,
        "category": _text(build.get("category"), TEXT_MAX) if side == "SURVIVOR" else "",
        "perks": perks,
        "addons": addons,
        "skin": _skin(build.get("skin")),
    }


class FavoriteBuilds:
    def __init__(self, saved=None, *, empty="", no_addons=""):
        self._empty = empty
        self._no_addons = no_addons
        self._entries = []
        if not isinstance(saved, list):
            return
        used_ids = set()
        for raw in saved[:MAX_FAVORITES * 2]:
            if not isinstance(raw, dict):
                continue
            ident = raw.get("id")
            if (not isinstance(ident, str) or
                    not re.fullmatch(r"[0-9a-f]{16}", ident) or ident in used_ids):
                continue
            try:
                build = snapshot(raw.get("build"), empty, no_addons)
            except ValueError:
                continue
            used_ids.add(ident)
            self._entries.append({
                "id": ident,
                "title": _text(raw.get("title"), TITLE_MAX) or build["char"],
                "collection": _text(raw.get("collection"), COLLECTION_MAX) or "Мои сборки",
                "note": _text(raw.get("note"), NOTE_MAX),
                "saved_at": _text(raw.get("saved_at"), 25),
                "build": build,
            })
            if len(self._entries) >= MAX_FAVORITES:
                break

    @property
    def count(self):
        return len(self._entries)

    def add(self, build, title="", collection="", note=""):
        if self.count >= MAX_FAVORITES:
            raise ValueError("Достигнут лимит избранного: 180 билдов.")
        build = snapshot(build, self._empty, self._no_addons)
        ident = uuid.uuid4().hex[:16]
        while any(row["id"] == ident for row in self._entries):
            ident = uuid.uuid4().hex[:16]
        record = {
            "id": ident,
            "title": _text(title, TITLE_MAX) or build["char"],
            "collection": _text(collection, COLLECTION_MAX) or "Мои сборки",
            "note": _text(note, NOTE_MAX),
            "saved_at": datetime.now().astimezone().strftime("%d.%m.%Y %H:%M"),
            "build": build,
        }
        self._entries.insert(0, record)
        return ident

    def get(self, ident):
        for row in self._entries:
            if row["id"] == ident:
                return copy.deepcopy(row)
        return None

    def update(self, ident, title="", collection="", note=""):
        for row in self._entries:
            if row["id"] == ident:
                row["title"] = _text(title, TITLE_MAX) or row["build"]["char"]
                row["collection"] = _text(collection, COLLECTION_MAX) or "Мои сборки"
                row["note"] = _text(note, NOTE_MAX)
                return True
        return False

    def delete(self, ident):
        for i, row in enumerate(self._entries):
            if row["id"] == ident:
                del self._entries[i]
                return True
        return False

    def collections(self):
        return ["Все коллекции"] + sorted(set(row["collection"] for row in self._entries))

    def list(self, query="", side="ALL", collection="Все коллекции"):
        key = _text(query, 180).casefold().replace("ё", "е")
        results = []
        for row in self._entries:
            build = row["build"]
            if side not in ("ALL", build["side"]):
                continue
            if collection not in ("", "Все коллекции", row["collection"]):
                continue
            haystack = " ".join([
                row["title"], row["collection"], row["note"], build["char"],
                build["power_or_item"], *build["perks"], *build["addons"],
            ]).casefold().replace("ё", "е")
            if key and key not in haystack:
                continue
            results.append({
                "id": row["id"], "title": row["title"], "note": row["note"],
                "collection": row["collection"], "saved_at": row["saved_at"],
                "side": build["side"], "char": build["char"],
                "perks": build["perks"][:], "addons": build["addons"][:],
                "item": build["power_or_item"],
            })
        return results

    def restore(self, ident, db, core):
        record = self.get(ident)
        if record is None:
            raise ValueError("Билд не найден в избранном.")
        b = record["build"]
        side, char = b["side"], b["char"]
        chars = db.get("killers" if side == "KILLER" else "survivors", {})
        if char not in chars:
            raise ValueError("Персонаж больше не существует в текущей базе DBD.")
        perk_pool = set(core.all_unique_perks(db, side))
        perk_pool.update(db["killer_common_perks" if side == "KILLER" else "surv_common_perks"])
        for name in b["perks"]:
            if name != self._empty and name not in perk_pool:
                raise ValueError("В сохранённом билде есть устаревший навык: " + name)
        item = b["power_or_item"]
        category = ""
        if side == "KILLER":
            power = chars[char].get("power", self._empty)
            addons = set(core._playable_addons(chars[char].get("addons", [])))
        else:
            if item in ("", self._empty):
                power = self._empty
                addons = set()
            else:
                candidate = [
                    (name, spec) for name, spec in db["survivor_items"].items()
                    if item in spec.get("items", [])
                ]
                matching = next(((name, spec) for name, spec in candidate
                                 if name == b["category"]), None)
                if matching is None:
                    matching = candidate[0] if candidate else None
                if not matching:
                    raise ValueError("Предмет больше не существует в базе DBD.")
                category, spec = matching
                power = item
                addons = set(core._playable_addons(spec.get("addons", [])))
        for name in b["addons"]:
            if name not in ("", self._empty, self._no_addons) and name not in addons:
                raise ValueError("Аддон больше не совместим с этим персонажем или предметом: " + name)
        if side == "SURVIVOR" and power == self._empty:
            for name in b["addons"]:
                if name not in ("", self._empty, self._no_addons):
                    raise ValueError("Сохранён аддон без предмета.")
        return {
            "side": side, "char": char, "power_or_item": power,
            "power_is_item": side == "SURVIVOR", "category": category,
            "perks": b["perks"][:], "addons": b["addons"][:],
            "skin": copy.deepcopy(b["skin"]),
            "fx": {}, "forbidden": {},
        }

    def serialize(self):
        return copy.deepcopy(self._entries)
