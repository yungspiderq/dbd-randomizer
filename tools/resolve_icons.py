# -*- coding: utf-8 -*-
"""Сопоставляет русские имена навыков с реальными файлами иконок на wiki.gg.

Запуск:  python tools/resolve_icons.py          # отчёт + генерация dbd_icons.py
Сеть:    нужен доступ к https://deadbydaylight.wiki.gg/api.php
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from perk_icon_ids import PERK_ICON_IDS  # noqa: E402

API = "https://deadbydaylight.wiki.gg/api.php"
UA = {"User-Agent": "DBDiconFetcher/1.0 (contact: dev@example.com)"}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PREFIXES = ("IconPerks_", "IconPerk_", "IconsPerks_", "IconsPerks ", "IconPerks ",
            "T_UI_iconsPerks_", "T_UI_iconsAddons_", "IconPerk")
STRIP_HEAD = ("tuiperksiconperks", "tuierksiconperks", "iconperks", "iconperk",
              "dbdkillerperk", "dbdsurvivorperk", "dbdkillperk", "dbdsurvperk",
              "dbdperk", "icperks", "icperk", "icg", "ic", "adb", "dbd")
STRIP_TAIL = ("green", "manual", "gr", "g", "icon2", "2x", "png")

# Там, где имя файла на wiki.gg образовано от английского названия, а не от
# внутреннего ID старой вики.
# Проверено вручную через API: файл существует, но нормализация ID его не берёт.
MANUAL_FILES = {
    "Быстрый гамбит": "IconPerks_quickGambit.png",
    "Гибель Франклина": "IconPerks_franklinsDemise.png",
    "Разбитые надежды": "IconPerks_shatteredHope.png",
    "Секущий крюк: пучина ярости": "IconPerks_scourgeHookFloodsOfRage.png",
    "Состояние потока": "IconsPerks_FlowState.png",
    "Место для нас": "IconsPerks_aPlaceForUs.png",
    "На пять шагов впереди": "IconsPerks_FiveMovesAhead.png",
    # имена файлов выяснены через страницы навыков (EN-названия отличаются от внутренних ID)
    "Барбекю и чили": "IconPerks_barbecueAndChilli.png",     # EN Barbecue & Chilli
    "Жестокая изоляция": "IconPerks_cruelLimits.png",        # EN Cruel Limits (страница Cruel Confinement -> редирект)
    "Ненависть": "IconPerks_rancor.png",                     # EN Rancor (страница Hatred -> редирект)
}

# Совсем не находится по имени файла — берём иконку со страницы навыка.
PAGE_FALLBACK = {
    "Барбекю и чили": "BBQ & Chili",
    "Ненависть": "Hatred",
    "Жестокая изоляция": "Cruel Confinement",
}

EN_OVERRIDES = {
    "Нетерпимость": "Agitation", "Зверская сила": "BrutalStrength",
    "Пугающее присутствие": "UnnervingPresence",
    "Детище тьмы": "Shadowborn", "Ищейка": "Bloodhound", "Хищник": "Predator",
    "Стойкий": "Enduring", "Детище света": "Lightborn", "Умелец": "Tinkerer",
    "Зов медсестры": "ANursesCalling",
    "Оставьте лучшее напоследок": "SaveBestForLast", "Угасающий свет": "DyingLight",
    "Поиграть со своей жертвой": "PlayWithYourFood",
    "Порча: погибель": "HexRuin", "Порча: пожирание надежды": "HexDevourHope",
    "Порча: третья печать": "HexTheThirdSeal",
    "Территориальный императив": "TerritorialImperative",
    "Порча: колыбельная охотницы": "HexHuntressLullaby", "Хищный зверь": "BeastOfPrey",
    "Яркое пламя": "FireUp", "Помни меня": "RememberMe", "Кровавый смотритель": "BloodWarden",
    "Ловкое приземление": "BalancedLanding", "Городской бег": "UrbanEvasion",
    "Уроки улиц": "Streetwise",
    "Единственный выживший": "SoleSurvivor", "Решающий удар": "DecisiveStrike",
    "Объект одержимости": "ObjectOfObsession",
    "Туз в рукаве": "AceInTheHole", "Повысить ставки": "UpTheAnte", "Игра в открытую": "OpenHanded",
    "Сострадание": "Empathy", "Сам себе доктор": "SelfCare", "Познания в ботанике": "BotanyKnowledge",
    "Спокойствие духа": "CalmSpirit", "Железная воля": "IronWill", "Крушитель": "Saboteur",
    "Адреналин": "Adrenaline", "Быстрый и тихий": "QuickAndQuiet", "Спринтер": "SprintBurst",
    "Связь": "Bond", "Прояви себя": "ProveThyself", "Лидер": "Leader",
    "Одолженное время": "BorrowedTime", "Оставленный позади": "LeftBehind",
    "Несокрушимый": "Unbreakable",
    "Мы будем жить вечно": "WeAreGonnaLiveForever", "Крепкий орешек": "DeadHard",
    "Без сожаления": "NoMither",
    "Аптекарь": "Pharmacy", "Бессонница": "Vigil", "Проснись": "WakeUp",
    "Выдержка": "Tenacity", "Детективное чутье": "DetectivesHunch",
    "Выслеживание подозреваемого": "Stakeout",
}


def api(**kw):
    kw.setdefault("format", "json")
    url = API + "?" + urllib.parse.urlencode(kw)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


IMAGE_BASE = "https://deadbydaylight.wiki.gg/images/"


def _fetch_allimages(prefix):
    out, cont = [], None
    while True:
        kw = dict(action="query", list="allimages", aiprefix=prefix, ailimit="500")
        if cont:
            kw["aicontinue"] = cont
        d = api(**kw)
        out += [(i["name"], i["url"]) for i in d["query"]["allimages"]]
        if "continue" in d:
            cont = d["continue"]["aicontinue"]
        else:
            return out


def _fetch_category_files(cat="Category:Perk images"):
    out, cont = [], None
    while True:
        kw = dict(action="query", list="categorymembers", cmtitle=cat, cmtype="file", cmlimit="500")
        if cont:
            kw["cmcontinue"] = cont
        d = api(**kw)
        out += [m["title"][5:].replace(" ", "_") for m in d["query"]["categorymembers"]]
        if "continue" in d:
            cont = d["continue"]["cmcontinue"]
        else:
            return out


def fetch_icon_files():
    """Все иконки навыков на wiki.gg: {нормализованное имя: (имя файла, url)}.

    Источники: префиксы allimages (IconPerks_, IconPerk_, T_UI_iconsPerks_) И
    категория "Perk images" — там лежит семейство "IconPerks <id>.png" с пробелом,
    которое по префиксу с подчёркиванием не находится.
    """
    raw = []
    for prefix in PREFIXES:
        raw += _fetch_allimages(prefix)
    for name in _fetch_category_files():
        raw.append((name, IMAGE_BASE + urllib.parse.quote(name)))
    out = {}
    for name, url in raw:
        out.setdefault(norm(name), (name, url))
    return out


def norm(name):
    s = re.sub(r"\.(png|jpg|jpeg)$", "", name, flags=re.I)
    s = re.sub(r"[^A-Za-z0-9]", "", s).lower()
    for head in STRIP_HEAD:
        if s.startswith(head) and len(s) > len(head):
            s = s[len(head):]
            break
    for tail in STRIP_TAIL:
        if s.endswith(tail) and len(s) > len(tail) + 1:
            s = s[: -len(tail)]
            break
    return s


def main():
    files = fetch_icon_files()
    print(f"Файлов иконок на wiki.gg: {len(files)}")

    resolved, missing, fuzzy = {}, [], []
    by_name = {v[0].replace(" ", "_"): v[1] for v in files.values()}

    def page_icon(page_title):
        """Иконка навыка, вытащенная из списка изображений его страницы."""
        try:
            d = api(action="query", titles=page_title, prop="images", imlimit="50")
            pages = d["query"]["pages"]
            for pg in pages.values():
                for im in pg.get("images", []):
                    name = im["title"][5:].replace(" ", "_")
                    if re.search(r"(?i)^(icons?perks|t_ui_iconsperks)", name) and name.endswith(".png"):
                        url = IMAGE_BASE + urllib.parse.quote(name)
                        return url
        except Exception:
            pass
        return None

    for ru, icon_id in sorted(PERK_ICON_IDS.items()):
        if ru in MANUAL_FILES:
            fname = MANUAL_FILES[ru]
            resolved[ru] = by_name.get(fname, IMAGE_BASE + urllib.parse.quote(fname))
            continue
        hit = None
        for key in (norm(icon_id), norm(EN_OVERRIDES.get(ru, ""))):
            if key and key in files:
                hit = files[key]
                break
        if not hit:                       # нечётное сопоставление по похожести
            import difflib
            keys = list(files)
            for probe in {norm(icon_id), norm(EN_OVERRIDES.get(ru, ""))}:
                if not probe:
                    continue
                best, ratio = None, 0.0
                for k in keys:
                    if probe in k or k in probe:
                        r = 0.99
                    else:
                        r = difflib.SequenceMatcher(None, probe, k).ratio()
                    if r > ratio:
                        best, ratio = k, r
                if best and ratio >= 0.80:
                    hit = files[best]
                    fuzzy.append((ru, icon_id, files[best][0], round(ratio, 2)))
                    break
        if hit:
            resolved[ru] = hit[1]
            continue
        if ru in PAGE_FALLBACK:
            url = page_icon(PAGE_FALLBACK[ru])
            if url:
                resolved[ru] = url
                fuzzy.append((ru, icon_id, url.rsplit("/", 1)[-1].split("?")[0], "page"))
                continue
        missing.append((ru, icon_id, EN_OVERRIDES.get(ru, "")))

    print(f"Сопоставлено: {len(resolved)} из {len(PERK_ICON_IDS)} "
          f"({100 * len(resolved) // max(1, len(PERK_ICON_IDS))} %)")
    if fuzzy:
        print(f"\nСопоставлено нечётно ({len(fuzzy)}) — проверить глазами:")
        for ru, iid, fname, ratio in fuzzy:
            print(f"   {ru:<38} id={iid:<22} -> {fname}  ({ratio})")
    if missing:
        print(f"\nНе найдено ({len(missing)}):")
        for ru, iid, en in missing:
            print(f"   {ru:<42} id={iid:<26} en={en}")

    out = os.path.join(ROOT, "dbd_icons.py")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write('# -*- coding: utf-8 -*-\n')
        fh.write('"""Сгенерировано tools/resolve_icons.py — НЕ править вручную.\n\n')
        fh.write('Русское имя навыка -> прямой URL иконки на deadbydaylight.wiki.gg.\n')
        fh.write('Иконки НЕ лежат в репозитории: приложение качает их по мере надобности\n')
        fh.write('и кэширует локально (см. IconStore в dbd_icons_store.py).\n"""\n\n')
        fh.write('ICON_BASE = "https://deadbydaylight.wiki.gg/images/"\n\n')
        fh.write("PERK_ICONS = {\n")
        for ru in sorted(resolved):
            url = resolved[ru]
            fh.write(f"    {ru!r}: {url.rsplit('/', 1)[-1].split('?')[0]!r},\n")
        fh.write("}\n")
    print(f"\nЗаписано: {out}")
    with open(os.path.join(ROOT, "tools", "unresolved.json"), "w", encoding="utf-8") as fh:
        json.dump([{"ru": r, "id": i, "en": e} for r, i, e in missing], fh,
                  ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
