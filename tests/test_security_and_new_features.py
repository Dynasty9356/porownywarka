"""Kompleksowe testy bezpieczeństwa, rollbacku, blokad i nowych funkcji FolderSync (CERT / NASA)."""

from datetime import datetime
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from core.comparator import (
    FileStatus,
    OperationCancelledError,
    calculate_sha256,
    compare_directories,
    is_safe_relative_path,
    validate_safe_directory_path,
)
from core.lock import SingleInstanceLock
from core.synchronizer import (
    SyncDirection,
    execute_sync,
    plan_sync_actions,
    safe_restore_file,
)
from gui.report_exporter import export_csv, export_html


class TestSecurityAndNewFeatures(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="fs_sec_test_")
        self.base_path = Path(self.test_dir)
        self.dir_a = self.base_path / "katalog_A"
        self.dir_b = self.base_path / "katalog_B"
        self.dir_a.mkdir()
        self.dir_b.mkdir()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_single_instance_lock(self):
        """Test blokady pojedynczej instancji (Anti-Race Condition)."""
        lock1 = SingleInstanceLock(app_name="FolderSyncTest")
        self.assertTrue(lock1.acquire())

        # Druga próba powinna zostać odrzucona
        lock2 = SingleInstanceLock(app_name="FolderSyncTest")
        self.assertFalse(lock2.acquire())

        # Po zwolnieniu pierwszej, druga powinna móc założyć blokadę
        lock1.release()
        self.assertTrue(lock2.acquire())
        lock2.release()

    def test_safe_path_validation(self):
        """Test obrony przed nazwami urządzeń DOS i złośliwymi ścieżkami (CERT)."""
        self.assertTrue(validate_safe_directory_path(str(self.dir_a)))
        self.assertFalse(validate_safe_directory_path(""))
        self.assertFalse(validate_safe_directory_path(r"\\.\PhysicalDrive0"))
        self.assertFalse(validate_safe_directory_path(r"\\?\C:\Windows"))
        self.assertFalse(validate_safe_directory_path("C:\x00evil"))

        # Test is_safe_relative_path
        self.assertTrue(is_safe_relative_path(self.dir_a, self.dir_a / "sub" / "file.txt"))
        self.assertFalse(is_safe_relative_path(self.dir_a, self.dir_b / "file.txt"))
        # Nazwa urządzenia DOS w podścieżce
        self.assertFalse(is_safe_relative_path(self.dir_a, self.dir_a / "CON.txt"))
        self.assertFalse(is_safe_relative_path(self.dir_a, self.dir_a / "sub" / "NUL"))

    def test_safe_restore_file_and_integrity_check(self):
        """Test bezpiecznego rollbacku z weryfikacją sumy SHA-256."""
        src_file = self.base_path / "backup_source.txt"
        dst_file = self.base_path / "restored_target.txt"

        src_file.write_text("Oryginalna bezpieczna tresc", encoding="utf-8")

        # Pomyślny rollback
        ok, err = safe_restore_file(src_file, dst_file, verify_sha256=True)
        self.assertTrue(ok)
        self.assertEqual(err, "")
        self.assertTrue(dst_file.exists())
        self.assertEqual(dst_file.read_text(encoding="utf-8"), "Oryginalna bezpieczna tresc")

        # Test nieistniejącego pliku
        ok, err = safe_restore_file(self.base_path / "nonexistent.txt", dst_file)
        self.assertFalse(ok)
        self.assertIn("nie istnieje", err)

    def test_mirror_sync_mode(self):
        """Test trybu lustrzanego (Mirror Sync A -> B) z bezpiecznym usuwaniem do .backup."""
        # W katalogu A: plik_1, plik_2
        (self.dir_a / "plik_1.txt").write_text("Wspolny plik", encoding="utf-8")
        (self.dir_a / "nowy_w_a.txt").write_text("Nowy w A", encoding="utf-8")

        # W katalogu B: plik_1, stary_tylko_w_b
        (self.dir_b / "plik_1.txt").write_text("Wspolny plik", encoding="utf-8")
        (self.dir_b / "do_usuniecia.txt").write_text("Zbędny stary plik", encoding="utf-8")

        # Przeprowadź porównanie
        items = compare_directories(self.dir_a, self.dir_b, compare_hashes=True)
        actions = plan_sync_actions(items, self.dir_a, self.dir_b, SyncDirection.MIRROR_A_TO_B)

        # Powinny być 2 akcje: 1 skopiowanie nowy_w_a -> B, 1 usunięcie do_usuniecia z B
        self.assertEqual(len(actions), 2)
        deletions = [a for a in actions if a.is_delete]
        copies = [a for a in actions if not a.is_delete]

        self.assertEqual(len(deletions), 1)
        self.assertEqual(len(copies), 1)
        self.assertEqual(deletions[0].source_path.name, "do_usuniecia.txt")

        # Wykonaj synchronizację lustrzaną z włączonym backupem
        report = execute_sync(actions, create_backup=True, verify_sha256=True)
        self.assertTrue(report.success)
        self.assertEqual(report.files_updated, 1)
        self.assertEqual(report.files_deleted, 1)

        # Sprawdź stan katalogu B
        self.assertTrue((self.dir_b / "nowy_w_a.txt").exists())
        self.assertFalse((self.dir_b / "do_usuniecia.txt").exists())

        # Sprawdź czy usunięty plik trafił bezpiecznie do .backup
        backup_files = list((self.dir_b / ".backup").rglob("do_usuniecia.txt"))
        self.assertEqual(len(backup_files), 1)
        self.assertEqual(backup_files[0].read_text(encoding="utf-8"), "Zbędny stary plik")

    def test_compare_cancel_token(self):
        """Test natychmiastowego przerwania operacji porównywania (Cancel Token)."""
        (self.dir_a / "plik1.txt").write_text("Dane", encoding="utf-8")
        (self.dir_b / "plik1.txt").write_text("Dane", encoding="utf-8")

        # Anulowanie natychmiastowe
        with self.assertRaises(OperationCancelledError):
            compare_directories(
                self.dir_a,
                self.dir_b,
                compare_hashes=True,
                cancel_token=lambda: True,
            )

    def test_report_exporters(self):
        """Test generowania raportów HTML i CSV."""
        (self.dir_a / "test.txt").write_text("Treść", encoding="utf-8")
        items = compare_directories(self.dir_a, self.dir_b)

        html_out = self.base_path / "report.html"
        csv_out = self.base_path / "report.csv"

        self.assertTrue(export_html(items, str(self.dir_a), str(self.dir_b), html_out, "ProfilTestowy"))
        self.assertTrue(html_out.exists())
        self.assertIn("ProfilTestowy", html_out.read_text(encoding="utf-8"))

        self.assertTrue(export_csv(items, str(self.dir_a), str(self.dir_b), csv_out))
        self.assertTrue(csv_out.exists())
        self.assertIn("test.txt", csv_out.read_text(encoding="utf-8-sig"))


if __name__ == "__main__":
    unittest.main()
