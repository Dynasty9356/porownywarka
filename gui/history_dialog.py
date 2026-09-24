"""Okno historii porównań FolderSync (przeszukiwalna tabela z eksportem)."""

from __future__ import annotations
from datetime import datetime

from PyQt6.QtCore import Qt, QSortFilterProxyModel
from PyQt6.QtGui import QFont, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from core.history import HistoryEntry, load_history, save_history

HISTORY_STYLE = """
QWidget { background: #202020; color: #F3F3F3;
    font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif; font-size: 13px; }
QTableView { background: #1A1A1A; gridline-color: #2A2A2A; border: 1px solid #333; border-radius: 6px; }
QTableView::item { padding: 6px; }
QTableView::item:selected { background: #0078D4; color: white; }
QHeaderView::section { background: #252525; color: #AAAAAA; padding: 8px; border: none; font-weight: 600; }
QLineEdit { background: #2B2B2B; border: 1px solid #404040; border-radius: 6px; padding: 7px 12px; color: #FFFFFF; }
QLineEdit:focus { border: 1px solid #60CDFF; }
QPushButton { background: #2D2D2D; border: 1px solid #454545; border-radius: 6px; padding: 7px 14px; font-weight: 600; }
QPushButton:hover { background: #383838; }
QPushButton#dangerButton { background: #5C1A1A; border: 1px solid #7A2222; color: #FF6B6B; }
QPushButton#dangerButton:hover { background: #7A2222; }
"""

COLUMNS = ["Data i czas", "Szablon", "Katalog A", "Katalog B", "Pliki", "Różnice", "Sync", "Zaktualizowano", "MB"]


class HistoryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📜 Historia Porównań i Synchronizacji")
        self.resize(1000, 580)
        self.setStyleSheet(HISTORY_STYLE)

        self._entries: list[HistoryEntry] = []
        self._build_ui()
        self._load_history()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        header = QLabel("📜 Historia Porównań i Synchronizacji")
        header.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        header.setStyleSheet("color: #60CDFF; margin-bottom: 4px;")
        layout.addWidget(header)

        # Pasek wyszukiwania
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("🔍 Szukaj:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filtruj po szablonie, katalogu lub dacie...")
        self.search_edit.textChanged.connect(self._apply_filter)
        search_row.addWidget(self.search_edit)
        layout.addLayout(search_row)

        # Model + proxy
        self._model = QStandardItemModel(0, len(COLUMNS))
        self._model.setHorizontalHeaderLabels(COLUMNS)

        self._proxy = QSortFilterProxyModel()
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setFilterKeyColumn(-1)  # przeszukuje wszystkie kolumny

        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table)

        # Statystyki
        self.lbl_stats = QLabel()
        self.lbl_stats.setStyleSheet("color: #777; font-size: 12px;")
        layout.addWidget(self.lbl_stats)

        # Przyciski
        btn_row = QHBoxLayout()
        btn_clear_sel = QPushButton("🗑️ Usuń zaznaczone wpisy")
        btn_clear_sel.setObjectName("dangerButton")
        btn_clear_sel.clicked.connect(self._delete_selected)
        btn_row.addWidget(btn_clear_sel)

        btn_clear_all = QPushButton("❌ Wyczyść całą historię")
        btn_clear_all.setObjectName("dangerButton")
        btn_clear_all.clicked.connect(self._clear_all)
        btn_row.addWidget(btn_clear_all)

        btn_row.addStretch()
        btn_close = QPushButton("Zamknij")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    def _load_history(self):
        self._entries = load_history()
        self._model.setRowCount(0)
        for e in reversed(self._entries):
            self._add_row(e)
        self._update_stats()

    def _add_row(self, e: HistoryEntry):
        ts = e.timestamp[:19].replace("T", " ") if e.timestamp else "—"
        sync_txt = "✅ Tak" if e.synced else "—"
        updated = str(e.files_updated) if e.synced else "—"
        mb = f"{e.bytes_transferred / (1024*1024):.2f}" if e.synced and e.bytes_transferred else "—"

        row = [
            QStandardItem(ts),
            QStandardItem(e.profile_name or "—"),
            QStandardItem(e.dir_a),
            QStandardItem(e.dir_b),
            QStandardItem(str(e.total_files)),
            QStandardItem(str(e.different_files)),
            QStandardItem(sync_txt),
            QStandardItem(updated),
            QStandardItem(mb),
        ]
        for item in row:
            item.setData(e.entry_id, Qt.ItemDataRole.UserRole)
        self._model.appendRow(row)

    def _apply_filter(self, text: str):
        self._proxy.setFilterFixedString(text)
        self._update_stats()

    def _update_stats(self):
        total = len(self._entries)
        visible = self._proxy.rowCount()
        self.lbl_stats.setText(f"Wyświetlane: {visible} z {total} wpisów")

    def _delete_selected(self):
        sel_ids = set()
        for index in self._table.selectionModel().selectedRows():
            src_idx = self._proxy.mapToSource(index)
            item = self._model.item(src_idx.row(), 0)
            if item:
                sel_ids.add(item.data(Qt.ItemDataRole.UserRole))

        if not sel_ids:
            return

        self._entries = [e for e in self._entries if e.entry_id not in sel_ids]
        save_history(self._entries)
        self._load_history()

    def _clear_all(self):
        from PyQt6.QtWidgets import QMessageBox
        r = QMessageBox.question(self, "Potwierdzenie",
                                  "Czy na pewno chcesz usunąć całą historię porównań?")
        if r == QMessageBox.StandardButton.Yes:
            self._entries = []
            save_history(self._entries)
            self._load_history()
