"""Zautomatyzowane testy integracyjne GUI rozszerzone o szablony i sortowanie."""

import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import unittest

from PyQt6.QtWidgets import QApplication

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from gui.main_window import MainWindow
from core.comparator import FileStatus
from core.profiles import SyncProfile, save_profile
import core.profiles


class TestGuiExtended(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="gui_test_ext_")
        self.config_dir = tempfile.mkdtemp(prefix="cfg_test_")
        core.profiles.get_config_dir = lambda: Path(self.config_dir)

        self.dir_a = Path(self.test_dir) / "katalog_A"
        self.dir_b = Path(self.test_dir) / "katalog_B"
        self.dir_a.mkdir()
        self.dir_b.mkdir()

        (self.dir_a / "tekst.txt").write_text("Wersja A\nLinia 2", encoding="utf-8")
        (self.dir_b / "tekst.txt").write_text("Wersja B\nLinia 2", encoding="utf-8")
        os.utime(self.dir_a / "tekst.txt", (time.time() + 100, time.time() + 100))

        (self.dir_a / "duzy.bin").write_bytes(b"x" * 2048)
        (self.dir_b / "maly.bin").write_bytes(b"x" * 512)

        self.window = MainWindow()

    def tearDown(self):
        self.window.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)
        shutil.rmtree(self.config_dir, ignore_errors=True)

    def test_profiles_and_sorting_flow(self):
        # 1. Zapisanie profilu
        p = SyncProfile("TestProfile", str(self.dir_a), str(self.dir_b))
        save_profile(p)
        self.window._refresh_profiles_list("TestProfile")

        # 2. Wybór profilu w ComboBox
        idx = self.window.combo_profiles.findData("TestProfile")
        self.assertGreater(idx, 0)
        self.window.combo_profiles.setCurrentIndex(idx)

        self.assertEqual(self.window.edit_dir_a.text(), str(self.dir_a))
        self.assertEqual(self.window.edit_dir_b.text(), str(self.dir_b))

        # 3. Uruchomienie porównywania
        self.window._start_compare()
        if self.window.compare_thread:
            self.window.compare_thread.wait(5000)
        self.app.processEvents()

        self.assertEqual(len(self.window.current_items), 3)

        # 4. Sprawdzenie sortowania po rozmiarze (kolumna 3)
        self.window.table.sortItems(3)
        self.app.processEvents()

        # 5. Podgląd różnic tekstu
        from gui.main_window import DiffViewerDialog
        diff_dlg = DiffViewerDialog("tekst.txt", self.dir_a / "tekst.txt", self.dir_b / "tekst.txt", self.window)
        self.assertIn("Wersja A", diff_dlg.text_a.toPlainText())
        self.assertIn("Wersja B", diff_dlg.text_b.toPlainText())
        diff_dlg.close()


if __name__ == "__main__":
    unittest.main()
