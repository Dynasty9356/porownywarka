"""Moduł bezpiecznej synchronizacji plików (Security Level: NASA / CERT).
Realizuje:
- Tworzenie automatycznych kopii zapasowych (.backup) przed jakąkolwiek operacją nadpisania lub usunięcia
- Atomowy zapis plików (zapobiega uszkodzeniu w razie nagłego braku zasilania/przerwania)
- Weryfikację integralności kryptograficznej SHA-256 po zapisie i przy przywracaniu (Rollback)
- Ścisły audyt i raportowanie każdego kroku
- Tryb lustrzany (Mirror A -> B) z ochroną danych
- Obsługę przerywania operacji (Cancel Token)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import os
from pathlib import Path
import shutil
from typing import Callable, Optional

from core.comparator import ComparisonItem, FileStatus, OperationCancelledError, calculate_sha256, is_safe_relative_path


class SyncDirection(Enum):
    UPDATE_OLDER = "UPDATE_OLDER"  # Zastąp starsze pliki nowszymi (oraz brakujące)
    COPY_A_TO_B = "COPY_A_TO_B"    # Kopiuj wybrane z Katalogu A do B
    COPY_B_TO_A = "COPY_B_TO_A"    # Kopiuj wybrane z Katalogu B do A
    MIRROR_A_TO_B = "MIRROR_A_TO_B"  # Lustro A -> B (pliki nieobecne w A są usuwane z B z kopią w .backup)

    @property
    def display_name(self) -> str:
        names = {
            SyncDirection.UPDATE_OLDER: "Inteligentna aktualizacja (nowsze zastępują starsze)",
            SyncDirection.COPY_A_TO_B: "Kopiuj wybrane z Katalogu A do B",
            SyncDirection.COPY_B_TO_A: "Kopiuj wybrane z Katalogu B do A",
            SyncDirection.MIRROR_A_TO_B: "Kopia lustrzana A -> B (usuwaj z B pliki nieistniejące w A)",
        }
        return names.get(self, self.value)


@dataclass
class SyncAction:
    item: ComparisonItem
    source_path: Path
    dest_path: Path
    will_overwrite: bool
    is_delete: bool = False


@dataclass
class SyncReport:
    start_time: datetime
    end_time: Optional[datetime] = None
    files_processed: int = 0
    files_updated: int = 0
    files_deleted: int = 0
    files_backed_up: int = 0
    bytes_transferred: int = 0
    backup_dirs: list[Path] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    success: bool = True
    is_dry_run: bool = False
    cancelled: bool = False
    dry_run_actions: list[str] = field(default_factory=list)  # opisy symulowanych operacji
    cleaned_backups: int = 0
    pre_hook_output: str = ""
    post_hook_output: str = ""

    def summary(self) -> str:
        duration = ""
        if self.end_time:
            secs = (self.end_time - self.start_time).total_seconds()
            duration = f" w {secs:.1f} s"

        if self.cancelled:
            return f"🛑 OPERACJA ANULOWANA PRZEZ UŻYTKOWNIKA{duration}\nPrzetworzono bezpiecznie: {self.files_processed} operacji przed zatrzymaniem."

        if self.is_dry_run:
            return (
                f"⚠️ TRYB SYMULACJI (Dry-Run) — żadne pliki NIE zostały zmodyfikowane!{duration}\n"
                f"Planowane operacje: {len(self.dry_run_actions)}\n"
                + "\n".join(f"  • {a}" for a in self.dry_run_actions[:30])
                + (f"\n  ... i {len(self.dry_run_actions) - 30} więcej" if len(self.dry_run_actions) > 30 else "")
            )

        status_txt = "Zakończono sukcesem" if self.success and not self.errors else "Zakończono z ostrzeżeniami/błędami"
        backup_info = f"\nKopie zapasowe (.backup): {len(self.backup_dirs)} lokalizacji" if self.backup_dirs else ""
        cleaned_info = f"\n- Zretencjonowano (usunięto) starych kopii: {self.cleaned_backups}" if self.cleaned_backups else ""
        del_info = f"\n- Bezpiecznie usunięto z B: {self.files_deleted}" if self.files_deleted else ""
        return (
            f"Raport synchronizacji: {status_txt}{duration}\n"
            f"- Zaktualizowano plików: {self.files_updated}{del_info}\n"
            f"- Wykonano kopii zapasowych: {self.files_backed_up}{cleaned_info}\n"
            f"- Przesłano danych: {self.bytes_transferred / (1024 * 1024):.2f} MB\n"
            f"- Błędów: {len(self.errors)}{backup_info}"
        )


def safe_restore_file(src_backup: Path, dst_target: Path, verify_sha256: bool = True) -> tuple[bool, str]:
    """Bezpieczne, atomowe przywracanie pliku z kopii zapasowej z weryfikacją SHA-256 (CERT Level).
    
    Zwraca (sukces: bool, komunikat_błędu: str).
    """
    try:
        if not src_backup.is_file():
            return False, f"Plik źródłowy kopii zapasowej nie istnieje: {src_backup}"

        dst_target.parent.mkdir(parents=True, exist_ok=True)
        tmp_dst = dst_target.with_name(f".tmp_rollback_{dst_target.name}")

        shutil.copy2(src_backup, tmp_dst)

        if verify_sha256:
            src_hash = calculate_sha256(src_backup)
            tmp_hash = calculate_sha256(tmp_dst)
            if src_hash != tmp_hash:
                if tmp_dst.exists():
                    tmp_dst.unlink()
                return False, f"Niezgodność sumy SHA-256 pliku kopii: {src_backup.name}"

        if tmp_dst.exists():
            os.replace(tmp_dst, dst_target)

        return True, ""
    except Exception as e:
        return False, str(e)


def cleanup_old_backups(dest_root: Path, max_keep: int = 10) -> int:
    """Automatyczna polityka retencji: usuwa najstarsze katalogi backup_* zwalniając miejsce."""
    if max_keep <= 0:
        return 0
    backup_base = dest_root / ".backup"
    if not backup_base.is_dir():
        return 0
    try:
        session_dirs = [
            d for d in backup_base.iterdir()
            if d.is_dir() and (d.name.startswith("backup_") or d.name.startswith("20"))
        ]
        if len(session_dirs) <= max_keep:
            return 0
        session_dirs.sort(key=lambda d: d.name)
        to_delete = session_dirs[: len(session_dirs) - max_keep]
        deleted_count = 0
        for d in to_delete:
            shutil.rmtree(d, ignore_errors=True)
            deleted_count += 1
        return deleted_count
    except Exception:
        return 0


def check_disk_space(
    actions: list[SyncAction],
    safety_margin_bytes: int = 50 * 1024 * 1024,
) -> tuple[bool, str]:
    """Weryfikacja Pre-Flight wolnego miejsca na dysku docelowym (Standard NASA)."""
    needed_per_target: dict[str, int] = {}
    for act in actions:
        if act.is_delete:
            continue
        try:
            target_parent = act.dest_path.parent
            anchor = act.dest_path.drive or act.dest_path.anchor or str(target_parent)
            size = act.item.size_a or 0
            if act.will_overwrite:
                size += (act.item.size_b or 0)
            needed_per_target[anchor] = needed_per_target.get(anchor, 0) + size
        except Exception:
            continue

    for anchor, needed in needed_per_target.items():
        try:
            usage = shutil.disk_usage(anchor)
            if usage.free < (needed + safety_margin_bytes):
                free_mb = usage.free / (1024 * 1024)
                needed_mb = (needed + safety_margin_bytes) / (1024 * 1024)
                return False, f"Brak miejsca na dysku {anchor}: Dostępne {free_mb:.1f} MB, wymagane {needed_mb:.1f} MB."
        except Exception:
            pass
    return True, ""


def run_hook_command(command: str, timeout_sec: int = 30) -> tuple[bool, str]:
    """Bezpieczne wykonanie polecenia Pre/Post Sync Hook z limitem czasu (Standard CERT)."""
    if not command or not command.strip():
        return True, ""
    try:
        import subprocess
        res = subprocess.run(
            command.strip(),
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        out = (res.stdout or "") + ("\n" + res.stderr if res.stderr else "")
        return res.returncode == 0, out.strip()
    except subprocess.TimeoutExpired:
        return False, f"Przekroczono limit czasu ({timeout_sec}s) dla polecenia."
    except Exception as e:
        return False, str(e)


def safe_atomic_copy_file(
    src: Path,
    dst: Path,
    verify_sha256: bool = True,
    max_retries: int = 3,
    retry_delay_sec: float = 0.5,
) -> int:
    """Atomowe kopiowanie pliku z weryfikacją SHA-256 oraz odpornością na przejściowe błędy sieci (NASA / CERT)."""
    import time
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp_dst = dst.with_name(f".tmp_sync_{dst.name}")

    last_error: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            if tmp_dst.exists():
                tmp_dst.unlink(missing_ok=True)

            shutil.copy2(src, tmp_dst)

            if verify_sha256:
                src_hash = calculate_sha256(src)
                tmp_hash = calculate_sha256(tmp_dst)
                if src_hash != tmp_hash:
                    if tmp_dst.exists():
                        tmp_dst.unlink(missing_ok=True)
                    raise IOError(f"Błąd integralności pliku (SHA-256 mismatch): {src.name}")

            os.replace(tmp_dst, dst)
            return dst.stat().st_size
        except (OSError, IOError) as err:
            last_error = err
            if tmp_dst.exists():
                try:
                    tmp_dst.unlink(missing_ok=True)
                except Exception:
                    pass
            if attempt < max_retries:
                time.sleep(retry_delay_sec * attempt)
            else:
                raise last_error

    return 0


def recommend_sync_direction(items: list[ComparisonItem]) -> tuple[SyncDirection, str]:
    """Inteligentna rekomendacja kierunku synchronizacji na podstawie analizy różnic w plikach."""
    active_items = [i for i in items if i.status != FileStatus.IDENTICAL and i.status != FileStatus.ERROR]
    if not active_items:
        return SyncDirection.UPDATE_OLDER, "Katalogi są identyczne — brak wymaganych operacji."

    newer_a = sum(1 for i in active_items if i.status == FileStatus.NEWER_A)
    newer_b = sum(1 for i in active_items if i.status == FileStatus.NEWER_B)
    only_a = sum(1 for i in active_items if i.status == FileStatus.ONLY_A)
    only_b = sum(1 for i in active_items if i.status == FileStatus.ONLY_B)

    changes_a = newer_a + only_a
    changes_b = newer_b + only_b

    if changes_a > 0 and changes_b == 0:
        return (
            SyncDirection.COPY_A_TO_B,
            f"Wszystkie zmodyfikowane i nowe pliki ({changes_a}) znajdują się w Katalogu A.",
        )
    elif changes_b > 0 and changes_a == 0:
        return (
            SyncDirection.COPY_B_TO_A,
            f"Wszystkie zmodyfikowane i nowe pliki ({changes_b}) znajdują się w Katalogu B.",
        )
    else:
        return (
            SyncDirection.UPDATE_OLDER,
            f"Wykryto zmiany w obu katalogach (A: {changes_a}, B: {changes_b}). Zalecana inteligentna aktualizacja.",
        )



def plan_sync_actions(
    items: list[ComparisonItem],
    dir_a: Path,
    dir_b: Path,
    direction: SyncDirection,
) -> list[SyncAction]:
    """Przygotowuje bezpieczny plan operacji, analizując które pliki zostaną skopiowane, nadpisane lub usunięte."""
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

        elif direction == SyncDirection.MIRROR_A_TO_B:
            # Tryb lustrzany: A jest wzorcem, B ma wyglądać dokładnie jak A
            if item.status in (FileStatus.NEWER_A, FileStatus.ONLY_A, FileStatus.NEWER_B, FileStatus.DIFFERENT_CONTENT):
                if path_in_a.exists():
                    actions.append(SyncAction(item, path_in_a, path_in_b, will_overwrite=path_in_b.exists()))
            elif item.status == FileStatus.ONLY_B:
                # Plik istnieje tylko w B - w lustrze A->B należy go usunąć z B (z kopią zapasową w .backup)
                if path_in_b.exists():
                    actions.append(SyncAction(item, path_in_b, path_in_b, will_overwrite=False, is_delete=True))

    return actions


def execute_sync(
    actions: list[SyncAction],
    create_backup: bool = True,
    verify_sha256: bool = True,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    dry_run: bool = False,
    cancel_token: Optional[Callable[[], bool]] = None,
    pre_sync_cmd: str = "",
    post_sync_cmd: str = "",
    auto_cleanup_backups: bool = True,
    backup_retention_count: int = 10,
) -> SyncReport:
    """Wykonuje plan synchronizacji z atomowością operacji i weryfikacją sumy kontrolnej.

    :param actions: Lista zaplanowanych akcji synchronizacji
    :param create_backup: Czy tworzyć kopię zapasową w podkatalogu .backup
    :param verify_sha256: Czy weryfikować sumę SHA-256 po zapisie
    :param progress_callback: Funkcja postępu (indeks, łącznie, nazwa_pliku)
    :param dry_run: Jeśli True, symuluje operacje BEZ modyfikowania dysku
    :param cancel_token: Funkcja zwracająca True jeśli przerwano operację
    :param pre_sync_cmd: Opcjonalne polecenie wykonywane przed synchronizacją
    :param post_sync_cmd: Opcjonalne polecenie wykonywane po udanej synchronizacji
    :param auto_cleanup_backups: Czy automatycznie retencjonować stare kopie
    :param backup_retention_count: Maksymalna liczba zachowanych sesji kopii
    """
    report = SyncReport(start_time=datetime.now(), is_dry_run=dry_run)
    total_actions = len(actions)
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Weryfikacja wolnego miejsca (Pre-Flight Disk Space Check - Standard NASA)
    if not dry_run and actions:
        space_ok, space_err = check_disk_space(actions)
        if not space_ok:
            report.success = False
            report.errors.append(f"Odrzucono ze względów bezpieczeństwa: {space_err}")
            report.end_time = datetime.now()
            return report

    # Wykonanie polecenia Pre-Sync Hook
    if not dry_run and pre_sync_cmd:
        pre_ok, pre_out = run_hook_command(pre_sync_cmd)
        report.pre_hook_output = pre_out
        if not pre_ok:
            report.success = False
            report.errors.append(f"Błąd Pre-Sync Hook: {pre_out}")
            report.end_time = datetime.now()
            return report

    # Tryb symulacji (Dry-Run)
    if dry_run:
        for idx, act in enumerate(actions, start=1):
            if cancel_token and cancel_token():
                report.cancelled = True
                break
            if progress_callback:
                progress_callback(idx, total_actions, act.item.rel_path)

            if act.is_delete:
                action_verb = "USUWANIE (Lustro)"
            elif act.will_overwrite:
                action_verb = "NADPISANIE"
            else:
                action_verb = "KOPIOWANIE"

            report.dry_run_actions.append(
                f"[{action_verb}] {act.source_path.name} → {act.dest_path}"
            )
        report.end_time = datetime.now()
        return report

    for idx, act in enumerate(actions, start=1):
        if cancel_token and cancel_token():
            report.cancelled = True
            break

        if progress_callback:
            progress_callback(idx, total_actions, act.item.rel_path)

        report.files_processed += 1
        src = act.source_path
        dst = act.dest_path

        try:
            # Obsługa operacji usuwania (np. w trybie Mirror)
            if act.is_delete:
                if dst.exists():
                    if create_backup:
                        dest_root = dst
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

                    dst.unlink()
                    report.files_deleted += 1
                continue

            if not src.exists():
                report.errors.append(f"Plik źródłowy nie istnieje: {src}")
                continue

            # 1. Tworzenie kopii zapasowej (Backup) przed nadpisaniem
            if act.will_overwrite and dst.exists() and create_backup:
                dest_root = dst
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

            # 2. Bezpieczne kopiowanie atomowe z weryfikacją SHA-256 i odpornością sieciową
            copied_bytes = safe_atomic_copy_file(src, dst, verify_sha256=verify_sha256)
            report.bytes_transferred += copied_bytes
            report.files_updated += 1

        except Exception as e:
            report.success = False
            report.errors.append(f"Błąd przy {act.item.rel_path}: {e}")

    # Automatyczna retencja i czyszczenie starych sesji .backup
    if not dry_run and create_backup and auto_cleanup_backups and report.backup_dirs:
        unique_bases = set()
        for b_dir in report.backup_dirs:
            unique_bases.add(b_dir.parent.parent)
        for base in unique_bases:
            report.cleaned_backups += cleanup_old_backups(base, max_keep=backup_retention_count)

    # Wykonanie polecenia Post-Sync Hook
    if not dry_run and post_sync_cmd and report.success and not report.cancelled:
        post_ok, post_out = run_hook_command(post_sync_cmd)
        report.post_hook_output = post_out
        if not post_ok:
            report.errors.append(f"Ostrzeżenie Post-Sync Hook: {post_out}")

    report.end_time = datetime.now()
    return report
