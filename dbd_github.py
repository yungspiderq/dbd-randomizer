# -*- coding: utf-8 -*-
"""
dbd_github.py — сетевой слой DBD Randomizer.

Три независимые задачи:
  1. Билды сообщества  — чтение/публикация community_builds.json через Contents API.
  2. Автообновление    — проверка релизов и безопасная замена файлов приложения.
  3. Мелкие утилиты    — форматирование карточки билда, сравнение версий.

Модуль не импортирует tkinter и не трогает мышь/клавиатуру, поэтому полностью
тестируется headless (см. smoke_test.py).

БЕЗОПАСНОСТЬ АВТООБНОВЛЕНИЯ
---------------------------
Исходная v1.1.1 качала `dbd_randomizer.py` из ветки main и перезаписывала им саму
себя: любой, кто получил право записи в репозиторий, мог мгновенно разослать свой
код всем пользователям. Здесь это закрыто:
  * файлы берутся из ТЕГА РЕЛИЗА, а не из main (allow_branch — отдельная настройка);
  * скачиваются ВСЕ модули сразу во временные файлы и проверяются до замены —
    состояние «половина файлов новая, половина старая» невозможно;
  * проверка содержимого: размер + обязательный маркер в каждом файле;
  * старые файлы сохраняются как `.bak`;
  * пользователь видит версию, размер и SHA-256 каждого файла ДО применения;
  * конфиг, координаты и сохранённый токен не перезаписываются никогда.
"""

import base64
import hashlib
import json
import os
import random
import re
import time
import urllib.error
import urllib.request

APP_VERSION = "2.14.2"
GITHUB_REPO = "yungspiderq/dbd-randomizer"
API = "https://api.github.com"

BUILDS_FILE_NAME = "community_builds.json"
# Анонимный канал публикации (без токена GitHub): Firebase Realtime Database.
# Проект создаёт владелец (бесплатно, без карты); правила дают всем чтение и
# СОЗДАНИЕ записей (create-only), поэтому чужие билды нельзя править или удалять.
# Запись = append (POST с push-ключом) — гонок с перезаписью чужих данных нет.
FIREBASE_BASE_DEFAULT = "https://dbdbuilds-41c0c-default-rtdb.firebaseio.com"
FIREBASE_NODE = "community_builds"
BUILDS_LOCAL_CACHE = "community_builds_cache.json"
MAX_COMMUNITY_BUILDS = 200
UPDATE_CHECK_INTERVAL_MS = 30 * 60 * 1000

# Файлы приложения. REQUIRED обязан быть в релизе (иначе обновление отклоняется),
# OPTIONAL скачивается, если есть: так релиз v1.x (один файл) не блокирует проверку,
# а релиз v2.x обновляет все модули сразу.
REQUIRED_FILES = ("dbd_randomizer.py", "dbd_data.py", "dbd_github.py",
                  "dbd_icons.py", "dbd_icons_store.py", "dbd_skins.py")
OPTIONAL_FILES = ("requirements.txt",)
UPDATABLE_FILES = REQUIRED_FILES + OPTIONAL_FILES
# Маркер, который обязан присутствовать в скачанном файле (защита от подмены на HTML/пустышку).
SANITY_MARKERS = {
    "dbd_randomizer.py": "def main(",
    "dbd_data.py": "KILLERS",
    "dbd_github.py": "APP_VERSION",
    "dbd_icons.py": "PERK_ICONS",
    "dbd_icons_store.py": "class IconStore",
    "dbd_skins.py": "SKINS_BY_ID",
    "requirements.txt": None,
}
MIN_FILE_SIZE = 20


class UpdateError(RuntimeError):
    pass


