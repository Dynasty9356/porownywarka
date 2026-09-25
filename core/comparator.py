"""Moduł bezpiecznego porównywania katalogów (Security & Integrity Level: NASA / CERT).
Zapewnia ochronę przed Path Traversal, bezpieczną obsługę dowiązań symbolicznych oraz
kryptograficzną weryfikację integralności plików (SHA-256) z wielowątkową akceleracją.
"""

from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import fnmatch
import hashlib
import os
from pathlib import Path
import re
from typing import Callable, Optional


class OperationCancelledError(Exception):
    """Wyjątek zgłaszany w momencie anulowania operacji przez użytkownika."""
    pass


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


_RESERVED_DEVICE_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
}


def is_safe_relative_path(base_dir: Path, target_path: Path) -> bool:
    """Ochrona przed atakami Path Traversal, Symlink Escape i nazwami urządzeń DOS."""
    try:
        resolved_base = base_dir.resolve()
        resolved_target = target_path.resolve()
        
        # Sprawdzenie czy target znajduje się ściśle wewnątrz base_dir
        if os.path.commonpath([str(resolved_base), str(resolved_target)]) != str(resolved_base):
            return False

        # Weryfikacja nazw urządzeń DOS w segmentach ścieżki
        rel_parts = target_path.relative_to(base_dir).parts
        for part in rel_parts:
            stem = part.split(".")[0].upper()
            if stem in _RESERVED_DEVICE_NAMES:
                return False

        return True
    except (ValueError, OSError):
        return False


def validate_safe_directory_path(path_str: str) -> bool:
    """Weryfikuje czy ścieżka wprowadzona przez użytkownika lub profil jest bezpieczna (CERT)."""
    if not path_str or not path_str.strip():
        return False
    clean = path_str.strip()
    # Zakaz niebezpiecznych prefixów systemowych (NT / DOS device namespace)
    norm = clean.replace("/", "\\")
    if norm.startswith("\\\\.\\") or norm.startswith("\\\\?\\"):
        return False
    # Zakaz znaków kontrolnych
    if any(ord(c) < 32 for c in clean):
        return False
    try:
        p = Path(clean)
        # Sprawdzenie czy da się zresolvować bez błędów
        _ = p.resolve()
        return True
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
        norm_rel = rel_path.replace("\\", "/")
        if fnmatch.fnmatch(norm_rel, pat):
            return True
        # Dopasowanie po segmencie ścieżki (np. 'node_modules' w środku)
        if any(fnmatch.fnmatch(seg, pat) for seg in Path(rel_path).parts):
            return True
    return False


def scan_directory(
    base_dir: Path,
    follow_symlinks: bool = False,
    exclude_patterns: Optional[list[str]] = None,
    cancel_token: Optional[Callable[[], bool]] = None,
) -> dict[str, Path]:
    """Bezpieczne, rekursywne skanowanie katalogu zwracające mapę: rel_path -> full_path."""
    files: dict[str, Path] = {}
    base_dir = base_dir.resolve()
    patterns = exclude_patterns or []

    if not base_dir.is_dir():
        return files

    for root, dirs, filenames in os.walk(base_dir, followlinks=follow_symlinks):
        if cancel_token and cancel_token():
            raise OperationCancelledError("Przerwano skanowanie katalogu.")

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


def _compute_hash_safe(fpath: Path) -> tuple[Path, Optional[str], Optional[str]]:
    """Bezpieczne obliczanie skrótu SHA-256 zwracające (ścieżka, hash, błąd)."""
    try:
        return fpath, calculate_sha256(fpath), None
    except OSError as e:
        return fpath, None, str(e)


