"""Główne okno aplikacji FolderSync (Windows 11 Fluent Theme + WCAG AA/AAA).
Rozszerzone o:
- Menedżer szablonów / profili z szybkim dostępem do par katalogów
- Zaawansowane sortowanie tabeli (numeryczne po bajtach, chronologiczne po dacie, po wadze statusu)
- Menu kontekstowe (PPM) z otwieraniem plików w Eksploratorze Windows
- Podgląd różnic w treści plików tekstowych (Side-by-side Visual Diff)
"""

from __future__ import annotations
from datetime import datetime
import difflib
import os
from pathlib import Path
import subprocess
from typing import Any, Optional

from PyQt6.QtCore import QPoint, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFont, QIcon, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.comparator import ComparisonItem, FileStatus, calculate_sha256, compare_directories
from core.history import HistoryEntry, append_history_entry, make_entry_id
from core.profiles import SyncProfile, delete_profile, load_profiles, save_profile
from core.settings import load_settings
from core.i18n import tr, get_status_display_name
from gui.themes import (
    apply_theme_to_app,
    get_status_colors,
    get_theme_stylesheet,
    is_dark_theme_active,
)
from core.synchronizer import (
    SyncAction,
    SyncDirection,
    SyncReport,
    execute_sync,
    plan_sync_actions,
)


class SortableTableWidgetItem(QTableWidgetItem):
    """Element tabeli z precyzyjnym kluczem sortowania (liczbowy, chronologiczny, wagowy)."""

    def __init__(self, text: str, sort_key: Any = None):
        super().__init__(text)
        self.sort_key = sort_key

    def __lt__(self, other: QTableWidgetItem) -> bool:
        if isinstance(other, SortableTableWidgetItem) and self.sort_key is not None and other.sort_key is not None:
            return self.sort_key < other.sort_key
        return super().__lt__(other)


class CompareWorker(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, dir_a: Path, dir_b: Path, compare_hashes: bool,
                 exclude_patterns: list | None = None):
        super().__init__()
        self.dir_a = dir_a
        self.dir_b = dir_b
        self.compare_hashes = compare_hashes
        self.exclude_patterns = exclude_patterns or []

    def run(self):
        try:
            results = compare_directories(
                self.dir_a,
                self.dir_b,
                compare_hashes=self.compare_hashes,
                progress_callback=lambda cur, tot, name: self.progress.emit(cur, tot, name),
                exclude_patterns=self.exclude_patterns,
            )
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class SyncWorker(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, actions: list[SyncAction], create_backup: bool,
                 verify_sha256: bool, dry_run: bool = False):
        super().__init__()
        self.actions = actions
        self.create_backup = create_backup
        self.verify_sha256 = verify_sha256
        self.dry_run = dry_run

    def run(self):
        try:
            report = execute_sync(
                self.actions,
                create_backup=self.create_backup,
                verify_sha256=self.verify_sha256,
                progress_callback=lambda cur, tot, name: self.progress.emit(cur, tot, name),
                dry_run=self.dry_run,
            )
            self.finished.emit(report)
        except Exception as e:
            self.error.emit(str(e))


