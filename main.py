"""Główny punkt wejściowy aplikacji FolderSync (Security Level: NASA / CERT / WCAG AAA).
Uruchamia natywny interfejs graficzny Windows 11 z ochroną Single-Instance Mutex.
"""

from pathlib import Path
import sys
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QMessageBox

from core.lock import SingleInstanceLock
from core.version import APP_NAME, __version__
from gui.main_window import MainWindow


def main():
    # Zapewnienie pełnej obsługi High-DPI na nowoczesnych monitorach Windows 11
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setApplicationDisplayName(f"{APP_NAME} v{__version__} — Porównywarka i Synchronizator")
    app.setOrganizationName("SecurityTools")

    icon_path = Path(__file__).resolve().parent / "app_icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Ochrona przed równoległym uruchomieniem wielu instancji (Anti-Race Condition)
    lock = SingleInstanceLock(app_name="FolderSync")
    if not lock.acquire():
        QMessageBox.warning(
            None,
            "Aplikacja już działa",
            "Aplikacja FolderSync jest już uruchomiona na tym komputerze.\n\n"
            "Ze względów bezpieczeństwa integralności danych (standard CERT / NASA)\n"
            "dozwolona jest tylko jedna aktywna instancja programu jednocześnie.",
        )
        sys.exit(0)

    try:
        window = MainWindow()
        window.show()
        exit_code = app.exec()
    finally:
        lock.release()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
