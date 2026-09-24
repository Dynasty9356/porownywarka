"""Okno ustawień aplikacji FolderSync (Windows 11 Fluent Theme, WCAG AA).
Zakładki: Wygląd | Porównywanie | Synchronizacja | Wykluczenia | Historia i Raporty | Zasobnik
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)

from core.settings import AppSettings, load_settings, save_settings

SETTINGS_STYLE = """
QWidget { background-color: #202020; color: #F3F3F3;
    font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif; font-size: 13px; }
QTabWidget::pane { border: 1px solid #3A3A3A; border-radius: 6px; }
QTabBar::tab { background: #2A2A2A; color: #AAAAAA; padding: 8px 18px; border-radius: 5px 5px 0 0; margin-right: 2px; }
QTabBar::tab:selected { background: #0078D4; color: #FFFFFF; font-weight: 600; }
QGroupBox { border: 1px solid #3A3A3A; border-radius: 8px; margin-top: 10px; padding-top: 12px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #60CDFF; }
QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {
    background: #2B2B2B; border: 1px solid #404040; border-radius: 6px;
    padding: 6px 10px; color: #FFFFFF; }
QComboBox:focus, QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus { border: 1px solid #60CDFF; }
QCheckBox { color: #EAEAEA; spacing: 8px; }
QCheckBox::indicator { width: 18px; height: 18px; border: 1px solid #555; border-radius: 4px; background: #2B2B2B; }
QCheckBox::indicator:checked { background: #0078D4; border: 1px solid #60CDFF; }
QPushButton { background: #2D2D2D; border: 1px solid #454545; border-radius: 6px; padding: 7px 14px; font-weight: 600; color: #FFFFFF; }
QPushButton:hover { background: #383838; }
QPushButton#primaryButton { background: #0078D4; border: 1px solid #1084D8; color: #FFFFFF; }
QPushButton#primaryButton:hover { background: #1084D8; }
QListWidget { background: #1A1A1A; border: 1px solid #333; border-radius: 6px; color: #F3F3F3; }
QTextEdit { background: #1A1A1A; border: 1px solid #333; border-radius: 6px; color: #F3F3F3; font-family: Consolas; font-size: 12px; }
"""


class SettingsDialog(QDialog):
    """Okno konfiguracji FolderSync z podziałem na zakładki tematyczne."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ Ustawienia FolderSync")
        self.resize(680, 560)
        self.setStyleSheet(SETTINGS_STYLE)

        self.settings = load_settings()
        self._build_ui()
        self._load_values()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QLabel("⚙️ Ustawienia Aplikacji FolderSync")
        header.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        header.setStyleSheet("color: #60CDFF; margin-bottom: 6px;")
        layout.addWidget(header)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.tabs.addTab(self._tab_appearance(), "🎨 Wygląd")
        self.tabs.addTab(self._tab_comparison(), "🔍 Porównywanie")
        self.tabs.addTab(self._tab_sync(), "⚡ Synchronizacja")
        self.tabs.addTab(self._tab_exclusions(), "🚫 Wykluczenia")
        self.tabs.addTab(self._tab_history(), "📜 Historia i Raporty")
        self.tabs.addTab(self._tab_tray(), "🔔 Zasobnik")

        # Przyciski
        btn_box = QDialogButtonBox()
        btn_save = btn_box.addButton("💾 Zapisz ustawienia", QDialogButtonBox.ButtonRole.AcceptRole)
        btn_save.setObjectName("primaryButton")
        btn_cancel = btn_box.addButton("Anuluj", QDialogButtonBox.ButtonRole.RejectRole)
        btn_box.accepted.connect(self._save)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    # ─── Zakładka: Wygląd ─────────────────────────────────────────────────
    def _tab_appearance(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        grp = QGroupBox("Motyw i Język")
        g_layout = QVBoxLayout(grp)

        row_theme = QHBoxLayout()
        row_theme.addWidget(QLabel("Motyw interfejsu:"))
        self.combo_theme = QComboBox()
        self.combo_theme.addItems(["Ciemny (Dark)", "Jasny (Light)", "Automatyczny (zgodny z Windows)"])
        row_theme.addWidget(self.combo_theme)
        g_layout.addLayout(row_theme)

        row_lang = QHBoxLayout()
        row_lang.addWidget(QLabel("Język:"))
        self.combo_lang = QComboBox()
        self.combo_lang.addItems(["Polski", "English"])
        row_lang.addWidget(self.combo_lang)
        g_layout.addLayout(row_lang)

        layout.addWidget(grp)
        layout.addStretch()
        return w

    # ─── Zakładka: Porównywanie ───────────────────────────────────────────
    def _tab_comparison(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        grp = QGroupBox("Parametry Porównywania")
        g_layout = QVBoxLayout(grp)
        g_layout.setSpacing(10)

        row_tol = QHBoxLayout()
        row_tol.addWidget(QLabel("Tolerancja czasu modyfikacji [sekundy]:"))
        self.spin_tolerance = QDoubleSpinBox()
        self.spin_tolerance.setRange(0.0, 60.0)
        self.spin_tolerance.setSingleStep(0.5)
        self.spin_tolerance.setToolTip("Ważne dla dysków FAT32/USB (np. 2s) lub NAS (np. 5s)")
        row_tol.addWidget(self.spin_tolerance)
        g_layout.addLayout(row_tol)

        row_block = QHBoxLayout()
        row_block.addWidget(QLabel("Rozmiar bloku SHA-256 [KB]:"))
        self.spin_block = QSpinBox()
        self.spin_block.setRange(8, 4096)
        self.spin_block.setSingleStep(64)
        self.spin_block.setToolTip("Większy blok = szybciej na SSD, mniejszy = mniejsze użycie RAM")
        row_block.addWidget(self.spin_block)
        g_layout.addLayout(row_block)

        self.chk_auto_compare = QCheckBox("Automatycznie porównaj po załadowaniu szablonu")
        self.chk_auto_compare.setToolTip("Po wyborze profilu z listy natychmiast uruchamia porównanie")
        g_layout.addWidget(self.chk_auto_compare)

        layout.addWidget(grp)

        grp2 = QGroupBox("Domyślny widok tabeli")
        g2_layout = QVBoxLayout(grp2)

        row_sort = QHBoxLayout()
        row_sort.addWidget(QLabel("Domyślne sortowanie:"))
        self.combo_sort = QComboBox()
        self.combo_sort.addItems(["Status (priorytety)", "Ścieżka pliku (A-Z)", "Data modyfikacji A", "Data modyfikacji B", "Rozmiar"])
        row_sort.addWidget(self.combo_sort)
        g2_layout.addLayout(row_sort)

        layout.addWidget(grp2)
        layout.addStretch()
        return w

    # ─── Zakładka: Synchronizacja ────────────────────────────────────────
    def _tab_sync(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        grp = QGroupBox("Zachowanie Synchronizacji")
        g_layout = QVBoxLayout(grp)
        g_layout.setSpacing(10)

        row_confirm = QHBoxLayout()
        row_confirm.addWidget(QLabel("Okno potwierdzenia przed synchronizacją:"))
        self.combo_confirm = QComboBox()
        self.combo_confirm.addItems([
            "Zawsze pytaj",
            "Tylko gdy nadpisujesz pliki",
            "Nigdy nie pytaj (niebezpieczne!)",
        ])
        row_confirm.addWidget(self.combo_confirm)
        g_layout.addLayout(row_confirm)

        row_mode = QHBoxLayout()
        row_mode.addWidget(QLabel("Domyślny tryb synchronizacji:"))
        self.combo_default_sync = QComboBox()
        self.combo_default_sync.addItems([
            "Inteligentna aktualizacja (nowsze zastępują starsze)",
            "Kopiuj z A do B",
            "Kopiuj z B do A",
        ])
        row_mode.addWidget(self.combo_default_sync)
        g_layout.addLayout(row_mode)

        layout.addWidget(grp)
        layout.addStretch()
        return w

    # ─── Zakładka: Wykluczenia ───────────────────────────────────────────
    def _tab_exclusions(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        grp = QGroupBox("Globalne wzorce wykluczeń (glob, jeden na linię)")
        g_layout = QVBoxLayout(grp)

        info = QLabel(
            "Pliki i katalogi pasujące do poniższych wzorców będą pomijane podczas skanowania.\n"
            "Wzorce obsługują znaki globbing: * (dowolny ciąg), ? (jeden znak).\n"
            "Przykłady: *.tmp  |  Thumbs.db  |  node_modules  |  .git"
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #AAAAAA; font-size: 12px;")
        g_layout.addWidget(info)

        self.text_exclusions = QTextEdit()
        self.text_exclusions.setPlaceholderText("*.tmp\nThumbs.db\n.git\nnode_modules")
        g_layout.addWidget(self.text_exclusions)

        btn_row = QHBoxLayout()
        btn_restore = QPushButton("⟳ Przywróć domyślne")
        btn_restore.clicked.connect(self._restore_default_exclusions)
        btn_row.addWidget(btn_restore)
        btn_row.addStretch()
        g_layout.addLayout(btn_row)

        layout.addWidget(grp)
        return w

    # ─── Zakładka: Historia i Raporty ────────────────────────────────────
    def _tab_history(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        grp = QGroupBox("Historia Porównań")
        g_layout = QVBoxLayout(grp)

        row_max = QHBoxLayout()
        row_max.addWidget(QLabel("Maksymalna liczba wpisów w historii:"))
        self.spin_max_history = QSpinBox()
        self.spin_max_history.setRange(10, 10000)
        self.spin_max_history.setSingleStep(50)
        row_max.addWidget(self.spin_max_history)
        g_layout.addLayout(row_max)

        layout.addWidget(grp)

        grp2 = QGroupBox("Eksport Raportów")
        g2_layout = QVBoxLayout(grp2)

        row_dir = QHBoxLayout()
        row_dir.addWidget(QLabel("Domyślny folder eksportu raportów:"))
        self.edit_report_dir = QLineEdit()
        self.edit_report_dir.setPlaceholderText("Pozostaw puste — program zapyta przy każdym eksporcie")
        btn_browse = QPushButton("Przeglądaj...")
        btn_browse.clicked.connect(self._browse_report_dir)
        row_dir.addWidget(self.edit_report_dir)
        row_dir.addWidget(btn_browse)
        g2_layout.addLayout(row_dir)

        layout.addWidget(grp2)
        layout.addStretch()
        return w

    # ─── Zakładka: Zasobnik ──────────────────────────────────────────────
    def _tab_tray(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        grp = QGroupBox("Zachowanie ikony w zasobniku systemowym")
        g_layout = QVBoxLayout(grp)
        g_layout.setSpacing(10)

        self.chk_minimize_to_tray = QCheckBox("Przy minimalizacji schowaj do zasobnika (zamiast na pasek zadań)")
        self.chk_close_to_tray = QCheckBox("Przy zamknięciu okna schowaj do zasobnika (kontynuuj w tle)")
        self.chk_tray_notifications = QCheckBox("Wyświetlaj powiadomienia Windows po zakończeniu synchronizacji")

        g_layout.addWidget(self.chk_minimize_to_tray)
        g_layout.addWidget(self.chk_close_to_tray)
        g_layout.addWidget(self.chk_tray_notifications)

        layout.addWidget(grp)
        layout.addStretch()
        return w

    # ─── Ładowanie i Zapisywanie ─────────────────────────────────────────
    def _load_values(self):
        s = self.settings
        theme_map = {"dark": 0, "light": 1, "auto": 2}
        self.combo_theme.setCurrentIndex(theme_map.get(s.theme, 0))
        self.combo_lang.setCurrentIndex(0 if s.language == "pl" else 1)

        self.spin_tolerance.setValue(s.time_tolerance_seconds)
        self.spin_block.setValue(s.sha256_block_size // 1024)
        self.chk_auto_compare.setChecked(s.auto_compare_on_profile_load)
        sort_map = {"status": 0, "path": 1, "mtime_a": 2, "mtime_b": 3, "size": 4}
        # Default
        self.combo_sort.setCurrentIndex(0)

        confirm_map = {"always": 0, "overwrite_only": 1, "never": 2}
        self.combo_confirm.setCurrentIndex(confirm_map.get(s.confirm_sync, 0))
        sync_map = {"UPDATE_OLDER": 0, "COPY_A_TO_B": 1, "COPY_B_TO_A": 2}
        self.combo_default_sync.setCurrentIndex(sync_map.get(s.default_sync_mode, 0))

        self.text_exclusions.setPlainText("\n".join(s.global_exclude_patterns))

        self.spin_max_history.setValue(s.max_history_entries)
        self.edit_report_dir.setText(s.report_output_dir)

        self.chk_minimize_to_tray.setChecked(s.minimize_to_tray)
        self.chk_close_to_tray.setChecked(s.close_to_tray)
        self.chk_tray_notifications.setChecked(s.show_tray_notifications)

    def _save(self):
        s = self.settings
        theme_vals = ["dark", "light", "auto"]
        s.theme = theme_vals[self.combo_theme.currentIndex()]
        s.language = "pl" if self.combo_lang.currentIndex() == 0 else "en"

        s.time_tolerance_seconds = self.spin_tolerance.value()
        s.sha256_block_size = self.spin_block.value() * 1024
        s.auto_compare_on_profile_load = self.chk_auto_compare.isChecked()

        confirm_vals = ["always", "overwrite_only", "never"]
        s.confirm_sync = confirm_vals[self.combo_confirm.currentIndex()]
        sync_vals = ["UPDATE_OLDER", "COPY_A_TO_B", "COPY_B_TO_A"]
        s.default_sync_mode = sync_vals[self.combo_default_sync.currentIndex()]

        patterns_raw = self.text_exclusions.toPlainText()
        s.global_exclude_patterns = [
            p.strip() for p in patterns_raw.splitlines() if p.strip()
        ]

        s.max_history_entries = self.spin_max_history.value()
        s.report_output_dir = self.edit_report_dir.text().strip()

        s.minimize_to_tray = self.chk_minimize_to_tray.isChecked()
        s.close_to_tray = self.chk_close_to_tray.isChecked()
        s.show_tray_notifications = self.chk_tray_notifications.isChecked()

        from core.settings import invalidate_cache
        invalidate_cache()
        if save_settings(s):
            self.accept()

    def _restore_default_exclusions(self):
        defaults = AppSettings().global_exclude_patterns
        self.text_exclusions.setPlainText("\n".join(defaults))

    def _browse_report_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Wybierz folder dla raportów")
        if path:
            self.edit_report_dir.setText(path)
