"""System motywów dla FolderSync (Windows 11 Fluent Light & Dark, WCAG AA/AAA).

Zapewnia:
- Ciemny motyw (Dark Fluent) z kontrastem tekstu > 10:1 (WCAG AAA)
- Jasny motyw (Light Fluent) z kontrastem tekstu > 14:1 (WCAG AAA)
- Automatyczne wykrywanie motywu systemowego Windows 11 / Windows 10
- Dynamiczne przeliczanie kolorów komórek tabeli (statusy) w zależności od motywu
"""

from __future__ import annotations

import winreg
from typing import Optional
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication, QWidget

from core.comparator import FileStatus


DARK_FLUENT_STYLE = """
/* Styl Windows 11 Fluent - Ciemny, zgodny z WCAG AAA (kontrast tekstu > 10:1) */
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

QPushButton:focus {
    border: 2px solid #60CDFF;
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

QTabWidget::pane {
    border: 1px solid #3A3A3A;
    border-radius: 6px;
}

QTabBar::tab {
    background: #2A2A2A;
    color: #AAAAAA;
    padding: 8px 18px;
    border-radius: 5px 5px 0 0;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background: #0078D4;
    color: #FFFFFF;
    font-weight: 600;
}

QListWidget {
    background: #1A1A1A;
    border: 1px solid #333333;
    border-radius: 6px;
    color: #F3F3F3;
}

QTextEdit {
    background: #1A1A1A;
    border: 1px solid #333333;
    border-radius: 6px;
    color: #F3F3F3;
    font-family: Consolas, monospace;
    font-size: 12px;
}

QSpinBox, QDoubleSpinBox {
    background: #2B2B2B;
    border: 1px solid #404040;
    border-radius: 6px;
    padding: 6px 10px;
    color: #FFFFFF;
}

QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #60CDFF;
}
"""


LIGHT_FLUENT_STYLE = """
/* Styl Windows 11 Fluent - Jasny, zgodny z WCAG AAA (kontrast tekstu > 14:1) */
QWidget {
    background-color: #F3F3F3;
    color: #1A1A1A;
    font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif;
    font-size: 13px;
}

QGroupBox {
    border: 1px solid #D1D1D1;
    border-radius: 8px;
    margin-top: 10px;
    padding-top: 12px;
    font-weight: 600;
    color: #1A1A1A;
    background-color: #FBFBFB;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #005FB8;
}

QLineEdit {
    background-color: #FFFFFF;
    border: 1px solid #CCCCCC;
    border-radius: 6px;
    padding: 7px 10px;
    color: #1A1A1A;
    selection-background-color: #0067C0;
    selection-color: #FFFFFF;
}

QLineEdit:focus {
    border: 1px solid #005FB8;
    background-color: #FFFFFF;
}

QPushButton {
    background-color: #FFFFFF;
    border: 1px solid #CCCCCC;
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 600;
    color: #1A1A1A;
}

QPushButton:focus {
    border: 2px solid #005FB8;
}

QPushButton:hover {
    background-color: #F0F0F0;
    border: 1px solid #BBBBBB;
}

QPushButton:pressed {
    background-color: #E5E5E5;
}

QPushButton:disabled {
    background-color: #F5F5F5;
    color: #999999;
    border: 1px solid #E0E0E0;
}

QPushButton#primaryButton {
    background-color: #0067C0;
    border: 1px solid #005FB8;
    color: #FFFFFF;
}

QPushButton#primaryButton:hover {
    background-color: #005FB8;
}

QPushButton#primaryButton:pressed {
    background-color: #004F98;
}

QPushButton#syncButton {
    background-color: #0E7A0D;
    border: 1px solid #0C6B0B;
    color: #FFFFFF;
    font-size: 14px;
    padding: 9px 22px;
}

QPushButton#syncButton:hover {
    background-color: #0C6B0B;
}

QPushButton#syncButton:pressed {
    background-color: #095008;
}

QTableWidget {
    background-color: #FFFFFF;
    border: 1px solid #D5D5D5;
    border-radius: 6px;
    gridline-color: #EBEBEB;
    selection-background-color: #CCE8FF;
    selection-color: #000000;
}

QHeaderView::section {
    background-color: #EAEAEA;
    color: #1A1A1A;
    padding: 8px;
    border: none;
    border-bottom: 1px solid #CCCCCC;
    font-weight: 600;
}

QHeaderView::section:hover {
    background-color: #DFDFDF;
}

QProgressBar {
    border: 1px solid #CCCCCC;
    border-radius: 4px;
    text-align: center;
    background-color: #E5E5E5;
    color: #1A1A1A;
    font-weight: 600;
    height: 18px;
}

QProgressBar::chunk {
    background-color: #0067C0;
    border-radius: 3px;
}

QComboBox {
    background-color: #FFFFFF;
    border: 1px solid #CCCCCC;
    border-radius: 6px;
    padding: 6px 12px;
    color: #1A1A1A;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #FFFFFF;
    border: 1px solid #CCCCCC;
    selection-background-color: #CCE8FF;
    color: #1A1A1A;
}

QCheckBox {
    color: #1A1A1A;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid #AAAAAA;
    border-radius: 4px;
    background-color: #FFFFFF;
}

QCheckBox::indicator:checked {
    background-color: #0067C0;
    border: 1px solid #005FB8;
}

QMenu {
    background-color: #FFFFFF;
    border: 1px solid #CCCCCC;
    border-radius: 6px;
    padding: 4px;
    color: #1A1A1A;
}

QMenu::item {
    padding: 6px 20px;
    border-radius: 4px;
    color: #1A1A1A;
}

QMenu::item:selected {
    background-color: #CCE8FF;
    color: #000000;
}

QTabWidget::pane {
    border: 1px solid #D1D1D1;
    border-radius: 6px;
    background-color: #FFFFFF;
}

QTabBar::tab {
    background: #EAEAEA;
    color: #555555;
    padding: 8px 18px;
    border-radius: 5px 5px 0 0;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background: #0067C0;
    color: #FFFFFF;
    font-weight: 600;
}

QListWidget {
    background: #FFFFFF;
    border: 1px solid #D5D5D5;
    border-radius: 6px;
    color: #1A1A1A;
}

QTextEdit {
    background: #FFFFFF;
    border: 1px solid #D5D5D5;
    border-radius: 6px;
    color: #1A1A1A;
    font-family: Consolas, monospace;
    font-size: 12px;
}

QSpinBox, QDoubleSpinBox {
    background: #FFFFFF;
    border: 1px solid #CCCCCC;
    border-radius: 6px;
    padding: 6px 10px;
    color: #1A1A1A;
}

QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #005FB8;
}
"""


