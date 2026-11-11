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
                from PySide6.QtCore import QMetaObject, QPoint, Qt
                from PySide6.QtTest import QTest

                window.setProperty("page", "Конструктор")
                app.processEvents()
                assert QMetaObject.invokeMethod(window, "runBuilderSmoke")
                app.processEvents()
                assert window.property("builderSmokeStatus") == 1, (
                    "QML builder logic: " + str(window.property("builderSmokeError"))
                )
                QTest.qWait(80)  # let Qt Quick finish dynamic Column/Grid layout
                assert QMetaObject.invokeMethod(window, "prepareBuilderDrag")
                QTest.qWait(90)  # let the Flickable settle after scrolling
                assert QMetaObject.invokeMethod(window, "captureBuilderDrag")
                app.processEvents()
                assert window.property("builderSmokeStatus") == 1, (
                    "Builder scene position: " + str(window.property("builderSmokeError"))
                )
                # Coordinates come from QML directly, so the test doesn't depend
                # on QObject parenting of Repeater delegates.
                start = QPoint(round(window.property("builderSmokeStartX")),
                               round(window.property("builderSmokeStartY")))
                target = QPoint(round(window.property("builderSmokeTargetX")),
                                round(window.property("builderSmokeTargetY")))
                assert start != target, "Slot scene coordinates overlap"
                window.requestActivate()
                app.processEvents()
                QTest.mousePress(window, Qt.LeftButton, Qt.NoModifier, start)
                app.processEvents()
                QTest.mouseMove(window, start + QPoint((target.x() - start.x()) // 4,
                                                       (target.y() - start.y()) // 4), 35)
                QTest.mouseMove(window, target, 40)
                QTest.mouseRelease(window, Qt.LeftButton, Qt.NoModifier, target, 40)
                app.processEvents()
                assert QMetaObject.invokeMethod(window, "evaluateBuilderDrag")
                assert window.property("builderSmokeDragPassed"), (
                    str(window.property("builderSmokeError"))
                )
                assert QMetaObject.invokeMethod(window, "captureBuilderCatalogDrag")
                app.processEvents()
                assert window.property("builderSmokeStatus") == 1, (
                    "Builder catalog geometry: " + str(window.property("builderSmokeError"))
                )
                source = QPoint(round(window.property("builderSmokeCatalogX")),
                                round(window.property("builderSmokeCatalogY")))
                destination = QPoint(round(window.property("builderSmokeCatalogTargetX")),
                                     round(window.property("builderSmokeCatalogTargetY")))
                QTest.mousePress(window, Qt.LeftButton, Qt.NoModifier, source)
                QTest.mouseMove(window, source + QPoint((destination.x() - source.x()) // 4,
                                                        (destination.y() - source.y()) // 4), 35)
                QTest.mouseMove(window, destination, 40)
                QTest.mouseRelease(window, Qt.LeftButton, Qt.NoModifier, destination, 40)
                app.processEvents()
                assert QMetaObject.invokeMethod(window, "evaluateBuilderCatalogDrag")
                assert window.property("builderSmokeCatalogPassed"), (
                    "Catalog mouse drag: " + str(window.property("builderSmokeError")) +
                    ""
                )
                print("Qt builder smoke OK: slot swaps and catalog-to-slot mouse drag")
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
