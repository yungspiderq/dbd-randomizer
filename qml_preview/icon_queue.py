"""Bounded asynchronous icon downloading for the Qt frontend.

The old QML binding could spawn a worker thread per image. This queue caps
active workers, deduplicates names, and serializes portrait-sprite cropping.
No network work ever runs on the Qt GUI thread.
"""
from __future__ import annotations

import queue
import threading


class IconDownloadQueue:
    def __init__(self, store, on_processed, workers=3):
        self._store = store
        self._on_processed = on_processed
        self._queue = queue.Queue()
        self._lock = threading.Lock()
        self._sprite_lock = threading.Lock()
        self._pending = set()
        self._failed = set()
        self._closed = False
        self._threads = [
            threading.Thread(target=self._worker, daemon=True, name="dbd-icon-worker-" + str(i))
            for i in range(max(1, min(4, int(workers))))
        ]
        for thread in self._threads:
            thread.start()

    def request(self, key):
        if not key or not self._store.enabled or not self._store.filename(key):
            return False
        if self._store.is_cached(key):
            return False
        with self._lock:
            if self._closed or key in self._pending or key in self._failed:
                return False
            self._pending.add(key)
        self._queue.put(key)
        return True

    def _worker(self):
        while True:
            name = self._queue.get()
            try:
                if name is None:
                    return
                try:
                    # Several killer portraits share one local sprite sheet.
                    sprite = self._store._sprite()
                    if sprite and name in sprite.get("ports", {}):
                        with self._sprite_lock:
                            path = self._store.fetch_one(name)
                    else:
                        path = self._store.fetch_one(name)
                    success = bool(path)
                except Exception:
                    success = False
                with self._lock:
                    self._pending.discard(name)
                    if not success:
                        self._failed.add(name)
                try:
                    self._on_processed(name, success)
                except Exception:
                    pass
            finally:
                self._queue.task_done()

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
        for _ in self._threads:
            self._queue.put(None)

    @property
    def pending_count(self):
        with self._lock:
            return len(self._pending)

    @property
    def worker_count(self):
        return len(self._threads)
