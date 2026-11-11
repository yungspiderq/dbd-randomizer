"""Qt Quick frontend backed by the existing DBD Randomizer engine."""
from pathlib import Path
import sys

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtQuickControls2 import QQuickStyle
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
    # The native Windows style does not permit the customized QML controls.
    # Basic respects our fully custom buttons, fields, themes, and popups.
    QQuickStyle.setStyle("Basic")
    app.setApplicationName("DBD Randomizer Qt Beta 16")
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
                pages = ("Персонажи", "Внешность", "Избранное", "Конструктор", "Билд")
                assert len(backend.characters) > 0, "The character catalog is empty"
                for page in pages:
                    window.setProperty("page", page)
                    app.processEvents()
                    assert window.property("page") == page, (
                        "Qt failed to navigate to " + page
                    )
                print("Qt catalog smoke OK: character, outfit, favorites, builder and build pages")
            except Exception as exc:
                print("Qt catalog smoke FAILED: " + repr(exc), file=sys.stderr)
                appearance_check["ok"] = False
            finally:
                app.quit()

        QTimer.singleShot(350, verify_catalogs)
    elif "--smoke-builder" in sys.argv:
        window = engine.rootObjects()[0]

        def verify_builder():
            try:
                from PySide6.QtCore import QObject, QMetaObject, QPointF, Qt
                from PySide6.QtTest import QTest

                window.setProperty("page", "Конструктор")
                app.processEvents()
                assert QMetaObject.invokeMethod(window, "runBuilderSmoke")
                app.processEvents()
                assert window.property("builderSmokeStatus") == 1, (
                    "QML builder logic: " + str(window.property("builderSmokeError"))
                )
                first = window.findChild(QObject, "builderSlotArea0")
                second = window.findChild(QObject, "builderSlotArea1")
                val0 = window.findChild(QObject, "builderValue0")
                val1 = window.findChild(QObject, "builderValue1")
                assert first and second and val0 and val1, "Missing live builder slot objects"
                a, b = val0.property("text"), val1.property("text")
                assert a and b and a != b, "Builder smoke setup is incomplete"

                # Exercise actual Qt mouse press/move/release, rather than only
                # calling the JavaScript slot functions.
                start = first.mapToScene(QPointF(105, 43)).toPoint()
                target = second.mapToScene(QPointF(105, 43)).toPoint()
                QTest.mousePress(window, Qt.LeftButton, Qt.NoModifier, start)
                QTest.mouseMove(window, start + (target - start) / 4, 35)
                QTest.mouseMove(window, target, 40)
                QTest.mouseRelease(window, Qt.LeftButton, Qt.NoModifier, target, 40)
                app.processEvents()
                assert val0.property("text") == b and val1.property("text") == a, (
                    "Pointer drag did not swap occupied slots: "
                    + str((val0.property("text"), val1.property("text")))
                )
                print("Qt builder smoke OK: slot logic, viewport hit-test, real mouse drag")
            except Exception as exc:
                print("Qt builder smoke FAILED: " + repr(exc), file=sys.stderr)
                appearance_check["ok"] = False
            finally:
                app.quit()

        QTimer.singleShot(500, verify_builder)
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
