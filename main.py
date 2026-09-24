"""Główny punkt wejściowy aplikacji FolderSync.
Uruchamia natywny interfejs graficzny Windows 11.
"""

import sys
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from gui.main_window import MainWindow


def main():
    # Zapewnienie pełnej obsługi High-DPI na nowoczesnych monitorach
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("FolderSync")
    app.setApplicationDisplayName("FolderSync - Porównywarka i Synchronizator")
    app.setOrganizationName("SecurityTools")

    from pathlib import Path
    from PyQt6.QtGui import QIcon
    icon_path = Path(__file__).resolve().parent / "app_icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
