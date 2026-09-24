"""Menedżer kopii zapasowych (.backup) FolderSync.
Umożliwia przeglądanie, przywracanie (rollback) i usuwanie katalogów .backup.
"""

from __future__ import annotations
from datetime import datetime
from pathlib import Path
import shutil

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.settings import load_settings
from gui.themes import get_theme_stylesheet, is_dark_theme_active

def _find_backup_dirs(base_dirs: list[Path]) -> list[dict]:
    """Przeszukuje podane katalogi bazowe w poszukiwaniu podkatalogów .backup."""
    found = []
    for base in base_dirs:
        if not base or not base.is_dir():
            continue
        backup_dir = base / ".backup"
        if backup_dir.is_dir():
            # Szukamy podkatalogów z datą jako nazwą (np. 20260924_200000)
            for ts_dir in sorted(backup_dir.iterdir(), reverse=True):
                if ts_dir.is_dir():
                    files = list(ts_dir.rglob("*"))
                    file_count = sum(1 for f in files if f.is_file())
                    total_size = sum(f.stat().st_size for f in files if f.is_file())
                    try:
                        dt = datetime.strptime(ts_dir.name[:15], "%Y%m%d_%H%M%S")
                        ts_readable = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        ts_readable = ts_dir.name
                    found.append({
                        "path": ts_dir,
                        "base": base,
                        "timestamp": ts_readable,
                        "file_count": file_count,
                        "total_size": total_size,
                    })
    return found


def _fmt_size(b: int) -> str:
    if b < 1024:
        return f"{b} B"
    elif b < 1024 ** 2:
        return f"{b / 1024:.1f} KB"
    return f"{b / (1024 ** 2):.2f} MB"


class BackupManagerDialog(QDialog):
    def __init__(self, dir_a: str = "", dir_b: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("⏪ Menedżer Kopii Zapasowych (.backup)")
        self.resize(900, 500)
        theme = load_settings().theme
        self.setStyleSheet(get_theme_stylesheet(theme))

        self._dir_a = Path(dir_a) if dir_a else None
        self._dir_b = Path(dir_b) if dir_b else None
        self._backups: list[dict] = []

        self._build_ui()
        self._refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        is_dark = is_dark_theme_active(load_settings().theme)
        header_color = "#60CDFF" if is_dark else "#005FB8"

        header = QLabel("⏪ Menedżer Kopii Zapasowych (.backup)")
        header.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        header.setStyleSheet(f"color: {header_color}; margin-bottom: 4px;")
        layout.addWidget(header)

        info = QLabel(
            "Każda synchronizacja tworzy timestampowany podkatalog .backup z kopiami nadpisanych plików.\n"
            "Możesz przywrócić pliki (Rollback) lub usunąć stare kopie, by zwolnić miejsce na dysku."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #AAAAAA; font-size: 12px;")
        layout.addWidget(info)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["Data kopii zapasowej", "Katalog bazowy", "Liczba plików", "Rozmiar", "Ścieżka .backup"]
        )
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table)

        self._lbl_summary = QLabel()
        self._lbl_summary.setStyleSheet("color: #777; font-size: 12px;")
        layout.addWidget(self._lbl_summary)

        btn_row = QHBoxLayout()

        btn_rollback = QPushButton("⏪ Rollback — przywróć zaznaczone pliki")
        btn_rollback.setObjectName("rollbackBtn")
        btn_rollback.clicked.connect(self._rollback)
        btn_row.addWidget(btn_rollback)

        btn_del = QPushButton("🗑️ Usuń zaznaczoną kopię")
        btn_del.setObjectName("deleteBtn")
        btn_del.clicked.connect(self._delete_selected)
        btn_row.addWidget(btn_del)

        btn_row.addStretch()
        btn_close = QPushButton("Zamknij")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    def _refresh(self):
        bases = [d for d in [self._dir_a, self._dir_b] if d]
        self._backups = _find_backup_dirs(bases)
        self._table.setRowCount(0)

        total_size = 0
        for bk in self._backups:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(bk["timestamp"]))
            self._table.setItem(row, 1, QTableWidgetItem(str(bk["base"])))
            self._table.setItem(row, 2, QTableWidgetItem(str(bk["file_count"])))
            self._table.setItem(row, 3, QTableWidgetItem(_fmt_size(bk["total_size"])))
            self._table.setItem(row, 4, QTableWidgetItem(str(bk["path"])))
            total_size += bk["total_size"]

        self._lbl_summary.setText(
            f"Znaleziono {len(self._backups)} kopii zapasowych · Łączny rozmiar: {_fmt_size(total_size)}"
        )

    def _rollback(self):
        sel = self._table.currentRow()
        if sel < 0 or sel >= len(self._backups):
            QMessageBox.warning(self, "Brak zaznaczenia", "Zaznacz kopię zapasową, którą chcesz przywrócić.")
            return
        bk = self._backups[sel]
        result = QMessageBox.question(
            self, "Potwierdzenie Rollbacku",
            f"Czy przywrócić pliki z kopii:\n{bk['path']}\n\n"
            f"do katalogu:\n{bk['base']}\n\n"
            "⚠️ Istniejące pliki zostaną NADPISANE oryginalnymi wersjami!",
        )
        if result != QMessageBox.StandardButton.Yes:
            return

        errors = []
        src_root = bk["path"]
        dst_root = bk["base"]
        for src_file in src_root.rglob("*"):
            if not src_file.is_file():
                continue
            try:
                rel = src_file.relative_to(src_root)
                dst_file = dst_root / rel
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src_file), str(dst_file))
            except Exception as e:
                errors.append(str(e))

        if errors:
            QMessageBox.warning(self, "Błędy rollbacku",
                                f"Przywrócono z błędami:\n" + "\n".join(errors[:10]))
        else:
            QMessageBox.information(self, "Rollback zakończony",
                                    f"✅ Pliki zostały przywrócone pomyślnie z:\n{bk['path']}")

    def _delete_selected(self):
        sel = self._table.currentRow()
        if sel < 0 or sel >= len(self._backups):
            QMessageBox.warning(self, "Brak zaznaczenia", "Zaznacz kopię zapasową do usunięcia.")
            return
        bk = self._backups[sel]
        result = QMessageBox.question(
            self, "Potwierdzenie usunięcia",
            f"Czy na pewno usunąć kopię zapasową:\n{bk['path']}\n\n"
            "⚠️ Tej operacji NIE MOŻNA cofnąć!",
        )
        if result != QMessageBox.StandardButton.Yes:
            return
        try:
            shutil.rmtree(bk["path"])
            QMessageBox.information(self, "Usunięto", "Kopia zapasowa została trwale usunięta.")
        except Exception as e:
            QMessageBox.critical(self, "Błąd", f"Nie można usunąć katalogu:\n{e}")
        self._refresh()
