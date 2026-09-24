"""Generowanie nowoczesnej ikony Windows 11 dla aplikacji FolderSync."""

import os
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QImage, QLinearGradient, QPainter, QPen


def generate_app_icon(output_path: Path):
    size = 256
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Gradientowe tło w stylu Windows 11 Fluent
    gradient = QLinearGradient(0, 0, size, size)
    gradient.setColorAt(0.0, QColor("#0078D4"))
    gradient.setColorAt(1.0, QColor("#104A7F"))

    painter.setBrush(QBrush(gradient))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(QRectF(16, 16, 224, 224), 48, 48)

    # Rysowanie stylizowanej ikony dwóch folderów i strzałek synchronizacji
    painter.setPen(QPen(QColor("#FFFFFF"), 8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.setBrush(Qt.BrushStyle.NoBrush)

    # Strzałka w prawo
    painter.drawLine(60, 105, 175, 105)
    painter.drawLine(150, 85, 175, 105)
    painter.drawLine(150, 125, 175, 105)

    # Strzałka w lewo
    painter.drawLine(196, 150, 81, 150)
    painter.drawLine(106, 130, 81, 150)
    painter.drawLine(106, 170, 81, 150)

    # Tarcza bezpieczeństwa (Security Shield)
    shield_path_pen = QPen(QColor("#00E676"), 6)
    painter.setPen(shield_path_pen)
    painter.drawArc(QRectF(108, 175, 40, 40), 0, 360 * 16)

    painter.end()

    # Zapis do PNG i ICO
    png_path = output_path.with_suffix(".png")
    image.save(str(png_path), "PNG")
    image.scaled(128, 128, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation).save(str(output_path), "ICO")
    print(f"Ikona wygenerowana: {output_path}")


if __name__ == "__main__":
    generate_app_icon(Path("app_icon.ico"))
