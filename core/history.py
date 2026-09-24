"""Moduł historii porównań i synchronizacji FolderSync."""

from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Optional

from core.settings import load_settings


@dataclass
class HistoryEntry:
    entry_id: str
    timestamp: str                     # ISO 8601
    dir_a: str
    dir_b: str
    profile_name: str = ""
    total_files: int = 0
    identical_files: int = 0
    different_files: int = 0
    only_in_a: int = 0
    only_in_b: int = 0
    synced: bool = False
    sync_timestamp: Optional[str] = None
    files_updated: int = 0
    bytes_transferred: int = 0
    compare_hashes: bool = False
    errors: list[str] = field(default_factory=list)


def _get_history_path() -> Path:
    app_data = os.environ.get("APPDATA")
    cfg_dir = Path(app_data) / "FolderSync" if app_data else Path.home() / ".foldersync"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    return cfg_dir / "history.json"


def load_history() -> list[HistoryEntry]:
    path = _get_history_path()
    if not path.is_file():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        entries = []
        for item in data:
            if isinstance(item, dict):
                e = HistoryEntry(
                    entry_id=str(item.get("entry_id", "")),
                    timestamp=str(item.get("timestamp", "")),
                    dir_a=str(item.get("dir_a", "")),
                    dir_b=str(item.get("dir_b", "")),
                    profile_name=str(item.get("profile_name", "")),
                    total_files=int(item.get("total_files", 0)),
                    identical_files=int(item.get("identical_files", 0)),
                    different_files=int(item.get("different_files", 0)),
                    only_in_a=int(item.get("only_in_a", 0)),
                    only_in_b=int(item.get("only_in_b", 0)),
                    synced=bool(item.get("synced", False)),
                    sync_timestamp=item.get("sync_timestamp"),
                    files_updated=int(item.get("files_updated", 0)),
                    bytes_transferred=int(item.get("bytes_transferred", 0)),
                    compare_hashes=bool(item.get("compare_hashes", False)),
                    errors=list(item.get("errors", [])),
                )
                entries.append(e)
        return entries
    except Exception:
        return []


def save_history(entries: list[HistoryEntry]) -> bool:
    settings = load_settings()
    max_entries = settings.max_history_entries
    trimmed = entries[-max_entries:] if len(entries) > max_entries else entries

    path = _get_history_path()
    tmp_path = path.with_suffix(".tmp")
    try:
        data = [asdict(e) for e in trimmed]
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
        return True
    except OSError:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        return False


def append_history_entry(entry: HistoryEntry) -> bool:
    entries = load_history()
    entries.append(entry)
    return save_history(entries)


def make_entry_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")
