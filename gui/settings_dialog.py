"""Okno ustawień aplikacji FolderSync (Windows 11 Fluent Theme, WCAG AA).
Zakładki: Wygląd | Porównywanie | Synchronizacja | Wykluczenia | Historia i Raporty | Zasobnik
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QFont
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
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)

from core.settings import AppSettings, load_settings, save_settings, invalidate_cache
from core.i18n import tr
from core.updater import UpdateInfo, check_for_updates, validate_https_url
from core.version import __version__
from gui.themes import apply_theme_to_app, get_theme_stylesheet, is_dark_theme_active


class CheckUpdateWorker(QThread):
    """Wątek asynchronicznego sprawdzania aktualizacji (bez blokowania wątku głównego GUI)."""
    finished = pyqtSignal(object)

    def __init__(self, repo: str, parent=None):
        super().__init__(parent)
        self.repo = repo

    def run(self):
        info = check_for_updates(repo=self.repo)
        self.finished.emit(info)


class SettingsDialog(QDialog):
    """Okno konfiguracji FolderSync z podziałem na zakładki tematyczne."""

    def __init__(self, parent=None, initial_tab: int = 0):
        super().__init__(parent)
        self.settings = load_settings()
        self.lang = self.settings.language

        self.setWindowTitle(tr("settings_title", self.lang))
        self.resize(680, 560)
        self.setStyleSheet(get_theme_stylesheet(self.settings.theme))

        self._build_ui()
        self._load_values()
        if 0 <= initial_tab < self.tabs.count():
            self.tabs.setCurrentIndex(initial_tab)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        is_dark = is_dark_theme_active(self.settings.theme)
        header_color = "#60CDFF" if is_dark else "#005FB8"

        self.lbl_header = QLabel(tr("settings_header", self.lang))
        self.lbl_header.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.lbl_header.setStyleSheet(f"color: {header_color}; margin-bottom: 6px;")
        layout.addWidget(self.lbl_header)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.tabs.addTab(self._tab_appearance(), tr("tab_appearance", self.lang))
        self.tabs.addTab(self._tab_comparison(), tr("tab_comparison", self.lang))
        self.tabs.addTab(self._tab_sync(), tr("tab_sync", self.lang))
        self.tabs.addTab(self._tab_exclusions(), tr("tab_exclusions", self.lang))
        self.tabs.addTab(self._tab_history(), tr("tab_history", self.lang))
        self.tabs.addTab(self._tab_tray(), tr("tab_tray", self.lang))
        self.tabs.addTab(self._tab_updates(), tr("tab_updates", self.lang))

        # Przyciski
        btn_box = QDialogButtonBox()
        btn_save = btn_box.addButton(tr("btn_save_settings", self.lang), QDialogButtonBox.ButtonRole.AcceptRole)
        btn_save.setObjectName("primaryButton")
        btn_cancel = btn_box.addButton(tr("btn_cancel", self.lang), QDialogButtonBox.ButtonRole.RejectRole)
        btn_box.accepted.connect(self._save)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    # ─── Zakładka: Wygląd ─────────────────────────────────────────────────
    def _tab_appearance(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        grp = QGroupBox(tr("grp_theme_lang", self.lang))
        g_layout = QVBoxLayout(grp)

        row_theme = QHBoxLayout()
        row_theme.addWidget(QLabel(tr("lbl_theme", self.lang)))
        self.combo_theme = QComboBox()
        self.combo_theme.addItems([
            tr("theme_dark", self.lang),
            tr("theme_light", self.lang),
            tr("theme_auto", self.lang),
        ])
        self.combo_theme.currentIndexChanged.connect(self._on_theme_preview_changed)
        row_theme.addWidget(self.combo_theme)
        g_layout.addLayout(row_theme)

        row_lang = QHBoxLayout()
        row_lang.addWidget(QLabel(tr("lbl_lang", self.lang)))
        self.combo_lang = QComboBox()
        self.combo_lang.addItems(["Polski", "English"])
        row_lang.addWidget(self.combo_lang)
        g_layout.addLayout(row_lang)

        layout.addWidget(grp)
        layout.addStretch()
        return w

    def _on_theme_preview_changed(self, idx: int):
        theme_vals = ["dark", "light", "auto"]
        if 0 <= idx < len(theme_vals):
            is_dark = apply_theme_to_app(theme_vals[idx], self)
            header_color = "#60CDFF" if is_dark else "#005FB8"
            self.lbl_header.setStyleSheet(f"color: {header_color}; margin-bottom: 6px;")

    # ─── Zakładka: Porównywanie ───────────────────────────────────────────
    def _tab_comparison(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        is_pl = self.lang == "pl"
        grp = QGroupBox("Parametry Porównywania" if is_pl else "Comparison Parameters")
        g_layout = QVBoxLayout(grp)
        g_layout.setSpacing(10)

        row_tol = QHBoxLayout()
        row_tol.addWidget(QLabel(
            "Tolerancja czasu modyfikacji [sekundy]:" if is_pl else "Modification time tolerance [seconds]:"
        ))
        self.spin_tolerance = QDoubleSpinBox()
        self.spin_tolerance.setRange(0.0, 60.0)
        self.spin_tolerance.setSingleStep(0.5)
        self.spin_tolerance.setToolTip("Ważne dla dysków FAT32/USB (np. 2s) lub NAS (np. 5s)" if is_pl else "Important for FAT32/USB (e.g. 2s) or NAS drives (e.g. 5s)")
        row_tol.addWidget(self.spin_tolerance)
        g_layout.addLayout(row_tol)

        row_block = QHBoxLayout()
        row_block.addWidget(QLabel(
            "Rozmiar bloku SHA-256 [KB]:" if is_pl else "SHA-256 block size [KB]:"
        ))
        self.spin_block = QSpinBox()
        self.spin_block.setRange(8, 4096)
        self.spin_block.setSingleStep(64)
        self.spin_block.setToolTip("Większy blok = szybciej na SSD, mniejszy = mniejsze użycie RAM" if is_pl else "Larger block = faster on SSD, smaller = lower RAM usage")
        row_block.addWidget(self.spin_block)
        g_layout.addLayout(row_block)

        self.chk_auto_compare = QCheckBox(
            "Automatycznie porównaj po załadowaniu szablonu" if is_pl else "Auto-compare after loading a profile"
        )
        self.chk_auto_compare.setToolTip("Po wyborze profilu z listy natychmiast uruchamia porównanie" if is_pl else "Immediately starts comparison when profile is chosen")
        g_layout.addWidget(self.chk_auto_compare)

        layout.addWidget(grp)

        grp2 = QGroupBox("Domyślny widok tabeli" if is_pl else "Default Table View")
        g2_layout = QVBoxLayout(grp2)

        row_sort = QHBoxLayout()
        row_sort.addWidget(QLabel("Domyślne sortowanie:" if is_pl else "Default sorting:"))
        self.combo_sort = QComboBox()
        if is_pl:
            self.combo_sort.addItems(["Status (priorytety)", "Ścieżka pliku (A-Z)", "Data modyfikacji A", "Data modyfikacji B", "Rozmiar"])
        else:
            self.combo_sort.addItems(["Status (priority)", "File path (A-Z)", "Modified date A", "Modified date B", "Size"])
        row_sort.addWidget(self.combo_sort)
        g2_layout.addLayout(row_sort)

        layout.addWidget(grp2)
        layout.addStretch()
        return w

    # ─── Zakładka: Synchronizacja ────────────────────────────────────────
    def _tab_sync(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        is_pl = self.lang == "pl"
        grp = QGroupBox("Zachowanie Synchronizacji" if is_pl else "Synchronization Behavior")
        g_layout = QVBoxLayout(grp)
        g_layout.setSpacing(10)

        row_confirm = QHBoxLayout()
        row_confirm.addWidget(QLabel("Okno potwierdzenia przed synchronizacją:" if is_pl else "Confirmation prompt before sync:"))
        self.combo_confirm = QComboBox()
        if is_pl:
            self.combo_confirm.addItems([
                "Zawsze pytaj",
                "Tylko gdy nadpisujesz pliki",
                "Nigdy nie pytaj (niebezpieczne!)",
            ])
        else:
            self.combo_confirm.addItems([
                "Always ask",
                "Only when overwriting files",
                "Never ask (dangerous!)",
            ])
        row_confirm.addWidget(self.combo_confirm)
        g_layout.addLayout(row_confirm)

        row_mode = QHBoxLayout()
        row_mode.addWidget(QLabel("Domyślny tryb synchronizacji:" if is_pl else "Default sync mode:"))
        self.combo_default_sync = QComboBox()
        if is_pl:
            self.combo_default_sync.addItems([
                "Inteligentna aktualizacja (nowsze zastępują starsze)",
                "Kopiuj z A do B",
                "Kopiuj z B do A",
            ])
        else:
            self.combo_default_sync.addItems([
                "Smart update (newer replaces older)",
                "Copy from A to B",
                "Copy from B to A",
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

        is_pl = self.lang == "pl"
        grp = QGroupBox(
            "Globalne wzorce wykluczeń (glob, jeden na linię)" if is_pl else "Global Exclusion Patterns (glob, one per line)"
        )
        g_layout = QVBoxLayout(grp)

        info_text = (
            "Pliki i katalogi pasujące do poniższych wzorców będą pomijane podczas skanowania.\n"
            "Wzorce obsługują znaki globbing: * (dowolny ciąg), ? (jeden znak).\n"
            "Przykłady: *.tmp  |  Thumbs.db  |  node_modules  |  .git"
            if is_pl else
            "Files and folders matching patterns below will be skipped during scan.\n"
            "Supports globbing wildcards: * (any sequence), ? (single character).\n"
            "Examples: *.tmp  |  Thumbs.db  |  node_modules  |  .git"
        )
        info = QLabel(info_text)
        info.setWordWrap(True)
        info.setStyleSheet("color: #888888; font-size: 12px;")
        g_layout.addWidget(info)

        self.text_exclusions = QTextEdit()
        self.text_exclusions.setPlaceholderText("*.tmp\nThumbs.db\n.git\nnode_modules")
        g_layout.addWidget(self.text_exclusions)

        btn_row = QHBoxLayout()
        btn_restore = QPushButton("⟳ Przywróć domyślne" if is_pl else "⟳ Restore Defaults")
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

        is_pl = self.lang == "pl"
        grp = QGroupBox("Historia Porównań" if is_pl else "Comparison History")
        g_layout = QVBoxLayout(grp)

        row_max = QHBoxLayout()
        row_max.addWidget(QLabel("Maksymalna liczba wpisów w historii:" if is_pl else "Max history entries:"))
        self.spin_max_history = QSpinBox()
        self.spin_max_history.setRange(10, 10000)
        self.spin_max_history.setSingleStep(50)
        row_max.addWidget(self.spin_max_history)
        g_layout.addLayout(row_max)

        layout.addWidget(grp)

        grp2 = QGroupBox("Eksport Raportów" if is_pl else "Report Export")
        g2_layout = QVBoxLayout(grp2)

        row_dir = QHBoxLayout()
        row_dir.addWidget(QLabel("Domyślny folder eksportu raportów:" if is_pl else "Default reports folder:"))
        self.edit_report_dir = QLineEdit()
        self.edit_report_dir.setPlaceholderText(
            "Pozostaw puste — program zapyta przy każdym eksporcie" if is_pl else "Leave blank — ask each time"
        )
        btn_browse = QPushButton("Przeglądaj..." if is_pl else "Browse...")
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

        is_pl = self.lang == "pl"
        grp = QGroupBox("Zachowanie ikony w zasobniku systemowym" if is_pl else "System Tray Behavior")
        g_layout = QVBoxLayout(grp)
        g_layout.setSpacing(10)

        self.chk_minimize_to_tray = QCheckBox(
            "Przy minimalizacji schowaj do zasobnika (zamiast na pasek zadań)" if is_pl else "Minimize window to system tray"
        )
        self.chk_close_to_tray = QCheckBox(
            "Przy zamknięciu okna schowaj do zasobnika (kontynuuj w tle)" if is_pl else "Close window to system tray (keep running)"
        )
        self.chk_tray_notifications = QCheckBox(
            "Wyświetlaj powiadomienia Windows po zakończeniu synchronizacji" if is_pl else "Show Windows desktop notifications upon completion"
        )

        g_layout.addWidget(self.chk_minimize_to_tray)
        g_layout.addWidget(self.chk_close_to_tray)
        g_layout.addWidget(self.chk_tray_notifications)
        layout.addWidget(grp)

        # Grupa 2: Harmonogram zadań
        grp_sched = QGroupBox("Harmonogram zadań w tle (Scheduler)" if is_pl else "Background Scheduler")
        g_sched_layout = QVBoxLayout(grp_sched)
        g_sched_layout.setSpacing(10)

        self.chk_scheduler_enabled = QCheckBox(
            "Włącz cykliczne sprawdzanie w tle (Harmonogram)" if is_pl else "Enable periodic background check (Scheduler)"
        )
        row_interval = QHBoxLayout()
        row_interval.addWidget(QLabel("Częstotliwość:" if is_pl else "Frequency:"))
        self.combo_scheduler_interval = QComboBox()
        self._interval_values = [5, 15, 30, 60, 120, 360, 1440]
        intervals_labels_pl = [
            "Co 5 minut", "Co 15 minut", "Co 30 minut",
            "Co 1 godzinę", "Co 2 godziny", "Co 6 godzin", "Codziennie (co 24h)"
        ]
        intervals_labels_en = [
            "Every 5 min", "Every 15 min", "Every 30 min",
            "Every 1 hour", "Every 2 hours", "Every 6 hours", "Daily (every 24h)"
        ]
        labels = intervals_labels_pl if is_pl else intervals_labels_en
        for idx, val in enumerate(self._interval_values):
            self.combo_scheduler_interval.addItem(labels[idx], val)
        row_interval.addWidget(self.combo_scheduler_interval)
        row_interval.addStretch()

        self.chk_scheduler_auto_sync = QCheckBox(
            "Automatycznie synchronizuj (z kopią zapasową .backup) przy wykryciu różnic"
            if is_pl else "Automatically sync (with .backup copy) when differences are detected"
        )

        g_sched_layout.addWidget(self.chk_scheduler_enabled)
        g_sched_layout.addLayout(row_interval)
        g_sched_layout.addWidget(self.chk_scheduler_auto_sync)
        layout.addWidget(grp_sched)

        # Grupa 3: Watch Mode
        grp_watch = QGroupBox("Ciągły Tryb Obserwatora (Watch Mode)" if is_pl else "Continuous Watch Mode")
        g_watch_layout = QVBoxLayout(grp_watch)
        g_watch_layout.setSpacing(10)

        self.chk_watch_mode = QCheckBox(
            "Monitoruj aktywne foldery w czasie rzeczywistym i reaguj na zmiany plików"
            if is_pl else "Monitor active folders in real-time and react to file changes"
        )
        g_watch_layout.addWidget(self.chk_watch_mode)
        layout.addWidget(grp_watch)

        layout.addStretch()
        return w

    # ─── Zakładka: Aktualizacje ──────────────────────────────────────────
    def _tab_updates(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(14)

        is_dark = is_dark_theme_active(self.settings.theme)
        accent_color = "#60CDFF" if is_dark else "#005FB8"

        # 1. Informacja o zainstalowanej wersji
        self.lbl_installed_ver = QLabel(f"🛡️ {tr('lbl_installed_version', self.lang, version=__version__)}")
        self.lbl_installed_ver.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.lbl_installed_ver.setStyleSheet(f"color: {accent_color}; margin-bottom: 2px;")
        layout.addWidget(self.lbl_installed_ver)

        # 2. Opcja automatycznego sprawdzania przy starcie
        grp_auto = QGroupBox(tr("grp_updates_status", self.lang))
        g_auto_layout = QVBoxLayout(grp_auto)
        g_auto_layout.setSpacing(10)

        self.chk_auto_updates = QCheckBox(tr("chk_check_updates_startup", self.lang))
        g_auto_layout.addWidget(self.chk_auto_updates)
        layout.addWidget(grp_auto)

        # 3. Ręczne sprawdzanie aktualizacji
        grp_manual = QGroupBox(tr("btn_check_updates_now", self.lang))
        g_manual_layout = QVBoxLayout(grp_manual)
        g_manual_layout.setSpacing(10)

        row_btn = QHBoxLayout()
        self.btn_check_updates = QPushButton(tr("btn_check_updates_now", self.lang))
        self.btn_check_updates.setObjectName("primaryButton")
        self.btn_check_updates.clicked.connect(self._on_manual_check_updates)
        row_btn.addWidget(self.btn_check_updates)
        row_btn.addStretch()
        g_manual_layout.addLayout(row_btn)

        self.lbl_update_status = QLabel(tr("status_update_idle", self.lang))
        self.lbl_update_status.setWordWrap(True)
        self.lbl_update_status.setFont(QFont("Segoe UI", 10))
        g_manual_layout.addWidget(self.lbl_update_status)

        self.btn_download_update = QPushButton(tr("btn_download_update", self.lang, version=""))
        self.btn_download_update.setVisible(False)
        self.btn_download_update.setStyleSheet(
            "background-color: #107C10; color: #FFFFFF; font-weight: bold; padding: 8px 16px; border-radius: 6px;"
        )
        self.btn_download_update.clicked.connect(self._on_download_update_clicked)
        g_manual_layout.addWidget(self.btn_download_update)

        self.txt_release_notes = QTextEdit()
        self.txt_release_notes.setReadOnly(True)
        self.txt_release_notes.setMaximumHeight(140)
        self.txt_release_notes.setVisible(False)
        g_manual_layout.addWidget(self.txt_release_notes)

        layout.addWidget(grp_manual)
        layout.addStretch()
        return w

    def _on_manual_check_updates(self):
        """Uruchamia asynchroniczne sprawdzanie aktualizacji w osobnym wątku."""
        self.btn_check_updates.setEnabled(False)
        self.btn_download_update.setVisible(False)
        self.txt_release_notes.setVisible(False)
        self.lbl_update_status.setText(tr("status_update_checking", self.lang))
        is_dark = is_dark_theme_active(self.settings.theme)
        self.lbl_update_status.setStyleSheet("color: #60CDFF;" if is_dark else "color: #005FB8;")

        self._update_worker = CheckUpdateWorker(repo=self.settings.github_repo, parent=self)
        self._update_worker.finished.connect(self._on_update_check_finished)
        self._update_worker.start()

    def _on_update_check_finished(self, info: UpdateInfo):
        """Prezentuje rezultat weryfikacji wersji użytkownikowi (WCAG AAA)."""
        self.btn_check_updates.setEnabled(True)
        is_dark = is_dark_theme_active(self.settings.theme)

        if info.error_message:
            self.lbl_update_status.setText(tr("status_update_error", self.lang, error=info.error_message))
            self.lbl_update_status.setStyleSheet("color: #FF5555; font-weight: 600;")
            return

        if info.is_available:
            self.lbl_update_status.setText(
                tr("status_update_available", self.lang, version=info.latest_version, current=info.current_version)
            )
            self.lbl_update_status.setStyleSheet("color: #107C10; font-weight: bold;" if not is_dark else "color: #4CAF50; font-weight: bold;")

            self._latest_download_url = info.download_url
            self.btn_download_update.setText(tr("btn_download_update", self.lang, version=info.latest_version))
            self.btn_download_update.setVisible(True)

            if info.release_notes:
                self.txt_release_notes.setPlainText(info.release_notes)
                self.txt_release_notes.setVisible(True)
        else:
            self.lbl_update_status.setText(tr("status_update_latest", self.lang, version=info.current_version))
            self.lbl_update_status.setStyleSheet("color: #107C10; font-weight: bold;" if not is_dark else "color: #4CAF50; font-weight: bold;")

    def _on_download_update_clicked(self):
        url = getattr(self, "_latest_download_url", "")
        if validate_https_url(url):
            QDesktopServices.openUrl(QUrl(url))

    # ─── Ładowanie i Zapisywanie ─────────────────────────────────────────
    def _load_values(self):
        s = self.settings
        theme_map = {"dark": 0, "light": 1, "auto": 2}
        self.combo_theme.setCurrentIndex(theme_map.get(s.theme, 0))
        self.combo_lang.setCurrentIndex(0 if s.language == "pl" else 1)

        self.spin_tolerance.setValue(s.time_tolerance_seconds)
        self.spin_block.setValue(s.sha256_block_size // 1024)
        self.chk_auto_compare.setChecked(s.auto_compare_on_profile_load)
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

        self.chk_scheduler_enabled.setChecked(s.scheduler_enabled)
        curr_int = s.scheduler_interval_minutes
        idx = self._interval_values.index(curr_int) if curr_int in self._interval_values else 2
        self.combo_scheduler_interval.setCurrentIndex(idx)
        self.chk_scheduler_auto_sync.setChecked(s.scheduler_auto_sync)
        self.chk_watch_mode.setChecked(s.watch_mode_enabled)

        self.chk_auto_updates.setChecked(s.check_updates_on_startup)

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

        s.scheduler_enabled = self.chk_scheduler_enabled.isChecked()
        s.scheduler_interval_minutes = self.combo_scheduler_interval.currentData() or 30
        s.scheduler_auto_sync = self.chk_scheduler_auto_sync.isChecked()
        s.watch_mode_enabled = self.chk_watch_mode.isChecked()

        s.check_updates_on_startup = self.chk_auto_updates.isChecked()

        invalidate_cache()
        if save_settings(s):
            apply_theme_to_app(s.theme)
            self.accept()

    def _restore_default_exclusions(self):
        defaults = AppSettings().global_exclude_patterns
        self.text_exclusions.setPlainText("\n".join(defaults))

    def _browse_report_dir(self):
        title = "Wybierz folder dla raportów" if self.lang == "pl" else "Select Reports Folder"
        path = QFileDialog.getExistingDirectory(self, title)
        if path:
            self.edit_report_dir.setText(path)
