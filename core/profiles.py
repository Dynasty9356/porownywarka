"""Moduł bezpiecznego zarządzania szablonami i profilami synchronizacji (Security Standards).
Zapewnia atomowy zapis konfiguracji w profilu użytkownika (AppData), walidację integralności
oraz pełną kompatybilność wsteczną ze strukturami listowymi i słownikowymi JSON.
"""

from __future__ import annotations
from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
from typing import Any, Optional


@dataclass
class SyncProfile:
    name: str
    dir_a: str
    dir_b: str
    compare_hashes: bool = False
    create_backup: bool = True
    sync_mode: str = "UPDATE_OLDER"
    raw_data: Optional[dict[str, Any]] = None
    exclude_patterns: list[str] = field(default_factory=list)
    description: str = ""
    pre_sync_cmd: str = ""
    post_sync_cmd: str = ""


def get_config_dir() -> Path:
    """Zwraca dedykowany i bezpieczny katalog konfiguracyjny aplikacji w profilu użytkownika."""
    app_data = os.environ.get("APPDATA")
    if app_data:
        cfg_dir = Path(app_data) / "FolderSync"
    else:
        cfg_dir = Path.home() / ".foldersync"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    return cfg_dir


def get_profiles_path() -> Path:
    return get_config_dir() / "profiles.json"


def _normalize_sync_mode(mode_val: Any) -> str:
    """Konwertuje różne nazwy trybów synchronizacji (np. 'Obustronna') na standardowe wartości."""
    if not isinstance(mode_val, str):
        return "UPDATE_OLDER"
    val = mode_val.strip().lower()
    if "obustronn" in val or "update" in val or "inteligentn" in val:
        return "UPDATE_OLDER"
    elif "a_to_b" in val or "a do b" in val:
        return "COPY_A_TO_B"
    elif "b_to_a" in val or "b do a" in val:
        return "COPY_B_TO_A"
    return "UPDATE_OLDER"


def _parse_profile_dict(name: str, item: dict[str, Any]) -> Optional[SyncProfile]:
    """Bezpiecznie mapuje pola profilu, tolerując alternatywne nazewnictwo (use_checksum, backup itp.)."""
    if not isinstance(item, dict):
        return None

    dir_a = str(item.get("dir_a", "")).strip()
    dir_b = str(item.get("dir_b", "")).strip()
    p_name = str(item.get("name", name)).strip()

    if not p_name:
        return None

    # Obsługa alternatywnych kluczy z innych wersji
    compare_hashes = bool(item.get("compare_hashes", item.get("use_checksum", False)))
    create_backup = bool(item.get("create_backup", item.get("backup", True)))
    sync_mode = _normalize_sync_mode(item.get("sync_mode", "UPDATE_OLDER"))

    raw_patterns = item.get("exclude_patterns", [])
    exclude_patterns = [str(x) for x in raw_patterns] if isinstance(raw_patterns, list) else []
    description = str(item.get("description", "")).strip()
    pre_sync_cmd = str(item.get("pre_sync_cmd", "")).strip()
    post_sync_cmd = str(item.get("post_sync_cmd", "")).strip()

    return SyncProfile(
        name=p_name,
        dir_a=dir_a,
        dir_b=dir_b,
        compare_hashes=compare_hashes,
        create_backup=create_backup,
        sync_mode=sync_mode,
        raw_data=item,
        exclude_patterns=exclude_patterns,
        description=description,
        pre_sync_cmd=pre_sync_cmd,
        post_sync_cmd=post_sync_cmd,
    )


def load_profiles() -> dict[str, SyncProfile]:
    """Wczytuje listę zapisanych szablonów, obsługując zarówno format listowy [{}], jak i słownikowy {{}}."""
    path = get_profiles_path()
    if not path.is_file():
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        profiles: dict[str, SyncProfile] = {}

        if isinstance(data, list):
            # Format: [ {"name": "...", "dir_a": "..."}, ... ]
            for entry in data:
                if isinstance(entry, dict):
                    name = str(entry.get("name", "")).strip()
                    p = _parse_profile_dict(name, entry)
                    if p:
                        profiles[p.name] = p

        elif isinstance(data, dict):
            # Format: { "Profil1": {"dir_a": "..."}, ... }
            for name, entry in data.items():
                if isinstance(entry, dict):
                    p = _parse_profile_dict(str(name), entry)
                    if p:
                        profiles[p.name] = p

        return profiles
    except Exception:
        # Odporność CERT: Błąd w pliku konfiguracyjnym nigdy nie zawiesza uruchomienia aplikacji
        return {}


def save_profile(profile: SyncProfile) -> bool:
    """Zapisuje lub aktualizuje profil z użyciem bezpiecznego zapisu atomowego."""
    if not profile.name.strip():
        return False

    profiles = load_profiles()
    profiles[profile.name.strip()] = profile

    path = get_profiles_path()
    tmp_path = path.with_suffix(".tmp")

    try:
        # Zapisujemy w uniwersalnym, eleganckim formacie listy
        output_list = []
        for p in profiles.values():
            base_dict = p.raw_data.copy() if p.raw_data else {}
            base_dict.update({
                "name": p.name,
                "dir_a": p.dir_a,
                "dir_b": p.dir_b,
                "compare_hashes": p.compare_hashes,
                "create_backup": p.create_backup,
                "sync_mode": p.sync_mode,
                "exclude_patterns": getattr(p, "exclude_patterns", []),
                "description": getattr(p, "description", ""),
                "pre_sync_cmd": getattr(p, "pre_sync_cmd", ""),
                "post_sync_cmd": getattr(p, "post_sync_cmd", ""),
            })
            output_list.append(base_dict)

        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(output_list, f, ensure_ascii=False, indent=2)

        os.replace(tmp_path, path)
        return True
    except OSError:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        return False


def delete_profile(name: str) -> bool:
    """Usuwa profil o podanej nazwie."""
    profiles = load_profiles()
    clean_name = name.strip()
    if clean_name not in profiles:
        return False

    del profiles[clean_name]

    path = get_profiles_path()
    tmp_path = path.with_suffix(".tmp")

    try:
        output_list = []
        for p in profiles.values():
            base_dict = p.raw_data.copy() if p.raw_data else {}
            base_dict.update({
                "name": p.name,
                "dir_a": p.dir_a,
                "dir_b": p.dir_b,
                "compare_hashes": p.compare_hashes,
                "create_backup": p.create_backup,
                "sync_mode": p.sync_mode,
                "exclude_patterns": getattr(p, "exclude_patterns", []),
                "description": getattr(p, "description", ""),
                "pre_sync_cmd": getattr(p, "pre_sync_cmd", ""),
                "post_sync_cmd": getattr(p, "post_sync_cmd", ""),
            })
            output_list.append(base_dict)

        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(output_list, f, ensure_ascii=False, indent=2)

        os.replace(tmp_path, path)
        return True
    except OSError:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        return False
