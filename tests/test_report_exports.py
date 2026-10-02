"""Testy eksportu raportów do formatów HTML, CSV, JSON i TXT."""

import json
from pathlib import Path
import tempfile
import unittest
from datetime import datetime

from core.comparator import ComparisonItem, FileStatus
from gui.report_exporter import export_html, export_csv, export_json, export_txt


class TestReportExports(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.out_dir = Path(self.temp_dir)
        self.sample_items = [
            ComparisonItem(
                rel_path="plik1.txt",
                status=FileStatus.NEWER_A,
                size_a=1024,
                size_b=512,
                mtime_a=datetime(2026, 1, 1, 12, 0, 0),
                mtime_b=datetime(2025, 12, 31, 12, 0, 0),
                sha256_a="abc1",
                sha256_b="abc2",
            ),
            ComparisonItem(
                rel_path="identyczny.pdf",
                status=FileStatus.IDENTICAL,
                size_a=2048,
                size_b=2048,
                mtime_a=datetime(2026, 1, 1, 10, 0, 0),
                mtime_b=datetime(2026, 1, 1, 10, 0, 0),
                sha256_a="same",
                sha256_b="same",
            ),
        ]

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_export_html(self):
        out = self.out_dir / "report.html"
        ok = export_html(self.sample_items, "C:\\A", "C:\\B", out, "TestProfil")
        self.assertTrue(ok)
        self.assertTrue(out.is_file())
        content = out.read_text(encoding="utf-8")
        self.assertIn("plik1.txt", content)
        self.assertIn("identyczny.pdf", content)

    def test_export_csv(self):
        out = self.out_dir / "report.csv"
        ok = export_csv(self.sample_items, "C:\\A", "C:\\B", out)
        self.assertTrue(ok)
        self.assertTrue(out.is_file())
        content = out.read_text(encoding="utf-8-sig")
        self.assertIn("plik1.txt", content)

    def test_export_json(self):
        out = self.out_dir / "report.json"
        ok = export_json(self.sample_items, "C:\\A", "C:\\B", out, "TestProfil")
        self.assertTrue(ok)
        self.assertTrue(out.is_file())
        with open(out, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["profile"], "TestProfil")
        self.assertEqual(data["summary"]["total_files"], 2)
        self.assertEqual(data["summary"]["newer_a"], 1)
        self.assertEqual(data["summary"]["identical_files"], 1)
        self.assertEqual(len(data["items"]), 2)
        self.assertEqual(data["items"][0]["rel_path"], "plik1.txt")

    def test_export_txt(self):
        out = self.out_dir / "report.txt"
        ok = export_txt(self.sample_items, "C:\\A", "C:\\B", out, "TestProfil")
        self.assertTrue(ok)
        self.assertTrue(out.is_file())
        content = out.read_text(encoding="utf-8")
        self.assertIn("RAPORT PORÓWNANIA KATALOGÓW", content)
        self.assertIn("plik1.txt", content)
        self.assertIn("TestProfil", content)


if __name__ == "__main__":
    unittest.main()
