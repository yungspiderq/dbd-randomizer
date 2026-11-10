"""Launch the isolated Qt Quick UI preview.

This preview does not modify or invoke the legacy Tkinter automation.
"""
from pathlib import Path
import sys

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from preview_backend import PreviewBackend


def main() -> int:
    app = QGuiApplication(sys.argv)
    app.setApplicationName("DBD Randomizer | QML Preview")
    engine = QQmlApplicationEngine()
    backend = PreviewBackend()
    engine.rootContext().setContextProperty("backend", backend)
    qml_file = Path(__file__).with_name("Main.qml")
    engine.load(QUrl.fromLocalFile(str(qml_file)))
    if not engine.rootObjects():
        print("QML could not be loaded", file=sys.stderr)
        return 1
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
