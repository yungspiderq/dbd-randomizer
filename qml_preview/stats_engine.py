"""Persistent, mode-independent statistics for DBD Randomizer Qt.

Tracks real generated builds in both classic and balanced modes. Legacy
rotation counters are intentionally not imported because they only cover the
balanced mode and don't provide reliable chronology for previous versions.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, date, timedelta
from collections import Counter

SIDES = ("KILLER", "SURVIVOR")
GROUPS = ("characters", "perks", "addons", "items")
MAX_HISTORY = 100
MAX_NAMES = 2400
MAX_DAYS = 400
PERIODS = (0, 1, 7, 30)


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
            "recent": [], "daily": {}}


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
            src_daily = src.get("daily")
            if isinstance(src_daily, dict):
                for day, original in sorted(src_daily.items())[-MAX_DAYS:]:
                    if not isinstance(day, str) or not isinstance(original, dict):
                        continue
                    try:
                        if date.fromisoformat(day).isoformat() != day:
                            continue
                    except ValueError:
                        continue
                    bucket = self._new_daily()
                    for k in ("generated", "classic", "balanced", "rerolls"):
                        if _valid_count(original.get(k)):
                            bucket[k] = original[k]
                    source = original.get("groups")
                    if isinstance(source, dict):
                        for k in GROUPS:
                            bucket["groups"][k] = _safe_group(source.get(k))
                    dst["daily"][day] = bucket
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
                        "day": entry.get("day", "") if isinstance(entry.get("day"), str)
                               and len(entry.get("day")) == 10 else "",
                    })

    @staticmethod
    def _new_daily():
        return {"generated": 0, "classic": 0, "balanced": 0, "rerolls": 0,
                "groups": {group: {} for group in GROUPS}}

    def _bucket(self, side, on_date=None):
        if on_date is None:
            day = datetime.now().astimezone().date().isoformat()
        else:
            day = on_date.isoformat() if isinstance(on_date, date) else str(on_date)
            date.fromisoformat(day)
        daily = self._data[side]["daily"]
        if day not in daily:
            if len(daily) >= MAX_DAYS:
                del daily[sorted(daily)[0]]
            daily[day] = self._new_daily()
        return day, daily[day]

    @staticmethod
    def _daily_add(bucket, group, names):
        counts = bucket["groups"][group]
        for name in names:
            if _valid_name(name) and (name in counts or len(counts) < MAX_NAMES):
                counts[name] = min(10_000_000, counts.get(name, 0) + 1)

    def _days(self, side, days, today=None):
        if days not in PERIODS or days == 0:
            raise ValueError("Invalid nonzero period")
        end = today or datetime.now().astimezone().date()
        if isinstance(end, str):
            end = date.fromisoformat(end)
        start = end - timedelta(days=days - 1)
        return [b for key, b in self._data[side]["daily"].items()
                if start <= date.fromisoformat(key) <= end]

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

    def record_build(self, build, *, balanced=False, empty="", no_addons="", on_date=None):
        side = build.get("side")
        if side not in SIDES:
            raise ValueError("Invalid statistics side")
        s = self._data[side]
        s["serial"] += 1
        s["generated"] += 1
        s["balanced" if balanced else "classic"] += 1
        day, daily = self._bucket(side, on_date)
        daily["generated"] += 1
        daily["balanced" if balanced else "classic"] += 1
        char = build.get("char", "")
        self._daily_add(daily, "characters", [char])
        self._add(side, "characters", [char])
        forbidden = build.get("forbidden") or {}
        perks = [x for x in build.get("perks", []) if x not in (empty, "", None)]
        addons = [x for x in build.get("addons", []) if x not in (empty, no_addons, "", None)]
        if not forbidden.get("perks"):
            self._add(side, "perks", perks)
            self._daily_add(daily, "perks", perks)
        if not forbidden.get("addons"):
            self._add(side, "addons", addons)
            self._daily_add(daily, "addons", addons)
        if side == "SURVIVOR" and not forbidden.get("item"):
            self._add(side, "items", [build.get("power_or_item", "")])
            self._daily_add(daily, "items", [build.get("power_or_item", "")])
        self._insert_recent(side, char, "build", balanced,
                            perks if not forbidden.get("perks") else [],
                            addons if not forbidden.get("addons") else [], day)

    def record_perk_reroll(self, side, char, perk, *, balanced=False, empty="", on_date=None):
        if side not in SIDES:
            raise ValueError("Invalid statistics side")
        if perk in ("", empty, None):
            return
        s = self._data[side]
        s["serial"] += 1
        s["rerolls"] += 1
        day, daily = self._bucket(side, on_date)
        daily["rerolls"] += 1
        self._add(side, "perks", [perk])
        self._daily_add(daily, "perks", [perk])
        self._insert_recent(side, char, "reroll", balanced, [perk], [], day)

    def _insert_recent(self, side, character, kind, balanced, perks, addons, day):
        self._data[side]["recent"].insert(0, {
            "character": str(character or "")[:180],
            "kind": kind, "mode": "balanced" if balanced else "classic",
            "perks": [str(x)[:180] for x in perks][:4],
            "addons": [str(x)[:180] for x in addons][:2],
            "time": datetime.now().astimezone().strftime("%d.%m %H:%M"),
            "day": day,
        })
        del self._data[side]["recent"][MAX_HISTORY:]

    def summary(self, side, group, population=(), *, limit=10, order="top"):
        if side not in SIDES or group not in GROUPS:
            return []
        state = self._data[side]
        return self._ranking(state["groups"][group], state["last"][group],
                             state["serial"], population, limit, order)

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

    @staticmethod
    def _merge_counts(parts, group):
        counter = Counter()
        for part in parts:
            counter.update(part["groups"][group])
        return dict(counter)

    def overview_period(self, side, population=(), days=0, *, today=None):
        if days == 0:
            return self.overview(side, population)
        parts = self._days(side, days, today)
        character_counts = self._merge_counts(parts, "characters")
        pool = set(x for x in population if _valid_name(x))
        return {
            "generated": sum(p["generated"] for p in parts),
            "rerolls": sum(p["rerolls"] for p in parts),
            "classic": sum(p["classic"] for p in parts),
            "balanced": sum(p["balanced"] for p in parts),
            "seen": sum(character_counts.get(x, 0) > 0 for x in pool),
            "total": len(pool),
            "uniquePerks": len(self._merge_counts(parts, "perks")),
            "uniqueAddons": len(self._merge_counts(parts, "addons")),
            "last": self._data[side]["recent"][0]["character"]
                    if self._data[side]["recent"] else "",
        }

    def summary_period(self, side, group, population=(), *, days=0, limit=10,
                       order="top", today=None):
        if days == 0:
            return self.summary(side, group, population, limit=limit, order=order)
        if side not in SIDES or group not in GROUPS:
            return []
        counts = self._merge_counts(self._days(side, days, today), group)
        return self._ranking(counts, {}, 0, population, limit, order)

    @staticmethod
    def _ranking(counts, last, serial, population, limit, order):
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
                         "since": serial - last[name] if name in last else -1,
                         "seen": value > 0})
        return rows

    def recent_period(self, side, days=0, count=30, *, today=None):
        if days == 0:
            return self.recent(side, count)
        end = today or datetime.now().astimezone().date()
        if isinstance(end, str):
            end = date.fromisoformat(end)
        start = end - timedelta(days=days - 1)
        return [dict(row) for row in self._data[side]["recent"]
                if row.get("day") and start <= date.fromisoformat(row["day"]) <= end][:count]

    def recent(self, side, count=30):
        return [dict(row) for row in self._data[side]["recent"][:count]]

    def reset(self, side):
        if side not in SIDES:
            raise ValueError("Invalid statistics side")
        self._data[side] = _new_side()

    def serialize(self):
        import copy
        return copy.deepcopy(self._data)
