"""Moduł trwałych ustawień aplikacji FolderSync (Security Standard: atomowy zapis, walidacja).
Wszystkie preferencje użytkownika są zapisywane w %APPDATA%\\FolderSync\\settings.json.
"""

from __future__ import annotations
from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
from typing import Any


@dataclass
class AppSettings:
    # Wygląd
    theme: str = "dark"                         # dark | light | auto
    language: str = "pl"                        # pl | en

    # Zachowanie porównywania
    time_tolerance_seconds: float = 1.0
    sha256_block_size: int = 65536
    auto_compare_on_profile_load: bool = False

    # Zachowanie synchronizacji
    confirm_sync: str = "always"                # always | overwrite_only | never
    default_sync_mode: str = "UPDATE_OLDER"
    backup_retention_count: int = 10            # Maksymalna liczba zachowanych sesji .backup na folder
    backup_auto_cleanup: bool = True            # Automatyczne usuwanie najstarszych kopii zapasowych

    # Tabela wyników
    default_sort_column: int = 1                # kolumna Statusu
    default_sort_ascending: bool = True
    visible_columns: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5])

    # Wykluczenia globalne
    global_exclude_patterns: list[str] = field(default_factory=lambda: [
        "Thumbs.db", ".DS_Store", "desktop.ini",
        "*.tmp", "*.bak", "*.log",
        "$RECYCLE.BIN", "System Volume Information",
        "node_modules", ".git", ".svn", "__pycache__",
        ".venv", ".backup",
    ])

    # Historia i raporty
    max_history_entries: int = 100
    report_output_dir: str = ""

    # Zasobnik i harmonogram
    minimize_to_tray: bool = False
    close_to_tray: bool = False
    show_tray_notifications: bool = True
    scheduler_enabled: bool = False
    scheduler_interval_minutes: int = 30
    scheduler_auto_sync: bool = False
    watch_mode_enabled: bool = False

    # Aktualizacje programu
    check_updates_on_startup: bool = True
    github_repo: str = "Dynasty9356/porownywarka"


def _get_settings_path() -> Path:
    app_data = os.environ.get("APPDATA")
    if app_data:
        cfg_dir = Path(app_data) / "FolderSync"
    else:
        cfg_dir = Path.home() / ".foldersync"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    return cfg_dir / "settings.json"


_cached_settings: AppSettings | None = None


def load_settings() -> AppSettings:
    """Wczytuje ustawienia z pliku JSON. Przy błędzie lub braku pliku zwraca domyślne."""
    global _cached_settings
    if _cached_settings is not None:
        return _cached_settings

    path = _get_settings_path()
    if not path.is_file():
        _cached_settings = AppSettings()
        return _cached_settings

    try:
        with open(path, "r", encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)

        s = AppSettings()
        for key, val in data.items():
            if hasattr(s, key):
                setattr(s, key, val)
        _cached_settings = s
    except Exception:
        _cached_settings = AppSettings()

    return _cached_settings


def save_settings(settings: AppSettings) -> bool:
    """Atomowy zapis ustawień do pliku JSON."""
    global _cached_settings
    path = _get_settings_path()
    tmp_path = path.with_suffix(".tmp")

    try:
        data = asdict(settings)
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
        _cached_settings = settings
        return True
    except OSError:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        return False


def invalidate_cache() -> None:
    """Wymusza ponowne wczytanie ustawień przy następnym wywołaniu load_settings()."""
    global _cached_settings
    _cached_settings = None