class DiffViewerDialog(QDialog):
    """Wbudowany podgląd różnic Side-by-Side dla plików tekstowych i kodu."""

    def __init__(self, rel_path: str, file_a: Path, file_b: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Podgląd różnic w treści: {rel_path}")
        self.resize(950, 650)
        theme = load_settings().theme
        self.setStyleSheet(get_theme_stylesheet(theme))

        is_dark = is_dark_theme_active(theme)
        color_a = "#60CDFF" if is_dark else "#005FB8"
        color_b = "#FFA500" if is_dark else "#D83B01"

        layout = QVBoxLayout(self)

        lbl_header = QLabel(f"Porównanie zawartości pliku: <b>{rel_path}</b>")
        lbl_header.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        layout.addWidget(lbl_header)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Panel A
        widget_a = QWidget()
        layout_a = QVBoxLayout(widget_a)
        layout_a.setContentsMargins(0, 0, 0, 0)
        lbl_a = QLabel(f"Katalog A ({file_a.parent.name}):")
        lbl_a.setStyleSheet(f"color: {color_a}; font-weight: bold;")
        self.text_a = QTextEdit()
        self.text_a.setReadOnly(True)
        self.text_a.setFont(QFont("Consolas", 10))
        layout_a.addWidget(lbl_a)
        layout_a.addWidget(self.text_a)
        splitter.addWidget(widget_a)

        # Panel B
        widget_b = QWidget()
        layout_b = QVBoxLayout(widget_b)
        layout_b.setContentsMargins(0, 0, 0, 0)
        lbl_b = QLabel(f"Katalog B ({file_b.parent.name}):")
        lbl_b.setStyleSheet(f"color: {color_b}; font-weight: bold;")
        self.text_b = QTextEdit()
        self.text_b.setReadOnly(True)
        self.text_b.setFont(QFont("Consolas", 10))
        layout_b.addWidget(lbl_b)
        layout_b.addWidget(self.text_b)
        splitter.addWidget(widget_b)

        layout.addWidget(splitter)

        btn_close = QPushButton("Zamknij podgląd")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

        self._load_and_diff(file_a, file_b)

    def _load_and_diff(self, file_a: Path, file_b: Path):
        content_a = ""
        content_b = ""
        try:
            if file_a.exists():
                content_a = file_a.read_text(encoding="utf-8", errors="replace")
            else:
                content_a = "[Plik nie istnieje w Katalogu A]"
        except Exception as e:
            content_a = f"[Błąd odczytu: {e}]"

        try:
            if file_b.exists():
                content_b = file_b.read_text(encoding="utf-8", errors="replace")
            else:
                content_b = "[Plik nie istnieje w Katalogu B]"
        except Exception as e:
            content_b = f"[Błąd odczytu: {e}]"

        self.text_a.setPlainText(content_a)
        self.text_b.setPlainText(content_b)


class ConfirmSyncDialog(QDialog):
    """Certyfikowane okno dialogowe potwierdzenia operacji nadpisywania (NASA / CERT Security Rule)."""

    def __init__(self, actions: list[SyncAction], create_backup: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Potwierdzenie Bezpieczeństwa Synchronizacji")
        self.resize(550, 320)
        theme = load_settings().theme
        self.setStyleSheet(get_theme_stylesheet(theme))

        total = len(actions)
        overwrites = sum(1 for a in actions if a.will_overwrite)
        new_files = total - overwrites

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        is_dark = is_dark_theme_active(theme)
        title_color = "#FFA500" if is_dark else "#D83B01"

        title = QLabel("⚠️ Wymagane potwierdzenie operacji na plikach")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {title_color};")
        layout.addWidget(title)

        info_text = (
            f"Za chwilę zostanie wykonana synchronizacja plików według wybranego planu:\n\n"
            f"  • Łączna liczba operacji: <b>{total}</b>\n"
            f"  • Pliki nowe (zostaną utworzone): <b>{new_files}</b>\n"
            f"  • Pliki istniejące (zostaną <b>NAD PISANE</b>): <b>{overwrites}</b>\n\n"
        )
        if create_backup:
            info_text += (
                "🛡️ <b>Aktywna ochrona danych:</b> Zostanie utworzona automatyczna kopia zapasowa (.backup) "
                "każdego nadpisywanego pliku z pełną weryfikacją sumy SHA-256."
            )
        else:
            info_text += (
                "<font color='#FF5555'><b>UWAGA:</b> Wyłączono tworzenie kopii zapasowej. "
                "Nadpisane pliki nie będą mogły zostać odzyskane!</font>"
            )

        msg_label = QLabel(info_text)
        msg_label.setWordWrap(True)
        layout.addWidget(msg_label)

        button_box = QDialogButtonBox()
        btn_cancel = button_box.addButton("Anuluj (bezpieczny powrót)", QDialogButtonBox.ButtonRole.RejectRole)
        btn_confirm = button_box.addButton("Zatwierdź i rozpocznij", QDialogButtonBox.ButtonRole.AcceptRole)
        btn_confirm.setObjectName("primaryButton")

        btn_cancel.setDefault(True)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)


class DropLineEdit(QLineEdit):
    """Pole tekstowe z obsługą przeciągania folderów (Drag & Drop)."""

    def __init__(self, placeholder: str = ""):
        super().__init__()
        self.setPlaceholderText(placeholder)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            local_path = url.toLocalFile()
            if Path(local_path).is_dir():
                self.setText(local_path)
                break


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        settings = load_settings()
        self.setWindowTitle(tr("window_title", settings.language))
        self.resize(1150, 780)
        apply_theme_to_app(settings.theme, self)

        icon_path = Path(__file__).resolve().parent.parent / "app_icon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.current_items: list[ComparisonItem] = []
        self.compare_thread: Optional[CompareWorker] = None
        self.sync_thread: Optional[SyncWorker] = None
        self.profiles: dict[str, SyncProfile] = {}
        self._current_entry_id: str = ""

        self._build_ui()
        self._refresh_profiles_list()
        self._apply_settings_to_ui()

    def _build_ui(self):
        settings = load_settings()
        lang = settings.language

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(10)

        # 1. Pasek Szablonów / Profili (Szybki Dostęp)
        self.profile_group = QGroupBox(tr("group_profiles", lang))
        profile_layout = QHBoxLayout(self.profile_group)

        self.combo_profiles = QComboBox()
        self.combo_profiles.setMinimumWidth(320)
        self.combo_profiles.currentIndexChanged.connect(self._on_profile_selected)

        self.btn_save_profile = QPushButton(tr("btn_save_profile", lang))
        self.btn_save_profile.setToolTip(tr("btn_save_profile_tip", lang))
        self.btn_save_profile.clicked.connect(self._save_current_as_profile)

        self.btn_delete_profile = QPushButton(tr("btn_delete_profile", lang))
        self.btn_delete_profile.setToolTip(tr("btn_delete_profile_tip", lang))
        self.btn_delete_profile.clicked.connect(self._delete_current_profile)

        self.lbl_select_profile = QLabel(tr("lbl_select_profile", lang))
        profile_layout.addWidget(self.lbl_select_profile)
        profile_layout.addWidget(self.combo_profiles)
        profile_layout.addWidget(self.btn_save_profile)
        profile_layout.addWidget(self.btn_delete_profile)
        profile_layout.addStretch()

        main_layout.addWidget(self.profile_group)

        # 2. Wybór katalogów A i B
        self.dir_group = QGroupBox(tr("group_directories", lang))
        dir_layout = QGridLayout(self.dir_group)
        dir_layout.setSpacing(8)

        self.lbl_dir_a = QLabel(tr("lbl_dir_a", lang))
        self.lbl_dir_a.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        self.edit_dir_a = DropLineEdit(tr("placeholder_dir_a", lang))
        self.btn_browse_a = QPushButton(tr("btn_browse", lang))
        self.btn_browse_a.clicked.connect(self._browse_a)

        dir_layout.addWidget(self.lbl_dir_a, 0, 0)
        dir_layout.addWidget(self.edit_dir_a, 0, 1)
        dir_layout.addWidget(self.btn_browse_a, 0, 2)

        self.lbl_dir_b = QLabel(tr("lbl_dir_b", lang))
        self.lbl_dir_b.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        self.edit_dir_b = DropLineEdit(tr("placeholder_dir_b", lang))
        self.btn_browse_b = QPushButton(tr("btn_browse", lang))
        self.btn_browse_b.clicked.connect(self._browse_b)

        dir_layout.addWidget(self.lbl_dir_b, 1, 0)
        dir_layout.addWidget(self.edit_dir_b, 1, 1)
        dir_layout.addWidget(self.btn_browse_b, 1, 2)

        main_layout.addWidget(self.dir_group)

        # 3. Opcje porównywania i przycisk startowy
        opt_layout = QHBoxLayout()
        self.chk_hash = QCheckBox(tr("chk_hash", lang))
        self.chk_hash.setToolTip(tr("chk_hash_tip", lang))
        self.chk_hash.setChecked(False)

        self.btn_compare = QPushButton(tr("btn_compare", lang))
        self.btn_compare.setObjectName("primaryButton")
        self.btn_compare.setFixedHeight(36)
        self.btn_compare.clicked.connect(self._start_compare)

        self.btn_dry_run = QPushButton(tr("btn_dry_run", lang))
        self.btn_dry_run.setToolTip(tr("btn_dry_run_tip", lang))
        self.btn_dry_run.setFixedHeight(36)
        self.btn_dry_run.setEnabled(False)
        self.btn_dry_run.clicked.connect(self._start_dry_run)

        opt_layout.addWidget(self.chk_hash)
        opt_layout.addStretch()
        opt_layout.addWidget(self.btn_dry_run)
        opt_layout.addWidget(self.btn_compare)
        main_layout.addLayout(opt_layout)

        # Pasek postępu operacji
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel(tr("lbl_status_initial", lang))
        self.lbl_status.setStyleSheet("color: #888888;")
        main_layout.addWidget(self.lbl_status)

        # 4. Pasek filtrów i szybkich akcji
        filter_layout = QHBoxLayout()
        self.lbl_filter = QLabel(tr("lbl_filter", lang))
        filter_layout.addWidget(self.lbl_filter)

        self.combo_filter = QComboBox()
        self._populate_filter_combo(lang)
        self.combo_filter.currentIndexChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.combo_filter)

        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText(tr("placeholder_search", lang))
        self.edit_search.textChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.edit_search)

        filter_layout.addStretch()

        self.btn_select_all = QPushButton(tr("btn_select_all", lang))
        self.btn_select_all.clicked.connect(lambda: self._set_all_visible_checked(True))
        self.btn_deselect_all = QPushButton(tr("btn_deselect_all", lang))
        self.btn_deselect_all.clicked.connect(lambda: self._set_all_visible_checked(False))
        filter_layout.addWidget(self.btn_select_all)
        filter_layout.addWidget(self.btn_deselect_all)

        main_layout.addLayout(filter_layout)

        # 5. Tabela wyników porównania z obsługą sortowania i menu kontekstowego
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self._set_table_headers(lang)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        # Włączenie natywnego sortowania po nagłówkach kolumn
        self.table.setSortingEnabled(True)

        # Menu kontekstowe pod prawym przyciskiem myszy
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._open_context_menu)
        self.table.cellDoubleClicked.connect(self._on_table_double_click)

        main_layout.addWidget(self.table)

        # 6. Panel dolny: Synchronizacja i Ochrona Danych
        self.sync_group = QGroupBox(tr("group_sync", lang))
        sync_layout = QHBoxLayout(self.sync_group)

        self.chk_backup = QCheckBox(tr("chk_backup", lang))
        self.chk_backup.setChecked(True)
        self.chk_backup.setToolTip(tr("chk_backup_tip", lang))

        self.combo_sync_mode = QComboBox()
        self._populate_sync_modes(lang)

        self.btn_sync = QPushButton(tr("btn_sync", lang))
        self.btn_sync.setObjectName("syncButton")
        self.btn_sync.setEnabled(False)
        self.btn_sync.clicked.connect(self._start_sync)

        self.lbl_sync_mode = QLabel(tr("lbl_sync_mode", lang))
        sync_layout.addWidget(self.chk_backup)
        sync_layout.addSpacing(20)
        sync_layout.addWidget(self.lbl_sync_mode)
        sync_layout.addWidget(self.combo_sync_mode)
        sync_layout.addStretch()
        sync_layout.addWidget(self.btn_sync)

        main_layout.addWidget(self.sync_group)

        # 7. Pasek narzędzi dolny: Historia, Eksport, Backup Manager, Ustawienia
        tools_layout = QHBoxLayout()

        self.btn_history = QPushButton(tr("btn_history", lang))
        self.btn_history.setToolTip(tr("btn_history_tip", lang))
        self.btn_history.clicked.connect(self._open_history)
        tools_layout.addWidget(self.btn_history)

        self.btn_export_html = QPushButton(tr("btn_export_html", lang))
        self.btn_export_html.setToolTip(tr("btn_export_html_tip", lang))
        self.btn_export_html.clicked.connect(lambda: self._export_report("html"))
        tools_layout.addWidget(self.btn_export_html)

        self.btn_export_csv = QPushButton(tr("btn_export_csv", lang))
        self.btn_export_csv.setToolTip(tr("btn_export_csv_tip", lang))
        self.btn_export_csv.clicked.connect(lambda: self._export_report("csv"))
        tools_layout.addWidget(self.btn_export_csv)

        self.btn_backup_mgr = QPushButton(tr("btn_backup_mgr", lang))
        self.btn_backup_mgr.setToolTip(tr("btn_backup_mgr_tip", lang))
        self.btn_backup_mgr.clicked.connect(self._open_backup_manager)
        tools_layout.addWidget(self.btn_backup_mgr)

        tools_layout.addStretch()

        self.btn_settings = QPushButton(tr("btn_settings", lang))
        self.btn_settings.setToolTip(tr("btn_settings_tip", lang))
        self.btn_settings.clicked.connect(self._open_settings)
        self.btn_settings.setShortcut(QKeySequence("Ctrl+,"))
        tools_layout.addWidget(self.btn_settings)

        main_layout.addLayout(tools_layout)

    def _populate_filter_combo(self, lang: str):
        curr = self.combo_filter.currentIndex() if hasattr(self, "combo_filter") and self.combo_filter.count() > 0 else 0
        self.combo_filter.blockSignals(True)
        self.combo_filter.clear()
        self.combo_filter.addItems([
            tr("filter_all", lang),
            tr("filter_diff_only", lang),
            tr("filter_newer_a", lang),
            tr("filter_newer_b", lang),
            tr("filter_only_a_b", lang),
            tr("filter_identical", lang),
        ])
        if 0 <= curr < self.combo_filter.count():
            self.combo_filter.setCurrentIndex(curr)
        self.combo_filter.blockSignals(False)

    def _set_table_headers(self, lang: str):
        self.table.setHorizontalHeaderLabels([
            tr("col_select", lang),
            tr("col_status", lang),
            tr("col_rel_path", lang),
            tr("col_size", lang),
            tr("col_mtime_a", lang),
            tr("col_mtime_b", lang),
        ])

    def _populate_sync_modes(self, lang: str):
        curr = self.combo_sync_mode.currentIndex() if hasattr(self, "combo_sync_mode") and self.combo_sync_mode.count() > 0 else 0
        self.combo_sync_mode.blockSignals(True)
        self.combo_sync_mode.clear()
        self.combo_sync_mode.addItem(tr("sync_mode_update", lang), SyncDirection.UPDATE_OLDER)
        self.combo_sync_mode.addItem(tr("sync_mode_a_to_b", lang), SyncDirection.COPY_A_TO_B)
        self.combo_sync_mode.addItem(tr("sync_mode_b_to_a", lang), SyncDirection.COPY_B_TO_A)
        if 0 <= curr < self.combo_sync_mode.count():
            self.combo_sync_mode.setCurrentIndex(curr)
        self.combo_sync_mode.blockSignals(False)

    # ================= Menedżer Szablonów / Profili =================

    def _refresh_profiles_list(self, select_name: Optional[str] = None):
        self.profiles = load_profiles()
        self.combo_profiles.blockSignals(True)
        self.combo_profiles.clear()
        self.combo_profiles.addItem("-- Wybierz lub zapisz szablon --", None)

        selected_idx = 0
        for idx, name in enumerate(sorted(self.profiles.keys()), start=1):
            self.combo_profiles.addItem(f"📁 {name}", name)
            if select_name and name == select_name:
                selected_idx = idx

        self.combo_profiles.setCurrentIndex(selected_idx)
        self.combo_profiles.blockSignals(False)
        if select_name and selected_idx > 0:
            self._on_profile_selected(selected_idx)

    def _on_profile_selected(self, index: int):
        profile_name = self.combo_profiles.currentData()
        if not profile_name or profile_name not in self.profiles:
            return

        p = self.profiles[profile_name]
        self.edit_dir_a.setText(p.dir_a)
        self.edit_dir_b.setText(p.dir_b)
        self.chk_hash.setChecked(p.compare_hashes)
        self.chk_backup.setChecked(p.create_backup)

        # Ustawienie trybu synchronizacji
        for i in range(self.combo_sync_mode.count()):
            if self.combo_sync_mode.itemData(i).value == p.sync_mode:
                self.combo_sync_mode.setCurrentIndex(i)
                break

        self.lbl_status.setText(f"Załadowano szablon „{p.name}”. Kliknij „Porównaj zawartość”.")

        settings = load_settings()
        if settings.auto_compare_on_profile_load:
            self._start_compare()

    def _save_current_as_profile(self):
        dir_a = self.edit_dir_a.text().strip()
        dir_b = self.edit_dir_b.text().strip()

        if not dir_a or not dir_b:
            QMessageBox.warning(
                self,
                "Brak ścieżek",
                "Wskaż najpierw Katalog A oraz Katalog B, aby zapisać je jako szablon.",
            )
            return

        suggested_name = f"{Path(dir_a).name} ➔ {Path(dir_b).name}"
        name, ok = QInputDialog.getText(
            self,
            "Nowy szablon",
            "Wpisz nazwę dla nowego szablonu:",
            text=suggested_name,
        )

        if ok and name.strip():
            clean_name = name.strip()
            profile = SyncProfile(
                name=clean_name,
                dir_a=dir_a,
                dir_b=dir_b,
                compare_hashes=self.chk_hash.isChecked(),
                create_backup=self.chk_backup.isChecked(),
                sync_mode=self.combo_sync_mode.currentData().value,
            )
            if save_profile(profile):
                self._refresh_profiles_list(select_name=clean_name)
                QMessageBox.information(self, "Szablon zapisany", f"Szablon „{clean_name}” został pomyślnie zapisany!")
            else:
                QMessageBox.critical(self, "Błąd", "Nie udało się zapisać szablonu.")

    def _delete_current_profile(self):
        profile_name = self.combo_profiles.currentData()
        if not profile_name:
            QMessageBox.information(self, "Informacja", "Wybierz z listy szablon, który chcesz usunąć.")
            return

        res = QMessageBox.question(
            self,
            "Potwierdzenie usunięcia",
            f"Czy na pewno chcesz trwale usunąć szablon „{profile_name}”?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if res == QMessageBox.StandardButton.Yes:
            delete_profile(profile_name)
            self._refresh_profiles_list()
            self.lbl_status.setText(f"Usunięto szablon „{profile_name}”.")

    # ================= Obsługa Porównywania =================

    def _browse_a(self):
        path = QFileDialog.getExistingDirectory(self, "Wybierz Katalog A")
        if path:
            self.edit_dir_a.setText(path)

    def _browse_b(self):
        path = QFileDialog.getExistingDirectory(self, "Wybierz Katalog B")
        if path:
            self.edit_dir_b.setText(path)

    def _start_compare(self):
        path_a = Path(self.edit_dir_a.text().strip())
        path_b = Path(self.edit_dir_b.text().strip())

        if not path_a.is_dir() or not path_b.is_dir():
            QMessageBox.warning(
                self,
                "Błąd ścieżki",
                "Upewnij się, że oba katalogi (A i B) zostały poprawnie wybrane i istnieją na dysku.",
            )
            return

        self.btn_compare.setEnabled(False)
        self.btn_sync.setEnabled(False)
        self.btn_dry_run.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Skanowanie i porównywanie plików w toku...")

        settings = load_settings()
        self._current_entry_id = make_entry_id()
        self.compare_thread = CompareWorker(
            path_a, path_b, self.chk_hash.isChecked(),
            exclude_patterns=settings.global_exclude_patterns,
        )
        self.compare_thread.progress.connect(self._on_compare_progress)
        self.compare_thread.finished.connect(self._on_compare_finished)
        self.compare_thread.error.connect(self._on_compare_error)
        self.compare_thread.start()

    def _on_compare_progress(self, current: int, total: int, file_name: str):
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
            self.lbl_status.setText(f"Porównywanie [{current}/{total}]: {file_name}")

    def _on_compare_finished(self, items: list[ComparisonItem]):
        self.current_items = items
        self.progress_bar.setVisible(False)
        self.btn_compare.setEnabled(True)
        self.btn_dry_run.setEnabled(True)

        self._populate_table()

        total = len(items)
        diff_count = sum(1 for it in items if it.status.is_different)
        newer_a = sum(1 for it in items if it.status == FileStatus.NEWER_A)
        newer_b = sum(1 for it in items if it.status == FileStatus.NEWER_B)
        only_a = sum(1 for it in items if it.status == FileStatus.ONLY_A)
        only_b = sum(1 for it in items if it.status == FileStatus.ONLY_B)
        identical = sum(1 for it in items if it.status == FileStatus.IDENTICAL)

        self.lbl_status.setText(
            f"Zakończono: Łącznie: {total} | Różniących się: {diff_count} "
            f"(Nowsze w A: {newer_a}, Nowsze w B: {newer_b}, Tylko w A: {only_a}, Tylko w B: {only_b}). "
            f"Kliknij kolumnę, aby posortować."
        )
        self.btn_sync.setEnabled(diff_count > 0)

        # Zapis do historii
        profile_name = self.combo_profiles.currentData() or ""
        entry = HistoryEntry(
            entry_id=self._current_entry_id,
            timestamp=datetime.now().isoformat(),
            dir_a=self.edit_dir_a.text().strip(),
            dir_b=self.edit_dir_b.text().strip(),
            profile_name=profile_name if isinstance(profile_name, str) else "",
            total_files=total,
            identical_files=identical,
            different_files=diff_count,
            only_in_a=only_a,
            only_in_b=only_b,
            compare_hashes=self.chk_hash.isChecked(),
        )
        append_history_entry(entry)

    def _on_compare_error(self, err_msg: str):
        self.progress_bar.setVisible(False)
        self.btn_compare.setEnabled(True)
        self.lbl_status.setText("Wystąpił błąd podczas porównywania.")
        QMessageBox.critical(self, "Błąd porównywania", f"Operacja nie powiodła się:\n{err_msg}")

    # ================= Wypełnianie i Inteligentne Sortowanie Tabeli =================

    def _populate_table(self):
        # Wyłączamy sortowanie na czas wstawiania dla optymalizacji wydajności
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.current_items))

        lang = load_settings().language

        status_weights = {
            FileStatus.ERROR: 0,
            FileStatus.DIFFERENT_CONTENT: 1,
            FileStatus.NEWER_A: 2,
            FileStatus.NEWER_B: 3,
            FileStatus.ONLY_A: 4,
            FileStatus.ONLY_B: 5,
            FileStatus.IDENTICAL: 6,
        }

        for row, item in enumerate(self.current_items):
            # Kolumna 0: Checkbox z kluczem sortowania (1 = zaznaczony, 0 = odznaczony)
            chk_widget = QWidget()
            chk_layout = QHBoxLayout(chk_widget)
            chk_layout.setContentsMargins(8, 0, 8, 0)
            chk_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cb = QCheckBox()
            cb.setChecked(item.is_checked)

            col0_item = SortableTableWidgetItem("", sort_key=int(item.is_checked))
            self.table.setItem(row, 0, col0_item)

            def make_handler(it=item, c_item=col0_item):
                def handler(state):
                    it.is_checked = bool(state)
                    c_item.sort_key = int(it.is_checked)
                return handler

            cb.stateChanged.connect(make_handler())
            chk_layout.addWidget(cb)
            self.table.setCellWidget(row, 0, chk_widget)

            # Kolumna 1: Status z wagą sortowania
            s_weight = status_weights.get(item.status, 99)
            status_text = get_status_display_name(item.status, lang)
            status_item = SortableTableWidgetItem(status_text, sort_key=s_weight)
            status_item.setData(Qt.ItemDataRole.UserRole, item)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._apply_status_style(status_item, item.status)
            self.table.setItem(row, 1, status_item)

            # Kolumna 2: Ścieżka (sortowanie alfabetyczne po tekście)
            path_item = SortableTableWidgetItem(item.rel_path, sort_key=item.rel_path.lower())
            path_item.setData(Qt.ItemDataRole.UserRole, item)
            self.table.setItem(row, 2, path_item)

            # Kolumna 3: Rozmiar (sortowanie precyzyjne numerycznie po bajtach)
            size_txt_a = self._format_size(item.size_a)
            size_txt_b = self._format_size(item.size_b)
            raw_size = max(item.size_a or 0, item.size_b or 0)
            size_item = SortableTableWidgetItem(f"{size_txt_a} / {size_txt_b}", sort_key=raw_size)
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 3, size_item)

            # Kolumna 4: Data w A (sortowanie po timestampie)
            ts_a = item.mtime_a.timestamp() if item.mtime_a else 0.0
            mtime_a_str = item.mtime_a.strftime("%Y-%m-%d %H:%M:%S") if item.mtime_a else "—"
            item_ma = SortableTableWidgetItem(mtime_a_str, sort_key=ts_a)
            item_ma.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 4, item_ma)

            # Kolumna 5: Data w B (sortowanie po timestampie)
            ts_b = item.mtime_b.timestamp() if item.mtime_b else 0.0
            mtime_b_str = item.mtime_b.strftime("%Y-%m-%d %H:%M:%S") if item.mtime_b else "—"
            item_mb = SortableTableWidgetItem(mtime_b_str, sort_key=ts_b)
            item_mb.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 5, item_mb)

        self.table.setSortingEnabled(True)
        self._apply_filter()

    def _apply_status_style(self, table_item: QTableWidgetItem, status: FileStatus):
        font = table_item.font()
        font.setBold(True)
        table_item.setFont(font)

        settings = load_settings()
        is_dark = is_dark_theme_active(settings.theme)
        bg, fg = get_status_colors(status, is_dark)
        table_item.setBackground(bg)
        table_item.setForeground(fg)

    def _format_size(self, size_bytes: Optional[int]) -> str:
        if size_bytes is None:
            return "—"
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.2f} MB"

    def _apply_filter(self):
        filter_idx = self.combo_filter.currentIndex()
        search_query = self.edit_search.text().strip().lower()

        for row in range(self.table.rowCount()):
            path_item = self.table.item(row, 2)
            if not path_item:
                continue

            item: Optional[ComparisonItem] = path_item.data(Qt.ItemDataRole.UserRole)
            if not item:
                continue

            matches_filter = True
            if filter_idx == 1:
                matches_filter = item.status.is_different
            elif filter_idx == 2:
                matches_filter = item.status == FileStatus.NEWER_A
            elif filter_idx == 3:
                matches_filter = item.status == FileStatus.NEWER_B
            elif filter_idx == 4:
                matches_filter = item.status in (FileStatus.ONLY_A, FileStatus.ONLY_B)
            elif filter_idx == 5:
                matches_filter = item.status == FileStatus.IDENTICAL

            matches_search = True
            if search_query:
                matches_search = search_query in item.rel_path.lower()

            self.table.setRowHidden(row, not (matches_filter and matches_search))

    def _set_all_visible_checked(self, checked: bool):
        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row):
                chk_widget = self.table.cellWidget(row, 0)
                if chk_widget:
                    cb = chk_widget.findChild(QCheckBox)
                    if cb:
                        cb.setChecked(checked)

    # ================= Menu Kontekstowe i Podgląd Różnic =================

    def _open_context_menu(self, position: QPoint):
        row = self.table.rowAt(position.y())
        if row < 0:
            return

        path_item = self.table.item(row, 2)
        if not path_item:
            return

        item: Optional[ComparisonItem] = path_item.data(Qt.ItemDataRole.UserRole)
        if not item:
            return

        base_a = Path(self.edit_dir_a.text().strip())
        base_b = Path(self.edit_dir_b.text().strip())
        file_a = base_a / item.rel_path
        file_b = base_b / item.rel_path

        menu = QMenu(self)

        act_diff = QAction("🔍 Pokaż różnice w treści (Side-by-Side Diff)", self)
        act_diff.setEnabled(file_a.exists() and file_b.exists())
        act_diff.triggered.connect(lambda: self._show_diff(item.rel_path, file_a, file_b))
        menu.addAction(act_diff)

        menu.addSeparator()

        act_open_a = QAction("📂 Pokaż w Eksploratorze (Katalog A)", self)
        act_open_a.setEnabled(file_a.exists())
        act_open_a.triggered.connect(lambda: self._reveal_in_explorer(file_a))
        menu.addAction(act_open_a)

        act_open_b = QAction("📂 Pokaż w Eksploratorze (Katalog B)", self)
        act_open_b.setEnabled(file_b.exists())
        act_open_b.triggered.connect(lambda: self._reveal_in_explorer(file_b))
        menu.addAction(act_open_b)

        menu.addSeparator()

        act_copy_path = QAction("📋 Kopiuj względną ścieżkę do schowka", self)
        act_copy_path.triggered.connect(lambda: QApplication.clipboard().setText(item.rel_path))
        menu.addAction(act_copy_path)

        menu.exec(self.table.viewport().mapToGlobal(position))

    def _on_table_double_click(self, row: int, col: int):
        path_item = self.table.item(row, 2)
        if not path_item:
            return
        item: Optional[ComparisonItem] = path_item.data(Qt.ItemDataRole.UserRole)
        if not item:
            return

        base_a = Path(self.edit_dir_a.text().strip())
        base_b = Path(self.edit_dir_b.text().strip())
        file_a = base_a / item.rel_path
        file_b = base_b / item.rel_path

        if file_a.exists() and file_b.exists():
            self._show_diff(item.rel_path, file_a, file_b)
        elif file_a.exists():
            self._reveal_in_explorer(file_a)
        elif file_b.exists():
            self._reveal_in_explorer(file_b)

    def _show_diff(self, rel_path: str, file_a: Path, file_b: Path):
        dlg = DiffViewerDialog(rel_path, file_a, file_b, self)
        dlg.exec()

    def _reveal_in_explorer(self, target_path: Path):
        if not target_path.exists():
            return
        try:
            # Bezpieczne zaznaczenie pliku w Windows Explorer
            subprocess.run(["explorer.exe", f"/select,{target_path}"], check=False)
        except Exception as e:
            QMessageBox.warning(self, "Błąd", f"Nie można otworzyć Eksploratora: {e}")

    # ================= Synchronizacja =================

    def _start_sync(self):
        path_a = Path(self.edit_dir_a.text().strip())
        path_b = Path(self.edit_dir_b.text().strip())
        direction = self.combo_sync_mode.currentData()

        actions = plan_sync_actions(self.current_items, path_a, path_b, direction)

        if not actions:
            QMessageBox.information(
                self,
                "Brak plików do synchronizacji",
                "Żaden z zaznaczonych plików nie wymaga synchronizacji w wybranym trybie.",
            )
            return

        confirm_dlg = ConfirmSyncDialog(actions, self.chk_backup.isChecked(), self)
        if confirm_dlg.exec() != QDialog.DialogCode.Accepted:
            return

        self.btn_compare.setEnabled(False)
        self.btn_sync.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Synchronizowanie plików...")

        self.sync_thread = SyncWorker(
            actions=actions,
            create_backup=self.chk_backup.isChecked(),
            verify_sha256=True,
        )
        self.sync_thread.progress.connect(self._on_sync_progress)
        self.sync_thread.finished.connect(self._on_sync_finished)
        self.sync_thread.error.connect(self._on_sync_error)
        self.sync_thread.start()

    def _on_sync_progress(self, current: int, total: int, file_name: str):
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
            self.lbl_status.setText(f"Synchronizacja [{current}/{total}]: {file_name}")

    def _on_sync_finished(self, report: SyncReport):
        self.progress_bar.setVisible(False)
        self.btn_compare.setEnabled(True)

        summary_msg = report.summary()
        if report.errors:
            summary_msg += "\n\nBłędy operacji:\n" + "\n".join(report.errors[:5])

        if report.is_dry_run:
            QMessageBox.information(self, "⚠️ Wynik Symulacji (Dry-Run)", summary_msg)
        else:
            QMessageBox.information(self, "Raport Końcowy Synchronizacji", summary_msg)
            # Aktualizuj historię o status synchronizacji
            entries = __import__('core.history', fromlist=['load_history', 'save_history'])
            from core.history import load_history, save_history
            history = load_history()
            for e in history:
                if e.entry_id == self._current_entry_id:
                    e.synced = True
                    e.sync_timestamp = datetime.now().isoformat()
                    e.files_updated = report.files_updated
                    e.bytes_transferred = report.bytes_transferred
                    e.errors = report.errors[:10]
                    break
            save_history(history)
            self._start_compare()

    def _on_sync_error(self, err_msg: str):
        self.progress_bar.setVisible(False)
        self.btn_compare.setEnabled(True)
        self.btn_sync.setEnabled(True)
        QMessageBox.critical(self, "Błąd synchronizacji", f"Wystąpił błąd:\n{err_msg}")

    # ================= Dry-Run =================

    def _start_dry_run(self):
        """Uruchom synchronizację w trybie symulacji — bez żadnych zmian na dysku."""
        path_a = Path(self.edit_dir_a.text().strip())
        path_b = Path(self.edit_dir_b.text().strip())
        direction = self.combo_sync_mode.currentData()

        actions = plan_sync_actions(self.current_items, path_a, path_b, direction)
        if not actions:
            QMessageBox.information(self, "Dry-Run",
                                    "Brak plików do synchronizacji w wybranym trybie.")
            return

        self.btn_compare.setEnabled(False)
        self.btn_sync.setEnabled(False)
        self.btn_dry_run.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.lbl_status.setText("⚠️ Symulacja (Dry-Run) — żadne pliki nie zostaną zmodyfikowane...")

        self.sync_thread = SyncWorker(
            actions=actions,
            create_backup=False,
            verify_sha256=False,
            dry_run=True,
        )
        self.sync_thread.progress.connect(self._on_sync_progress)
        self.sync_thread.finished.connect(self._on_sync_finished)
        self.sync_thread.error.connect(self._on_sync_error)
        self.sync_thread.start()

    # ================= Eksport Raportów =================

    def _export_report(self, fmt: str):
        if not self.current_items:
            QMessageBox.warning(self, "Brak danych",
                                "Najpierw przeprowadź porównanie katalogów.")
            return

        settings = load_settings()
        default_dir = settings.report_output_dir or str(Path.home())
        ext = "html" if fmt == "html" else "csv"
        flt = "Raport HTML (*.html)" if fmt == "html" else "Raport CSV (*.csv)"
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Zapisz raport", str(Path(default_dir) / f"raport_foldersync.{ext}"), flt
        )
        if not path_str:
            return

        from gui.report_exporter import export_html, export_csv
        out_path = Path(path_str)
        profile_name = self.combo_profiles.currentData() or ""
        ok = False
        if fmt == "html":
            ok = export_html(
                self.current_items,
                self.edit_dir_a.text().strip(),
                self.edit_dir_b.text().strip(),
                out_path,
                profile_name=str(profile_name) if profile_name else "",
            )
        else:
            ok = export_csv(
                self.current_items,
                self.edit_dir_a.text().strip(),
                self.edit_dir_b.text().strip(),
                out_path,
            )

        if ok:
            res = QMessageBox.information(
                self, "Raport zapisany",
                f"Raport został zapisany:\n{out_path}\n\nCzy chcesz otworzyć plik?",
                QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Ok,
            )
            if res == QMessageBox.StandardButton.Open:
                import subprocess
                subprocess.run(["explorer.exe", str(out_path)], check=False)
        else:
            QMessageBox.critical(self, "Błąd", f"Nie można zapisać raportu: {out_path}")

    # ================= Historia, Backup Manager, Ustawienia =================

    def _open_history(self):
        from gui.history_dialog import HistoryDialog
        dlg = HistoryDialog(self)
        dlg.exec()

    def _open_backup_manager(self):
        from gui.backup_manager import BackupManagerDialog
        dlg = BackupManagerDialog(
            dir_a=self.edit_dir_a.text().strip(),
            dir_b=self.edit_dir_b.text().strip(),
            parent=self,
        )
        dlg.exec()

    def _open_settings(self):
        from gui.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self)
        dlg.exec()
        # Odśwież UI po zapisaniu ustawień (motyw, język, parametry)
        self._apply_settings_to_ui()

    def _update_ui_language(self, lang: str):
        """Aktualizuje wszystkie etykiety, przyciski i teksty w oknie na wskazany język."""
        self.setWindowTitle(tr("window_title", lang))

        if hasattr(self, "profile_group"):
            self.profile_group.setTitle(tr("group_profiles", lang))
        if hasattr(self, "lbl_select_profile"):
            self.lbl_select_profile.setText(tr("lbl_select_profile", lang))
        if hasattr(self, "btn_save_profile"):
            self.btn_save_profile.setText(tr("btn_save_profile", lang))
            self.btn_save_profile.setToolTip(tr("btn_save_profile_tip", lang))
        if hasattr(self, "btn_delete_profile"):
            self.btn_delete_profile.setText(tr("btn_delete_profile", lang))
            self.btn_delete_profile.setToolTip(tr("btn_delete_profile_tip", lang))

        if hasattr(self, "dir_group"):
            self.dir_group.setTitle(tr("group_directories", lang))
        if hasattr(self, "lbl_dir_a"):
            self.lbl_dir_a.setText(tr("lbl_dir_a", lang))
        if hasattr(self, "edit_dir_a"):
            self.edit_dir_a.setPlaceholderText(tr("placeholder_dir_a", lang))
        if hasattr(self, "btn_browse_a"):
            self.btn_browse_a.setText(tr("btn_browse", lang))
        if hasattr(self, "lbl_dir_b"):
            self.lbl_dir_b.setText(tr("lbl_dir_b", lang))
        if hasattr(self, "edit_dir_b"):
            self.edit_dir_b.setPlaceholderText(tr("placeholder_dir_b", lang))
        if hasattr(self, "btn_browse_b"):
            self.btn_browse_b.setText(tr("btn_browse", lang))

        if hasattr(self, "chk_hash"):
            self.chk_hash.setText(tr("chk_hash", lang))
            self.chk_hash.setToolTip(tr("chk_hash_tip", lang))
        if hasattr(self, "btn_compare"):
            self.btn_compare.setText(tr("btn_compare", lang))
        if hasattr(self, "btn_dry_run"):
            self.btn_dry_run.setText(tr("btn_dry_run", lang))
            self.btn_dry_run.setToolTip(tr("btn_dry_run_tip", lang))

        if hasattr(self, "lbl_filter"):
            self.lbl_filter.setText(tr("lbl_filter", lang))
        if hasattr(self, "combo_filter"):
            self._populate_filter_combo(lang)
        if hasattr(self, "edit_search"):
            self.edit_search.setPlaceholderText(tr("placeholder_search", lang))
        if hasattr(self, "btn_select_all"):
            self.btn_select_all.setText(tr("btn_select_all", lang))
        if hasattr(self, "btn_deselect_all"):
            self.btn_deselect_all.setText(tr("btn_deselect_all", lang))

        if hasattr(self, "table"):
            self._set_table_headers(lang)

        if hasattr(self, "sync_group"):
            self.sync_group.setTitle(tr("group_sync", lang))
        if hasattr(self, "chk_backup"):
            self.chk_backup.setText(tr("chk_backup", lang))
            self.chk_backup.setToolTip(tr("chk_backup_tip", lang))
        if hasattr(self, "lbl_sync_mode"):
            self.lbl_sync_mode.setText(tr("lbl_sync_mode", lang))
        if hasattr(self, "combo_sync_mode"):
            self._populate_sync_modes(lang)
        if hasattr(self, "btn_sync"):
            self.btn_sync.setText(tr("btn_sync", lang))

        if hasattr(self, "btn_history"):
            self.btn_history.setText(tr("btn_history", lang))
            self.btn_history.setToolTip(tr("btn_history_tip", lang))
        if hasattr(self, "btn_export_html"):
            self.btn_export_html.setText(tr("btn_export_html", lang))
            self.btn_export_html.setToolTip(tr("btn_export_html_tip", lang))
        if hasattr(self, "btn_export_csv"):
            self.btn_export_csv.setText(tr("btn_export_csv", lang))
            self.btn_export_csv.setToolTip(tr("btn_export_csv_tip", lang))
        if hasattr(self, "btn_backup_mgr"):
            self.btn_backup_mgr.setText(tr("btn_backup_mgr", lang))
            self.btn_backup_mgr.setToolTip(tr("btn_backup_mgr_tip", lang))
        if hasattr(self, "btn_settings"):
            self.btn_settings.setText(tr("btn_settings", lang))
            self.btn_settings.setToolTip(tr("btn_settings_tip", lang))

    def _refresh_table_visuals(self, is_dark: bool, lang: str):
        """Aktualizuje kolory i etykiety statusów w istniejących wierszach tabeli."""
        if not hasattr(self, "table"):
            return
        for row in range(self.table.rowCount()):
            status_item = self.table.item(row, 1)
            path_item = self.table.item(row, 2)
            if not status_item or not path_item:
                continue
            item: Optional[ComparisonItem] = path_item.data(Qt.ItemDataRole.UserRole)
            if item:
                status_item.setText(get_status_display_name(item.status, lang))
                self._apply_status_style(status_item, item.status)

    def _apply_settings_to_ui(self):
        """Stosuje motyw, język oraz preferencje z pliku konfiguracyjnego."""
        settings = load_settings()
        is_dark = apply_theme_to_app(settings.theme, self)
        self._update_ui_language(settings.language)
        self._refresh_table_visuals(is_dark, settings.language)

        sync_map = {"UPDATE_OLDER": 0, "COPY_A_TO_B": 1, "COPY_B_TO_A": 2}
        idx = sync_map.get(settings.default_sync_mode, 0)
        self.combo_sync_mode.setCurrentIndex(idx)

    # ================= Zamknięcie okna =================

    def closeEvent(self, event):
        settings = load_settings()
        if settings.close_to_tray:
            event.ignore()
            self.hide()
        else:
            event.accept()

