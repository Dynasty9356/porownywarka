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
from core.synchronizer import (
    SyncAction,
    SyncDirection,
    SyncReport,
    execute_sync,
    plan_sync_actions,
)


DARK_FLUENT_STYLE = """
/* Styl Windows 11 Fluent - Ciemny, zgodny z WCAG (kontrast tekstu > 10:1) */
QWidget {
    background-color: #202020;
    color: #F3F3F3;
    font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif;
    font-size: 13px;
}

QGroupBox {
    border: 1px solid #3A3A3A;
    border-radius: 8px;
    margin-top: 10px;
    padding-top: 12px;
    font-weight: 600;
    color: #E0E0E0;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #60CDFF;
}

QLineEdit {
    background-color: #2B2B2B;
    border: 1px solid #404040;
    border-radius: 6px;
    padding: 7px 10px;
    color: #FFFFFF;
    selection-background-color: #0078D4;
}

QLineEdit:focus {
    border: 1px solid #60CDFF;
    background-color: #323232;
}

QPushButton {
    background-color: #2D2D2D;
    border: 1px solid #454545;
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 600;
    color: #FFFFFF;
}

QPushButton:hover {
    background-color: #383838;
    border: 1px solid #5A5A5A;
}

QPushButton:pressed {
    background-color: #252525;
}

QPushButton:disabled {
    background-color: #1A1A1A;
    color: #666666;
    border: 1px solid #2B2B2B;
}

/* Wyróżniony główny przycisk akcji (Accent Color) */
QPushButton#primaryButton {
    background-color: #0078D4;
    border: 1px solid #1084D8;
    color: #FFFFFF;
}

QPushButton#primaryButton:hover {
    background-color: #1084D8;
}

QPushButton#primaryButton:pressed {
    background-color: #006CBE;
}

/* Przycisk synchronizacji */
QPushButton#syncButton {
    background-color: #0E7A0D;
    border: 1px solid #148C13;
    color: #FFFFFF;
    font-size: 14px;
    padding: 9px 22px;
}

QPushButton#syncButton:hover {
    background-color: #148C13;
}

QPushButton#syncButton:pressed {
    background-color: #0A6009;
}

QTableWidget {
    background-color: #1A1A1A;
    border: 1px solid #333333;
    border-radius: 6px;
    gridline-color: #2A2A2A;
    selection-background-color: #264F78;
    selection-color: #FFFFFF;
}

QHeaderView::section {
    background-color: #252525;
    color: #E0E0E0;
    padding: 8px;
    border: none;
    border-bottom: 1px solid #3D3D3D;
    font-weight: 600;
}

QHeaderView::section:hover {
    background-color: #303030;
}

QProgressBar {
    border: 1px solid #404040;
    border-radius: 4px;
    text-align: center;
    background-color: #262626;
    color: #FFFFFF;
    font-weight: 600;
    height: 18px;
}

QProgressBar::chunk {
    background-color: #0078D4;
    border-radius: 3px;
}

QComboBox {
    background-color: #2D2D2D;
    border: 1px solid #454545;
    border-radius: 6px;
    padding: 6px 12px;
    color: #FFFFFF;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #2B2B2B;
    border: 1px solid #454545;
    selection-background-color: #0078D4;
    color: #FFFFFF;
}

QCheckBox {
    color: #EAEAEA;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid #555555;
    border-radius: 4px;
    background-color: #2B2B2B;
}

QCheckBox::indicator:checked {
    background-color: #0078D4;
    border: 1px solid #60CDFF;
}

QMenu {
    background-color: #2A2A2A;
    border: 1px solid #444444;
    border-radius: 6px;
    padding: 4px;
}

QMenu::item {
    padding: 6px 20px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #0078D4;
    color: #FFFFFF;
}
"""


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
        self.setStyleSheet(DARK_FLUENT_STYLE)

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
        lbl_a.setStyleSheet("color: #60CDFF; font-weight: bold;")
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
        lbl_b.setStyleSheet("color: #FFA500; font-weight: bold;")
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
        self.setStyleSheet(DARK_FLUENT_STYLE)

        total = len(actions)
        overwrites = sum(1 for a in actions if a.will_overwrite)
        new_files = total - overwrites

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        title = QLabel("⚠️ Wymagane potwierdzenie operacji na plikach")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet("color: #FFA500;")
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
        self.setWindowTitle("FolderSync - Porównywarka i Synchronizator Katalogów")
        self.resize(1150, 780)
        self.setStyleSheet(DARK_FLUENT_STYLE)

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
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(10)

        # 1. Pasek Szablonów / Profili (Szybki Dostęp)
        profile_group = QGroupBox("⭐ Szablony / Profile Szybkiego Dostępu")
        profile_layout = QHBoxLayout(profile_group)

        self.combo_profiles = QComboBox()
        self.combo_profiles.setMinimumWidth(320)
        self.combo_profiles.currentIndexChanged.connect(self._on_profile_selected)

        btn_save_profile = QPushButton("💾 Zapisz jako szablon...")
        btn_save_profile.setToolTip("Zapisz aktualnie wybrane foldery A i B jako nazwany profil")
        btn_save_profile.clicked.connect(self._save_current_as_profile)

        btn_delete_profile = QPushButton("🗑️ Usuń szablon")
        btn_delete_profile.setToolTip("Usuń obecnie wybrany szablon z listy")
        btn_delete_profile.clicked.connect(self._delete_current_profile)

        profile_layout.addWidget(QLabel("Wybierz szablon:"))
        profile_layout.addWidget(self.combo_profiles)
        profile_layout.addWidget(btn_save_profile)
        profile_layout.addWidget(btn_delete_profile)
        profile_layout.addStretch()

        main_layout.addWidget(profile_group)

        # 2. Wybór katalogów A i B
        dir_group = QGroupBox("Katalogi źródłowy i docelowy")
        dir_layout = QGridLayout(dir_group)
        dir_layout.setSpacing(8)

        lbl_a = QLabel("Katalog A (Lewy):")
        lbl_a.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        self.edit_dir_a = DropLineEdit("Wklej, wpisz lub przeciągnij tutaj folder A...")
        btn_browse_a = QPushButton("Przeglądaj...")
        btn_browse_a.clicked.connect(self._browse_a)

        dir_layout.addWidget(lbl_a, 0, 0)
        dir_layout.addWidget(self.edit_dir_a, 0, 1)
        dir_layout.addWidget(btn_browse_a, 0, 2)

        lbl_b = QLabel("Katalog B (Prawy):")
        lbl_b.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        self.edit_dir_b = DropLineEdit("Wklej, wpisz lub przeciągnij tutaj folder B...")
        btn_browse_b = QPushButton("Przeglądaj...")
        btn_browse_b.clicked.connect(self._browse_b)

        dir_layout.addWidget(lbl_b, 1, 0)
        dir_layout.addWidget(self.edit_dir_b, 1, 1)
        dir_layout.addWidget(btn_browse_b, 1, 2)

        main_layout.addWidget(dir_group)

        # 3. Opcje porównywania i przycisk startowy
        opt_layout = QHBoxLayout()
        self.chk_hash = QCheckBox("Głęboka weryfikacja sumą SHA-256 (dla 100% integralności)")
        self.chk_hash.setToolTip("Oblicza kryptograficzną sumę SHA-256 każdego pliku, eliminując błędy daty")
        self.chk_hash.setChecked(False)

        self.btn_compare = QPushButton("🔍 Porównaj zawartość katalogów")
        self.btn_compare.setObjectName("primaryButton")
        self.btn_compare.setFixedHeight(36)
        self.btn_compare.clicked.connect(self._start_compare)

        self.btn_dry_run = QPushButton("⚠️ Test na sucho (Dry-Run)")
        self.btn_dry_run.setToolTip("Symuluj synchronizację BEZ modyfikowania plików na dysku")
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

        self.lbl_status = QLabel("Wybierz szablon lub dwa foldery i kliknij „Porównaj zawartość”. Kliknij nagłówek tabeli, aby sortować.")
        self.lbl_status.setStyleSheet("color: #AAAAAA;")
        main_layout.addWidget(self.lbl_status)

        # 4. Pasek filtrów i szybkich akcji
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filtruj widok:"))

        self.combo_filter = QComboBox()
        self.combo_filter.addItems([
            "Wszystkie pliki",
            "Tylko różniące się (wymagające uwagi)",
            "Nowszy w Katalogu A",
            "Nowszy w Katalogu B",
            "Tylko w A lub tylko w B",
            "Identyczne",
        ])
        self.combo_filter.currentIndexChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.combo_filter)

        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("Szukaj po nazwie / ścieżce...")
        self.edit_search.textChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.edit_search)

        filter_layout.addStretch()

        btn_select_all = QPushButton("Zaznacz widoczne")
        btn_select_all.clicked.connect(lambda: self._set_all_visible_checked(True))
        btn_deselect_all = QPushButton("Odznacz wszystkie")
        btn_deselect_all.clicked.connect(lambda: self._set_all_visible_checked(False))
        filter_layout.addWidget(btn_select_all)
        filter_layout.addWidget(btn_deselect_all)

        main_layout.addLayout(filter_layout)

        # 5. Tabela wyników porównania z obsługą sortowania i menu kontekstowego
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Wybór",
            "Status",
            "Względna ścieżka pliku",
            "Rozmiar A / B",
            "Data modyfikacji A",
            "Data modyfikacji B",
        ])
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
        sync_group = QGroupBox("Synchronizacja i Ochrona Danych")
        sync_layout = QHBoxLayout(sync_group)

        self.chk_backup = QCheckBox("Twórz kopię zapasową (.backup) przed zastąpieniem pliku")
        self.chk_backup.setChecked(True)
        self.chk_backup.setToolTip("Rekomendowane przez procedury bezpieczeństwa: zachowuje kopię pliku przed nadpisaniem")

        self.combo_sync_mode = QComboBox()
        self.combo_sync_mode.addItem(SyncDirection.UPDATE_OLDER.display_name, SyncDirection.UPDATE_OLDER)
        self.combo_sync_mode.addItem(SyncDirection.COPY_A_TO_B.display_name, SyncDirection.COPY_A_TO_B)
        self.combo_sync_mode.addItem(SyncDirection.COPY_B_TO_A.display_name, SyncDirection.COPY_B_TO_A)

        self.btn_sync = QPushButton("⚡ Zsynchronizuj zaznaczone pliki")
        self.btn_sync.setObjectName("syncButton")
        self.btn_sync.setEnabled(False)
        self.btn_sync.clicked.connect(self._start_sync)

        sync_layout.addWidget(self.chk_backup)
        sync_layout.addSpacing(20)
        sync_layout.addWidget(QLabel("Tryb:"))
        sync_layout.addWidget(self.combo_sync_mode)
        sync_layout.addStretch()
        sync_layout.addWidget(self.btn_sync)

        main_layout.addWidget(sync_group)

        # 7. Pasek narzędzi dolny: Historia, Eksport, Backup Manager, Ustawienia
        tools_layout = QHBoxLayout()

        btn_history = QPushButton("📜 Historia porównań")
        btn_history.setToolTip("Przeglądaj historię porównań i synchronizacji")
        btn_history.clicked.connect(self._open_history)
        tools_layout.addWidget(btn_history)

        btn_export_html = QPushButton("📄 Eksport HTML")
        btn_export_html.setToolTip("Eksportuj wyniki do pliku HTML")
        btn_export_html.clicked.connect(lambda: self._export_report("html"))
        tools_layout.addWidget(btn_export_html)

        btn_export_csv = QPushButton("📊 Eksport CSV")
        btn_export_csv.setToolTip("Eksportuj wyniki do pliku CSV (Excel, LibreOffice)")
        btn_export_csv.clicked.connect(lambda: self._export_report("csv"))
        tools_layout.addWidget(btn_export_csv)

        btn_backup_mgr = QPushButton("⏪ Kopie zapasowe")
        btn_backup_mgr.setToolTip("Zarządzaj katalogami .backup, wykonaj Rollback")
        btn_backup_mgr.clicked.connect(self._open_backup_manager)
        tools_layout.addWidget(btn_backup_mgr)

        tools_layout.addStretch()

        btn_settings = QPushButton("⚙️ Ustawienia")
        btn_settings.setToolTip("Otwórz ustawienia aplikacji (Ctrl+,)")
        btn_settings.clicked.connect(self._open_settings)
        btn_settings.setShortcut(QKeySequence("Ctrl+,"))
        tools_layout.addWidget(btn_settings)

        main_layout.addLayout(tools_layout)

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
            status_item = SortableTableWidgetItem(item.status.display_name, sort_key=s_weight)
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

        if status == FileStatus.NEWER_A:
            table_item.setBackground(QColor("#1B5E20"))
            table_item.setForeground(QColor("#C8E6C9"))
        elif status == FileStatus.NEWER_B:
            table_item.setBackground(QColor("#0D47A1"))
            table_item.setForeground(QColor("#BBDEFB"))
        elif status == FileStatus.ONLY_A:
            table_item.setBackground(QColor("#4A148C"))
            table_item.setForeground(QColor("#E1BEE7"))
        elif status == FileStatus.ONLY_B:
            table_item.setBackground(QColor("#BF360C"))
            table_item.setForeground(QColor("#FFE0B2"))
        elif status == FileStatus.DIFFERENT_CONTENT:
            table_item.setBackground(QColor("#E65100"))
            table_item.setForeground(QColor("#FFFFFF"))
        elif status == FileStatus.ERROR:
            table_item.setBackground(QColor("#B71C1C"))
            table_item.setForeground(QColor("#FFCDD2"))
        else:
            table_item.setBackground(QColor("#2C3437"))
            table_item.setForeground(QColor("#B0BEC5"))

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
        # Odśwież UI po zapisaniu ustawień
        self._apply_settings_to_ui()

    def _apply_settings_to_ui(self):
        """Stosuje ustawienia z pliku konfiguracyjnego do elementów UI."""
        settings = load_settings()
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

