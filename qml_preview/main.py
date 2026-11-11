"""Qt Quick frontend backed by the existing DBD Randomizer engine."""
from pathlib import Path
import sys

from PySide6.QtCore import QObject, QTimer, QUrl
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from native_backend import QtBridge


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("DBD Randomizer Qt Beta 14")
    frozen = bool(getattr(sys, "frozen", False))
    packaged_root = Path(sys._MEIPASS) if frozen else HERE.parent
    icon = packaged_root / "qml_preview" / "assets" / "app_icon.png"
    if not frozen and not icon.is_file():
        from build_icon import build
        build()
    if icon.is_file():
        app.setWindowIcon(QIcon(str(icon)))
    backend = QtBridge()
    engine = QQmlApplicationEngine()
    engine.warnings.connect(lambda messages: [
        print("QML WARNING: " + str(message), file=sys.stderr) for message in messages
    ])
    engine.rootContext().setContextProperty("backend", backend)
    qml_path = (Path(sys._MEIPASS) / "qml_preview" / "Main.qml") if getattr(sys, "frozen", False) else HERE / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml_path)))
    if not engine.rootObjects():
        backend.close()
        print("ERROR: cannot load Main.qml", file=sys.stderr)
        return 1
    if icon.is_file():
        window = engine.rootObjects()[0]
        if hasattr(window, "setIcon"):
            window.setIcon(QIcon(str(icon)))
    appearance_check = {"ok": True}
    if "--smoke-catalogs" in sys.argv:
        window = engine.rootObjects()[0]

        def verify_catalogs():
            try:
                pages = [
                    ("Персонажи", "charactersCatalog"),
                    ("Внешность", "outfitCharactersCatalog"),
                    ("Внешность", "outfitsCatalog"),
                    ("Избранное", "favoritesCatalog"),
                    ("Билд", None),
                ]
                for page, object_name in pages:
                    window.setProperty("page", page)
                    app.processEvents()
                    if object_name:
                        view = window.findChild(QObject, object_name)
                        assert view is not None, object_name + " not present in QML"
                        assert view.property("count") is not None, object_name + " has no data model"
                print("Qt catalog smoke OK: character, outfit, favorites and build pages")
            except Exception as exc:
                print("Qt catalog smoke FAILED: " + repr(exc), file=sys.stderr)
                appearance_check["ok"] = False
            finally:
                app.quit()

        QTimer.singleShot(350, verify_catalogs)
    elif "--smoke-appearance" in sys.argv:
        window = engine.rootObjects()[0]

        def verify_live_appearance():
            try:
                window.setProperty("page", "Оформление")
                backend.setAppearanceTheme("frost")
                backend.setAppearanceScale(1.2)
                backend.setAnimationsEnabled(False)
                app.processEvents()
                assert window.property("page") == "Оформление"
                assert abs(window.property("uiScale") - 1.2) < 0.01
                assert window.property("color").name().lower() == "#0b1018"
                assert backend.appearancePalette["accent"] == "#4298e5"
                backend.setAppearanceTheme("violet")
                app.processEvents()
                assert window.property("color").name().lower() == "#100f18"
                backend.resetAppearance()
                app.processEvents()
                assert abs(window.property("uiScale") - 1.0) < 0.01
                assert backend.appearanceTheme == "crimson"
                assert backend.animationsEnabled
                print("Qt appearance smoke OK: all three themes, scale, motion and reset")
            except Exception as exc:
                print("Qt appearance smoke FAILED: " + repr(exc), file=sys.stderr)
                appearance_check["ok"] = False
            finally:
                app.quit()

        QTimer.singleShot(300, verify_live_appearance)
    elif "--smoke" in sys.argv:
        QTimer.singleShot(2800, app.quit)
    app.aboutToQuit.connect(backend.close)
    result = app.exec()
    return result if appearance_check["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
