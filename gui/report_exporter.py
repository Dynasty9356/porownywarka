"""Eksporter raportów do HTML i CSV — bez zewnętrznych zależności."""

from __future__ import annotations
from datetime import datetime
from pathlib import Path
import csv

from core.comparator import ComparisonItem, FileStatus
from core.version import APP_NAME, __version__


def export_html(
    items: list[ComparisonItem],
    dir_a: str,
    dir_b: str,
    output_path: Path,
    profile_name: str = "",
) -> bool:
    """Generuje bogaty raport HTML z tabelą wyników porównania."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = len(items)
    diff = sum(1 for i in items if i.status.is_different)

    status_colors = {
        FileStatus.NEWER_A: ("#1B5E20", "#C8E6C9"),
        FileStatus.NEWER_B: ("#0D47A1", "#BBDEFB"),
        FileStatus.ONLY_A: ("#4A148C", "#E1BEE7"),
        FileStatus.ONLY_B: ("#BF360C", "#FFE0B2"),
        FileStatus.DIFFERENT_CONTENT: ("#E65100", "#FFFFFF"),
        FileStatus.ERROR: ("#B71C1C", "#FFCDD2"),
        FileStatus.IDENTICAL: ("#263238", "#B0BEC5"),
    }

    rows_html = ""
    for item in items:
        bg, fg = status_colors.get(item.status, ("#263238", "#B0BEC5"))
        size_a = _fmt_size(item.size_a)
        size_b = _fmt_size(item.size_b)
        mtime_a = item.mtime_a.strftime("%Y-%m-%d %H:%M:%S") if item.mtime_a else "—"
        mtime_b = item.mtime_b.strftime("%Y-%m-%d %H:%M:%S") if item.mtime_b else "—"
        rows_html += (
            f'<tr>'
            f'<td style="background:{bg};color:{fg};font-weight:bold;padding:6px 10px;border-radius:4px;">'
            f'{item.status.display_name}</td>'
            f'<td style="padding:6px 10px;">{item.rel_path}</td>'
            f'<td style="padding:6px 10px;text-align:center;">{size_a} / {size_b}</td>'
            f'<td style="padding:6px 10px;text-align:center;">{mtime_a}</td>'
            f'<td style="padding:6px 10px;text-align:center;">{mtime_b}</td>'
            f'</tr>\n'
        )

    profile_row = f"<tr><th>Szablon:</th><td colspan='4'>{profile_name or '—'}</td></tr>" if profile_name else ""

    html = f"""<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Raport FolderSync — {now}</title>
<style>
  body {{ font-family: 'Segoe UI', sans-serif; background: #1A1A1A; color: #F3F3F3; margin: 0; padding: 24px; }}
  h1 {{ color: #60CDFF; font-size: 22px; margin-bottom: 4px; }}
  .meta-table {{ border-collapse: collapse; margin-bottom: 20px; width: 100%; max-width: 700px; }}
  .meta-table th {{ text-align: left; color: #AAAAAA; padding: 4px 12px 4px 0; font-weight: 600; width: 160px; }}
  .meta-table td {{ color: #FFFFFF; padding: 4px 0; }}
  .stats {{ display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }}
  .stat-card {{ background: #252525; border: 1px solid #3A3A3A; border-radius: 8px; padding: 14px 20px; min-width: 130px; }}
  .stat-card .val {{ font-size: 28px; font-weight: 700; color: #60CDFF; }}
  .stat-card .lbl {{ font-size: 12px; color: #AAAAAA; margin-top: 2px; }}
  table.results {{ width: 100%; border-collapse: collapse; }}
  table.results th {{ background: #252525; color: #CCCCCC; padding: 10px; text-align: left; border-bottom: 1px solid #3A3A3A; font-weight: 600; }}
  table.results tr:nth-child(even) {{ background: #1E1E1E; }}
  table.results td {{ vertical-align: middle; }}
  .footer {{ margin-top: 24px; color: #666; font-size: 11px; }}
</style>
</head>
<body>
<h1>📋 Raport Porównania Katalogów — FolderSync</h1>
<table class="meta-table">
  {profile_row}
  <tr><th>Katalog A:</th><td>{dir_a}</td></tr>
  <tr><th>Katalog B:</th><td>{dir_b}</td></tr>
  <tr><th>Data raportu:</th><td>{now}</td></tr>
</table>

<div class="stats">
  <div class="stat-card"><div class="val">{total}</div><div class="lbl">Łącznie plików</div></div>
  <div class="stat-card"><div class="val" style="color:#FF5555;">{diff}</div><div class="lbl">Różniących się</div></div>
  <div class="stat-card"><div class="val" style="color:#4CAF50;">{total - diff}</div><div class="lbl">Identycznych</div></div>
  <div class="stat-card"><div class="val" style="color:#C8E6C9;">{sum(1 for i in items if i.status == FileStatus.NEWER_A)}</div><div class="lbl">Nowsze w A</div></div>
  <div class="stat-card"><div class="val" style="color:#BBDEFB;">{sum(1 for i in items if i.status == FileStatus.NEWER_B)}</div><div class="lbl">Nowsze w B</div></div>
  <div class="stat-card"><div class="val" style="color:#E1BEE7;">{sum(1 for i in items if i.status == FileStatus.ONLY_A)}</div><div class="lbl">Tylko w A</div></div>
  <div class="stat-card"><div class="val" style="color:#FFE0B2;">{sum(1 for i in items if i.status == FileStatus.ONLY_B)}</div><div class="lbl">Tylko w B</div></div>
</div>

<table class="results">
  <thead>
    <tr>
      <th>Status</th>
      <th>Względna ścieżka pliku</th>
      <th style="text-align:center;">Rozmiar A / B</th>
      <th style="text-align:center;">Data modyfikacji A</th>
      <th style="text-align:center;">Data modyfikacji B</th>
    </tr>
  </thead>
  <tbody>
    {rows_html}
  </tbody>
</table>

<div class="footer">
  Wygenerowano przez {APP_NAME} v{__version__} | {now} | Suma SHA-256 weryfikuje integralność danych.
</div>
</body>
</html>"""

    try:
        output_path.write_text(html, encoding="utf-8")
        return True
    except OSError:
        return False


def export_csv(
    items: list[ComparisonItem],
    dir_a: str,
    dir_b: str,
    output_path: Path,
) -> bool:
    """Generuje raport CSV gotowy do analizy w Excelu/LibreOffice."""
    try:
        with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["Status", "Ścieżka względna", "Rozmiar A [B]", "Rozmiar B [B]",
                              "Data modyfikacji A", "Data modyfikacji B",
                              "SHA-256 A", "SHA-256 B", "Błąd"])
            for item in items:
                writer.writerow([
                    item.status.value,
                    item.rel_path,
                    item.size_a if item.size_a is not None else "",
                    item.size_b if item.size_b is not None else "",
                    item.mtime_a.isoformat() if item.mtime_a else "",
                    item.mtime_b.isoformat() if item.mtime_b else "",
                    item.sha256_a or "",
                    item.sha256_b or "",
                    item.error_msg or "",
                ])
        return True
    except OSError:
        return False


def _fmt_size(size_bytes):
    if size_bytes is None:
        return "—"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.2f} MB"
