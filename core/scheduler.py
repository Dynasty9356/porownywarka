"""Moduł Harmonogramu i Obserwatora Katalogów (Scheduler & Watch Mode).
Zgodny ze standardami bezpieczeństwa CERT / NASA:
- Asynchroniczna praca bez blokowania wątku głównego GUI
- Mechanizm Debounce (stabilizacja zapisu plików przed rozpoczęciem porównania)
- Odporność na błędy odłączonych nośników i uprawnień dostępu
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QFileSystemWatcher, QObject, QTimer, pyqtSignal


class SyncScheduler(QObject):
    """Odpowiada za cykliczne uruchamianie porównania/synchronizacji w tle."""
    scheduled_trigger = pyqtSignal(bool)  # argument: czy wykonać auto-sync (True) czy tylko porównać (False)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timeout)
        self._auto_sync = False

    def start(self, interval_minutes: int, auto_sync: bool = False):
        """Uruchamia harmonogram z podanym interwałem (w minutach)."""
        self._auto_sync = auto_sync
        self.stop()
        if interval_minutes <= 0:
            return
        interval_ms = max(60_000, interval_minutes * 60 * 1000)
        self._timer.start(interval_ms)

    def stop(self):
        """Zatrzymuje harmonogram."""
        if self._timer.isActive():
            self._timer.stop()

    @property
    def is_running(self) -> bool:
        return self._timer.isActive()

    def _on_timeout(self):
        self.scheduled_trigger.emit(self._auto_sync)


class DirectoryWatcher(QObject):
    """Monitoruje wybrane katalogi w czasie rzeczywistym i zgłasza zmiany z filtrem debounce."""
    change_detected = pyqtSignal(str)

    def __init__(self, debounce_ms: int = 3000, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(self._on_path_changed)
        self._watcher.fileChanged.connect(self._on_path_changed)

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(debounce_ms)
        self._debounce_timer.timeout.connect(self._on_debounce_timeout)

        self._pending_change_path: str = ""
        self._watched_paths: list[str] = []

    def set_watch_paths(self, paths: list[str]):
        """Ustawia ścieżki do aktywnego monitorowania."""
        self.clear()
        valid = []
        for p in paths:
            if not p or not p.strip():
                continue
            path_obj = Path(p.strip())
            if path_obj.is_dir():
                valid.append(str(path_obj.resolve()))
                # Dodajemy również bezpośrednie podkatalogi pierwszego poziomu dla większej czułości
                try:
                    for child in path_obj.iterdir():
                        if child.is_dir() and not child.name.startswith("."):
                            valid.append(str(child.resolve()))
                except (PermissionError, OSError):
                    pass

        if valid:
            self._watcher.addPaths(valid)
            self._watched_paths = valid

    def clear(self):
        """Czyści listę obserwowanych ścieżek."""
        if self._watched_paths:
            self._watcher.removePaths(self._watched_paths)
            self._watched_paths = []
        self._debounce_timer.stop()
        self._pending_change_path = ""

    def _on_path_changed(self, path: str):
        """Odbiera sygnał ze sterownika systemu Windows i restartuje timer debounce."""
        self._pending_change_path = path
        self._debounce_timer.start()

    def _on_debounce_timeout(self):
        """Emituje sygnał po upływie czasu stabilizacji (pliki zostały w pełni zapisane)."""
        if self._pending_change_path:
            target = self._pending_change_path
            self._pending_change_path = ""
            self.change_detected.emit(target)
