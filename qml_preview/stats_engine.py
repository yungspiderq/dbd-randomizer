"""Persistent, mode-independent statistics for DBD Randomizer Qt.

Tracks real generated builds in both classic and balanced modes. Legacy
rotation counters are intentionally not imported because they only cover the
balanced mode and don't provide reliable chronology for previous versions.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime

SIDES = ("KILLER", "SURVIVOR")
GROUPS = ("characters", "perks", "addons", "items")
MAX_HISTORY = 100
MAX_NAMES = 2400


def _valid_count(value):
    return type(value) is int and 0 <= value <= 10_000_000


def _valid_name(value):
    return isinstance(value, str) and 0 < len(value) <= 180


def _safe_group(data):
    if not isinstance(data, dict):
        return {}
    return {name: count for name, count in list(data.items())[:MAX_NAMES]
            if _valid_name(name) and _valid_count(count) and count > 0}


def _new_side():
    return {"generated": 0, "rerolls": 0, "serial": 0,
            "classic": 0, "balanced": 0,
            "groups": {name: {} for name in GROUPS},
            "last": {name: {} for name in GROUPS},
            "recent": []}


class BuildStatistics:
    def __init__(self, saved=None):
        self._data = {side: _new_side() for side in SIDES}
        if not isinstance(saved, dict):
            return
        for side in SIDES:
            src = saved.get(side)
            if not isinstance(src, dict):
                continue
            dst = self._data[side]
            for key in ("generated", "rerolls", "serial", "classic", "balanced"):
                val = src.get(key)
                if _valid_count(val):
                    dst[key] = val
            src_groups = src.get("groups") if isinstance(src.get("groups"), dict) else {}
            src_last = src.get("last") if isinstance(src.get("last"), dict) else {}
            for group in GROUPS:
                dst["groups"][group] = _safe_group(src_groups.get(group))
                dst["last"][group] = _safe_group(src_last.get(group))
            src_recent = src.get("recent")
            if isinstance(src_recent, list):
                for entry in src_recent[:MAX_HISTORY]:
                    if not isinstance(entry, dict):
                        continue
                    label = entry.get("character")
                    if not _valid_name(label):
                        continue
                    dst["recent"].append({
                        "character": label, "mode": "balanced" if entry.get("mode") == "balanced" else "classic",
                        "kind": "reroll" if entry.get("kind") == "reroll" else "build",
                        "perks": [s for s in entry.get("perks", [])[:4] if _valid_name(s)]
                                 if isinstance(entry.get("perks"), list) else [],
                        "addons": [s for s in entry.get("addons", [])[:2] if _valid_name(s)]
                                  if isinstance(entry.get("addons"), list) else [],
                        "time": str(entry.get("time", ""))[:25],
                    })

    def _add(self, side, group, names):
        state = self._data[side]
        counts, last = state["groups"][group], state["last"][group]
        for value in names:
            if not _valid_name(value):
                continue
            if value not in counts and len(counts) >= MAX_NAMES:
                continue
            counts[value] = min(10_000_000, counts.get(value, 0) + 1)
            last[value] = state["serial"]

    def record_build(self, build, *, balanced=False, empty="", no_addons=""):
        side = build.get("side")
        if side not in SIDES:
            raise ValueError("Invalid statistics side")
        s = self._data[side]
        s["serial"] += 1
        s["generated"] += 1
        s["balanced" if balanced else "classic"] += 1
        char = build.get("char", "")
        self._add(side, "characters", [char])
        forbidden = build.get("forbidden") or {}
        perks = [x for x in build.get("perks", []) if x not in (empty, "", None)]
        addons = [x for x in build.get("addons", []) if x not in (empty, no_addons, "", None)]
        if not forbidden.get("perks"):
            self._add(side, "perks", perks)
        if not forbidden.get("addons"):
            self._add(side, "addons", addons)
        if side == "SURVIVOR" and not forbidden.get("item"):
            self._add(side, "items", [build.get("power_or_item", "")])
        self._insert_recent(side, char, "build", balanced,
                            perks if not forbidden.get("perks") else [],
                            addons if not forbidden.get("addons") else [])

    def record_perk_reroll(self, side, char, perk, *, balanced=False, empty=""):
        if side not in SIDES:
            raise ValueError("Invalid statistics side")
        if perk in ("", empty, None):
            return
        s = self._data[side]
        s["serial"] += 1
        s["rerolls"] += 1
        self._add(side, "perks", [perk])
        self._insert_recent(side, char, "reroll", balanced, [perk], [])

    def _insert_recent(self, side, character, kind, balanced, perks, addons):
        self._data[side]["recent"].insert(0, {
            "character": str(character or "")[:180],
            "kind": kind, "mode": "balanced" if balanced else "classic",
            "perks": [str(x)[:180] for x in perks][:4],
            "addons": [str(x)[:180] for x in addons][:2],
            "time": datetime.now().astimezone().strftime("%d.%m %H:%M"),
        })
        del self._data[side]["recent"][MAX_HISTORY:]

    def summary(self, side, group, population=(), *, limit=10, order="top"):
        if side not in SIDES or group not in GROUPS:
            return []
        state = self._data[side]
        counts = state["groups"][group]
        last = state["last"][group]
        pool = sorted(set(x for x in population if _valid_name(x))) if population else sorted(counts)
        if order == "top":
            pool.sort(key=lambda n: (-counts.get(n, 0), n.casefold()))
        elif order == "least":
            pool.sort(key=lambda n: (counts.get(n, 0), n.casefold()))
        elif order == "stale":
            pool = [n for n in pool if counts.get(n, 0) > 0]
            pool.sort(key=lambda n: (last.get(n, 0), n.casefold()))
        else:
            return []
        maximum = max((counts.get(n, 0) for n in pool), default=0)
        rows = []
        for name in pool[:max(0, min(100, int(limit)))]:
            value = counts.get(name, 0)
            rows.append({"name": name, "count": value,
                         "fraction": value / maximum if maximum else 0.0,
                         "since": (state["serial"] - last[name]) if name in last else -1,
                         "seen": value > 0})
        return rows

    def overview(self, side, population=()):
        state = self._data[side]
        counts = state["groups"]["characters"]
        pool = set(x for x in population if _valid_name(x))
        return {
            "generated": state["generated"],
            "rerolls": state["rerolls"],
            "classic": state["classic"],
            "balanced": state["balanced"],
            "seen": sum(counts.get(n, 0) > 0 for n in pool),
            "total": len(pool),
            "uniquePerks": len(state["groups"]["perks"]),
            "uniqueAddons": len(state["groups"]["addons"]),
            "last": state["recent"][0]["character"] if state["recent"] else "",
        }

    def recent(self, side, count=30):
        return [dict(row) for row in self._data[side]["recent"][:count]]

    def reset(self, side):
        if side not in SIDES:
            raise ValueError("Invalid statistics side")
        self._data[side] = _new_side()

    def serialize(self):
        import copy
        return copy.deepcopy(self._data)
