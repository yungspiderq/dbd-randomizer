"""Opt-in adaptive randomization for DBD: frequency and recency-aware draws.

The classic generator remains unchanged. Rotation is scoped by role; add-ons
are scoped by killer or survivor item category. No candidate is forbidden just
because it was picked recently. Save state in the regular options config.
"""
from __future__ import annotations
import copy
import random

SIDES = ("KILLER", "SURVIVOR")
BAD = frozenset(("", None))


class RotationState:
    RECENT_MAX = 16

    def __init__(self, saved=None, rng=None):
        self._rng = rng or random
        self._data = {side: {} for side in SIDES}
        if not isinstance(saved, dict):
            return
        for side in SIDES:
            raw = saved.get(side, {})
            if not isinstance(raw, dict):
                continue
            for bucket, section in list(raw.items())[:200]:
                if not isinstance(bucket, str) or not isinstance(section, dict):
                    continue
                counts = {}
                values = section.get("counts", {})
                if isinstance(values, dict):
                    for name, count in list(values.items())[:300]:
                        if isinstance(name, str) and isinstance(count, int) and 0 < count < 1_000_000_000:
                            counts[name] = count
                recent = section.get("recent", [])
                recent = ([x for x in recent if isinstance(x, str)][:self.RECENT_MAX]
                          if isinstance(recent, list) else [])
                self._data[side][bucket] = {"counts": counts, "recent": recent}

    def _section(self, side, group, scope=""):
        if side not in SIDES:
            raise ValueError("Unknown DBD side")
        bucket = group + ":" + scope if scope else group
        return self._data[side].setdefault(bucket, {"counts": {}, "recent": []})

    def weights(self, side, group, candidates, scope=""):
        values = list(dict.fromkeys(x for x in candidates if x not in BAD))
        if not values:
            return {}
        section = self._section(side, group, scope)
        counts, recent = section["counts"], section["recent"]
        floor = min(counts.get(x, 0) for x in values)
        weights = {}
        for name in values:
            relative = max(0, counts.get(name, 0) - floor)
            weight = 1.0 / ((1.0 + relative) ** 2.4)
            if recent:
                if name == recent[0]:
                    weight *= 0.035
                elif name in recent[:4]:
                    weight *= 0.20
                elif name in recent[:12]:
                    weight *= 0.60
            weights[name] = max(0.0001, weight)
        return weights

    def select(self, side, group, candidates, count=1, scope=""):
        pool = list(dict.fromkeys(x for x in candidates if x not in BAD))
        chosen = []
        for _ in range(min(max(0, int(count)), len(pool))):
            weights = self.weights(side, group, pool, scope)
            item = self._rng.choices(pool, weights=[weights[x] for x in pool], k=1)[0]
            chosen.append(item)
            pool.remove(item)
        return chosen

    def record(self, side, group, names, scope=""):
        state = self._section(side, group, scope)
        for name in names:
            if name in BAD:
                continue
            state["counts"][name] = state["counts"].get(name, 0) + 1
            state["recent"].insert(0, name)
            del state["recent"][self.RECENT_MAX:]

    def record_build(self, build, empty="", no_addons=""):
        side = build["side"]
        char = build["char"]
        self.record(side, "characters", [char])
        if side == "SURVIVOR":
            category = build.get("category", "")
            self.record(side, "categories", [category])
            item = build.get("power_or_item")
            if item not in (empty, None, ""):
                self.record(side, "items", [item], scope=category)
        forbidden = build.get("forbidden") or {}
        if not forbidden.get("addons"):
            self.record(side, "addons", [a for a in build.get("addons", [])
                                        if a not in (empty, no_addons, None, "")],
                        scope=char if side == "KILLER" else build.get("category", ""))
        if not forbidden.get("perks"):
            self.record(side, "perks", [p for p in build.get("perks", [])
                                       if p not in (empty, None, "")])

    def info(self, side, eligible):
        pool = list(dict.fromkeys(eligible))
        data = self._section(side, "characters")
        counts = data["counts"]
        return {"seen": sum(counts.get(x, 0) > 0 for x in pool),
                "total": len(pool), "last": data["recent"][0] if data["recent"] else "",
                "generated": sum(counts.values())}

    def reset(self, side):
        if side not in SIDES:
            raise ValueError("Unknown DBD side")
        self._data[side] = {}

    def serialize(self):
        return copy.deepcopy(self._data)