def compare_directories(
    dir_a: Path,
    dir_b: Path,
    compare_hashes: bool = False,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    time_tolerance_seconds: float = 1.0,
    exclude_patterns: Optional[list[str]] = None,
    cancel_token: Optional[Callable[[], bool]] = None,
    max_hash_threads: int = 4,
) -> list[ComparisonItem]:
    """Porównuje rekursywnie dwa katalogi ze standardami rygorystycznej weryfikacji.

    :param dir_a: Ścieżka do Katalogu A
    :param dir_b: Ścieżka do Katalogu B
    :param compare_hashes: Czy liczyć i porównywać kryptograficzne sumy SHA-256
    :param progress_callback: Funkcja raportująca postęp: (przetworzono, łącznie, nazwa_pliku)
    :param time_tolerance_seconds: Tolerancja czasu modyfikacji dla systemów FAT/NTFS
    :param exclude_patterns: Lista wzorców wykluczeń
    :param cancel_token: Opcjonalne wywołanie zwracające True jeśli zażądano przerwania
    :param max_hash_threads: Maksymalna liczba wątków do równoległego haszowania SHA-256
    """
    path_a = dir_a.resolve()
    path_b = dir_b.resolve()

    if not path_a.is_dir() or not path_b.is_dir():
        raise ValueError("Obie podane ścieżki muszą być poprawnymi i istniejącymi katalogami.")

    if cancel_token and cancel_token():
        raise OperationCancelledError("Operacja została anulowana przed rozpoczęciem.")

    files_a = scan_directory(path_a, exclude_patterns=exclude_patterns, cancel_token=cancel_token)
    files_b = scan_directory(path_b, exclude_patterns=exclude_patterns, cancel_token=cancel_token)

    all_rel_paths = sorted(set(files_a.keys()) | set(files_b.keys()))
    total_files = len(all_rel_paths)
    results: list[ComparisonItem] = []

    # Faza 1: Szybka analiza metadanych i identyfikacja plików do hashowania
    items_to_hash: list[tuple[ComparisonItem, Path, Path, float]] = []

    for index, rel_path in enumerate(all_rel_paths, start=1):
        if cancel_token and cancel_token():
            raise OperationCancelledError("Operacja anulowana przez użytkownika.")

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

        # Klasyfikacja obecności jednostronnej
        if in_a and not in_b:
            item.status = FileStatus.ONLY_A
            item.is_checked = item.default_sync_selected()
            results.append(item)
        elif in_b and not in_a:
            item.status = FileStatus.ONLY_B
            item.is_checked = item.default_sync_selected()
            results.append(item)
        else:
            # Plik istnieje w obu katalogach
            assert file_a_path is not None and file_b_path is not None
            assert item.mtime_a is not None and item.mtime_b is not None

            time_diff = (item.mtime_a - item.mtime_b).total_seconds()
            same_size = item.size_a == item.size_b

            if compare_hashes:
                # Odkładamy do równoległego wyliczenia sum SHA-256
                items_to_hash.append((item, file_a_path, file_b_path, time_diff))
                results.append(item)
            else:
                # Szybkie porównanie po dacie i rozmiarze
                if abs(time_diff) <= time_tolerance_seconds and same_size:
                    item.status = FileStatus.IDENTICAL
                elif time_diff > time_tolerance_seconds:
                    item.status = FileStatus.NEWER_A
                elif time_diff < -time_tolerance_seconds:
                    item.status = FileStatus.NEWER_B
                else:
                    item.status = FileStatus.DIFFERENT_CONTENT

                item.is_checked = item.default_sync_selected()
                results.append(item)

    # Faza 2: Równoległe wielowątkowe haszowanie SHA-256 [CORE-1]
    if compare_hashes and items_to_hash:
        files_to_hash = set()
        for _, fa, fb, _ in items_to_hash:
            files_to_hash.add(fa)
            files_to_hash.add(fb)

        num_threads = min(max_hash_threads, os.cpu_count() or 4, len(files_to_hash) or 1)
        hash_results: dict[Path, tuple[Optional[str], Optional[str]]] = {}

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = {executor.submit(_compute_hash_safe, fp): fp for fp in files_to_hash}
            for fut in as_completed(futures):
                if cancel_token and cancel_token():
                    executor.shutdown(wait=False, cancel_futures=True)
                    raise OperationCancelledError("Anulowano podczas haszowania SHA-256.")
                fpath, h_val, err = fut.result()
                hash_results[fpath] = (h_val, err)

        # Przypisanie hashy i ostateczna klasyfikacja
        for item, file_a_path, file_b_path, time_diff in items_to_hash:
            h_a, err_a = hash_results.get(file_a_path, (None, "Nieznany błąd haszowania A"))
            h_b, err_b = hash_results.get(file_b_path, (None, "Nieznany błąd haszowania B"))

            if err_a or err_b:
                item.status = FileStatus.ERROR
                item.error_msg = f"Błąd haszowania: {err_a or err_b}"
                item.is_checked = False
                continue

            item.sha256_a = h_a
            item.sha256_b = h_b

            if item.sha256_a == item.sha256_b:
                item.status = FileStatus.IDENTICAL
            else:
                if time_diff > time_tolerance_seconds:
                    item.status = FileStatus.NEWER_A
                elif time_diff < -time_tolerance_seconds:
                    item.status = FileStatus.NEWER_B
                else:
                    item.status = FileStatus.DIFFERENT_CONTENT

            item.is_checked = item.default_sync_selected()

    return results
