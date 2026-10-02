"""Testy modułu zarządzania szablonami (Profiles Test Suite)."""

import os
from pathlib import Path
import tempfile
import unittest

from core.profiles import SyncProfile, delete_profile, load_profiles, save_profile
import core.profiles


class TestProfiles(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.orig_get_config_dir = core.profiles.get_config_dir
        core.profiles.get_config_dir = lambda: Path(self.temp_dir)

    def tearDown(self):
        core.profiles.get_config_dir = self.orig_get_config_dir
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_load_delete_profile(self):
        self.assertEqual(len(load_profiles()), 0)

        p1 = SyncProfile(
            name="Backup Danych",
            dir_a="C:\\Projekty",
            dir_b="D:\\Backup_Projekty",
            compare_hashes=True,
            create_backup=True,
            sync_mode="UPDATE_OLDER"
        )
        self.assertTrue(save_profile(p1))

        profiles = load_profiles()
        self.assertEqual(len(profiles), 1)
        self.assertIn("Backup Danych", profiles)
        self.assertEqual(profiles["Backup Danych"].dir_a, "C:\\Projekty")
        self.assertTrue(profiles["Backup Danych"].compare_hashes)

        # Usunięcie profilu
        self.assertTrue(delete_profile("Backup Danych"))
        self.assertEqual(len(load_profiles()), 0)

    def test_profile_extended_fields(self):
        p = SyncProfile(
            name="Profil Zaawansowany",
            dir_a="C:\\Dane",
            dir_b="D:\\Dane",
            compare_hashes=False,
            create_backup=True,
            sync_mode="COPY_A_TO_B",
            exclude_patterns=["*.tmp", "cache/*"],
            description="Kopia robocza"
        )
        self.assertTrue(save_profile(p))

        loaded = load_profiles()
        self.assertIn("Profil Zaawansowany", loaded)
        item = loaded["Profil Zaawansowany"]
        self.assertEqual(item.exclude_patterns, ["*.tmp", "cache/*"])
        self.assertEqual(item.description, "Kopia robocza")


if __name__ == "__main__":
    unittest.main()
