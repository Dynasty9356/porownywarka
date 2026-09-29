"""Testy jednostkowe modułu bezpiecznych aktualizacji core.updater."""

import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from core.updater import (
    UpdateInfo,
    check_for_updates,
    is_version_newer,
    parse_version,
    validate_https_url,
)


class TestUpdater(unittest.TestCase):
    def test_parse_version(self):
        self.assertEqual(parse_version("1.3.0"), (1, 3, 0))
        self.assertEqual(parse_version("v1.3.0"), (1, 3, 0))
        self.assertEqual(parse_version("V2.0.1"), (2, 0, 1))
        self.assertEqual(parse_version("1.4"), (1, 4, 0))
        self.assertEqual(parse_version("2"), (2, 0, 0))
        self.assertEqual(parse_version("invalid"), (0, 0, 0))
        self.assertEqual(parse_version(""), (0, 0, 0))

    def test_is_version_newer(self):
        self.assertTrue(is_version_newer("1.4.0", "1.3.0"))
        self.assertTrue(is_version_newer("v1.3.1", "1.3.0"))
        self.assertTrue(is_version_newer("2.0.0", "1.9.9"))
        self.assertFalse(is_version_newer("1.3.0", "1.3.0"))
        self.assertFalse(is_version_newer("v1.2.9", "1.3.0"))
        self.assertFalse(is_version_newer("1.3.0", "1.4.0"))

    def test_validate_https_url(self):
        self.assertTrue(validate_https_url("https://github.com/Dynasty9356/porownywarka/releases"))
        self.assertFalse(validate_https_url("http://insecure.site.com/setup.exe"))
        self.assertFalse(validate_https_url("ftp://files.example.com"))
        self.assertFalse(validate_https_url("javascript:alert(1)"))
        self.assertFalse(validate_https_url(""))
        self.assertFalse(validate_https_url(None))

    @patch("urllib.request.urlopen")
    def test_check_for_updates_available(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b"""{
            "tag_name": "v1.4.0",
            "name": "FolderSync v1.4.0 - Nowa wersja",
            "body": "- Dodano sprawdzanie aktualizacji\\n- Usprawniono wydajnosc",
            "html_url": "https://github.com/Dynasty9356/porownywarka/releases/tag/v1.4.0",
            "published_at": "2026-09-30T10:00:00Z",
            "assets": [
                {
                    "name": "FolderSync_Setup_v1.4.0.exe",
                    "browser_download_url": "https://github.com/Dynasty9356/porownywarka/releases/download/v1.4.0/FolderSync_Setup_v1.4.0.exe"
                }
            ]
        }"""
        mock_urlopen.return_value.__enter__.return_value = mock_response

        info = check_for_updates(repo="Dynasty9356/porownywarka", current_ver="1.3.0")
        self.assertTrue(info.is_available)
        self.assertEqual(info.latest_version, "v1.4.0")
        self.assertEqual(info.current_version, "1.3.0")
        self.assertIn("Nowa wersja", info.release_name)
        self.assertIn("Dodano sprawdzanie", info.release_notes)
        self.assertEqual(info.download_url, "https://github.com/Dynasty9356/porownywarka/releases/download/v1.4.0/FolderSync_Setup_v1.4.0.exe")
        self.assertEqual(info.error_message, "")

    @patch("urllib.request.urlopen")
    def test_check_for_updates_already_latest(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b"""{
            "tag_name": "v1.3.0",
            "name": "FolderSync v1.3.0",
            "body": "Aktualna wersja",
            "html_url": "https://github.com/Dynasty9356/porownywarka/releases/tag/v1.3.0",
            "published_at": "2026-09-20T10:00:00Z",
            "assets": []
        }"""
        mock_urlopen.return_value.__enter__.return_value = mock_response

        info = check_for_updates(repo="Dynasty9356/porownywarka", current_ver="1.3.0")
        self.assertFalse(info.is_available)
        self.assertEqual(info.latest_version, "v1.3.0")
        self.assertEqual(info.error_message, "")

    @patch("urllib.request.urlopen")
    def test_check_for_updates_network_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Brak sieci")

        info = check_for_updates(repo="Dynasty9356/porownywarka", current_ver="1.3.0")
        self.assertFalse(info.is_available)
        self.assertIn("Internetem", info.error_message)


if __name__ == "__main__":
    unittest.main()
