"""Testy jednostkowe modułów i18n (wielojęzyczność) oraz themes (motywy WCAG)."""

import os
import sys
import unittest
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from core.comparator import FileStatus
from core.i18n import tr, get_status_display_name
from gui.themes import (
    apply_theme_to_app,
    get_status_colors,
    get_theme_stylesheet,
    is_dark_theme_active,
)
from gui.main_window import MainWindow
from gui.settings_dialog import SettingsDialog


class TestThemeAndI18n(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_i18n_translations(self):
        # Polski
        self.assertEqual(tr("btn_compare", "pl"), "🔍 Porównaj zawartość katalogów")
        self.assertEqual(tr("window_title", "pl"), "FolderSync - Porównywarka i Synchronizator Katalogów")

        # Angielski
        self.assertEqual(tr("btn_compare", "en"), "🔍 Compare Directories")
        self.assertEqual(tr("window_title", "en"), "FolderSync - Directory Comparator & Synchronizer")

        # Statusy
        self.assertEqual(get_status_display_name(FileStatus.IDENTICAL, "pl"), "[=] Identyczne")
        self.assertEqual(get_status_display_name(FileStatus.IDENTICAL, "en"), "[=] Identical")
        self.assertEqual(get_status_display_name(FileStatus.NEWER_A, "en"), "[A > B] Newer in A")

    def test_themes_and_wcag_colors(self):
        dark_css = get_theme_stylesheet("dark")
        light_css = get_theme_stylesheet("light")

        self.assertIn("#202020", dark_css)
        self.assertIn("#F3F3F3", light_css)

        # Sprawdzenie kolorów dla Dark Mode
        bg_dark, fg_dark = get_status_colors(FileStatus.NEWER_A, is_dark=True)
        self.assertEqual(bg_dark.name().upper(), "#1B5E20")

        # Sprawdzenie kolorów dla Light Mode (pastelowe tło, wysoki kontrast tekstu)
        bg_light, fg_light = get_status_colors(FileStatus.NEWER_A, is_dark=False)
        self.assertEqual(bg_light.name().upper(), "#E8F5E9")
        self.assertEqual(fg_light.name().upper(), "#1B5E20")

    def test_main_window_language_switch(self):
        win = MainWindow()
        try:
            # Domyślny język PL
            win._update_ui_language("pl")
            self.assertEqual(win.btn_compare.text(), "🔍 Porównaj zawartość katalogów")
            self.assertEqual(win.lbl_dir_a.text(), "Katalog A (Lewy):")

            # Przełączenie na EN
            win._update_ui_language("en")
            self.assertEqual(win.btn_compare.text(), "🔍 Compare Directories")
            self.assertEqual(win.lbl_dir_a.text(), "Directory A (Left):")
            self.assertEqual(win.btn_sync.text(), "⚡ Synchronize selected files")
        finally:
            win.close()


if __name__ == "__main__":
    unittest.main()