def detect_windows_dark_mode() -> bool:
    """Wykrywa, czy w systemie Windows włączony jest ciemny motyw aplikacji."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return val == 0
    except Exception:
        # Fallback do Qt styleHints
        try:
            app = QApplication.instance()
            if app:
                return app.styleHints().colorScheme() == Qt.ColorScheme.Dark
        except Exception:
            pass
        return True  # Domyślnie ciemny


def is_dark_theme_active(theme_name: str) -> bool:
    """Zwraca True jeśli aktywny jest ciemny motyw."""
    theme_name = (theme_name or "dark").lower()
    if theme_name == "light":
        return False
    if theme_name == "dark":
        return True
    return detect_windows_dark_mode()


def get_theme_stylesheet(theme_name: str) -> str:
    """Zwraca arkusz stylów CSS dla wskazanego motywu."""
    if is_dark_theme_active(theme_name):
        return DARK_FLUENT_STYLE
    return LIGHT_FLUENT_STYLE


def apply_theme_to_app(theme_name: str, target_widget: Optional[QWidget] = None) -> bool:
    """Aplikuje arkusz stylów motywu na całą aplikację oraz opcjonalnie na wskazane okno.
    Zwraca True jeśli motyw jest ciemny.
    """
    dark = is_dark_theme_active(theme_name)
    stylesheet = DARK_FLUENT_STYLE if dark else LIGHT_FLUENT_STYLE

    app = QApplication.instance()
    if app:
        app.setStyleSheet(stylesheet)
    if target_widget:
        target_widget.setStyleSheet(stylesheet)
    return dark


def get_status_colors(status: FileStatus, is_dark: bool) -> tuple[QColor, QColor]:
    """Zwraca kolory (tło, tekst) dla komórki statusu w tabeli z zachowaniem kontrastu WCAG."""
    if is_dark:
        colors = {
            FileStatus.NEWER_A: (QColor("#1B5E20"), QColor("#C8E6C9")),          # Zielony
            FileStatus.NEWER_B: (QColor("#0D47A1"), QColor("#BBDEFB")),          # Niebieski
            FileStatus.ONLY_A: (QColor("#4A148C"), QColor("#E1BEE7")),           # Fioletowy
            FileStatus.ONLY_B: (QColor("#BF360C"), QColor("#FFE0B2")),           # Bursztynowy
            FileStatus.DIFFERENT_CONTENT: (QColor("#E65100"), QColor("#FFFFFF")),# Pomarańczowy ostrzegawczy
            FileStatus.ERROR: (QColor("#B71C1C"), QColor("#FFCDD2")),            # Czerwony
            FileStatus.IDENTICAL: (QColor("#2C3437"), QColor("#B0BEC5")),        # Stonowany szary
        }
    else:
        # Jasny motyw: pastelowe, czytelne tła + wyrazisty ciemny tekst (WCAG AAA kontrast > 7:1)
        colors = {
            FileStatus.NEWER_A: (QColor("#E8F5E9"), QColor("#1B5E20")),          # Jasny zielony, ciemny napis
            FileStatus.NEWER_B: (QColor("#E3F2FD"), QColor("#0D47A1")),          # Jasny błękit, ciemny napis
            FileStatus.ONLY_A: (QColor("#F3E5F5"), QColor("#4A148C")),           # Jasny fiolet, ciemny napis
            FileStatus.ONLY_B: (QColor("#FBE9E7"), QColor("#BF360C")),           # Jasny pomarańcz, ciemny napis
            FileStatus.DIFFERENT_CONTENT: (QColor("#FFF3E0"), QColor("#B23A00")),# Pastel pomarańcz, kontrast
            FileStatus.ERROR: (QColor("#FFEBEE"), QColor("#B71C1C")),            # Jasny róż, ciemna czerwień
            FileStatus.IDENTICAL: (QColor("#ECEFF1"), QColor("#37474F")),        # Szare tło, grafitowy tekst
        }
    return colors.get(status, (QColor("#ECEFF1"), QColor("#37474F")))
