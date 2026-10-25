"""Convert the approved PNG into a Windows ICO with multiple resolutions."""
import struct
from pathlib import Path

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage


root = Path(__file__).resolve().parent.parent
source = QImage(str(root / "assets" / "app-icon.png"))
if source.isNull():
    raise RuntimeError("Не удалось прочитать PNG иконки.")
images = []
for size in (16, 24, 32, 48, 64, 128, 256):
    image = source.scaled(size, size, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise RuntimeError("Не удалось преобразовать иконку.")
    images.append((size, bytes(data)))

offset = 6 + 16 * len(images)
entries = []
for size, data in images:
    entries.append(struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset))
    offset += len(data)
target = root / "assets" / "app-icon.ico"
target.write_bytes(struct.pack("<HHH", 0, 1, len(images)) + b"".join(entries) + b"".join(data for _, data in images))
print(f"Иконка сохранена: {target}")
