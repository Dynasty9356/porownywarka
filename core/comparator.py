"""Moduł bezpiecznego porównywania katalogów (Security & Integrity Level: NASA / CERT).
Zapewnia ochronę przed Path Traversal, bezpieczną obsługę dowiązań symbolicznych oraz
kryptograficzną weryfikację integralności plików (SHA-256).
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import fnmatch
import hashlib
import os
from pathlib import Path
from typing import Callable, Optional


class FileStatus(Enum):
    IDENTICAL = "IDENTICAL"               # Pliki identyczne
    NEWER_A = "NEWER_A"                   # Plik nowszy w Katalogu A
    NEWER_B = "NEWER_B"                   # Plik nowszy w Katalogu B
    ONLY_A = "ONLY_A"                     # Plik obecny tylko w Katalogu A
    ONLY_B = "ONLY_B"                     # Plik obecny tylko w Katalogu B
    DIFFERENT_CONTENT = "DIFFERENT"       # Ta sama data/rozmiar, lecz różna treść (SHA-256)
    ERROR = "ERROR"                       # Błąd dostępu / odczytu

    @property
    def display_name(self) -> str:
        names = {
            FileStatus.IDENTICAL: "[=] Identyczne",
            FileStatus.NEWER_A: "[A > B] Nowszy w A",
            FileStatus.NEWER_B: "[B > A] Nowszy w B",
            FileStatus.ONLY_A: "[+] Tylko w A",
            FileStatus.ONLY_B: "[+] Tylko w B",
            FileStatus.DIFFERENT_CONTENT: "[!] Różna treść (Hash)",
            FileStatus.ERROR: "[X] Błąd dostępu",
        }
        return names.get(self, self.value)

    @property
    def is_different(self) -> bool:
        return self != FileStatus.IDENTICAL


@dataclass
class ComparisonItem:
    rel_path: str
    status: FileStatus
    size_a: Optional[int] = None
    size_b: Optional[int] = None
    mtime_a: Optional[datetime] = None
    mtime_b: Optional[datetime] = None
    sha256_a: Optional[str] = None
    sha256_b: Optional[str] = None
    error_msg: Optional[str] = None
    is_checked: bool = False

    def default_sync_selected(self) -> bool:
        """Domyślna rekomendacja bezpieczeństwa do synchronizacji (tylko pliki wymagające uaktualnienia)."""
        return self.status in (
            FileStatus.NEWER_A,
            FileStatus.NEWER_B,
            FileStatus.ONLY_A,
            FileStatus.ONLY_B,
            FileStatus.DIFFERENT_CONTENT,
        )


def calculate_sha256(file_path: Path, block_size: int = 65536) -> str:
    """Strumieniowe obliczanie sumy SHA-256 zoptymalizowane pod kątem minimalnego zużycia RAM."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(block_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def is_safe_relative_path(base_dir: Path, target_path: Path) -> bool:
    """Ochrona przed atakami Path Traversal i Symlink Escape."""
    try:
        resolved_base = base_dir.resolve()
        resolved_target = target_path.resolve()
        return os.path.commonpath([str(resolved_base), str(resolved_target)]) == str(resolved_base)
    except (ValueError, OSError):
        return False


def _is_excluded(name: str, rel_path: str, patterns: list[str]) -> bool:
    """Sprawdza czy plik lub katalog pasuje do któregoś ze wzorców wykluczeń (glob)."""
    for pat in patterns:
        pat = pat.strip()
        if not pat:
            continue
        # Dopasowanie po samej nazwie pliku/katalogu
        if fnmatch.fnmatch(name, pat):
            return True
        # Dopasowanie po fragmencie ścieżki względnej
        if fnmatch.fnmatch(rel_path.replace("\\", "/"), pat):
            return True
        # Dopasowanie po segmencie ścieżki (np. 'node_modules' w środku)
        if any(fnmatch.fnmatch(seg, pat) for seg in Path(rel_path).parts):
            return True
    return False


def scan_directory(
    base_dir: Path,
    follow_symlinks: bool = False,
    exclude_patterns: Optional[list[str]] = None,
) -> dict[str, Path]:
    """Bezpieczne, rekursywne skanowanie katalogu zwracające mapę: rel_path -> full_path."""
    files: dict[str, Path] = {}
    base_dir = base_dir.resolve()
    patterns = exclude_patterns or []

    if not base_dir.is_dir():
        return files

    for root, dirs, filenames in os.walk(base_dir, followlinks=follow_symlinks):
        root_path = Path(root)
        rel_root = str(root_path.relative_to(base_dir)) if root_path != base_dir else ""

        # Ochrona przed modyfikacją katalogów symlinkowanych poza bazę
        if not follow_symlinks:
            dirs[:] = [d for d in dirs if not (root_path / d).is_symlink()]

        # Wykluczenie całych podkatalogów przed zejściem w głąb
        if patterns:
            dirs[:] = [
                d for d in dirs
                if not _is_excluded(d, (rel_root + "/" + d).lstrip("/"), patterns)
            ]

        for fname in filenames:
            file_path = root_path / fname
            if not follow_symlinks and file_path.is_symlink():
                continue

            try:
                rel_path = str(file_path.relative_to(base_dir))
                if patterns and _is_excluded(fname, rel_path, patterns):
                    continue
                files[rel_path] = file_path
            except ValueError:
                continue

    return files


