"""Perk card metadata and safe retention of pinned perks across full rerolls.

No Tk or Qt dependencies: this module is shared by UI and tests.
"""
from __future__ import annotations

import random

from perk_descriptions import description_for


def perk_info(db, side, name, *, empty=""):
    if not name or name == empty:
        return {"name": "Не выбран", "owner": "", "kind": "Пустой слот",
                "common": False, "found": False, "description": ""}
    if side not in ("KILLER", "SURVIVOR"):
        return {"name": name, "owner": "", "kind": "Неизвестная сторона",
                "common": False, "found": False, "description": ""}
    common = set(db.get("killer_common_perks" if side == "KILLER" else "surv_common_perks", []))
    chars = db.get("killers" if side == "KILLER" else "survivors", {})
    owners = []
    for char, info in chars.items():
        perks = info.get("perks", []) if isinstance(info, dict) else info
        if name in perks:
            owners.append(char)
    is_common = name in common
    return {"name": name, "owner": ", ".join(owners),
            "kind": "Общий навык" if is_common else "Уникальный навык" if owners else "Навык вне базы",
            "common": is_common, "found": is_common or bool(owners),
            "description": description_for(side, name)}


def reconcile_pins(db, previous_build, locks, next_build, *, respect_owned=False,
                   empty="", rng=None):
    """Mutate next_build['perks'], retaining eligible same-side pins by slot.

    Returns (updated_locks, dropped_pins). Explicit challenge bans,
    owned-perk restrictions and strict perk_pool='own'/'common' are respected.
    No duplicate nonempty perks are created.
    """
    rng = rng or random
    prior = previous_build or {}
    next_perks = list(next_build.get("perks") or [])[:4]
    next_perks += [empty] * (4 - len(next_perks))
    old_perks = list(prior.get("perks") or [])[:4]
    old_perks += [empty] * (4 - len(old_perks))
    old_locks = [bool(locks[i]) if i < len(locks) else False for i in range(4)]
    if not any(old_locks):
        return [False] * 4, 0

    side = next_build.get("side")
    if prior.get("side") != side or side not in ("KILLER", "SURVIVOR"):
        return [False] * 4, sum(old_locks)

    fx = next_build.get("fx") or {}
    if (next_build.get("forbidden") or {}).get("perks") or "perks" in (fx.get("drop") or []):
        return [False] * 4, sum(old_locks)

    common = db.get("killer_common_perks" if side == "KILLER" else "surv_common_perks", [])
    char_source = db.get("killers" if side == "KILLER" else "survivors", {})
    char_data = char_source.get(next_build.get("char"), [])
    own = char_data.get("perks", []) if isinstance(char_data, dict) else char_data
    all_role = set(common)
    for info in char_source.values():
        all_role.update(info.get("perks", []) if isinstance(info, dict) else info)

    mode = fx.get("perk_pool")
    if mode == "common":
        allowed = set(common)
    elif mode == "own":
        allowed = set(own)
    else:
        allowed = all_role
    allowed.difference_update(fx.get("ban_perks") or [])

    if respect_owned:
        owned = db.get("owned", {}).get("killer_perks" if side == "KILLER" else "survivor_perks")
        if owned:
            allowed.intersection_update(owned)

    kept = [False] * 4
    result = [empty] * 4
    used = set()
    dropped = 0
    for i in range(4):
        name = old_perks[i]
        if old_locks[i] and name not in (empty, "", None):
            if name in allowed and name not in used:
                kept[i] = True
                result[i] = name
                used.add(name)
            else:
                dropped += 1
        elif old_locks[i]:
            dropped += 1

    # Prefer freshly generated cards where they do not collide with held perks.
    unused_original = [p for p in next_perks if p not in used and p in allowed and p not in (empty, "", None)]
    for i in range(4):
        if kept[i]:
            continue
        name = next_perks[i]
        if name in unused_original:
            result[i] = name
            used.add(name)
            unused_original.remove(name)
        elif unused_original:
            result[i] = unused_original.pop(0)
            used.add(result[i])
        else:
            remaining = [p for p in allowed if p not in used and p not in (empty, "", None)]
            if remaining:
                chosen = rng.choice(sorted(remaining))
                result[i] = chosen
                used.add(chosen)

    next_build["perks"] = result
    return kept, dropped
