#!/usr/bin/env python3
"""Generate the TypeFlow app icon (icon.png + icon.ico).

    QT_QPA_PLATFORM=offscreen python assets/generate_icon.py

The icon is drawn with Qt (rounded gradient tile + keyboard keys) and written as
a 512x512 PNG plus a multi-size .ico for the Windows build.  No binary assets
need to be committed by hand.
"""
from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QRectF, Qt          # noqa: E402
from PyQt6.QtGui import (                              # noqa: E402
    QBrush, QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen,
)
from PyQt6.QtWidgets import QApplication               # noqa: E402

OUT_DIR = Path(__file__).resolve().parent
SIZE = 512


def draw(size: int = SIZE):
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Rounded gradient tile.
    tile = QRectF(8, 8, size - 16, size - 16)
    path = QPainterPath()
    path.addRoundedRect(tile, size * 0.22, size * 0.22)
    gradient = QLinearGradient(tile.topLeft(), tile.bottomRight())
    gradient.setColorAt(0.0, QColor("#6ea8ff"))
    gradient.setColorAt(0.55, QColor("#4f7dff"))
    gradient.setColorAt(1.0, QColor("#8b5cf6"))
    painter.fillPath(path, QBrush(gradient))

    # Three keyboard keys, the middle one "pressed" (accent highlight).
    key_w, key_h = size * 0.17, size * 0.17
    gap = size * 0.045
    total = key_w * 3 + gap * 2
    x0 = (size - total) / 2
    y = size * 0.34
    for index in range(3):
        rect = QRectF(x0 + index * (key_w + gap), y, key_w, key_h)
        key_path = QPainterPath()
        radius = key_w * 0.22
        key_path.addRoundedRect(rect, radius, radius)
        if index == 1:
            painter.fillPath(key_path, QColor("#ffffff"))
        else:
            painter.setPen(QPen(QColor("#ffffff"), size * 0.022))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(key_path)
            painter.setPen(Qt.PenStyle.NoPen)

    # A typing caret under the keys.
    caret = QRectF(size * 0.42, y + key_h + size * 0.075, size * 0.16, size * 0.075)
    caret_path = QPainterPath()
    caret_path.addRoundedRect(caret, size * 0.035, size * 0.035)
    painter.fillPath(caret_path, QColor("#ffffff"))

    painter.end()
    return image


def png_bytes(image) -> bytes:
    from PyQt6.QtCore import QBuffer, QIODevice

    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def write_ico(image, path: Path) -> None:
    """Write a Windows .ico that embeds the PNG at several sizes."""
    sizes = [16, 32, 48, 64, 128, 256]
    blobs = []
    for size in sizes:
        scaled = image.scaled(size, size, Qt.AspectRatioMode.IgnoreAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
        blobs.append(png_bytes(scaled))

    header = struct.pack("<HHH", 0, 1, len(blobs))       # reserved, type=icon, count
    offset = 6 + 16 * len(blobs)
    entries = b""
    for size, blob in zip(sizes, blobs):
        entries += struct.pack("<BBBBHHII", size if size < 256 else 0,
                               size if size < 256 else 0, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
    path.write_bytes(header + entries + b"".join(blobs))


def main() -> None:
    QApplication(sys.argv[:1])              # needed before any QImage
    image = draw()
    image.save(str(OUT_DIR / "icon.png"), "PNG")
    write_ico(image, OUT_DIR / "icon.ico")
    print(f"wrote {OUT_DIR / 'icon.png'} ({SIZE}x{SIZE}) and icon.ico")


if __name__ == "__main__":
    main()
