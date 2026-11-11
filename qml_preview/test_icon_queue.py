"""Regression tests for throttled Qt icon downloads (no network)."""
import threading
import time
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from icon_queue import IconDownloadQueue


class FakeStore:
    enabled = True
    def __init__(self):
        self.finished = set()
        self.calls = []
        self.lock = threading.Lock()
        self.inflight = 0
        self.peak = 0

    def filename(self, key):
        return key + ".png" if key != "unknown" else None

    def is_cached(self, key):
        return key in self.finished

    def _sprite(self):
        return None

    def fetch_one(self, key):
        with self.lock:
            self.calls.append(key)
            self.inflight += 1
            self.peak = max(self.peak, self.inflight)
        time.sleep(0.015)
        with self.lock:
            self.inflight -= 1
            if key != "failed":
                self.finished.add(key)
        return None if key == "failed" else "/test/" + key + ".png"


class IconQueueTests(unittest.TestCase):
    def test_deduplicates_and_limits_workers(self):
        store = FakeStore()
        events = []
        signal = threading.Event()
        def notify(key, successful):
            events.append((key, successful))
            if len(events) == 25:
                signal.set()
        workers = IconDownloadQueue(store, notify, workers=3)
        try:
            for i in range(25):
                self.assertTrue(workers.request("icon_" + str(i)))
                self.assertFalse(workers.request("icon_" + str(i)))
            self.assertTrue(signal.wait(5), "Icon requests did not complete")
            self.assertEqual(len(store.calls), 25)
            self.assertLessEqual(store.peak, 3)
            self.assertEqual(workers.worker_count, 3)
            self.assertEqual(workers.pending_count, 0)
            self.assertFalse(workers.request("icon_0"))
        finally:
            workers.close()

    def test_invalid_and_failed_icon_do_not_spawn_repeated_downloads(self):
        store = FakeStore()
        failed = threading.Event()
        worker = IconDownloadQueue(store, lambda key, ok: failed.set(), workers=2)
        try:
            self.assertFalse(worker.request("unknown"))
            self.assertTrue(worker.request("failed"))
            self.assertTrue(failed.wait(2))
            self.assertFalse(worker.request("failed"))
            self.assertEqual(store.calls.count("failed"), 1)
        finally:
            worker.close()

    def test_close_rejects_new_requests(self):
        store = FakeStore()
        worker = IconDownloadQueue(store, lambda *_: None)
        worker.close()
        self.assertFalse(worker.request("something"))


if __name__ == "__main__":
    unittest.main()
