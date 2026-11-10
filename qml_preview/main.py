"""Qt Quick frontend backed by the existing DBD Randomizer engine."""
from pathlib import Path
import sys

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from native_backend import QtBridge


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("DBD Randomizer Qt Beta 2")
    backend = QtBridge()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", backend)
    qml_path = (Path(sys._MEIPASS) / "qml_preview" / "Main.qml") if getattr(sys, "frozen", False) else HERE / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml_path)))
    if not engine.rootObjects():
        backend.close()
        print("ERROR: cannot load Main.qml", file=sys.stderr)
        return 1
    if "--smoke" in sys.argv:
        QTimer.singleShot(2800, app.quit)
    app.aboutToQuit.connect(backend.close)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
