"""Resolve the new chapter's real Wiki assets at build time.

Never replace an existing cosmetic ID or insert a guessed filename. The
diagnostic JSON is kept separately from the application and contains no images.
"""
from __future__ import annotations

import concurrent.futures
import json
import re
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import dbd_data as DATA
import dbd_icons as ICONS
import dbd_skins as SKINS
from dbd_icons_store import IconStore
from resolve_skins import parse_outfits, parse_coschars, preserve_catalog_ids

API = "https://deadbydaylight.wiki.gg/api.php"
UA = {"User-Agent": "DBDRandomizer/3.2.2 (catalog validation; github.com/yungspiderq/dbd-randomizer)"}
KILLER = "Ужасающий"
SURVIVOR = "Сиенна Шоу"


def api(**params):
    params.update(format="json", formatversion=2)
    request = urllib.request.Request(API + "?" + urllib.parse.urlencode(params), headers=UA)
    with urllib.request.urlopen(request, timeout=12) as response:
        return json.load(response)


def module_text(page):
    result = api(action="parse", page=page, prop="wikitext")
    value = result["parse"]["wikitext"]
    return value if isinstance(value, str) else value["*"]


def checked_file_names(names):
    """Resolve only files that actually have an imageinfo entry."""
    result = {}
    names = sorted(set(n for n in names if n and n.lower().endswith(".png")))
    for start in range(0, len(names), 40):
        batch = names[start:start + 40]
        query = api(action="query", titles="|".join("File:" + n for n in batch),
                    prop="imageinfo", iiprop="url|mime", redirects=1)["query"]
        pages = {p["title"]: p for p in query.get("pages", [])}
        aliases = {n["from"]: n["to"] for n in query.get("normalized", [])}
        aliases.update({n["from"]: n["to"] for n in query.get("redirects", [])})
        for name in batch:
            title = "File:" + name
            for _ in range(4):
                if title not in aliases:
                    break
                title = aliases[title]
            page = pages.get(title) or pages.get(title.replace("_", " "))
            info = (page or {}).get("imageinfo", [])
            if info and info[0].get("mime") == "image/png":
                result[name] = page["title"].removeprefix("File:").replace(" ", "_")
    return result


def portrait_candidates(text):
    entries = dict(re.findall(r'\["([^"]+)"\]\s*=\s*\{[^{}]*?iconFile\s*=\s*"([^"]+)"', text))
    candidates = {
        KILLER: ["K45_TheTerrifier_Portrait.png", "K45_Terrifier_Portrait.png", "K45_Portrait.png"],
        SURVIVOR: ["SurvivorSienna.png", "SurvivorSiennaShaw.png", "S55_Portrait.png"],
    }
    for character, keys in ((KILLER, ("The Terrifier", "Terrifier", "Art The Clown")),
                            (SURVIVOR, ("Sienna Shaw", "Sienna"))):
        for key in keys:
            name = entries.get(key, "")
            if re.search(r"portrait|^survivor", name, re.I):
                candidates[character].insert(0, name)
    return candidates


def prepare_cosmetics(text, available, previous):
    outfits, _ = parse_outfits(text, {45: KILLER}, {55: SURVIVOR})
    try:
        characters = parse_coschars(text, {45: KILLER}, {55: SURVIVOR})
    except ValueError:
        characters = []
    records = [r for r in outfits + characters if r.get("name") and r.get("file") in available]
    for record in records:
        record["file"] = available[record["file"]]
    records.sort(key=lambda r: (r["kind"], r["char"], r["file"]))
    records = preserve_catalog_ids(records, previous)
    return {r["id"]: {"name": r["name"], "char": r["char"], "side": r["side"],
                       "rarity": r["rarity"], "rarity_ru": SKINS.RARITY_RU.get(r["rarity"], ""),
                       "file": r["file"], "kind": r["kind"], "date": r["date"],
                       "wiki_id": r["wiki_id"]}
            for r in records if r["id"] not in previous}


def append_data(path, code):
    with path.open("a", encoding="utf-8") as stream:
        stream.write("\n\n# Verified Terrifier asset overlay generated for this build.\n" + code + "\n")


def main():
    report = {"portraits": {}, "cosmetics": [], "png_checks": {}, "errors": []}
    try:
        candidates = portrait_candidates(module_text("Module:Datatable/Icons"))
    except Exception as exc:
        candidates = portrait_candidates("")
        report["errors"].append("Icons module: " + str(exc))
    try:
        actual = checked_file_names(n for values in candidates.values() for n in values)
        for name, values in candidates.items():
            resolved = next((actual[n] for n in values if n in actual), None)
            if resolved:
                mapping = "KILLER_PORTRAITS" if name == KILLER else "SURVIVOR_PORTRAITS"
                append_data(ROOT / "dbd_icons.py", f"{mapping}[{name!r}] = {resolved!r}")
                getattr(ICONS, mapping)[name] = resolved
                report["portraits"][name] = resolved
    except Exception as exc:
        report["errors"].append("Portrait lookup: " + str(exc))
    try:
        source = module_text("Module:Datatable/Cosmetics")
        outfits, _ = parse_outfits(source, {45: KILLER}, {55: SURVIVOR})
        try:
            chars = parse_coschars(source, {45: KILLER}, {55: SURVIVOR})
        except ValueError:
            chars = []
        available = checked_file_names(r["file"] for r in outfits + chars)
        records = prepare_cosmetics(source, available, SKINS.SKINS_BY_ID)
        if records:
            by_character = {}
            for ident, row in records.items():
                by_character.setdefault(row["char"], []).append(ident)
            file_map = {f"skin:{ident}": row["file"] for ident, row in records.items()}
            code = f"SKINS_BY_ID.update({records!r})\n"
            code += f"for _char, _ids in {by_character!r}.items():\n    CHAR_SKINS.setdefault(_char, []).extend(_ids)\n"
            code += f"SKIN_FILES.update({file_map!r})"
            append_data(ROOT / "dbd_skins.py", code)
            SKINS.SKINS_BY_ID.update(records)
            SKINS.SKIN_FILES.update(file_map)
            report["cosmetics"] = [{"id": ident, **row} for ident, row in records.items()]
    except Exception as exc:
        report["errors"].append("Cosmetic lookup: " + str(exc))

    names = [KILLER, SURVIVOR, DATA.KILLERS[KILLER]["power"]]
    names += DATA.KILLERS[KILLER]["perks"] + DATA.KILLERS[KILLER]["addons"]
    names += DATA.SURVIVORS[SURVIVOR]
    names += ["skin:" + str(row["id"]) for row in report["cosmetics"]]
    with tempfile.TemporaryDirectory() as folder:
        store = IconStore(folder, timeout=8)
        def check(name):
            if not store.filename(name):
                return name, "not mapped"
            try:
                return name, "PNG OK" if store.fetch_one(name) else "download unavailable"
            except Exception as exc:
                return name, "download error: " + str(exc)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            report["png_checks"] = dict(pool.map(check, names))
    path = ROOT / "terrifier-assets-report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"portraits": len(report["portraits"]), "cosmetics": len(report["cosmetics"]),
                      "verified_png": sum(v == "PNG OK" for v in report["png_checks"].values()),
                      "total_png": len(names), "errors": len(report["errors"])}, ensure_ascii=True))


if __name__ == "__main__":
    main()
