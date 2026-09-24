"""Testy jednostkowe mechanizmu porównywania i synchronizacji (Security & Functionality Test Suite)."""

import os
from pathlib import Path
import shutil
import tempfile
import time
import unittest

from core.comparator import FileStatus, compare_directories
from core.synchronizer import SyncDirection, execute_sync, plan_sync_actions


class TestFolderSyncCore(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="foldersync_test_")
        self.base_path = Path(self.test_dir)
        self.dir_a = self.base_path / "katalog_A"
        self.dir_b = self.base_path / "katalog_B"
        self.dir_a.mkdir()
        self.dir_b.mkdir()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_compare_identical_and_differences(self):
        # 1. Identyczny plik w A i B
        file_shared_a = self.dir_a / "identyczny.txt"
        file_shared_b = self.dir_b / "identyczny.txt"
        file_shared_a.write_text("Hello World", encoding="utf-8")
        file_shared_b.write_text("Hello World", encoding="utf-8")
        os.utime(file_shared_b, (file_shared_a.stat().st_atime, file_shared_a.stat().st_mtime))

        # 2. Tylko w A
        (self.dir_a / "tylko_w_A.txt").write_text("Tylko A", encoding="utf-8")

        # 3. Tylko w B
        (self.dir_b / "tylko_w_B.txt").write_text("Tylko B", encoding="utf-8")

        # 4. Nowszy w A
        file_newer_a = self.dir_a / "aktualizacja.txt"
        file_older_b = self.dir_b / "aktualizacja.txt"
        file_older_b.write_text("Stara wersja", encoding="utf-8")
        time.sleep(0.05)
        file_newer_a.write_text("Nowa wersja v2", encoding="utf-8")
        # upewniamy się że mtime A > B
        os.utime(file_newer_a, (time.time() + 10, time.time() + 10))

        # Wykonaj porównanie
        items = compare_directories(self.dir_a, self.dir_b, compare_hashes=True)
        items_map = {item.rel_path: item for item in items}

        self.assertEqual(items_map["identyczny.txt"].status, FileStatus.IDENTICAL)
        self.assertEqual(items_map["tylko_w_A.txt"].status, FileStatus.ONLY_A)
        self.assertEqual(items_map["tylko_w_B.txt"].status, FileStatus.ONLY_B)
        self.assertEqual(items_map["aktualizacja.txt"].status, FileStatus.NEWER_A)

    def test_sync_with_backup_and_integrity(self):
        # Przygotowanie: plik w B jest starszy, plik w A jest nowszy
        file_a = self.dir_a / "dokument.docx"
        file_b = self.dir_b / "dokument.docx"
        file_b.write_text("Stara tresc w B", encoding="utf-8")
        file_a.write_text("Nowa tresc w A - wazne dane", encoding="utf-8")
        os.utime(file_a, (time.time() + 20, time.time() + 20))

        items = compare_directories(self.dir_a, self.dir_b, compare_hashes=True)
        actions = plan_sync_actions(items, self.dir_a, self.dir_b, SyncDirection.UPDATE_OLDER)

        self.assertEqual(len(actions), 1)
        self.assertTrue(actions[0].will_overwrite)

        report = execute_sync(actions, create_backup=True, verify_sha256=True)
        self.assertTrue(report.success)
        self.assertEqual(report.files_updated, 1)
        self.assertEqual(report.files_backed_up, 1)

        # Sprawdzenie czy w B jest nowa treść
        self.assertEqual(file_b.read_text(encoding="utf-8"), "Nowa tresc w A - wazne dane")

        # Sprawdzenie czy kopia zapasowa powstała w .backup
        backup_files = list((self.dir_b / ".backup").rglob("dokument.docx"))
        self.assertEqual(len(backup_files), 1)
        self.assertEqual(backup_files[0].read_text(encoding="utf-8"), "Stara tresc w B")


if __name__ == "__main__":
    unittest.main()