# ============================================================================
# HTTP
# ============================================================================
def _http_request(url, data=None, timeout=10, headers=None, method=None):
    """GET без data; POST/PUT/PATCH с JSON-телом. К запросам добавляется anti-cache параметр."""
    h = {"User-Agent": f"DBDRandomizer/{APP_VERSION}"}
    if headers:
        h.update(headers)
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        h["Content-Type"] = "application/json"
    sep = "&" if "?" in url else "?"
    req = urllib.request.Request(url + sep + "_=" + str(int(time.time() * 1000)),
                                 data=body, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _http_get(url, timeout=8, headers=None):
    return _http_request(url, timeout=timeout, headers=headers)


def gh_headers(token=None):
    h = {"User-Agent": f"DBDRandomizer/{APP_VERSION}", "Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = "Bearer " + token
    return h


def resolve_token(cfg=None):
    """Токен из окружения DBD_UPDATE_TOKEN или из конфига (вкладка «БИЛДЫ»)."""
    tok = os.environ.get("DBD_UPDATE_TOKEN", "")
    if tok:
        return tok.strip()
    if isinstance(cfg, dict):
        pub = cfg.get("publish") or {}
        tok = str(pub.get("gh_token", "") or "").strip()
        if tok:
            return tok
        # совместимость со старым плоским конфигом
        tok = str(cfg.get("gh_token", "") or "").strip()
    return tok


def _get_remote_file_b64(path, token=None, ref="main"):
    """(content_bytes, sha) файла из указанной ветки/тега или (None, None)."""
    try:
        url = f"{API}/repos/{GITHUB_REPO}/contents/{path}?ref={ref}"
        data = json.loads(_http_get(url, headers=gh_headers(token)).decode("utf-8"))
        return base64.b64decode(data["content"]), data.get("sha")
    except Exception:
        return None, None


# ============================================================================
# ВЕРСИИ
# ============================================================================
def version_tuple(v):
    try:
        return tuple(int(x) for x in str(v).strip().lstrip("vV").split(".")[:3])
    except Exception:
        return (0,)


def get_latest_release_info(token=None):
    """(tag, notes) последнего релиза; если релизов нет — максимальный тег; иначе None."""
    try:
        data = json.loads(_http_get(f"{API}/repos/{GITHUB_REPO}/releases/latest",
                                    headers=gh_headers(token)).decode("utf-8"))
        tag = data.get("tag_name", "")
        if tag:
            return tag, data.get("body", "") or ""
    except Exception:
        pass
    try:                                            # запасной вариант: просто теги
        tags = json.loads(_http_get(f"{API}/repos/{GITHUB_REPO}/tags",
                                    headers=gh_headers(token)).decode("utf-8"))
        best = None
        for t in tags if isinstance(tags, list) else []:
            name = t.get("name", "")
            if version_tuple(name) > version_tuple(best or "0"):
                best = name
        if best:
            return best, "Описание релиза отсутствует (найден только тег)."
    except Exception:
        pass
    return None


# ============================================================================
# БИЛДЫ СООБЩЕСТВА
# ============================================================================
def load_community_builds(cache_dir="."):
    """Читает общий файл билдов из GitHub; при сетевой ошибке — локальный кэш.

    Возвращает (builds, online).
    """
    cache_path = os.path.join(cache_dir, BUILDS_LOCAL_CACHE)
    try:
        content, _ = _get_remote_file_b64(BUILDS_FILE_NAME)
        if content:
            builds = json.loads(content.decode("utf-8"))
            if isinstance(builds, list):
                try:
                    with open(cache_path, "w", encoding="utf-8") as f:
                        json.dump(builds, f, ensure_ascii=False)
                except OSError:
                    pass
                return builds, True
        return [], True                                # 404 — никто ещё не публиковал
    except Exception:
        pass
    try:
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return (data if isinstance(data, list) else []), False
    except (OSError, ValueError):
        pass
    return [], False


def make_build_payload(side, char, power_or_item, addons, perks, author, version=APP_VERSION,
                       title="", description="", skin=""):
    """Словарь билда в ТОМ ЖЕ формате, что и v1.1.x — старые публикации читаются как есть.

    v2.3: необязательные ``title`` и ``description`` (конструктор билдов). Старые
    клиенты их просто не показывают, новые — рисуют в карточке и списке.
    """
    addons = list(addons or [])
    while len(addons) < 2:
        addons.append("—")
    out = {
        "id": f"{int(time.time())}-{random.randint(1000, 9999)}",
        "app_version": version,
        "date": time.strftime("%d.%m.%Y"),
        "author": (author or "anon")[:30],
        "side": side,
        "char": char,
        "power_or_item": power_or_item,
        "addons": addons[:2],
        "perks": list(perks or [])[:4],
    }
    title = (title or "").strip()
    description = (description or "").strip()
    if title:
        out["title"] = title[:60]
    if description:
        out["description"] = description[:300]
    if (skin or "").strip():
        out["skin"] = str(skin).strip()[:60]
    return out


def publish_build_to_github(build, token):
    """Публикует билд в общий community_builds.json через Contents API.

    Читает текущий файл, добавляет билд в начало, шлёт PUT c sha (защита от
    перезаписи чужих данных) или POST, если файла ещё нет. Возвращает (ok, message).
    """
    if not token:
        return False, "Не указан токен GitHub. Сохраните его в настройках вкладки «БИЛДЫ»."
    headers = gh_headers(token)
    url = f"{API}/repos/{GITHUB_REPO}/contents/{BUILDS_FILE_NAME}"
    message = f"community: +{build.get('author', 'anon')} '{build.get('char', '?')}'"

    def _encode(builds):
        return base64.b64encode(json.dumps(builds, ensure_ascii=False, indent=1).encode("utf-8")).decode("ascii")

    try:
        builds, sha = [], None
        try:
            data = json.loads(_http_get(url, headers=headers).decode("utf-8"))
            builds = json.loads(base64.b64decode(data["content"]).decode("utf-8"))
            sha = data.get("sha")
            if not isinstance(builds, list):
                builds = []
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
        except ValueError:
            builds = []

        if any(b.get("id") == build.get("id") for b in builds if isinstance(b, dict)):
            return True, "Такой билд уже опубликован."
        builds.insert(0, build)
        builds = builds[:MAX_COMMUNITY_BUILDS]

        payload = {"message": message, "content": _encode(builds)}
        if sha:
            payload["sha"] = sha
        try:
            _http_request(url, data=payload, method="PUT" if sha else "POST", headers=headers)
        except urllib.error.HTTPError as exc:
            if exc.code == 409:                       # гонка: файл изменили, один повтор
                data = json.loads(_http_get(url, headers=headers).decode("utf-8"))
                builds = json.loads(base64.b64decode(data["content"]).decode("utf-8"))
                if any(b.get("id") == build.get("id") for b in builds if isinstance(b, dict)):
                    return True, "Такой билд уже опубликован."
                builds.insert(0, build)
                payload = {"message": message, "content": _encode(builds[:MAX_COMMUNITY_BUILDS]),
                           "sha": data.get("sha")}
                _http_request(url, data=payload, method="PUT", headers=headers)
            elif exc.code == 401:
                return False, "Токен недействителен или отозван. Создайте новый с правом Contents: Write."
            elif exc.code == 403:
                return False, "У токена нет прав на запись (нужен fine-grained Contents: Read and write или classic repo)."
            elif exc.code == 404:
                return False, f"Репозиторий или файл не найдены: {GITHUB_REPO}/{BUILDS_FILE_NAME}"
            else:
                return False, f"Ошибка GitHub API: HTTP {exc.code}"
        return True, "Билд опубликован! Он появится у всех пользователей после обновления списка."
    except Exception as exc:
        return False, f"Не удалось опубликовать: {exc}"


def load_firebase_builds(base=FIREBASE_BASE_DEFAULT, node=FIREBASE_NODE):
    """Читает билды из анонимного канала Firebase. None = канал не настроен/сеть лежит."""
    if not base:
        return None
    try:
        raw = _http_get(f"{base.rstrip('/')}/{node}.json", timeout=12)
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return None
    return _parse_firebase(data)


def _parse_firebase(data):
    """Сторонний мусор (служебные/тестовые записи без id/char) в список не попадает."""
    if not data or not isinstance(data, dict):
        return []
    items = [v for v in data.values()
             if isinstance(v, dict) and v.get("id") and v.get("char")]
    items.sort(key=lambda b: str(b.get("id", "")))
    return items[::-1]                                # свежие сверху


def publish_build_firebase(build, base=FIREBASE_BASE_DEFAULT, node=FIREBASE_NODE, tries=2):
    """Публикация БЕЗ токена: append-only POST в Firebase RTDB.

    Create-only правила не дают перезаписать чужие записи; повторная публикация
    того же id отклоняется на клиенте после чтения списка.
    """
    if not base:
        return False, ("Анонимный канал не настроен: владелец проекта должен создать "
                       "бесплатный Firebase-проект и вписать его URL в настройки "
                       "(или дождаться релиза с прошитым URL).")
    url = f"{base.rstrip('/')}/{node}.json"
    last = ""
    for _ in range(max(1, tries)):
        existing = load_firebase_builds(base, node)
        if existing and any(b.get("id") == build.get("id") for b in existing):
            return True, "Такой билд уже опубликован."
        try:
            resp = _http_request(url, data=build, method="POST")
            key = json.loads(resp.decode("utf-8")).get("name")
        except Exception as exc:
            last = str(exc)
            continue
        if not key:
            last = "Firebase не вернул ключ записи"
            continue
        check = load_firebase_builds(base, node) or []
        if any(b.get("id") == build.get("id") for b in check):
            return True, ("Билд опубликован в анонимном облаке (Firebase). "
                          "Он виден всем, кто читает список из этого канала.")
        last = "запись не подтвердилась при повторном чтении"
    return False, f"Не удалось опубликовать анонимно: {last}"


def format_build_text(b):
    """Карточка билда для копирования в буфер обмена (формат v1.1.x)."""
    side_icon = "👹" if b.get("side") == "KILLER" else "👤"
    addons = list(b.get("addons") or ["—", "—"])
    lines = [
        f"=== DBD БИЛД {side_icon} ===",
    ]
    if (b.get("title") or "").strip():
        lines.append(f"Название: {b['title']}")
    lines.append(f"Автор: {b.get('author', '—')} | {b.get('date', '')}")
    if (b.get("description") or "").strip():
        lines.append(f"Описание: {b['description']}")
    if (b.get("skin") or "").strip():
        lines.append(f"Внешность: {b['skin']}")
    lines += [
        f"Персонаж: {b.get('char', '—')}",
        f"{'Сила' if b.get('side') == 'KILLER' else 'Предмет'}: {b.get('power_or_item', '—')}",
        "Аддоны:",
        f"  • {addons[0] if len(addons) > 0 else '—'}",
        f"  • {addons[1] if len(addons) > 1 else '—'}",
        "Навыки:",
    ]
    lines += [f"  {i}. {p}" for i, p in enumerate(b.get("perks", []), 1)]
    return "\n".join(lines)


# ============================================================================
# АВТООБНОВЛЕНИЕ
# ============================================================================
def _verify_bundle(bundle):
    """Проверяет скачанные файлы. Возвращает список описаний для диалога."""
    info = []
    for name, content in bundle.items():
        if not content or len(content) < MIN_FILE_SIZE:
            raise UpdateError(f"{name}: пустой или слишком маленький файл ({len(content or b'')} байт)")
        marker = SANITY_MARKERS.get(name)
        text = content.decode("utf-8", "replace")
        if marker and marker not in text:
            raise UpdateError(f"{name}: не найден маркер «{marker}» — файл не похож на ожидаемый")
        if name.endswith(".py"):
            try:
                compile(text, name, "exec")           # синтаксис до записи на диск
            except SyntaxError as exc:
                raise UpdateError(f"{name}: синтаксическая ошибка в скачанном файле ({exc.msg}, строка {exc.lineno})")
        info.append({
            "name": name,
            "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        })
    return info


def check_update(current_version=APP_VERSION, token=None, allow_branch=False):
    """Возвращает dict(tag, notes, ref) если есть обновление, иначе None.

    allow_branch=True разрешает брать файлы из main, когда релизов ещё нет.
    """
    info = get_latest_release_info(token)
    if info:
        tag, notes = info
        if version_tuple(tag) > version_tuple(current_version):
            return {"tag": tag, "notes": notes, "ref": tag}
        return None
    if not allow_branch:
        return None
    try:                                                # релизов нет: смотрим версию в main
        content, _ = _get_remote_file_b64("dbd_randomizer.py", token=token, ref="main")
        raw = content.decode("utf-8", "replace") if content else ""
        m = re.search(r'APP_VERSION\s*=\s*"([\d.]+)"', raw)
        if m and version_tuple(m.group(1)) > version_tuple(current_version):
            return {"tag": "v" + m.group(1),
                    "notes": "Обновление найдено в ветке main (релизы не опубликованы).",
                    "ref": "main"}
    except Exception:
        pass
    return None


def download_update(ref, token=None, required=REQUIRED_FILES, optional=OPTIONAL_FILES):
    """Скачивает файлы приложения из ref и проверяет их, НИЧЕГО не записывая на диск.

    Возвращает (bundle, info, missing_optional). Бросает UpdateError, если не удалось
    получить или проверить обязательный файл (по умолчанию — dbd_randomizer.py).
    """
    bundle, missing = {}, []
    for name in tuple(required) + tuple(optional):
        content, _sha = _get_remote_file_b64(name, token=token, ref=ref)
        if content is None:
            missing.append(name)
            continue
        bundle[name] = content
    absent = [n for n in required if n in missing]
    if absent:
        raise UpdateError("не удалось скачать обязательные файлы: " + ", ".join(absent))
    return bundle, _verify_bundle(bundle), [n for n in optional if n in missing]


def apply_update(bundle, app_dir):
    """Заменяет файлы приложения. Старые версии сохраняются рядом как `.bak`.

    Возвращает список имён изменённых файлов. Конфиг и токен не затрагиваются.
    """
    changed, backups = [], []
    for name, content in bundle.items():
        path = os.path.join(app_dir, name)
        old = None
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    old = f.read()
            except OSError:
                old = None
        if old == content:
            continue
        tmp = path + ".new"
        try:
            with open(tmp, "wb") as f:
                f.write(content)
            if old is not None:
                try:
                    with open(path + ".bak", "wb") as f:
                        f.write(old)
                    backups.append(name + ".bak")
                except OSError:
                    pass
            os.replace(tmp, path)
            changed.append(name)
        except OSError as exc:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except OSError:
                pass
            raise UpdateError(f"не удалось записать {name}: {exc}")
    return changed
