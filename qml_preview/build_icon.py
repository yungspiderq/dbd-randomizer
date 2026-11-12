"""Build native Windows .ico and QML PNG icon from a source image.

If assets/app_icon_source.png is present, that is used unchanged (aside from
resizing for icon dimensions). Otherwise render our original vector app_icon.svg.
"""
from __future__ import annotations

from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"


def build():
    from PIL import Image
    src = ASSETS / "app_icon_source.png"
    if src.is_file():
        base = Image.open(src).convert("RGBA")
        side = min(base.size)
        left = (base.width - side) // 2
        top = (base.height - side) // 2
        base = base.crop((left, top, left + side, top + side))
        base = base.resize((512, 512), Image.Resampling.LANCZOS)
    else:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QImage, QPainter
        from PySide6.QtSvg import QSvgRenderer

        svg = ASSETS / "app_icon.svg"
        renderer = QSvgRenderer(str(svg))
        if not renderer.isValid():
            raise ValueError("App icon vector is invalid")
        image = QImage(512, 512, QImage.Format_ARGB32)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        png = ASSETS / "app_icon.png"
        if not image.save(str(png), "PNG"):
            raise RuntimeError("Failed to rasterize vector application icon")
        base = Image.open(png).convert("RGBA")

    ASSETS.mkdir(parents=True, exist_ok=True)
    png = ASSETS / "app_icon.png"
    ico = ASSETS / "app_icon.ico"
    base.resize((256, 256), Image.Resampling.LANCZOS).save(png)
    base.save(ico, format="ICO", sizes=[
        (16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
        (128, 128), (256, 256),
    ])
    return png, ico


if __name__ == "__main__":
    output = build()
    for p in output:
        print(p)
