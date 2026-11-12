# -*- coding: utf-8 -*-
"""Reproducible, offline catalog audit for DBD Randomizer.

Names must NOT be translated or replaced based on fuzzy similarity. This tool
checks current stored Russian strings and cross-reference coverage, and lists
unconfirmed rows. A clean report is NOT proof of live in-game localization.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from collections import Counter, defaultdict
from datetime import date

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import dbd_data as DATA
import dbd_skins as SKINS
from addon_names_ru_en import ADDON_RU_EN, ITEM_ADDON_RU_EN
from perk_icon_ids import PERK_ICON_IDS


def _names(spec):
    """Handle both legacy survivor perk lists and character dictionaries."""
    if isinstance(spec, dict):
        return list(spec.get("perks") or [])
    if isinstance(spec, (tuple, list)):
        return list(spec)
    return []


def audit(baseline=None):
    errors = []
    warnings = []
    skin_rows = SKINS.SKINS_BY_ID
    memberships = defaultdict(list)
    for character, ids in SKINS.CHAR_SKINS.items():
        for ident in ids:
            memberships[ident].append(character)
            if ident not in skin_rows:
                errors.append("skin reference missing: %s / %s" % (character, ident))
    missing_ru = []
    suspicious = []
    for ident, info in sorted(skin_rows.items()):
        char = info.get("char")
        name = info.get("name")
        label = info.get("name_ru") or ""
        if not isinstance(name, str) or not name.strip():
            errors.append("skin with empty English name: %s" % ident)
        if char not in SKINS.CHAR_SKINS:
            errors.append("skin references unknown character: %s / %s" % (ident, char))
        if memberships[ident] != [char]:
            errors.append("skin must belong to one matching character: %s / %s" % (ident, memberships[ident]))
        if label:
            if label != label.strip() or len(label) > 100:
                suspicious.append({"id": ident, "character": char, "ru": label, "issue": "suspicious whitespace/length"})
        else:
            missing_ru.append({"id": ident, "character": char, "english": name,
                               "type": info.get("kind"), "file": info.get("file") or ""})
    if baseline:
        old = baseline.get("skins", {})
        for ident, prev in old.items():
            current = skin_rows.get(int(ident))
            if current is None:
                errors.append("previous skin ID missing: " + str(ident))
                continue
            if prev.get("char") != current.get("char") or prev.get("side") != current.get("side"):
                errors.append("skin ID reassigned to another character: " + str(ident))
            if prev.get("name_ru") and not current.get("name_ru"):
                errors.append("verified RU name lost for skin ID " + str(ident))

    perk_missing = {}
    perk_total = {}
    perk_bad = []
    for side, chars, common in (
        ("KILLER", DATA.KILLERS, DATA.KILLER_COMMON_PERKS),
        ("SURVIVOR", DATA.SURVIVORS, DATA.SURV_COMMON_PERKS),
    ):
        perks = set(common)
        for character, spec in chars.items():
            values = _names(spec)
            for name in values:
                if not isinstance(name, str) or not name.strip():
                    perk_bad.append("invalid perk for " + character)
                else:
                    perks.add(name)
        perk_total[side] = len(perks)
        perk_missing[side] = sorted(x for x in perks if x not in PERK_ICON_IDS)
    if perk_bad:
        errors.extend(perk_bad)

    addons = defaultdict(set)
    invalid_addons = []
    for char, spec in DATA.KILLERS.items():
        for name in spec.get("addons") or ():
            if isinstance(name, str) and name.strip():
                if name not in DATA.REMOVED_FROM_GAME:
                    addons[("KILLER", char)].add(DATA.ADDON_RENAMES.get(name, name))
            else:
                invalid_addons.append("invalid add-on for " + char)
    for category, spec in DATA.SURVIVOR_ITEMS.items():
        for name in spec.get("addons") or ():
            if isinstance(name, str) and name.strip():
                if name not in DATA.REMOVED_FROM_GAME:
                    addons[("SURVIVOR", category)].add(DATA.ADDON_RENAMES.get(name, name))
            else:
                invalid_addons.append("invalid add-on for " + category)
    if invalid_addons:
        errors.extend(invalid_addons)

    missing_addon_mapping = {}
    addon_count = {}
    for (side, char), names in sorted(addons.items()):
        translations = (ADDON_RU_EN if side == "KILLER" else ITEM_ADDON_RU_EN).get(char, {})
        missing = sorted(x for x in names if x not in translations)
        if missing:
            missing_addon_mapping[side + ":" + char] = missing
        addon_count[side + ":" + char] = len(names)
    translated = len(skin_rows) - len(missing_ru)
    by_char = Counter(x["character"] for x in missing_ru)
    result = {
        "source": {
            "cosmetics_game_version": getattr(SKINS, "GAME_VERSION", "unknown"),
            "cosmetics_source_stamp": getattr(SKINS, "DATA_STAMP", "unknown"),
            "perks_addons_version": getattr(DATA, "VERSION", "unknown"),
            "skin_ru_source": "dead-by-daylight.fandom.com/ru",
            "cosmetics_source": "deadbydaylight.wiki.gg",
            "reference_note": "Russian names are checked against committed source maps, not the live DBD client.",
        },
        "skins": {
            "total": len(skin_rows), "with_russian": translated, "without_russian": len(missing_ru),
            "russian_percentage": round(100 * translated / len(skin_rows), 2) if skin_rows else 0.0,
            "missing_by_character": dict(by_char.most_common()),
            "missing_records": missing_ru,
            "suspicious_records": suspicious,
        },
        "perks": {
            "distinct_by_side": perk_total,
            "missing_in_ru_icon_reference": perk_missing,
            "reference_note": "Presence in icon map does not prove the spelling in the current game client.",
        },
        "addons": {
            "playable_count_by_owner": addon_count,
            "missing_in_ru_en_reference": missing_addon_mapping,
            "missing_mapping_count": sum(map(len, missing_addon_mapping.values())),
            "reference_note": "Name map is historical; re-check questionable spellings with the Russian game client.",
        },
        "errors": errors,
        "warnings": warnings,
    }
    return result


def baseline_snapshot():
    return {"skins": {
        str(ident): {"char": info.get("char"), "side": info.get("side"), "name_ru": info.get("name_ru", "")}
        for ident, info in SKINS.SKINS_BY_ID.items()
    }}


def markdown(report):
    skin = report["skins"]
    perks = report["perks"]
    addons = report["addons"]
    src = report["source"]
    lines = [
        "# DBD Randomizer — аудит русской локализации",
        "",
        "## Источники и версия",
        "",
        "- Cosmetics wiki.gg: " + str(src["cosmetics_game_version"]) + ", снимок " + str(src["cosmetics_source_stamp"]),
        "- Перки/аддоны в приложении: " + str(src["perks_addons_version"]),
        "- RU-наборы: русская Dead by Daylight Wiki (статьи о наборах одежды и кастомизации)",
        "",
        "## Покрытие",
        "",
        "- Наборы и скины: **%s**, есть RU-название у **%s** (%.2f%%), без RU — **%s**."
        % (skin["total"], skin["with_russian"], skin["russian_percentage"], skin["without_russian"]),
        "- Навыки: %s убийц, %s выживших; нет сопоставления с RU-картой иконок: %s / %s."
        % (perks["distinct_by_side"]["KILLER"], perks["distinct_by_side"]["SURVIVOR"],
           len(perks["missing_in_ru_icon_reference"]["KILLER"]),
           len(perks["missing_in_ru_icon_reference"]["SURVIVOR"])),
        "- Аддоны: без RU→EN сопоставления в исходных справочниках: **%s**."
        % addons["missing_mapping_count"],
        "",
        "## Важно",
        "",
        "Аудит проверяет структуру и полноту сопоставлений **в репозитории**.",
        "Он не подтверждает каждый перевод в актуальном русскоязычном клиенте игры.",
        "Несопоставленные записи остаются с оригинальным названием — без выдуманного перевода.",
        "",
        "## Скины без русского названия (по персонажам)",
        "",
    ]
    for char, count in skin["missing_by_character"].items():
        lines.append("- %s: %s" % (char, count))
    lines.extend(["", "## Навыки без RU-карты иконок", ""])
    for side in ("KILLER", "SURVIVOR"):
        names = perks["missing_in_ru_icon_reference"][side]
        lines.append("- %s (%s): %s" % (side, len(names), ", ".join(names) if names else "нет"))
    lines.extend(["", "## Аддоны без RU→EN сопоставления", ""])
    for group, names in addons["missing_in_ru_en_reference"].items():
        lines.append("- %s (%s): %s" % (group, len(names), ", ".join(names)))
    lines.extend(["", "## Ошибки структуры", ""])
    lines.extend("- " + item for item in report["errors"])
    if not report["errors"]:
        lines.append("Нет.")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--baseline", type=Path, help="Previous exported baseline JSON for regression guards")
    ap.add_argument("--export-baseline", type=Path, help="Save current skin IDs and Russian names for later comparison")
    ap.add_argument("--json", type=Path, help="Write machine-readable catalog report")
    ap.add_argument("--markdown", type=Path, help="Write a human-readable catalog report")
    ap.add_argument("--strict", action="store_true", help="Fail when structural integrity or RU regression errors appear")
    opts = ap.parse_args(argv)
    baseline = json.loads(opts.baseline.read_text(encoding="utf-8")) if opts.baseline else None
    result = audit(baseline)
    if opts.export_baseline:
        opts.export_baseline.parent.mkdir(parents=True, exist_ok=True)
        opts.export_baseline.write_text(json.dumps(baseline_snapshot(), ensure_ascii=False), encoding="utf-8")
    if opts.json:
        opts.json.parent.mkdir(parents=True, exist_ok=True)
        opts.json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if opts.markdown:
        opts.markdown.parent.mkdir(parents=True, exist_ok=True)
        opts.markdown.write_text(markdown(result), encoding="utf-8")
    print("Skins: %s RU / %s total. Missing perk icon references: %s. Add-on mapping gaps: %s. Errors: %s."
          % (result["skins"]["with_russian"], result["skins"]["total"],
             sum(len(v) for v in result["perks"]["missing_in_ru_icon_reference"].values()),
             result["addons"]["missing_mapping_count"], len(result["errors"])))
    if result["errors"]:
        print("\n".join(result["errors"][:25]), file=sys.stderr)
    return 1 if opts.strict and result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
