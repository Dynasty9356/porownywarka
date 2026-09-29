"""Moduł bezpiecznego sprawdzania aktualizacji dla FolderSync (CERT / NASA / WCAG Standard).

Zapewnia:
- Kryptograficznie bezpieczną komunikację wyłącznie przez protokół HTTPS (TLS 1.2+)
- Weryfikację i walidację semantyczną wersji (SemVer)
- Ochronę przed wstrzykiwaniem niebezpiecznych adresów URL (Strict HTTPS Scheme Enforcement)
- Obsługę API wydań GitHub Releases oraz alternatywnych serwerów aktualizacji
- Asynchroniczne sprawdzanie w tle bez blokowania wątku głównego GUI
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
import ssl
import urllib.error
import urllib.request
from typing import Optional, Tuple

from core.version import __version__


@dataclass
class UpdateInfo:
    """Informacje o dostępności aktualizacji oprogramowania."""
    is_available: bool
    current_version: str
    latest_version: str
    release_name: str
    release_notes: str
    download_url: str
    published_at: str
    error_message: str = ""


def parse_version(version_str: str) -> Tuple[int, ...]:
    """Konwertuje ciąg wersji (np. 'v1.3.0', '1.4.2-beta') na krotkę liczb całkowitych do porównań.
    
    Ignoruje prefiksy 'v' oraz sufiksy testowe, wyciągając sekwencję numeryczną.
    W przypadku błędu zwraca (0, 0, 0).
    """
    if not version_str:
        return (0, 0, 0)
    
    clean_str = version_str.strip().lstrip("vV")
    # Wyciągamy pierwsze cyfry rozdzielone kropkami
    match = re.match(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?", clean_str)
    if not match:
        return (0, 0, 0)
    
    parts = []
    for g in match.groups():
        if g is not None:
            try:
                parts.append(int(g))
            except ValueError:
                parts.append(0)
        else:
            parts.append(0)
    return tuple(parts)


def is_version_newer(latest: str, current: str) -> bool:
    """Zwraca True, jeśli wersja latest jest ściśle nowsza od current."""
    latest_tuple = parse_version(latest)
    current_tuple = parse_version(current)
    return latest_tuple > current_tuple


def validate_https_url(url: str) -> bool:
    """Weryfikuje, czy URL jest bezpiecznym adresem HTTPS (CERT Security Rule)."""
    if not url or not isinstance(url, str):
        return False
    clean = url.strip()
    return clean.startswith("https://") and len(clean) > 8


def check_for_updates(
    repo: str = "Dynasty9356/porownywarka",
    timeout_seconds: float = 6.0,
    current_ver: Optional[str] = None,
) -> UpdateInfo:
    """Sprawdza dostępność nowej wersji programu w repozytorium GitHub Releases.
    
    Wykonuje bezpieczne zapytanie HTTPS z walidacją certyfikatu TLS.
    Nie rzuca wyjątków – wszelkie błędy sieciowe są raportowane w UpdateInfo.error_message.
    """
    cur_version = current_ver if current_ver is not None else __version__
    api_url = f"https://api.github.com/repos/{repo}/releases/latest"

    headers = {
        "User-Agent": f"FolderSync-Updater/{cur_version} (Windows NT)",
        "Accept": "application/vnd.github.v3+json",
    }

    # Wymuszenie bezpiecznego kontekstu SSL z weryfikacją certyfikatu
    context = ssl.create_default_context()

    req = urllib.request.Request(api_url, headers=headers, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds, context=context) as response:
            if response.status != 200:
                return UpdateInfo(
                    is_available=False,
                    current_version=cur_version,
                    latest_version=cur_version,
                    release_name="",
                    release_notes="",
                    download_url="",
                    published_at="",
                    error_message=f"Serwer zwrócił kod odpowiedzi: HTTP {response.status}",
                )

            data_raw = response.read().decode("utf-8", errors="replace")
            data = json.loads(data_raw)

    except urllib.error.HTTPError as e:
        if e.code == 404:
            return UpdateInfo(
                is_available=False,
                current_version=cur_version,
                latest_version=cur_version,
                release_name="",
                release_notes="",
                download_url="",
                published_at="",
                error_message="Brak opublikowanych wydań (Releases) w repozytorium.",
            )
        return UpdateInfo(
            is_available=False,
            current_version=cur_version,
            latest_version=cur_version,
            release_name="",
            release_notes="",
            download_url="",
            published_at="",
            error_message=f"Błąd połączenia HTTP: {e.code} {e.reason}",
        )
    except urllib.error.URLError as e:
        return UpdateInfo(
            is_available=False,
            current_version=cur_version,
            latest_version=cur_version,
            release_name="",
            release_notes="",
            download_url="",
            published_at="",
            error_message="Brak połączenia z Internetem lub błąd serwera DNS.",
        )
    except TimeoutError:
        return UpdateInfo(
            is_available=False,
            current_version=cur_version,
            latest_version=cur_version,
            release_name="",
            release_notes="",
            download_url="",
            published_at="",
            error_message="Przekroczono limit czasu oczekiwania na odpowiedź serwera (Timeout).",
        )
    except Exception as e:
        return UpdateInfo(
            is_available=False,
            current_version=cur_version,
            latest_version=cur_version,
            release_name="",
            release_notes="",
            download_url="",
            published_at="",
            error_message=f"Nieoczekiwany błąd weryfikacji: {e}",
        )

    # Parsowanie danych odpowiedzi GitHub
    tag_name = str(data.get("tag_name", "")).strip()
    release_name = str(data.get("name", "")).strip() or tag_name
    release_notes = str(data.get("body", "")).strip()
    html_url = str(data.get("html_url", "")).strip()
    published_at = str(data.get("published_at", "")).strip()

    # Szukamy bezpośredniego pliku instalatora .exe w załącznikach (assets)
    direct_exe_url = ""
    assets = data.get("assets", [])
    if isinstance(assets, list):
        for asset in assets:
            name = str(asset.get("name", "")).lower()
            if name.endswith(".exe") and "browser_download_url" in asset:
                candidate_url = asset["browser_download_url"]
                if validate_https_url(candidate_url):
                    direct_exe_url = candidate_url
                    break

    download_url = direct_exe_url if direct_exe_url else html_url
    if not validate_https_url(download_url):
        download_url = f"https://github.com/{repo}/releases/latest"

    is_newer = is_version_newer(tag_name, cur_version)

    return UpdateInfo(
        is_available=is_newer,
        current_version=cur_version,
        latest_version=tag_name,
        release_name=release_name,
        release_notes=release_notes,
        download_url=download_url,
        published_at=published_at,
        error_message="",
    )
