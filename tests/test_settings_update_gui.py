"""Testy integracyjne opcji aktualizacji w SettingsDialog oraz UpdateAvailableDialog."""

import os
import sys
import unittest
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication

from core.settings import AppSettings, load_settings, save_settings
from core.updater import UpdateInfo
from gui.settings_dialog import SettingsDialog
from gui.update_dialog import UpdateAvailableDialog


class TestSettingsUpdateGUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_settings_dialog_has_updates_tab(self):
        dlg = SettingsDialog()
        try:
            tab_texts = [dlg.tabs.tabText(i) for i in range(dlg.tabs.count())]
            self.assertTrue(any("Aktualizacj" in t or "Update" in t for t in tab_texts))
            self.assertTrue(hasattr(dlg, "chk_auto_updates"))
            self.assertTrue(hasattr(dlg, "btn_check_updates"))
            self.assertTrue(hasattr(dlg, "lbl_update_status"))
        finally:
            dlg.close()

    def test_toggle_auto_updates_setting(self):
        s = load_settings()
        initial_val = s.check_updates_on_startup

        dlg = SettingsDialog()
        try:
            dlg.chk_auto_updates.setChecked(not initial_val)
            dlg._save()
            
            s2 = load_settings()
            self.assertEqual(s2.check_updates_on_startup, not initial_val)
        finally:
            dlg.close()
            # Przywrócenie stanu początkowego
            s.check_updates_on_startup = initial_val
            save_settings(s)

    def test_update_available_dialog_build(self):
        info = UpdateInfo(
            is_available=True,
            current_version="1.3.0",
            latest_version="1.4.0",
            release_name="Wydanie 1.4.0",
            release_notes="- Nowy wygląd\\n- Poprawki błędów",
            download_url="https://github.com/Dynasty9356/porownywarka/releases",
            published_at="2026-09-30",
        )
        dlg = UpdateAvailableDialog(info)
        try:
            self.assertIn("1.4.0", dlg.windowTitle() or dlg.txt_notes.toPlainText() or "")
            self.assertIn("Poprawki błędów", dlg.txt_notes.toPlainText())
        finally:
            dlg.close()


if __name__ == "__main__":
    unittest.main()
