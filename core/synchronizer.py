"""Moduł bezpiecznej synchronizacji plików (Security Level: NASA / CERT).
Realizuje:
- Tworzenie automatycznych kopii zapasowych (.backup) przed jakąkolwiek operacją nadpisania
- Atomowy zapis plików (zapobiega uszkodzeniu w razie nagłego braku zasilania/przerwania)
- Weryfikację integralności kryptograficznej SHA-256 po zapisie
- Ścisły audyt i raportowanie każdego kroku
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import os
from pathlib import Path
import shutil
from typing import Callable, Optional

from core.comparator import ComparisonItem, FileStatus, calculate_sha256, is_safe_relative_path


class SyncDirection(Enum):
    UPDATE_OLDER = "UPDATE_OLDER"  # Zastąp starsze pliki nowszymi (oraz brakujące)
    COPY_A_TO_B = "COPY_A_TO_B"    # Kopiuj wybrane z Katalogu A do B
    COPY_B_TO_A = "COPY_B_TO_A"    # Kopiuj wybrane z Katalogu B do A

    @property
    def display_name(self) -> str:
        names = {
            SyncDirection.UPDATE_OLDER: "Inteligentna aktualizacja (nowsze zastępują starsze)",
            SyncDirection.COPY_A_TO_B: "Kopiuj wybrane z Katalogu A do B",
            SyncDirection.COPY_B_TO_A: "Kopiuj wybrane z Katalogu B do A",
        }
        return names.get(self, self.value)


@dataclass
class SyncAction:
    item: ComparisonItem
    source_path: Path
    dest_path: Path
    will_overwrite: bool


@dataclass
class SyncReport:
    start_time: datetime
    end_time: Optional[datetime] = None
    files_processed: int = 0
    files_updated: int = 0
    files_backed_up: int = 0
    bytes_transferred: int = 0
    backup_dirs: list[Path] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    success: bool = True
    is_dry_run: bool = False
    dry_run_actions: list[str] = field(default_factory=list)  # opisy symulowanych operacji

    def summary(self) -> str:
        duration = ""
        if self.end_time:
            secs = (self.end_time - self.start_time).total_seconds()
            duration = f" w {secs:.1f} s"

        if self.is_dry_run:
            return (
                f"⚠️ TRYB SYMULACJI (Dry-Run) — żadne pliki NIE zostały zmodyfikowane!{duration}\n"
                f"Planowane operacje: {len(self.dry_run_actions)}\n"
                + "\n".join(f"  • {a}" for a in self.dry_run_actions[:30])
                + (f"\n  ... i {len(self.dry_run_actions) - 30} więcej" if len(self.dry_run_actions) > 30 else "")
            )

        status_txt = "Zakończono sukcesem" if self.success and not self.errors else "Zakończono z ostrzeżeniami/błędami"
        backup_info = f"\nKopie zapasowe (.backup): {len(self.backup_dirs)} lokalizacji" if self.backup_dirs else ""
        return (
            f"Raport synchronizacji: {status_txt}{duration}\n"
            f"- Zaktualizowano plików: {self.files_updated}\n"
            f"- Wykonano kopii zapasowych: {self.files_backed_up}\n"
            f"- Przesłano danych: {self.bytes_transferred / (1024 * 1024):.2f} MB\n"
            f"- Błędów: {len(self.errors)}{backup_info}"
        )


def plan_sync_actions(
    items: list[ComparisonItem],
    dir_a: Path,
    dir_b: Path,
    direction: SyncDirection,
) -> list[SyncAction]:
    """Przygotowuje bezpieczny plan operacji, analizując które pliki zostaną skopiowane lub nadpisane."""
    actions: list[SyncAction] = []
    base_a = dir_a.resolve()
    base_b = dir_b.resolve()

    for item in items:
        if not item.is_checked or item.status == FileStatus.IDENTICAL or item.status == FileStatus.ERROR:
            continue

        rel = Path(item.rel_path)
        path_in_a = base_a / rel
        path_in_b = base_b / rel

        # Weryfikacja bezpieczeństwa ścieżek
        if not is_safe_relative_path(base_a, path_in_a) or not is_safe_relative_path(base_b, path_in_b):
            continue

        if direction == SyncDirection.UPDATE_OLDER:
            if item.status == FileStatus.NEWER_A or item.status == FileStatus.ONLY_A:
                actions.append(SyncAction(item, path_in_a, path_in_b, will_overwrite=path_in_b.exists()))
            elif item.status == FileStatus.NEWER_B or item.status == FileStatus.ONLY_B:
                actions.append(SyncAction(item, path_in_b, path_in_a, will_overwrite=path_in_a.exists()))
            elif item.status == FileStatus.DIFFERENT_CONTENT:
                # W przypadku tej samej daty i różnej treści, jeśli użytkownik zaznaczył, preferujemy A -> B
                actions.append(SyncAction(item, path_in_a, path_in_b, will_overwrite=path_in_b.exists()))

        elif direction == SyncDirection.COPY_A_TO_B:
            if item.status in (FileStatus.NEWER_A, FileStatus.ONLY_A, FileStatus.NEWER_B, FileStatus.DIFFERENT_CONTENT):
                if path_in_a.exists():
                    actions.append(SyncAction(item, path_in_a, path_in_b, will_overwrite=path_in_b.exists()))

        elif direction == SyncDirection.COPY_B_TO_A:
            if item.status in (FileStatus.NEWER_B, FileStatus.ONLY_B, FileStatus.NEWER_A, FileStatus.DIFFERENT_CONTENT):
                if path_in_b.exists():
                    actions.append(SyncAction(item, path_in_b, path_in_a, will_overwrite=path_in_a.exists()))

    return actions


def execute_sync(
    actions: list[SyncAction],
    create_backup: bool = True,
    verify_sha256: bool = True,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    dry_run: bool = False,
) -> SyncReport:
    """Wykonuje plan synchronizacji z atomowością operacji i weryfikacją sumy kontrolnej.

    :param actions: Lista zaplanowanych akcji synchronizacji
    :param create_backup: Czy tworzyć kopię zapasową w podkatalogu .backup
    :param verify_sha256: Czy weryfikować sumę SHA-256 po zapisie
    :param progress_callback: Funkcja postępu (indeks, łącznie, nazwa_pliku)
    :param dry_run: Jeśli True, symuluje operacje BEZ modyfikowania dysku
    """
    report = SyncReport(start_time=datetime.now(), is_dry_run=dry_run)
    total_actions = len(actions)
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Tryb symulacji (Dry-Run)
    if dry_run:
        for idx, act in enumerate(actions, start=1):
            if progress_callback:
                progress_callback(idx, total_actions, act.item.rel_path)
            action_verb = "NAD PISANIE" if act.will_overwrite else "KOPIOWANIE"
            report.dry_run_actions.append(
                f"[{action_verb}] {act.source_path.name} → {act.dest_path}"
            )
        report.end_time = datetime.now()
        return report

    for idx, act in enumerate(actions, start=1):
        if progress_callback:
            progress_callback(idx, total_actions, act.item.rel_path)

        report.files_processed += 1
        src = act.source_path
        dst = act.dest_path

        try:
            if not src.exists():
                report.errors.append(f"Plik źródłowy nie istnieje: {src}")
                continue

            # 1. Tworzenie kopii zapasowej (Backup) przed nadpisaniem
            if act.will_overwrite and dst.exists() and create_backup:
                # Katalog docelowy nadrzędny
                # Tworzymy folder .backup w katalogu bazowym docelowym
                dest_root = dst
                # cofamy się do katalogu bazowego po liczbie segmentów rel_path
                rel_parts_count = len(Path(act.item.rel_path).parts)
                for _ in range(rel_parts_count):
                    dest_root = dest_root.parent

                backup_root = dest_root / ".backup" / f"backup_{timestamp_str}"
                backup_file_path = backup_root / act.item.rel_path
                backup_file_path.parent.mkdir(parents=True, exist_ok=True)

                shutil.copy2(dst, backup_file_path)
                report.files_backed_up += 1
                if backup_root not in report.backup_dirs:
                    report.backup_dirs.append(backup_root)

            # 2. Bezpieczne kopiowanie atomowe (najpierw do pliku .tmp, potem replace)
            dst.parent.mkdir(parents=True, exist_ok=True)
            tmp_dst = dst.with_name(f".tmp_sync_{dst.name}")

            shutil.copy2(src, tmp_dst)

            # 3. Weryfikacja kryptograficzna (NASA / CERT Standard)
            if verify_sha256:
                src_hash = calculate_sha256(src)
                tmp_hash = calculate_sha256(tmp_dst)
                if src_hash != tmp_hash:
                    if tmp_dst.exists():
                        tmp_dst.unlink()
                    raise IOError(f"Błąd integralności pliku (SHA-256 mismatch): {act.item.rel_path}")

            # Atomowa podmiana pliku docelowego
            if tmp_dst.exists():
                os.replace(tmp_dst, dst)

            file_size = dst.stat().st_size
            report.bytes_transferred += file_size
            report.files_updated += 1

        except Exception as e:
            report.success = False
            report.errors.append(f"Błąd przy {act.item.rel_path}: {e}")

    report.end_time = datetime.now()
    return report