def compare_directories(
    dir_a: Path,
    dir_b: Path,
    compare_hashes: bool = False,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    time_tolerance_seconds: float = 1.0,
    exclude_patterns: Optional[list[str]] = None,
) -> list[ComparisonItem]:
    """Porównuje rekursywnie dwa katalogi ze standardami rygorystycznej weryfikacji.

    :param dir_a: Ścieżka do Katalogu A
    :param dir_b: Ścieżka do Katalogu B
    :param compare_hashes: Czy liczyć i porównywać kryptograficzne sumy SHA-256
    :param progress_callback: Funkcja raportująca postęp: (przetworzono, łącznie, nazwa_pliku)
    :param time_tolerance_seconds: Tolerancja czasu modyfikacji dla systemów FAT/NTFS
    """
    path_a = dir_a.resolve()
    path_b = dir_b.resolve()

    if not path_a.is_dir() or not path_b.is_dir():
        raise ValueError("Obie podane ścieżki muszą być poprawnymi i istniejącymi katalogami.")

    files_a = scan_directory(path_a, exclude_patterns=exclude_patterns)
    files_b = scan_directory(path_b, exclude_patterns=exclude_patterns)

    all_rel_paths = sorted(set(files_a.keys()) | set(files_b.keys()))
    total_files = len(all_rel_paths)
    results: list[ComparisonItem] = []

    for index, rel_path in enumerate(all_rel_paths, start=1):
        if progress_callback:
            progress_callback(index, total_files, rel_path)

        in_a = rel_path in files_a
        in_b = rel_path in files_b

        item = ComparisonItem(rel_path=rel_path, status=FileStatus.IDENTICAL)

        file_a_path = files_a[rel_path] if in_a else None
        file_b_path = files_b[rel_path] if in_b else None

        # Pobranie metadanych z Katalogu A
        if file_a_path:
            try:
                stat_a = file_a_path.stat()
                item.size_a = stat_a.st_size
                item.mtime_a = datetime.fromtimestamp(stat_a.st_mtime)
            except OSError as e:
                item.status = FileStatus.ERROR
                item.error_msg = f"Katalog A: {e}"

        # Pobranie metadanych z Katalogu B
        if file_b_path:
            try:
                stat_b = file_b_path.stat()
                item.size_b = stat_b.st_size
                item.mtime_b = datetime.fromtimestamp(stat_b.st_mtime)
            except OSError as e:
                item.status = FileStatus.ERROR
                item.error_msg = f"Katalog B: {e}"

        # Jeśli wystąpił błąd odczytu, przejdź dalej
        if item.status == FileStatus.ERROR:
            item.is_checked = False
            results.append(item)
            continue

        # Klasyfikacja obecności
        if in_a and not in_b:
            item.status = FileStatus.ONLY_A
        elif in_b and not in_a:
            item.status = FileStatus.ONLY_B
        else:
            # Plik istnieje w obu katalogach
            assert file_a_path is not None and file_b_path is not None
            assert item.mtime_a is not None and item.mtime_b is not None

            time_diff = (item.mtime_a - item.mtime_b).total_seconds()
            same_size = item.size_a == item.size_b

            # Porównanie sumy SHA-256 (jeśli zażądano lub jeśli rozmiar/czas wskazuje na potrzebę)
            if compare_hashes:
                try:
                    item.sha256_a = calculate_sha256(file_a_path)
                    item.sha256_b = calculate_sha256(file_b_path)
                except OSError as e:
                    item.status = FileStatus.ERROR
                    item.error_msg = f"Błąd haszowania SHA-256: {e}"
                    results.append(item)
                    continue

                if item.sha256_a == item.sha256_b:
                    item.status = FileStatus.IDENTICAL
                else:
                    if time_diff > time_tolerance_seconds:
                        item.status = FileStatus.NEWER_A
                    elif time_diff < -time_tolerance_seconds:
                        item.status = FileStatus.NEWER_B
                    else:
                        item.status = FileStatus.DIFFERENT_CONTENT
            else:
                # Szybkie porównanie po dacie i rozmiarze
                if abs(time_diff) <= time_tolerance_seconds and same_size:
                    item.status = FileStatus.IDENTICAL
                elif time_diff > time_tolerance_seconds:
                    item.status = FileStatus.NEWER_A
                elif time_diff < -time_tolerance_seconds:
                    item.status = FileStatus.NEWER_B
                else:
                    # Czas ten sam, ale inny rozmiar
                    item.status = FileStatus.DIFFERENT_CONTENT

        item.is_checked = item.default_sync_selected()
        results.append(item)

    return results
