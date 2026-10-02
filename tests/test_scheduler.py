"""Testy jednostkowe modułu harmonogramu i obserwatora (Scheduler & Watcher Tests)."""

import os
from pathlib import Path
import tempfile
import time
import unittest

from PyQt6.QtCore import QCoreApplication
from core.scheduler import DirectoryWatcher, SyncScheduler


class TestSchedulerAndWatcher(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.scheduler = SyncScheduler()
        self.watcher = DirectoryWatcher(debounce_ms=50)

    def tearDown(self):
        self.scheduler.stop()
        self.watcher.clear()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_scheduler_start_stop(self):
        self.assertFalse(self.scheduler.is_running)
        self.scheduler.start(interval_minutes=15, auto_sync=True)
        self.assertTrue(self.scheduler.is_running)
        self.assertEqual(self.scheduler._auto_sync, True)

        self.scheduler.stop()
        self.assertFalse(self.scheduler.is_running)

    def test_scheduler_trigger_signal(self):
        received = []
        self.scheduler.scheduled_trigger.connect(lambda auto: received.append(auto))
        # Ręczne wywołanie timeoutu
        self.scheduler._auto_sync = True
        self.scheduler._on_timeout()
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0], True)

    def test_watcher_set_paths_and_clear(self):
        folder_a = Path(self.temp_dir) / "katalog_a"
        folder_a.mkdir()
        self.watcher.set_watch_paths([str(folder_a)])
        self.assertTrue(len(self.watcher._watched_paths) >= 1)

        self.watcher.clear()
        self.assertEqual(len(self.watcher._watched_paths), 0)

    def test_watcher_debounce_signal(self):
        received = []
        self.watcher.change_detected.connect(lambda p: received.append(p))

        # Symulacja zdarzenia zmiany
        test_path = str(Path(self.temp_dir) / "test.txt")
        self.watcher._on_path_changed(test_path)
        self.assertEqual(self.watcher._pending_change_path, test_path)

        # Wywołanie końca debounce
        self.watcher._on_debounce_timeout()
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0], test_path)


if __name__ == "__main__":
    unittest.main()