def choose_perks(core, db, side, char, mode, respect_owned, available, fx, rotation):
    if side == "KILLER":
        unique = list(db["killers"].get(char, {}).get("perks", []))
        common = list(db.get("killer_common_perks", []))
        owned = db.get("owned", {}).get("killer_perks")
    else:
        unique = list(db["survivors"].get(char, []))
        common = list(db.get("surv_common_perks", []))
        owned = db.get("owned", {}).get("survivor_perks")
    banned = set(fx.get("ban_perks") or ())
    unique = [x for x in unique if x not in banned]
    common = [x for x in common if x not in banned]
    special = fx.get("perk_pool")
    if special or banned:
        if special == "common":
            stages = [(common, 4)]
        elif special == "own":
            stages = [(unique, 4)]
        elif special == "half":
            stages = [(unique, 2), (common, 2)]
        else:
            stages = [(unique + common, 4)]
    else:
        foreign = [x for x in core.all_unique_perks(db, side)
                   if x not in unique and x not in common]
        source = db["killers"] if side == "KILLER" else db["survivors"]
        permitted = set()
        for name in available:
            entry = source.get(name)
            if entry is not None:
                permitted.update(entry.get("perks", []) if isinstance(entry, dict) else entry)
        foreign = [x for x in foreign if x in permitted]
        if mode == "any":
            stages = [(common + unique + foreign, 4)]
        elif mode == "unique":
            stages = [(unique, len(unique)), (foreign, 4), (common, 4)]
        elif mode == "mixed":
            stages = [(unique, len(unique)), (common, 4), (foreign, 4)]
        else:
            stages = [(common, 4), (unique, 4), (foreign, 4)]
    picked = []
    for pool, take in stages:
        if len(picked) >= 4:
            break
        valid = core._filter_owned([x for x in dict.fromkeys(pool) if x not in picked],
                                    owned, respect_owned)
        picked.extend(rotation.select(side, "perks", valid, min(take, 4 - len(picked))))
    return (picked + [core.EMPTY] * max(0, 4 - len(picked)))[:4]


def make_rotated_build(core, db, side, available, rotation, **kwargs):
    """Run original build constructor for compatible metadata, then rotate draws."""
    if side not in SIDES:
        raise ValueError("Invalid role")
    fx = kwargs.get("fx") or {}
    eligible = [name for name in sorted(set(available))
                if name not in set(fx.get("ban_chars") or ())]
    if not eligible:
        raise ValueError("Нет доступных персонажей для условий челленджа.")
    char = rotation.select(side, "characters", eligible)[0]
    original = core.make_killer_build if side == "KILLER" else core.make_survivor_build
    build = original(db, [char], **kwargs)
    if build["char"] != char:
        raise ValueError("Генератор вышел за разрешённый список")
    respect = bool(kwargs.get("respect_owned", False))
    use_addons = bool(kwargs.get("addons_enabled", True))
    owned = db.get("owned", {})
    if side == "KILLER":
        scope = char
        addon_pool = core._filter_owned(
            core._playable_addons(db["killers"][char].get("addons", [])),
            owned.get("killer_addons"), respect)
    else:
        categories = [cat for cat in db["survivor_items"]
                      if cat not in set(fx.get("ban_item_cats") or ())]
        if not categories:
            raise ValueError("Нет доступных типов предметов для челленджа")
        category = rotation.select(side, "categories", categories)[0]
        data = db["survivor_items"][category]
        items = core._filter_owned(data.get("items", []),
                                   owned.get("survivor_items"), respect)
        item = rotation.select(side, "items", items, scope=category)
        build["power_or_item"] = item[0] if item else core.EMPTY
        build["category"] = category
        scope = category
        addon_pool = core._filter_owned(
            core._playable_addons(data.get("addons", [])),
            owned.get("survivor_addons"), respect)
    if use_addons:
        addon_pool = core._ban_addons(addon_pool, fx)
        addons = rotation.select(side, "addons", addon_pool, 2, scope=scope)
    else:
        addons = []
    if side == "KILLER":
        while len(addons) < 2:
            addons.append(core.NO_ADDONS if not addons else core.EMPTY)
    else:
        if not addons:
            addons = [core.NO_ADDONS if use_addons and not addon_pool else core.EMPTY]
        while len(addons) < 2:
            addons.append(core.EMPTY)
    build["addons"] = addons
    build["perks"] = choose_perks(
        core, db, side, char, kwargs.get("perk_mode", "mixed"),
        respect, available, fx, rotation)
    return build
