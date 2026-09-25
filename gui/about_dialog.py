"""Okno informacyjne 'O programie' (About Dialog) dla FolderSync."""

from __future__ import annotations
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from core.version import APP_DESCRIPTION, APP_NAME, __version__
from core.settings import load_settings
from gui.themes import get_theme_stylesheet, is_dark_theme_active


class AboutDialog(QDialog):
    """Eleganckie okno informacji o wersji, bezpieczeństwie i prawach autorskich."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"O programie — {APP_NAME} v{__version__}")
        self.resize(520, 360)
        self.setModal(True)
        theme = load_settings().theme
        self.setStyleSheet(get_theme_stylesheet(theme))
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 18)
        layout.setSpacing(14)

        is_dark = is_dark_theme_active(load_settings().theme)
        accent_color = "#60CDFF" if is_dark else "#005FB8"

        # Tytuł
        title_lbl = QLabel(f"🛡️ {APP_NAME} <span style='font-size: 16px; color: {accent_color};'>v{__version__}</span>")
        title_lbl.setTextFormat(Qt.TextFormat.RichText)
        title_lbl.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(title_lbl)

        # Podtytuł
        desc_lbl = QLabel(APP_DESCRIPTION)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("font-size: 13px; color: #BBBBBB;" if is_dark else "font-size: 13px; color: #444444;")
        layout.addWidget(desc_lbl)

        # Standardy bezpieczeństwa
        sec_box = QLabel(
            "<b>Cechy architektury bezpieczeństwa:</b><br>"
            "• Kryptograficzna weryfikacja sum SHA-256 w czasie rzeczywistym<br>"
            "• Atomowe transakcje zapisu plików (odporność na awarie zasilania)<br>"
            "• Ochrona przed Path Traversal, Symlink Escape i nazwami urządzeń DOS<br>"
            "• Automatyczny system kopii zapasowych (.backup) z weryfikacją Rollbacku<br>"
            "• Blokada jednoczesnego uruchomienia wielu instancji (Anti-Race Condition)<br>"
            "• Dostępność zgodna ze standardami WCAG 2.2 AAA"
        )
        sec_box.setTextFormat(Qt.TextFormat.RichText)
        sec_box.setStyleSheet(
            f"background-color: {'#2A2A2A' if is_dark else '#EAEAEA'}; "
            f"border: 1px solid {'#3D3D3D' if is_dark else '#D0D0D0'}; "
            f"border-radius: 8px; padding: 12px; font-size: 12px; line-height: 1.4;"
        )
        layout.addWidget(sec_box)

        # Stopka
        copy_lbl = QLabel("© 2026 FolderSync Security & Core Team. Wszelkie prawa zastrzeżone.")
        copy_lbl.setStyleSheet("font-size: 11px; color: #888888;")
        layout.addWidget(copy_lbl)

        # Przycisk OK
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btn_box.accepted.connect(self.accept)
        layout.addWidget(btn_box)
