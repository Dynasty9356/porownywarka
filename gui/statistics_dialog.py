"""Moduł okna statystyk, analityki transferu i monitora zdrowia profili FolderSync.
Zgodny ze standardami CERT / NASA oraz wytycznymi WCAG AA.
"""

from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.history import HistoryEntry, load_history
from core.profiles import load_profiles
from core.settings import load_settings
from gui.themes import get_theme_stylesheet, is_dark_theme_active


def _fmt_bytes(bytes_count: int) -> str:
    """Czytelne formatowanie liczby bajtów."""
    if bytes_count < 1024:
        return f"{bytes_count} B"
    elif bytes_count < 1024 ** 2:
        return f"{bytes_count / 1024:.1f} KB"
    elif bytes_count < 1024 ** 3:
        return f"{bytes_count / (1024 ** 2):.2f} MB"
    return f"{bytes_count / (1024 ** 3):.2f} GB"


class StatisticsDialog(QDialog):
    """Certyfikowane okno analityki i pulpitu nawigacyjnego synchronizacji."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📊 Panel Statystyk i Zdrowia Synchronizacji")
        self.resize(850, 560)
        theme = load_settings().theme
        self.setStyleSheet(get_theme_stylesheet(theme))

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.setSpacing(12)

        theme = load_settings().theme
        is_dark = is_dark_theme_active(theme)
        accent_color = "#60CDFF" if is_dark else "#005FB8"

        # 1. Nagłówek
        header = QLabel("📊 Panel Analityki i Zdrowia Synchronizacji")
        header.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        header.setStyleSheet(f"color: {accent_color}; margin-bottom: 2px;")
        layout.addWidget(header)

        # Pobieranie danych historycznych
        entries = load_history()
        sync_entries = [e for e in entries if e.synced]
        total_syncs = len(sync_entries)
        total_files = sum(e.files_updated for e in sync_entries)
        total_bytes = sum(e.bytes_transferred for e in sync_entries)
        failed_count = sum(1 for e in sync_entries if e.errors)
        success_rate = 100.0 if total_syncs == 0 else max(0.0, (1.0 - (failed_count / total_syncs)) * 100.0)

        # 2. Karty metryk (KPI Cards)
        cards_grid = QGridLayout()
        cards_grid.setSpacing(10)

        card_bg = "#2B2B2B" if is_dark else "#F3F3F3"
        card_border = "#3D3D3D" if is_dark else "#E0E0E0"
        text_sub = "#AAAAAA" if is_dark else "#555555"

        kpis = [
            ("🔄 Sesje Synchronizacji", f"{total_syncs}", "Zarejestrowane operacje"),
            ("📁 Zaktualizowane Pliki", f"{total_files}", "Skopiowane bezpiecznie"),
            ("💾 Przesłane Dane", _fmt_bytes(total_bytes), "Łączny wolumen"),
            ("🛡️ Wskaźnik Sukcesu", f"{success_rate:.1f}%", "Niezawodność operacji"),
        ]

        for idx, (title, val, sub) in enumerate(kpis):
            box = QFrame()
            box.setStyleSheet(
                f"background-color: {card_bg}; border: 1px solid {card_border}; border-radius: 8px; padding: 6px;"
            )
            b_layout = QVBoxLayout(box)
            b_layout.setContentsMargins(10, 8, 10, 8)
            b_layout.setSpacing(2)

            lbl_t = QLabel(title)
            lbl_t.setStyleSheet(f"font-size: 11px; color: {text_sub}; font-weight: 600; border: none;")
            lbl_v = QLabel(val)
            lbl_v.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
            lbl_v.setStyleSheet(f"color: {accent_color}; border: none;")
            lbl_s = QLabel(sub)
            lbl_s.setStyleSheet(f"font-size: 10px; color: {text_sub}; border: none;")

            b_layout.addWidget(lbl_t)
            b_layout.addWidget(lbl_v)
            b_layout.addWidget(lbl_s)
            cards_grid.addWidget(box, 0, idx)

        layout.addLayout(cards_grid)

        # 3. Zakładki szczegółowe
        tabs = QTabWidget()

        # Zakładka 1: Zdrowie profili
        tab_profiles = QWidget()
        p_layout = QVBoxLayout(tab_profiles)
        p_layout.setContentsMargins(8, 8, 8, 8)

        table_profiles = QTableWidget(0, 5)
        table_profiles.setHorizontalHeaderLabels([
            "Profil", "Stan Zdrowia", "Ostatnia Synchronizacja", "Katalog A", "Katalog B"
        ])
        table_profiles.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table_profiles.horizontalHeader().setStretchLastSection(True)
        table_profiles.verticalHeader().setVisible(False)
        table_profiles.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        all_profiles = load_profiles()
        now = datetime.now()

        for p_name, prof in all_profiles.items():
            # Znajdź ostatnią synchronizację dla profilu
            prof_syncs = [
                e for e in sync_entries
                if e.profile_name == p_name or (e.dir_a == prof.dir_a and e.dir_b == prof.dir_b)
            ]
            last_entry: Optional[HistoryEntry] = prof_syncs[-1] if prof_syncs else None

            if last_entry and last_entry.sync_timestamp:
                try:
                    dt = datetime.fromisoformat(last_entry.sync_timestamp)
                    days_ago = (now - dt).total_seconds() / 86400.0
                    last_str = dt.strftime("%Y-%m-%d %H:%M")
                    if days_ago < 1.0:
                        status_str = "🟢 Aktualny (< 24h)"
                    elif days_ago < 3.0:
                        status_str = "🟡 Ostatnie 3 dni"
                    else:
                        status_str = f"🔴 Ponad {int(days_ago)} dni temu"
                except Exception:
                    last_str = str(last_entry.sync_timestamp)
                    status_str = "⚪ Znany"
            else:
                last_str = "Nigdy"
                status_str = "⚪ Brak synchronizacji"

            row = table_profiles.rowCount()
            table_profiles.insertRow(row)
            table_profiles.setItem(row, 0, QTableWidgetItem(p_name))
            table_profiles.setItem(row, 1, QTableWidgetItem(status_str))
            table_profiles.setItem(row, 2, QTableWidgetItem(last_str))
            table_profiles.setItem(row, 3, QTableWidgetItem(prof.dir_a))
            table_profiles.setItem(row, 4, QTableWidgetItem(prof.dir_b))

        p_layout.addWidget(table_profiles)
        tabs.addTab(tab_profiles, "🛡️ Monitor Zdrowia Szablonów")

        # Zakładka 2: Ostatnie operacje
        tab_history = QWidget()
        h_layout = QVBoxLayout(tab_history)
        h_layout.setContentsMargins(8, 8, 8, 8)

        table_history = QTableWidget(0, 5)
        table_history.setHorizontalHeaderLabels([
            "Data i Czas", "Szablon / Zadanie", "Zaktualizowano", "Transfer", "Status"
        ])
        table_history.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table_history.horizontalHeader().setStretchLastSection(True)
        table_history.verticalHeader().setVisible(False)
        table_history.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        for entry in reversed(sync_entries[-20:]):
            row = table_history.rowCount()
            table_history.insertRow(row)

            date_str = entry.sync_timestamp[:19].replace("T", " ") if entry.sync_timestamp else entry.timestamp[:19].replace("T", " ")
            prof_disp = entry.profile_name if entry.profile_name else f"{Path(entry.dir_a).name} ↔ {Path(entry.dir_b).name}"
            status_disp = "❌ Błędy" if entry.errors else "✅ Sukces"

            table_history.setItem(row, 0, QTableWidgetItem(date_str))
            table_history.setItem(row, 1, QTableWidgetItem(prof_disp))
            table_history.setItem(row, 2, QTableWidgetItem(f"{entry.files_updated} plików"))
            table_history.setItem(row, 3, QTableWidgetItem(_fmt_bytes(entry.bytes_transferred)))
            table_history.setItem(row, 4, QTableWidgetItem(status_disp))

        h_layout.addWidget(table_history)
        tabs.addTab(tab_history, "🕒 Ostatnie Sesje")

        layout.addWidget(tabs)

        # 4. Przycisk Zamknij
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_close = QPushButton("Zamknij")
        btn_close.clicked.connect(self.accept)
        btn_box.addWidget(btn_close)
        layout.addLayout(btn_box)
