"""Moduł wielojęzyczności (i18n) dla aplikacji FolderSync.
Obsługuje natywne przełączanie języka interfejsu (Polski / English) w locie.
"""

from __future__ import annotations

from typing import Any, Optional
from core.comparator import FileStatus
from core.settings import load_settings


TRANSLATIONS: dict[str, dict[str, str]] = {
    # Główne okno - paski i grupy
    "window_title": {
        "pl": "FolderSync - Porównywarka i Synchronizator Katalogów",
        "en": "FolderSync - Directory Comparator & Synchronizer",
    },
    "group_profiles": {
        "pl": "⭐ Szablony / Profile Szybkiego Dostępu",
        "en": "⭐ Quick Access Profiles & Templates",
    },
    "lbl_select_profile": {
        "pl": "Wybierz szablon:",
        "en": "Select profile:",
    },
    "btn_save_profile": {
        "pl": "💾 Zapisz jako szablon...",
        "en": "💾 Save as profile...",
    },
    "btn_save_profile_tip": {
        "pl": "Zapisz aktualnie wybrane foldery A i B jako nazwany profil",
        "en": "Save current folders A and B as a named profile",
    },
    "btn_delete_profile": {
        "pl": "🗑️ Usuń szablon",
        "en": "🗑️ Delete profile",
    },
    "btn_delete_profile_tip": {
        "pl": "Usuń obecnie wybrany szablon z listy",
        "en": "Delete selected profile from list",
    },
    "group_directories": {
        "pl": "Katalogi źródłowy i docelowy",
        "en": "Source and Target Directories",
    },
    "lbl_dir_a": {
        "pl": "Katalog A (Lewy):",
        "en": "Directory A (Left):",
    },
    "lbl_dir_b": {
        "pl": "Katalog B (Prawy):",
        "en": "Directory B (Right):",
    },
    "placeholder_dir_a": {
        "pl": "Wklej, wpisz lub przeciągnij tutaj folder A...",
        "en": "Paste, type or drag folder A here...",
    },
    "placeholder_dir_b": {
        "pl": "Wklej, wpisz lub przeciągnij tutaj folder B...",
        "en": "Paste, type or drag folder B here...",
    },
    "btn_browse": {
        "pl": "Przeglądaj...",
        "en": "Browse...",
    },
    "chk_hash": {
        "pl": "Głęboka weryfikacja sumą SHA-256 (dla 100% integralności)",
        "en": "Deep SHA-256 hash verification (for 100% integrity)",
    },
    "chk_hash_tip": {
        "pl": "Oblicza kryptograficzną sumę SHA-256 każdego pliku, eliminując błędy daty",
        "en": "Calculates SHA-256 hash for every file, eliminating timestamp skew errors",
    },
    "btn_compare": {
        "pl": "🔍 Porównaj zawartość katalogów",
        "en": "🔍 Compare Directories",
    },
    "btn_dry_run": {
        "pl": "⚠️ Test na sucho (Dry-Run)",
        "en": "⚠️ Dry-Run Simulation",
    },
    "btn_dry_run_tip": {
        "pl": "Symuluj synchronizację BEZ modyfikowania plików na dysku",
        "en": "Simulate synchronization WITHOUT modifying any files on disk",
    },
    "lbl_status_initial": {
        "pl": "Wybierz szablon lub dwa foldery i kliknij „Porównaj zawartość”. Kliknij nagłówek tabeli, aby sortować.",
        "en": "Select a profile or two folders and click 'Compare Directories'. Click column headers to sort.",
    },
    "lbl_filter": {
        "pl": "Filtruj widok:",
        "en": "Filter view:",
    },
    "filter_all": {
        "pl": "Wszystkie pliki",
        "en": "All files",
    },
    "filter_diff_only": {
        "pl": "Tylko różniące się (wymagające uwagi)",
        "en": "Only differences (requiring attention)",
    },
    "filter_newer_a": {
        "pl": "Nowszy w Katalogu A",
        "en": "Newer in Directory A",
    },
    "filter_newer_b": {
        "pl": "Nowszy w Katalogu B",
        "en": "Newer in Directory B",
    },
    "filter_only_a_b": {
        "pl": "Tylko w A lub tylko w B",
        "en": "Only in A or only in B",
    },
    "filter_identical": {
        "pl": "Identyczne",
        "en": "Identical",
    },
    "placeholder_search": {
        "pl": "Szukaj po nazwie / ścieżce...",
        "en": "Search by filename / path...",
    },
    "btn_select_all": {
        "pl": "Zaznacz widoczne",
        "en": "Select visible",
    },
    "btn_deselect_all": {
        "pl": "Odznacz wszystkie",
        "en": "Deselect all",
    },
    # Kolumny tabeli
    "col_select": {
        "pl": "Wybór",
        "en": "Select",
    },
    "col_status": {
        "pl": "Status",
        "en": "Status",
    },
    "col_rel_path": {
        "pl": "Względna ścieżka pliku",
        "en": "Relative file path",
    },
    "col_size": {
        "pl": "Rozmiar A / B",
        "en": "Size A / B",
    },
    "col_mtime_a": {
        "pl": "Data modyfikacji A",
        "en": "Modified date A",
    },
    "col_mtime_b": {
        "pl": "Data modyfikacji B",
        "en": "Modified date B",
    },
    # Panel synchronizacji
    "group_sync": {
        "pl": "Synchronizacja i Ochrona Danych",
        "en": "Synchronization & Data Protection",
    },
    "chk_backup": {
        "pl": "Twórz kopię zapasową (.backup) przed zastąpieniem pliku",
        "en": "Create backup (.backup) before replacing files",
    },
    "chk_backup_tip": {
        "pl": "Rekomendowane przez procedury bezpieczeństwa: zachowuje kopię pliku przed nadpisaniem",
        "en": "Recommended security procedure: saves previous version before overwriting",
    },
    "lbl_sync_mode": {
        "pl": "Tryb:",
        "en": "Mode:",
    },
    "sync_mode_update": {
        "pl": "Inteligentna aktualizacja (nowsze zastępują starsze)",
        "en": "Smart update (newer replaces older)",
    },
    "sync_mode_a_to_b": {
        "pl": "Kopiuj wybrane z Katalogu A do B",
        "en": "Copy selected from A to B",
    },
    "sync_mode_b_to_a": {
        "pl": "Kopiuj wybrane z Katalogu B do A",
        "en": "Copy selected from B to A",
    },
    "sync_mode_mirror": {
        "pl": "Kopia lustrzana A -> B (usuwaj z B pliki nieistniejące w A)",
        "en": "Mirror A -> B (delete files from B that do not exist in A)",
    },
    "btn_stop": {
        "pl": "⏹ Zatrzymaj operację",
        "en": "⏹ Stop operation",
    },
    "btn_about": {
        "pl": "ℹ️ O programie",
        "en": "ℹ️ About",
    },
    "about_title": {
        "pl": "O programie FolderSync",
        "en": "About FolderSync",
    },
    "msg_op_cancelled": {
        "pl": "Operacja została pomyślnie i bezpiecznie przerwana.",
        "en": "Operation was successfully and safely cancelled.",
    },
    "col_sha256": {
        "pl": "Suma SHA-256",
        "en": "SHA-256 Hash",
    },
    "card_total": {
        "pl": "Wszystkie",
        "en": "All",
    },
    "card_diff": {
        "pl": "Różniące się",
        "en": "Differences",
    },
    "card_newer_a": {
        "pl": "Nowsze w A",
        "en": "Newer in A",
    },
    "card_newer_b": {
        "pl": "Nowsze w B",
        "en": "Newer in B",
    },
    "card_only_a": {
        "pl": "Tylko w A",
        "en": "Only in A",
    },
    "card_only_b": {
        "pl": "Tylko w B",
        "en": "Only in B",
    },
    "card_identical": {
        "pl": "Identyczne",
        "en": "Identical",
    },
    "card_errors": {
        "pl": "Błędy",
        "en": "Errors",
    },
    "btn_sync": {
        "pl": "⚡ Zsynchronizuj zaznaczone pliki",
        "en": "⚡ Synchronize selected files",
    },
    # Dolny pasek
    "btn_history": {
        "pl": "📜 Historia porównań",
        "en": "📜 Comparison History",
    },
    "btn_history_tip": {
        "pl": "Przeglądaj historię porównań i synchronizacji",
        "en": "View comparison and synchronization history",
    },
    "btn_export_html": {
        "pl": "📄 Eksport HTML",
        "en": "📄 Export HTML",
    },
    "btn_export_html_tip": {
        "pl": "Eksportuj wyniki do pliku HTML",
        "en": "Export results to an HTML report",
    },
    "btn_export_csv": {
        "pl": "📊 Eksport CSV",
        "en": "📊 Export CSV",
    },
    "btn_export_csv_tip": {
        "pl": "Eksportuj wyniki do pliku CSV (Excel, LibreOffice)",
        "en": "Export results to a CSV file (Excel, Calc)",
    },
    "btn_backup_mgr": {
        "pl": "⏪ Kopie zapasowe",
        "en": "⏪ Backup Manager",
    },
    "btn_backup_mgr_tip": {
        "pl": "Zarządzaj katalogami .backup, wykonaj Rollback",
        "en": "Manage .backup directories, perform rollback",
    },
    "btn_settings": {
        "pl": "⚙️ Ustawienia",
        "en": "⚙️ Settings",
    },
    "btn_settings_tip": {
        "pl": "Otwórz ustawienia aplikacji (Ctrl+,)",
        "en": "Open application settings (Ctrl+,)",
    },
    # Menu kontekstowe
    "ctx_open_a": {
        "pl": "Otwórz plik w A",
        "en": "Open file in A",
    },
    "ctx_open_b": {
        "pl": "Otwórz plik w B",
        "en": "Open file in B",
    },
    "ctx_explore_a": {
        "pl": "Pokaż w Eksploratorze (folder A)",
        "en": "Show in Explorer (folder A)",
    },
    "ctx_explore_b": {
        "pl": "Pokaż w Eksploratorze (folder B)",
        "en": "Show in Explorer (folder B)",
    },
    "ctx_diff": {
        "pl": "Porównaj treść wizualnie (Diff)...",
        "en": "Compare text diff (Visual Diff)...",
    },
    # Okno Ustawień
    "settings_title": {
        "pl": "⚙️ Ustawienia FolderSync",
        "en": "⚙️ FolderSync Settings",
    },
    "settings_header": {
        "pl": "⚙️ Ustawienia Aplikacji FolderSync",
        "en": "⚙️ FolderSync Application Settings",
    },
    "tab_appearance": {
        "pl": "🎨 Wygląd",
        "en": "🎨 Appearance",
    },
    "tab_comparison": {
        "pl": "🔍 Porównywanie",
        "en": "🔍 Comparison",
    },
    "tab_sync": {
        "pl": "⚡ Synchronizacja",
        "en": "⚡ Synchronization",
    },
    "tab_exclusions": {
        "pl": "🚫 Wykluczenia",
        "en": "🚫 Exclusions",
    },
    "tab_history": {
        "pl": "📜 Historia i Raporty",
        "en": "📜 History & Reports",
    },
    "tab_tray": {
        "pl": "🔔 Zasobnik",
        "en": "🔔 Tray",
    },
    "grp_theme_lang": {
        "pl": "Motyw i Język",
        "en": "Theme & Language",
    },
    "lbl_theme": {
        "pl": "Motyw interfejsu:",
        "en": "Interface theme:",
    },
    "theme_dark": {
        "pl": "Ciemny (Dark)",
        "en": "Dark",
    },
    "theme_light": {
        "pl": "Jasny (Light)",
        "en": "Light",
    },
    "theme_auto": {
        "pl": "Automatyczny (zgodny z Windows)",
        "en": "Auto (match Windows)",
    },
    "lbl_lang": {
        "pl": "Język:",
        "en": "Language:",
    },
    "btn_save_settings": {
        "pl": "💾 Zapisz ustawienia",
        "en": "💾 Save settings",
    },
    "btn_cancel": {
        "pl": "Anuluj",
        "en": "Cancel",
    },
    # Statusy plików
    "status_identical": {
        "pl": "[=] Identyczne",
        "en": "[=] Identical",
    },
    "status_newer_a": {
        "pl": "[A > B] Nowszy w A",
        "en": "[A > B] Newer in A",
    },
    "status_newer_b": {
        "pl": "[B > A] Nowszy w B",
        "en": "[B > A] Newer in B",
    },
    "status_only_a": {
        "pl": "[+] Tylko w A",
        "en": "[+] Only in A",
    },
    "status_only_b": {
        "pl": "[+] Tylko w B",
        "en": "[+] Only in B",
    },
    "status_different": {
        "pl": "[!] Różna treść (Hash)",
        "en": "[!] Different content (Hash)",
    },
    "status_error": {
        "pl": "[X] Błąd dostępu",
        "en": "[X] Access error",
    },
    # Podsumowania
    "summary_compared": {
        "pl": "Porównano: {total} plików | Różniących się: {diff} | Nowszy w A: {newer_a} | Nowszy w B: {newer_b} | Tylko A: {only_a} | Tylko B: {only_b} | Identycznych: {identical}",
        "en": "Compared: {total} files | Different: {diff} | Newer in A: {newer_a} | Newer in B: {newer_b} | Only A: {only_a} | Only B: {only_b} | Identical: {identical}",
    },
}


def tr(key: str, lang: Optional[str] = None, **kwargs: Any) -> str:
    """Pobiera przetłumaczony tekst na podstawie klucza i kodu języka (domyślnie z ustawień)."""
    if lang is None:
        try:
            lang = load_settings().language
        except Exception:
            lang = "pl"

    lang = (lang or "pl").lower()
    entry = TRANSLATIONS.get(key)
    if not entry:
        return key

    text = entry.get(lang) or entry.get("pl") or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            pass
    return text


def get_status_display_name(status: FileStatus, lang: Optional[str] = None) -> str:
    """Zwraca zlokalizowaną nazwę statusu pliku."""
    mapping = {
        FileStatus.IDENTICAL: "status_identical",
        FileStatus.NEWER_A: "status_newer_a",
        FileStatus.NEWER_B: "status_newer_b",
        FileStatus.ONLY_A: "status_only_a",
        FileStatus.ONLY_B: "status_only_b",
        FileStatus.DIFFERENT_CONTENT: "status_different",
        FileStatus.ERROR: "status_error",
    }
    key = mapping.get(status)
    if key:
        return tr(key, lang)
    return status.value
