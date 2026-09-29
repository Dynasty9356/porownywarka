"""Eleganckie i bezpieczne okno powiadomienia o nowej wersji (WCAG AAA, Windows 11 Fluent)."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QFont
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from core.i18n import tr
from core.settings import load_settings
from core.updater import UpdateInfo, validate_https_url
from gui.themes import get_theme_stylesheet, is_dark_theme_active


class UpdateAvailableDialog(QDialog):
    """Natywne okno powiadomienia o dostępności nowej wersji FolderSync."""

    def __init__(self, info: UpdateInfo, parent=None):
        super().__init__(parent)
        self.info = info
        self.settings = load_settings()
        self.lang = self.settings.language

        self.setWindowTitle(f"{tr('dlg_update_title', self.lang)} — {self.info.latest_version}")
        self.resize(540, 420)
        self.setModal(True)
        self.setStyleSheet(get_theme_stylesheet(self.settings.theme))

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(14)

        is_dark = is_dark_theme_active(self.settings.theme)
        accent_color = "#60CDFF" if is_dark else "#005FB8"

        # Nagłówek
        header_text = tr("dlg_update_header", self.lang, version=self.info.latest_version)
        lbl_header = QLabel(f"🚀 {header_text}")
        lbl_header.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        lbl_header.setStyleSheet(f"color: {accent_color}; margin-bottom: 2px;")
        layout.addWidget(lbl_header)

        # Informacja o obecnej i nowej wersji
        lbl_current = QLabel(tr("dlg_update_current", self.lang, current=self.info.current_version))
        lbl_current.setFont(QFont("Segoe UI", 10))
        lbl_current.setStyleSheet("color: #AAAAAA;" if is_dark else "color: #555555;")
        layout.addWidget(lbl_current)

        # Sekcja: Co nowego w tym wydaniu
        lbl_notes_title = QLabel(tr("dlg_update_notes_title", self.lang))
        lbl_notes_title.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        layout.addWidget(lbl_notes_title)

        self.txt_notes = QTextEdit()
        self.txt_notes.setReadOnly(True)
        self.txt_notes.setFont(QFont("Segoe UI", 10))
        notes_text = self.info.release_notes.strip() if self.info.release_notes else "Nowe ulepszenia wydajności, bezpieczeństwa i stabilności."
        self.txt_notes.setPlainText(notes_text)
        layout.addWidget(self.txt_notes)

        # Przyciski akcji
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.btn_later = QPushButton(tr("dlg_update_btn_later", self.lang))
        self.btn_later.setFixedHeight(36)
        self.btn_later.clicked.connect(self.reject)

        self.btn_download = QPushButton(tr("dlg_update_btn_download", self.lang))
        self.btn_download.setObjectName("primaryButton")
        self.btn_download.setFixedHeight(36)
        self.btn_download.setStyleSheet(
            "background-color: #107C10; color: #FFFFFF; font-weight: bold; font-size: 13px; border-radius: 6px; padding: 6px 16px;"
        )
        self.btn_download.clicked.connect(self._on_download)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_later)
        btn_layout.addWidget(self.btn_download)
        layout.addLayout(btn_layout)

    def _on_download(self):
        """Otwiera bezpieczny link HTTPS w domyślnej przeglądarce i zamyka okno."""
        url = self.info.download_url
        if validate_https_url(url):
            QDesktopServices.openUrl(QUrl(url))
        self.accept()
