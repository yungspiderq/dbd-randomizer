# -*- coding: utf-8 -*-
"""
dbd_icons_store.py — загрузка и кэш иконок навыков.

Иконки НЕ хранятся в репозитории: это ассеты Behaviour Interactive, а их
перераспределение в публичном репозитории — лишний юридический риск (и +10 МБ
бинарников в git). Вместо этого приложение качает нужные PNG с вики по мере
надобности и кэширует их в `icons_cache/` рядом со скриптом. Кэш добавлен в
.gitignore, так что в коммиты он не попадает.

Модуль не импортирует tkinter: он только кладёт файлы на диск и сообщает,
какие имена стали доступны. Отрисовкой занимается App (см. _icon_photo).
"""
import os
import threading
import urllib.parse
import urllib.request

try:
    import dbd_icons as ICONS
except ImportError:                                   # pragma: no cover
    ICONS = None

UA = {"User-Agent": "DBDRandomizer/2.1 (icons cache; contact: see repository)"}
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
MIN_SIZE = 400                                        # меньше — точно не иконка


class IconStore:
    """Ленивая загрузка иконок в локальный кэш. Потокобезопасна."""

    def __init__(self, cache_dir, enabled=True, timeout=12):
        self.cache_dir = cache_dir
        self.enabled = bool(enabled) and ICONS is not None
        self.timeout = timeout
        self._lock = threading.Lock()
        self._inflight = set()
        self._failed = set()
        if self.enabled:
            try:
                os.makedirs(cache_dir, exist_ok=True)
            except OSError:
                self.enabled = False

    # ---------------------------------------------------------------- пути --
    @staticmethod
    def _maps():
        """Все карты «имя -> файл»: навыки и аддоны."""
        if not ICONS:
            return ()
        return (ICONS.PERK_ICONS, getattr(ICONS, "ADDON_ICONS", {}))

    def filename(self, name):
        """Имя файла в кэше — из URL-карты, с защитой от странных символов."""
        if not ICONS:
            return None
        rel = None
        for mapping in self._maps():
            rel = mapping.get(name)
            if rel:
                break
        if not rel:
            return None
        safe = urllib.parse.quote(rel, safe="._-")
        return safe

    def local_path(self, name):
        fname = self.filename(name)
        if not fname:
            return None
        return os.path.join(self.cache_dir, fname)

    def is_cached(self, name):
        path = self.local_path(name)
        try:
            return bool(path) and os.path.getsize(path) > MIN_SIZE
        except OSError:
            return False

    def missing(self, names):
        return [n for n in names if not self.is_cached(n) and n not in self._failed]

    def stats(self):
        total = 0
        for mapping in self._maps():
            total += len(mapping)
        try:
            have = len([f for f in os.listdir(self.cache_dir) if f.endswith(".png")])
        except OSError:
            have = 0
        return have, total

    # ------------------------------------------------------------- загрузка --
    def fetch_one(self, name):
        """Скачивает одну иконку (навыка ИЛИ аддона). Возвращает путь или None."""
        if not self.enabled:
            return None
        rel = None
        for mapping in self._maps():
            rel = mapping.get(name)
            if rel:
                break
        if not rel:
            return None
        url = ICONS.ICON_BASE + urllib.parse.quote(rel)
        path = self.local_path(name)
        tmp = path + ".part"
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                data = r.read()
            if len(data) < MIN_SIZE or not data.startswith(PNG_MAGIC):
                self._failed.add(name)
                return None
            with open(tmp, "wb") as fh:
                fh.write(data)
            os.replace(tmp, path)
            return path
        except Exception:
            self._failed.add(name)
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except OSError:
                pass
            return None

    def request(self, names, on_ready=None, limit=None):
        """Фоново докачивает отсутствующие иконки.

        on_ready(готовые_имена) вызывается ИЗ РАБОЧЕГО ПОТОКА — вызывающий обязан
        сам перенести обновление UI в главный поток.
        """
        if not self.enabled:
            return
        todo = self.missing([n for n in dict.fromkeys(names) if n])
        if limit:
            todo = todo[:limit]
        with self._lock:
            todo = [n for n in todo if n not in self._inflight]
            self._inflight.update(todo)
        if not todo:
            return
        threading.Thread(target=self._worker, args=(todo, on_ready), daemon=True).start()

    def _worker(self, todo, on_ready):
        ready = []
        try:
            for name in todo:
                if self.fetch_one(name):
                    ready.append(name)
        finally:
            with self._lock:
                self._inflight.difference_update(todo)
        if ready and on_ready:
            try:
                on_ready(ready)
            except Exception:
                pass

    def fetch_all(self, on_progress=None):
        """Массовая докачка всех карт — навыки и аддоны (кнопка «Скачать все иконки»)."""
        if not self.enabled or not ICONS:
            return 0, 0
        names = []
        for mapping in self._maps():
            names += list(mapping)
        todo = self.missing(names)
        done = 0
        for i, name in enumerate(todo, 1):
            if self.fetch_one(name):
                done += 1
            if on_progress and i % 10 == 0:
                on_progress(i, len(todo))
        return done, len(todo)


def pil_available():
    try:
        import PIL                                    # noqa: F401
        from PIL import Image, ImageTk                # noqa: F401
        return True
    except Exception:
        return False
