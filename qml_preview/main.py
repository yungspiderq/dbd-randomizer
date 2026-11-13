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
    app.setApplicationName("DBD Randomizer Qt 3.1.0")
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
    elif "--smoke-layout" in sys.argv:
        window = engine.rootObjects()[0]

        def verify_long_text_layout():
            try:
                from PySide6.QtCore import QMetaObject
                from PySide6.QtTest import QTest
                # Deliberately longer than any current 2v8 class description.
                long_skill = (
                    "Отслеживает окружающую область, обнаруживает союзников и "
                    "объясняет взаимодействие с генераторами, лечением и поиском. "
                ) * 35
                backend._classes = {
                    "SURVIVOR": {
                        "ru": "Медик с расширенным названием класса и подробными навыками",
                        "skills": [{"text": long_skill}, {"text": long_skill[:1200]}],
                    },
                    "KILLER": {
                        "ru": "Наводящий ужас — продолжительное описание силы",
                        "skills": [{"text": long_skill[:1900]},
                                   {"text": long_skill[:1250]}],
                    },
                }
                backend.detailChanged.emit()
                window.setProperty("page", "Классы 2v8")
                for width, height in ((1000, 700), (1350, 820)):
                    window.resize(width, height)
                    QTest.qWait(120)  # polish the wrapped Text and Column layout
                    assert QMetaObject.invokeMethod(window, "verifyClassLayout")
                    assert window.property("layoutSmokePassed"), (
                        window.property("layoutSmokeError") or
                        "class text overlaps adjacent content"
                    )
                print("Qt responsive layout smoke OK: full 2v8 text in 1000/1350px windows")
            except Exception as exc:
                print("Qt responsive layout smoke FAILED: " + repr(exc),
                      file=sys.stderr)
                appearance_check["ok"] = False
            finally:
                app.quit()

        QTimer.singleShot(450, verify_long_text_layout)
    elif "--smoke-design" in sys.argv:
        window = engine.rootObjects()[0]

        def verify_design():
            try:
                from PySide6.QtCore import QMetaObject
                from PySide6.QtTest import QTest
                window.setProperty("page", "Билд")
                for width, height in ((1050, 720), (1350, 850)):
                    window.resize(width, height)
                    QTest.qWait(140)
                    assert QMetaObject.invokeMethod(window, "verifyDesignLayout")
                    assert window.property("designSmokePassed"), (
                        window.property("designSmokeError") or "Design layout failed")
                print("Qt v3.1 design smoke OK at 1050 and 1350 px")
            except Exception as exc:
                print("Qt v3.1 design smoke FAILED: " + repr(exc),
                      file=sys.stderr)
                appearance_check["ok"] = False
            finally:
                app.quit()

        QTimer.singleShot(400, verify_design)
    elif "--smoke-scrollbars" in sys.argv:
        window = engine.rootObjects()[0]

        def verify_scrollbars():
            try:
                from PySide6.QtCore import QMetaObject
                assert QMetaObject.invokeMethod(window, "verifyFastScroll")
                app.processEvents()
                assert window.property("scrollSmokePassed"), (
                    window.property("scrollSmokeError") or "ScrollBar smoke returned false"
                )
                print("Qt draggable scrollbars smoke OK")
            except Exception as exc:
                print("Qt draggable scrollbars smoke FAILED: " + repr(exc),
                      file=sys.stderr)
                appearance_check["ok"] = False
            finally:
                app.quit()

        QTimer.singleShot(350, verify_scrollbars)
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
                assert window.property("color").name().lower() == "#0e1217"
                assert backend.appearancePalette["accent"] == "#8fb3cd"
                backend.setAppearanceTheme("violet")
                app.processEvents()
                assert window.property("color").name().lower() == "#111116"
                backend.resetAppearance()
                app.processEvents()
                assert abs(window.property("uiScale") - 1.0) < 0.01
                assert backend.appearanceTheme == "crimson"
                assert backend.animationsEnabled
                # Verify reflow on minimum and normal window sizes across pages.
                for width, height in ((1050, 700), (1350, 850)):
                    window.resize(width, height)
                    for page in ("Персонажи", "Внешность", "Избранное", "Конструктор"):
                        window.setProperty("page", page)
                        app.processEvents()
                        assert window.width() == width and window.height() == height, (
                            "Unexpected window geometry: " + str(window.size())
                        )
                backend.setAppearanceScale(1.2)
                window.resize(1400, 900)
                app.processEvents()
                assert abs(window.property("uiScale") - 1.2) < 0.01
                assert window.width() == 1400
                backend.resetAppearance()
                print("Qt appearance smoke OK: themes, scale, animation and catalog resize")
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
