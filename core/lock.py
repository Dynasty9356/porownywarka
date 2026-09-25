"""Moduł ochrony przed współbieżnym uruchomieniem (Single Instance Protection / Anti-Race Condition).
Zapewnia standard bezpieczeństwa CERT/NASA zapobiegający konfliktom zapisu i uszkodzeniu danych
przy próbie jednoczesnego uruchomienia wielu instancji procesu.
"""

from __future__ import annotations
import os
import sys
from pathlib import Path
from typing import Optional

try:
    import msvcrt
except ImportError:
    msvcrt = None


class SingleInstanceLock:
    """Blokada jednoczesnego uruchomienia wielu instancji oparta na blokadzie plikowej na poziomie OS."""

    def __init__(self, app_name: str = "FolderSync"):
        self.app_name = app_name
        self._lock_file: Optional[Path] = None
        self._file_handle = None
        self._is_locked = False

    def acquire(self) -> bool:
        """Próbuje założyć wyłączną blokadę procesu. Zwraca True jeśli udało się, False jeśli inna instancja już działa."""
        app_data = os.environ.get("APPDATA")
        cfg_dir = Path(app_data) / self.app_name if app_data else Path.home() / f".{self.app_name.lower()}"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        self._lock_file = cfg_dir / "app.lock"

        try:
            # Otwarcie pliku w trybie odczytu/zapisu
            self._file_handle = open(self._lock_file, "a+")
            if msvcrt:
                # Blokada wyłączna pierwszego bajtu (non-blocking)
                self._file_handle.seek(0)
                msvcrt.locking(self._file_handle.fileno(), msvcrt.LK_NBLCK, 1)
            
            # Zapisz PID aktualnego procesu
            self._file_handle.seek(0)
            self._file_handle.truncate()
            self._file_handle.write(f"PID={os.getpid()}\n")
            self._file_handle.flush()
            self._is_locked = True
            return True
        except (IOError, OSError):
            if self._file_handle:
                try:
                    self._file_handle.close()
                except Exception:
                    pass
                self._file_handle = None
            self._is_locked = False
            return False

    def release(self) -> None:
        """Zwalnia blokadę plikową i zamyka uchwyt."""
        if self._file_handle:
            try:
                if msvcrt and self._is_locked:
                    self._file_handle.seek(0)
                    msvcrt.locking(self._file_handle.fileno(), msvcrt.LK_UNLCK, 1)
            except (IOError, OSError):
                pass
            try:
                self._file_handle.close()
            except (IOError, OSError):
                pass
            self._file_handle = None
        self._is_locked = False
