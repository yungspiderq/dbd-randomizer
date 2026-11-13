import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

ApplicationWindow {
    id: win
    visible: true
    width: 1350
    height: 800
    minimumWidth: Math.round(1000 * uiScale)
    minimumHeight: Math.round(650 * uiScale)
    property real uiScale: backend.appearanceScale
    property var colors: backend.appearancePalette
    color: colors.background
    title: "DBD Randomizer Qt · v3.1.1"
    property string page: "Билд"
    property int builderSmokeStatus: 0
    property string builderSmokeError: ""
    property real builderSmokeStartX: 0
    property real builderSmokeStartY: 0
    property real builderSmokeTargetX: 0
    property real builderSmokeTargetY: 0
    property string builderSmokeExpectedA: ""
    property string builderSmokeExpectedB: ""
    property bool builderSmokeDragPassed: false
    property real builderSmokeCatalogX: 0
    property real builderSmokeCatalogY: 0
    property real builderSmokeCatalogTargetX: 0
    property real builderSmokeCatalogTargetY: 0
    property string builderSmokeCatalogExpected: ""
    property bool builderSmokeCatalogPassed: false
    property color surface: colors.surface
    property color stroke: colors.stroke
    property color muted: colors.muted
    property color accent: colors.accent
    font.family: "Segoe UI"
    // Graphite workspace: restrained chrome, character art as the hero.
    property int designUnit: 4
    onClosing: backend.close()

    // Headless QML check for interactive scrollbar instances.
    property bool scrollSmokePassed: false
    property string scrollSmokeError: ""
    function verifyFastScroll() {
        scrollSmokePassed = false;
        scrollSmokeError = "";
        var bars = [pageScrollBar, builderScrollBar, outfitScrollBar];
        for (var i = 0; i < bars.length; ++i) {
            if (!bars[i] || !bars[i].interactive || bars[i].width < 10) {
                scrollSmokeError = "Scrollbar missing or not draggable at index " + i;
                return;
            }
        }
        scrollSmokePassed = true;
    }

    // Original vector icons: no emoji fonts, extra assets or network access.
    // One painter works for navigation, perk categories and challenge modes.
    component MiniGlyph: Canvas {
        id: glyph
        property string kind: "all"
        property color tint: win.colors.accentSoft
        width: 18
        height: 18
        renderTarget: Canvas.FramebufferObject
        onKindChanged: requestPaint()
        onTintChanged: requestPaint()
        onPaint: {
            var ctx = getContext("2d");
            ctx.clearRect(0, 0, width, height);
            ctx.save();
            ctx.scale(width / 20, height / 20);
            ctx.strokeStyle = tint;
            ctx.fillStyle = tint;
            ctx.lineWidth = 1.8;
            ctx.lineCap = "round";
            ctx.lineJoin = "round";
            function line(x, y, ex, ey) {
                ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(ex, ey); ctx.stroke();
            }
            function rect(x, y, w, h) {
                ctx.strokeRect(x, y, w, h);
            }
            function circle(x, y, r) {
                ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.stroke();
            }
            function dot(x, y, r) {
                ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
            }
            function polygon(points, fill) {
                ctx.beginPath();
                ctx.moveTo(points[0], points[1]);
                for (var i = 2; i < points.length; i += 2)
                    ctx.lineTo(points[i], points[i + 1]);
                ctx.closePath();
                if (fill) ctx.fill(); else ctx.stroke();
            }
            switch (kind) {
            case "dice":
                rect(3, 3, 14, 14); dot(7, 7, 1); dot(13, 13, 1); dot(10, 10, 1);
                break;
            case "builder":
                line(3, 17, 14, 6); circle(15, 5, 3); line(3, 17, 6, 17);
                line(3, 17, 3, 14);
                break;
            case "favorite":
                polygon([10, 2, 12.4, 7.1, 18, 7.7, 14, 11.5, 15, 17.5,
                         10, 14.7, 5, 17.5, 6, 11.5, 2, 7.7, 7.6, 7.1], false);
                break;
            case "community":
                circle(7, 6, 2.5); circle(14.5, 7.5, 2);
                ctx.beginPath(); ctx.arc(7, 17, 5.2, Math.PI, 2 * Math.PI); ctx.stroke();
                ctx.beginPath(); ctx.arc(14.2, 17, 3.5, Math.PI, 2 * Math.PI); ctx.stroke();
                break;
            case "character":
                circle(10, 6, 3);
                ctx.beginPath(); ctx.arc(10, 19, 6.5, Math.PI, 2 * Math.PI); ctx.stroke();
                break;
            case "skin":
                polygon([6, 2, 14, 2, 18, 6, 15, 9, 14, 7.5, 14, 18,
                         6, 18, 6, 7.5, 5, 9, 2, 6], false);
                break;
            case "stats":
                rect(2, 12, 3, 6); rect(9, 8, 3, 10); rect(16, 3, 3, 15);
                break;
            case "timings":
                circle(10, 10, 7); circle(10, 10, 3); dot(10, 10, 1.3);
                break;
            case "class":
                polygon([10, 1, 17, 4, 16.2, 12, 10, 19, 3.8, 12, 3, 4], false);
                line(10, 5, 10, 15);
                break;
            case "theme":
                circle(9, 10, 7); dot(6, 7, 1.3); dot(10, 5, 1.3);
                dot(14, 8, 1.3); dot(6, 12, 1.3); circle(13, 14, 2);
                break;
            case "all":
                rect(2, 2, 7, 7); rect(11, 2, 7, 7);
                rect(2, 11, 7, 7); rect(11, 11, 7, 7);
                break;
            case "common":
                circle(7.4, 10, 5.3); circle(12.6, 10, 5.3);
                break;
            case "unique":
                polygon([10, 1.5, 18, 10, 10, 18.5, 2, 10], false);
                line(10, 5.5, 10, 14.5);
                break;
            case "mixed":
                line(3, 4, 17, 16); line(12.5, 16, 17, 16);
                line(17, 11.5, 17, 16); line(17, 4, 3, 16);
                line(3, 11.5, 3, 16); line(3, 16, 7.5, 16);
                break;
            case "general":
                rect(4, 3, 12, 15); line(7, 2, 13, 2);
                line(7, 8, 13, 8); line(7, 12, 13, 12);
                break;
            case "power":
                polygon([12, 1, 4, 11, 10, 11, 8, 19, 17, 8, 11, 8], false);
                break;
            case "easy":
                rect(3, 13, 4, 5);
                break;
            case "medium":
                rect(3, 13, 4, 5); rect(9, 9, 4, 9);
                break;
            case "hard":
                rect(2, 13, 4, 5); rect(8, 9, 4, 9); rect(14, 4, 4, 14);
                break;
            default:
                circle(10, 10, 6); dot(10, 10, 1.4);
            }
            ctx.restore();
        }
    }

    component UiButton: Rectangle {
        id: button
        property string label: ""
        property string iconName: ""
        property bool primary: false
        property bool prominent: false
        signal clicked()
        implicitHeight: 42
        opacity: enabled ? 1 : 0.5
        radius: 8
        color: prominent ? (over.containsMouse ? "#ffffff" : "#e8eef2") :
               primary ? win.colors.navActive :
               (over.containsMouse ? win.colors.buttonHover : win.colors.button)
        border.width: prominent ? 0 : 1
        border.color: primary ? win.colors.accent : win.colors.stroke
        Behavior on color { ColorAnimation { duration: backend.animationsEnabled ? 120 : 0 } }
        clip: true
        Row {
            width: Math.max(0, button.width - 16)
            anchors.centerIn: parent
            spacing: 6
            MiniGlyph {
                visible: !!button.iconName
                width: 15; height: 15
                kind: button.iconName
                tint: button.prominent ? "#141a20" : button.primary ? win.colors.accentSoft : win.colors.muted
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                id: buttonText
                width: Math.max(0, parent.width - (button.iconName ? 21 : 0))
                text: button.label
                elide: Text.ElideRight
                horizontalAlignment: Text.AlignHCenter
                font.pixelSize: 13
                font.weight: Font.DemiBold
                color: button.prominent ? "#141a20" : button.primary ? win.colors.text : win.colors.muted
                anchors.verticalCenter: parent.verticalCenter
            }
        }
        ToolTip.visible: over.containsMouse && buttonText.truncated
        ToolTip.text: button.label
        MouseArea {
            id: over
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: button.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
            enabled: button.enabled
            onClicked: button.clicked()
        }
    }

    // Grab and drag the thumb to jump across long pages and catalogues.
    component QuickScrollBar: ScrollBar {
        id: quickBar
        width: 14
        implicitWidth: 14
        active: true
        interactive: true
        hoverEnabled: true
        policy: ScrollBar.AsNeeded
        minimumSize: 0.07
        background: Rectangle {
            implicitWidth: 14
            radius: 7
            color: "#26313f"
            opacity: 0.88
        }
        contentItem: Rectangle {
            implicitWidth: 10
            radius: 5
            color: quickBar.pressed ? win.colors.accentSoft :
                   quickBar.hovered ? win.colors.accent : "#8595ab"
        }
    }

    component UiField: TextField {
        color: win.colors.text
        font.pixelSize: 12
        height: 39
        padding: 9
        selectByMouse: true
        placeholderTextColor: "#657385"
        selectionColor: "#87413f"
        background: Rectangle {
            radius: 8
            color: win.colors.input
            border.color: parent.activeFocus ? win.colors.inputFocus : win.colors.inputStroke
            border.width: 1
        }
    }

    // Portraits and outfit previews use the same lazy wiki.gg cache as the original app.
    component ArtThumb: Rectangle {
        id: art
        property string iconKey: ""
        property string placeholder: "DBD"
        property int pixels: 52
        width: pixels
        height: pixels
        radius: 10
        color: win.colors.button
        border.width: 1
        border.color: win.colors.stroke
        clip: true
        Image {
            id: portrait
            anchors.fill: parent
            anchors.margins: 3
            fillMode: Image.PreserveAspectFit
            asynchronous: true
            smooth: true
            sourceSize.width: Math.max(32, art.pixels * 2)
            sourceSize.height: Math.max(32, art.pixels * 2)
            source: backend.iconVersion >= 0 ? backend.iconPath(art.iconKey) : ""
        }
        Text {
            anchors.centerIn: parent
            visible: portrait.status !== Image.Ready
            text: art.placeholder
            font.pixelSize: art.pixels > 100 ? 18 : 10
            color: win.colors.muted
            font.bold: true
        }
    }

    // Shared catalog row: same portrait, selection rail, subtle hover and vector check
    // for the character picker and the outfit gallery.
    component CatalogRow: Rectangle {
        id: catalogRow
        property string title: ""
        property string subtitle: ""
        property string artKey: ""
        property string artLabel: "DBD"
        property bool selected: false
        property bool showCheck: true
        property color statusColor: win.colors.accentSoft
        signal activated()
        width: parent.width
        height: 66
        radius: 11
        color: selected ? win.colors.navActive :
               catalogHover.containsMouse ? win.colors.buttonHover : win.colors.panel
        border.width: 1
        border.color: selected ? win.accent : win.colors.stroke
        Behavior on color { ColorAnimation { duration: backend.animationsEnabled ? 150 : 0 } }
        Behavior on border.color { ColorAnimation { duration: backend.animationsEnabled ? 150 : 0 } }
        Rectangle {
            x: 0; y: 8; width: 3; height: parent.height - 16
            radius: 2; color: win.accent; visible: catalogRow.selected
        }
        ArtThumb {
            x: 9; y: 7; pixels: 52
            iconKey: catalogRow.artKey
            placeholder: catalogRow.artLabel
        }
        Column {
            x: 70
            y: 13
            width: parent.width - (catalogRow.showCheck ? 115 : 83)
            spacing: 5
            Text {
                text: catalogRow.title
                width: parent.width
                elide: Text.ElideRight
                color: catalogRow.selected ? win.colors.text : win.colors.muted
                font.pixelSize: 12
                font.bold: catalogRow.selected
            }
            Text {
                text: catalogRow.subtitle
                width: parent.width
                elide: Text.ElideRight
                color: catalogRow.selected ? catalogRow.statusColor : win.muted
                font.pixelSize: 10
            }
        }
        Rectangle {
            visible: catalogRow.showCheck
            anchors.right: parent.right
            anchors.rightMargin: 12
            anchors.verticalCenter: parent.verticalCenter
            width: 22; height: 22; radius: 6
            color: catalogRow.selected ? win.accent : win.colors.button
            border.width: 1
            border.color: catalogRow.selected ? win.accent : win.stroke
            // Draw a checkmark using two small rectangles rather than an emoji.
            Rectangle {
                visible: catalogRow.selected
                x: 5; y: 11; width: 6; height: 2; radius: 1
                rotation: 45; color: "#ffffff"
            }
            Rectangle {
                visible: catalogRow.selected
                x: 9; y: 9; width: 10; height: 2; radius: 1
                rotation: -45; color: "#ffffff"
            }
        }
        ToolTip.visible: catalogHover.containsMouse
        ToolTip.delay: 650
        ToolTip.text: catalogRow.title + (catalogRow.subtitle ? "\n" + catalogRow.subtitle : "")
        MouseArea {
            id: catalogHover
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: catalogRow.activated()
        }
    }

    component NavItem: Rectangle {
        id: nav
        property string label: ""
        property int ordinal: 0
        property string iconName: "all"
        signal clicked()
        width: parent.width
        height: 40
        radius: 8
        color: win.page === label ? win.colors.navActive : hover.containsMouse ? win.colors.navHover : "transparent"
        Behavior on color { ColorAnimation { duration: backend.animationsEnabled ? 170 : 0 } }
        Rectangle { width: 3; height: parent.height - 16; anchors.verticalCenter: parent.verticalCenter; color: win.accent; visible: win.page === nav.label; radius: 2 }
        Row {
            anchors.verticalCenter: parent.verticalCenter
            x: 12
            spacing: 12
            MiniGlyph { width: 18; height: 18; kind: nav.iconName; tint: win.page === nav.label ? win.colors.accentSoft : win.colors.muted; anchors.verticalCenter: parent.verticalCenter }
            Text { text: nav.label; color: win.page === nav.label ? win.colors.text : win.colors.muted; font.pixelSize: 13; font.weight: win.page === nav.label ? Font.DemiBold : Font.Normal }
        }
        MouseArea { id: hover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: nav.clicked() }
    }

    component StatRow: Rectangle {
        id: statLine
        property var rowData: ({name:"", count:0, fraction:0, since:-1})
        property color fillColor: win.colors.chart
        property bool showIcon: false
        width: parent.width
        height: 56
        radius: 9
        color: win.colors.panel
        border.color: win.colors.stroke
        ArtThumb {
            visible: statLine.showIcon
            x: 7; y: 7; pixels: 42
            iconKey: statLine.rowData.name
            placeholder: "DBD"
        }
        Text {
            x: statLine.showIcon ? 58 : 11
            y: 7
            width: parent.width - (statLine.showIcon ? 118 : 72)
            text: statLine.rowData.name
            color: win.colors.text
            font.pixelSize: 11
            font.bold: true
            elide: Text.ElideRight
        }
        Text {
            anchors.right: parent.right
            anchors.rightMargin: 12
            y: 6
            text: statLine.rowData.count + "×"
            color: win.colors.accentSoft
            font.pixelSize: 12
            font.bold: true
        }
        Rectangle {
            x: statLine.showIcon ? 58 : 11
            y: 36
            width: parent.width - (statLine.showIcon ? 72 : 25)
            height: 7
            radius: 4
            color: "#374354"
            Rectangle {
                width: Math.max(0, parent.width * Math.min(1, statLine.rowData.fraction || 0))
                height: parent.height
                radius: 4
                color: statLine.fillColor
                Behavior on width { NumberAnimation { duration: backend.animationsEnabled ? 230 : 0; easing.type: Easing.OutCubic } }
            }
        }
    }

    component OptionRow: Rectangle {
        id: option
        property string title: ""
        property string keyName: ""
        height: 47
        width: parent.width
        color: pointer.containsMouse ? win.colors.buttonHover : "transparent"
        Behavior on color { ColorAnimation { duration: backend.animationsEnabled ? 130 : 0 } }
        radius: 8
        Text {
            x: 12
            width: parent.width - 84
            anchors.verticalCenter: parent.verticalCenter
            text: option.title
            elide: Text.ElideRight
            color: win.colors.text
            font.pixelSize: 12
        }
        Rectangle {
            width: 38; height: 22
            x: parent.width - 52
            anchors.verticalCenter: parent.verticalCenter
            radius: 11
            color: backend.options[option.keyName] ? win.accent : "#434b57"
            Rectangle {
                width: 16; height: 16; radius: 8
                x: backend.options[option.keyName] ? 19 : 3
                y: 3
                color: "white"
                Behavior on x { NumberAnimation { duration: backend.animationsEnabled ? 160 : 0 } }
            }
        }
        MouseArea { id: pointer; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: backend.toggleOption(option.keyName) }
    }

    RowLayout {
        id: scaledWorkspace
        x: 0
        y: 0
        width: win.width / win.uiScale
        height: win.height / win.uiScale
        transform: Scale {
            origin.x: 0
            origin.y: 0
            xScale: win.uiScale
            yScale: win.uiScale
        }
        spacing: 0
        Rectangle {
            Layout.preferredWidth: 252
            Layout.fillHeight: true
            color: win.colors.sidebar
            border.color: win.colors.stroke
            Flickable {
                ScrollBar.vertical: QuickScrollBar {  }
                anchors.fill: parent
                contentWidth: width
                contentHeight: sidebarContents.implicitHeight + 50
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                Column {
                id: sidebarContents
                x: 16
                y: 20
                width: parent.width - 32
                spacing: 4
                Row {
                    width: parent.width
                    height: 60
                    spacing: 12
                    Image {
                        width: 40; height: 40
                        anchors.verticalCenter: parent.verticalCenter
                        source: "assets/app_icon.png"
                        fillMode: Image.PreserveAspectFit
                        smooth: true
                    }
                    Column {
                        width: parent.width - 52
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 5
                        Text { text: "DBD Randomizer"; color: win.colors.text; font.pixelSize: 16; font.weight: Font.DemiBold }
                        Text { text: "QT QUICK • STABLE 3.1.1"; color: win.colors.muted; font.pixelSize: 10 }
                    }
                }
                Rectangle { width: parent.width; height: 1; color: win.colors.stroke }
                Item { height: 12 }
                NavItem { ordinal: 1; label: "Билд"; iconName: "dice"; onClicked: win.page = label }
                NavItem { ordinal: 2; label: "Конструктор"; iconName: "builder"; onClicked: win.page = label }
                NavItem { ordinal: 3; label: "Избранное"; iconName: "favorite"; onClicked: win.page = label }
                NavItem { ordinal: 4; label: "Билды сообщества"; iconName: "community"; onClicked: win.page = label }
                NavItem { ordinal: 5; label: "Персонажи"; iconName: "character"; onClicked: win.page = label }
                NavItem { ordinal: 6; label: "Внешность"; iconName: "skin"; onClicked: win.page = label }
                NavItem { ordinal: 7; label: "Статистика"; iconName: "stats"; onClicked: win.page = label }
                NavItem { ordinal: 8; label: "Клики и тайминги"; iconName: "timings"; onClicked: win.page = label }
                NavItem { ordinal: 9; label: "Классы 2v8"; iconName: "class"; onClicked: win.page = label }
                NavItem { ordinal: 10; label: "Оформление"; iconName: "theme"; onClicked: win.page = label }
                Item { height: 16 }
                Rectangle { width: parent.width; height: 1; color: win.colors.stroke }
                Item { height: 12 }
                UiButton { width: parent.width; label: "Новый билд"; iconName: "dice"; onClicked: { win.page = "Билд"; backend.generate() } }
                UiButton { width: parent.width; label: "Копировать билд"; onClicked: backend.copyBuild() }
                Item { height: 10 }
                Rectangle {
                    width: parent.width; height: 62; radius: 8
                    color: win.colors.surface
                    border.color: win.colors.stroke
                    Column {
                        x: 12; y: 10; spacing: 6
                        Text { text: "Мастерская билдов"; color: win.colors.text; font.pixelSize: 12; font.weight: Font.DemiBold }
                        Text { text: "Навыки · внешность · испытания"; color: win.colors.muted; font.pixelSize: 10 }
                    }
                }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: win.color
            RowLayout {
                anchors.fill: parent
                spacing: 0
                Flickable {
                    ScrollBar.vertical: QuickScrollBar { id: pageScrollBar; objectName: "mainPageScrollBar" }
                    id: work
                    objectName: "workScroll"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    contentWidth: width
                    contentHeight: content.implicitHeight + 60
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    Column {
                        id: content
                        x: 32; y: 28
                        SequentialAnimation {
                            id: pageReveal
                            NumberAnimation {
                                target: content
                                property: "opacity"
                                from: 0.94
                                to: 1.0
                                duration: backend.animationsEnabled ? 140 : 0
                                easing.type: Easing.OutCubic
                            }
                        }
                        Connections {
                            target: win
                            function onPageChanged() {
                                if (backend.animationsEnabled) {
                                    pageReveal.restart()
                                } else {
                                    pageReveal.stop()
                                    content.opacity = 1
                                }
                                work.contentY = 0
                            }
                        }
                        width: Math.max(0, work.width - 64)
                        spacing: 20
                        Row {
                            width: parent.width; spacing: 16
                            Text {
                                text: win.page === "Билд" ? "Генератор билдов" : win.page
                                width: parent.width - 112
                                font.pixelSize: 29
                                font.weight: Font.DemiBold
                                color: win.colors.text
                                elide: Text.ElideRight
                            }
                            Text {
                                text: "DBD / 3.1"
                                width: 96
                                horizontalAlignment: Text.AlignRight
                                anchors.verticalCenter: parent.verticalCenter
                                font.pixelSize: 11
                                color: win.colors.muted
                            }
                        }
                        Text {
                            width: parent.width
                            text: win.page === "Билд"
                                  ? "Персонаж, навыки и испытание для следующего матча"
                                  : "Сборки и игровые данные"
                            font.pixelSize: 13
                            wrapMode: Text.Wrap
                            color: win.colors.muted
                        }
                        Rectangle { width: parent.width; height: 1; color: win.stroke }
                        Column {
                            visible: win.page === "Билд"
                            width: parent.width
                            spacing: 18
                            Row {
                                width: parent.width; spacing: 10
                                UiButton { width: (parent.width - 10) / 2; label: "ВЫЖИВШИЙ"; iconName: "character"; primary: backend.role === "survivor"; onClicked: backend.setRole("survivor") }
                                UiButton { width: (parent.width - 10) / 2; label: "МАНЬЯК"; iconName: "class"; primary: backend.role === "killer"; onClicked: backend.setRole("killer") }
                            }
                            OptionRow {
                                id: buildEventItemsOption
                                visible: backend.role === "survivor"
                                title: "Ивентовые предметы (выжившие)"
                                keyName: "event_items"
                            }
                            Row {
                                width: parent.width
                                spacing: 10
                                UiButton {
                                    width: (parent.width - 10) / 2
                                    height: 39
                                    primary: true
                                    label: "СОХРАНИТЬ БИЛД В ИЗБРАННОЕ"
                                    onClicked: favoriteEditor.openNew()
                                }
                                UiButton {
                                    width: (parent.width - 10) / 2
                                    height: 39
                                    label: "МОИ СОХРАНЁННЫЕ БИЛДЫ (" + backend.favoriteCount + ")"
                                    onClicked: win.page = "Избранное"
                                }
                            }
                            Rectangle {
                                id: rotationPanel
                                width: parent.width
                                height: Math.max(168, rotationBody.implicitHeight + 24)
                                radius: 13
                                color: win.colors.panel
                                border.width: 1
                                border.color: backend.rotationEnabled ? win.colors.accent : win.stroke
                                Column {
                                    id: rotationBody
                                    x: 12; y: 12
                                    width: parent.width - 24
                                    spacing: 9
                                    Row {
                                        width: parent.width
                                        spacing: 8
                                        Text {
                                            text: "Режим генерации"
                                            color: win.colors.text
                                            font.pixelSize: 11
                                            font.bold: true
                                            font.letterSpacing: 1
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                        Item { width: 1; height: 1 }
                                        Text {
                                            text: backend.rotationEnabled ? "Ротация активна" : "Обычный"
                                            color: backend.rotationEnabled ? win.colors.accentSoft : "#8493a5"
                                            font.pixelSize: 10
                                            font.bold: true
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                    }
                                    Row {
                                        width: parent.width
                                        spacing: 10
                                        UiButton {
                                            width: (parent.width - 10) / 2
                                            height: 37
                                            label: "ОБЫЧНЫЙ"
                                            primary: !backend.rotationEnabled
                                            onClicked: backend.setRotationEnabled(false)
                                        }
                                        UiButton {
                                            width: (parent.width - 10) / 2
                                            height: 37
                                            label: "СБАЛАНСИРОВАННЫЙ"
                                            primary: backend.rotationEnabled
                                            onClicked: backend.setRotationEnabled(true)
                                        }
                                    }
                                    Text {
                                        width: parent.width
                                        text: backend.rotationEnabled ?
                                            "Недавно выпавшие киллеры, перки и аддоны получают меньший шанс. Без жёсткого запрета." :
                                            "Чистая случайность: история не влияет на результат."
                                        color: win.colors.muted
                                        wrapMode: Text.Wrap
                                        font.pixelSize: 11
                                    }
                                    Row {
                                        width: parent.width
                                        spacing: 8
                                        Text {
                                            text: "В ротации: " + backend.rotationStats.seen +
                                                " из " + backend.rotationStats.total +
                                                (backend.rotationStats.last ? " · последний: " + backend.rotationStats.last : "")
                                            width: parent.width - 120
                                            elide: Text.ElideRight
                                            anchors.verticalCenter: parent.verticalCenter
                                            color: win.colors.accentSoft
                                            font.pixelSize: 10
                                        }
                                        UiButton {
                                            width: 112
                                            height: 28
                                            label: "СБРОС ИСТОРИИ"
                                            onClicked: resetRotationPopup.open()
                                        }
                                    }
                                }
                            }
                            Text { text: "Результат генерации"; color: win.colors.muted; font.pixelSize: 13; font.weight: Font.DemiBold }
                            Rectangle {
                                id: generatedHero
                                objectName: "generatedHero"
                                width: parent.width
                                height: Math.max(170, heroBody.implicitHeight + 36)
                                radius: 12
                                color: win.colors.surface
                                border.color: win.colors.stroke
                                Rectangle {
                                    x: 0; y: 18; width: 3; height: parent.height - 36
                                    radius: 2; color: win.colors.accent
                                }
                                Row {
                                    id: heroBody
                                    x: 20; y: 18
                                    width: parent.width - 40
                                    spacing: 20
                                    ArtThumb { pixels: 116; iconKey: backend.detail.char; placeholder: "DBD" }
                                    Column {
                                        width: parent.width - 136
                                        spacing: 10
                                        Text {
                                            text: backend.role === "killer" ? "Убийца" : "Выживший"
                                            color: win.colors.accentSoft
                                            font.pixelSize: 11; font.weight: Font.DemiBold
                                        }
                                        Text {
                                            text: backend.detail.char || "Персонаж ещё не выбран"
                                            width: parent.width; wrapMode: Text.Wrap
                                            color: win.colors.text; font.pixelSize: 23
                                            font.weight: Font.DemiBold
                                        }
                                        Row {
                                            width: parent.width; spacing: 12
                                            ArtThumb { pixels: 44; iconKey: backend.detail.power; placeholder: "ITEM" }
                                            Column {
                                                width: parent.width - 56
                                                spacing: 5
                                                Text {
                                                    text: backend.role === "killer" ? "Способность" : "Предмет"
                                                    color: win.colors.muted; font.pixelSize: 11
                                                }
                                                Text {
                                                    text: backend.detail.power || "Не выбрано"
                                                    width: parent.width; wrapMode: Text.Wrap
                                                    color: win.colors.text; font.pixelSize: 13
                                                }
                                            }
                                        }
                                        Text {
                                            text: backend.detail["class"] || ""
                                            visible: !!text
                                            width: parent.width; wrapMode: Text.Wrap
                                            color: win.colors.muted; font.pixelSize: 12
                                        }
                                    }
                                }
                            }
                            Rectangle {
                                id: rolledSkinCard
                                visible: backend.detail.hasBuild
                                width: parent.width
                                height: backend.detail.hasSkin ? 144 : 95
                                radius: 12
                                color: win.colors.panel
                                border.color: win.colors.stroke
                                Row {
                                    anchors.fill: parent
                                    anchors.margins: 12
                                    spacing: 14
                                    ArtThumb {
                                        pixels: backend.detail.hasSkin ? 116 : 68
                                        iconKey: backend.detail.skinImageKey || ""
                                        placeholder: "SKIN"
                                    }
                                    Column {
                                        width: parent.width - (backend.detail.hasSkin ? 132 : 84)
                                        anchors.verticalCenter: parent.verticalCenter
                                        spacing: 7
                                        Text {
                                            text: "Выбранная внешность"
                                            color: win.colors.accentSoft
                                            font.pixelSize: 11
                                            font.bold: true
                                            font.letterSpacing: 1
                                        }
                                        Text {
                                            text: backend.detail.skin || "Скин не выбран"
                                            width: parent.width
                                            color: win.colors.text
                                            font.pixelSize: 17
                                            font.bold: true
                                            wrapMode: Text.Wrap
                                            maximumLineCount: 2
                                            elide: Text.ElideRight
                                        }
                                        Text {
                                            visible: !!backend.detail.hasSkin
                                            text: [backend.detail.skinRarity, backend.detail.skinType]
                                                  .filter(Boolean).join(" · ") +
                                                  (backend.detail.skinId >= 0 ? " · ID " + backend.detail.skinId : "")
                                            width: parent.width
                                            color: win.colors.muted
                                            font.pixelSize: 11
                                            elide: Text.ElideRight
                                        }
                                        Text {
                                            visible: !!backend.detail.hasSkin &&
                                                     !!backend.detail.skinEnglish &&
                                                     backend.detail.skinEnglish !== backend.detail.skin
                                            text: "EN: " + backend.detail.skinEnglish
                                            width: parent.width
                                            color: win.colors.muted
                                            font.pixelSize: 10
                                            elide: Text.ElideRight
                                        }
                                        Text {
                                            visible: !backend.detail.hasSkin
                                            text: backend.detail.skinEnabled
                                                ? "В коллекции персонажа нет отмеченных скинов."
                                                : "Включите «Случайная внешность» в настройках."
                                            width: parent.width
                                            color: win.colors.muted
                                            font.pixelSize: 11
                                            wrapMode: Text.Wrap
                                        }
                                    }
                                }
                            }
                            Rectangle {
                                width: parent.width
                                height: Math.max(144, addonsBody.implicitHeight + 26)
                                radius: 13
                                color: win.surface
                                border.color: win.stroke
                                Column {
                                    id: addonsBody
                                    x: 13; y: 13
                                    width: parent.width - 26
                                    spacing: 10
                                    Text {
                                        text: "Улучшения"
                                        color: win.muted
                                        font.pixelSize: 11
                                        font.bold: true
                                        font.letterSpacing: 1
                                    }
                                    Row {
                                        width: parent.width
                                        spacing: 10
                                        Repeater {
                                            model: backend.detail.addonDetails || []
                                            Rectangle {
                                                id: addonCard
                                                property var addonInfo: modelData
                                                width: (parent.width - 10) / 2
                                                height: Math.max(91, addonTextColumn.implicitHeight + 18)
                                                radius: 10
                                                color: win.colors.button
                                                border.color: addonInfo.disabled ? "#a35d5b" : win.colors.stroke
                                                Row {
                                                    anchors.fill: parent
                                                    anchors.margins: 9
                                                    spacing: 10
                                                    ArtThumb {
                                                        pixels: 64
                                                        iconKey: addonCard.addonInfo.filled ? addonCard.addonInfo.raw : ""
                                                        placeholder: "ADD"
                                                    }
                                                    Column {
                                                        id: addonTextColumn
                                                        width: parent.width - 74
                                                        spacing: 6
                                                        Text {
                                                            text: "АДДОН " + addonCard.addonInfo.slot
                                                            color: win.colors.muted
                                                            font.pixelSize: 10
                                                            font.bold: true
                                                        }
                                                        Text {
                                                            text: addonCard.addonInfo.filled ? addonCard.addonInfo.name : "Нет аддона"
                                                            width: parent.width
                                                            color: win.colors.text
                                                            font.pixelSize: 12
                                                            font.bold: true
                                                            wrapMode: Text.Wrap
                                                        }
                                                        Text {
                                                            visible: addonCard.addonInfo.disabled
                                                            text: "ЗАПРЕЩЁН ЧЕЛЛЕНДЖЕМ"
                                                            color: win.colors.accentSoft
                                                            font.pixelSize: 9
                                                        }
                                                    }
                                                }
                                                ToolTip.visible: addonHover.containsMouse && addonCard.addonInfo.filled
                                                ToolTip.text: "Эффект аддона: " + addonCard.addonInfo.name
                                                MouseArea {
                                                    id: addonHover
                                                    anchors.fill: parent
                                                    hoverEnabled: true
                                                    enabled: addonCard.addonInfo.filled
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: {
                                                        backend.selectAddonEffect(backend.detail.side,
                                                            backend.detail.char, backend.detail.category,
                                                            addonCard.addonInfo.raw);
                                                        addonPopup.open();
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                            Rectangle {
                                id: challengeCard
                                visible: !!backend.detail.challenge
                                width: parent.width
                                height: Math.max(166, challengeContent.implicitHeight + 28)
                                radius: 12
                                color: win.colors.panel
                                border.color: win.colors.stroke
                                Column {
                                    id: challengeContent
                                    x: 15
                                    y: 14
                                    width: parent.width - 30
                                    spacing: 10
                                    Row {
                                        width: parent.width
                                        spacing: 10
                                        Text {
                                            text: "Испытание матча"
                                            color: win.colors.accentSoft
                                            font.pixelSize: 11
                                            font.bold: true
                                            font.letterSpacing: 1
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                        Text {
                                            text: backend.detail.challengeDifficulty ? "· " + backend.detail.challengeDifficulty.toUpperCase() + (backend.detail.challengeTheme ? " · " + backend.detail.challengeTheme.toUpperCase() : "") : ""
                                            color: win.colors.muted
                                            font.pixelSize: 10
                                            font.bold: true
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                    }
                                    Text {
                                        visible: !!backend.detail.challengeKiller
                                        text: "ДЛЯ " + backend.detail.challengeKiller.toUpperCase()
                                              + " · СИЛА: " + backend.detail.challengePower
                                        width: parent.width
                                        color: "#e9aa80"; font.pixelSize: 11
                                        font.bold: true; wrapMode: Text.Wrap
                                    }
                                    Text {
                                        text: backend.detail.challenge
                                        width: parent.width
                                        color: win.colors.text
                                        font.pixelSize: 17
                                        font.bold: true
                                        wrapMode: Text.Wrap
                                    }
                                    Text {
                                        text: backend.detail.challengeText || "Описание условия недоступно."
                                        width: parent.width
                                        color: "#e2d5dc"
                                        font.pixelSize: 13
                                        wrapMode: Text.Wrap
                                    }
                                    Text {
                                        visible: !!backend.detail.challengeWhy
                                        text: backend.detail.challengeWhy
                                        width: parent.width
                                        color: win.colors.muted
                                        font.pixelSize: 11
                                        font.italic: true
                                        wrapMode: Text.Wrap
                                    }
                                    Repeater {
                                        model: backend.detail.challengeRestrictions || []
                                        Text {
                                            width: challengeContent.width
                                            text: "ОГРАНИЧЕНИЕ: " + modelData
                                            color: win.colors.accentSoft
                                            font.pixelSize: 11
                                            font.bold: true
                                            wrapMode: Text.Wrap
                                        }
                                    }
                                    UiButton {
                                        width: Math.min(230, parent.width)
                                        height: 34
                                        label: backend.advanced.challengeType === "power" && backend.detail.challengeKind === "power" ? "ДРУГОЕ ИСПЫТАНИЕ" : "ДРУГОЙ ЧЕЛЛЕНДЖ + БИЛД"
                                        onClicked: backend.rerollChallenge()
                                    }
                                }
                            }
                            Row {
                                width: parent.width
                                spacing: 8
                                Text {
                                    text: "Навыки · 4 слота"
                                    color: win.colors.muted
                                    font.pixelSize: 11
                                    font.bold: true
                                    font.letterSpacing: 1
                                }
                                Item { width: 1; height: 1 }
                                Text {
                                    text: "Закреплено " + backend.lockedCount + " / 4"
                                    color: backend.lockedCount > 0 ? "#e5bd83" : "#8594a7"
                                    font.pixelSize: 11
                                }
                            }
                            GridLayout {
                                width: parent.width
                                columns: 2
                                rowSpacing: 12
                                columnSpacing: 12
                                Repeater {
                                    model: 4
                                    Rectangle {
                                        id: card
                                        property int slotIndex: index
                                        property var perkInfo: backend.perks[index]
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 242
                                        radius: 14
                                        color: win.colors.panel
                                        border.width: 1
                                        border.color: card.perkInfo.locked ? win.colors.accent :
                                                       cardHover.containsMouse ? win.colors.inputStroke : win.colors.stroke
                                        Behavior on border.color { ColorAnimation { duration: backend.animationsEnabled ? 160 : 0 } }
                                        clip: true

                                        Rectangle {
                                            width: 4; height: parent.height
                                            color: win.colors.accent
                                            visible: card.perkInfo.locked
                                        }
                                        Rectangle {
                                            x: 4; y: 0; width: parent.width - 4; height: 35
                                            color: win.colors.button
                                        }
                                        Text {
                                            x: 15; y: 11
                                            text: "Слот " + (card.slotIndex + 1)
                                            color: win.colors.muted
                                            font.pixelSize: 10
                                            font.bold: true
                                            font.letterSpacing: 1
                                        }
                                        UiButton {
                                            width: Math.min(126, card.width * 0.54)
                                            height: 28
                                            anchors.right: parent.right
                                            anchors.rightMargin: 8
                                            y: 4
                                            primary: card.perkInfo.locked
                                            label: card.perkInfo.locked ? "ЗАКРЕПЛЁН" : "ЗАКРЕПИТЬ"
                                            onClicked: backend.toggleLock(card.slotIndex)
                                        }
                                        Rectangle {
                                            x: (parent.width - 102) / 2
                                            y: 41
                                            width: 102; height: 93
                                            radius: 13
                                            color: win.colors.button
                                            border.color: win.colors.stroke
                                            Image {
                                                id: perkIcon
                                                anchors.fill: parent
                                                anchors.margins: 5
                                                fillMode: Image.PreserveAspectFit
                                                sourceSize.width: 204
                                                sourceSize.height: 186
                                                source: backend.iconVersion >= 0 ? backend.iconPath(card.perkInfo.raw) : ""
                                                asynchronous: true
                                                smooth: true
                                            }
                                            Canvas {
                                                anchors.centerIn: parent
                                                width: 53; height: 53
                                                visible: perkIcon.status !== Image.Ready
                                                onPaint: {
                                                    var p = getContext("2d");
                                                    p.clearRect(0, 0, width, height);
                                                    p.strokeStyle = "#aab8c8";
                                                    p.lineWidth = 2.5;
                                                    p.beginPath();
                                                    p.moveTo(26, 3); p.lineTo(48, 25);
                                                    p.lineTo(26, 49); p.lineTo(4, 25);
                                                    p.closePath();
                                                    p.moveTo(26, 12); p.lineTo(26, 40);
                                                    p.moveTo(13, 25); p.lineTo(39, 25);
                                                    p.stroke();
                                                }
                                            }
                                            MouseArea {
                                                anchors.fill: parent
                                                cursorShape: card.perkInfo.filled ? Qt.PointingHandCursor : Qt.ArrowCursor
                                                enabled: card.perkInfo.filled
                                                onClicked: {
                                                    perkPopup.info = backend.perkInfo(card.slotIndex);
                                                    perkPopup.open();
                                                }
                                            }
                                        }
                                        Text {
                                            x: 14; y: 141
                                            width: parent.width - 28
                                            height: 37
                                            text: card.perkInfo.name
                                            color: card.perkInfo.filled ? win.colors.text : "#8693a3"
                                            font.pixelSize: 14
                                            font.weight: Font.DemiBold
                                            horizontalAlignment: Text.AlignHCenter
                                            wrapMode: Text.Wrap
                                            elide: Text.ElideRight
                                            maximumLineCount: 2
                                        }
                                        Row {
                                            x: 12
                                            y: 189
                                            width: parent.width - 24
                                            spacing: 8
                                            UiButton {
                                                width: (parent.width - 8) / 2
                                                height: 36
                                                label: "ПОДРОБНО"
                                                onClicked: {
                                                    perkPopup.info = backend.perkInfo(card.slotIndex);
                                                    perkPopup.open();
                                                }
                                            }
                                            UiButton {
                                                width: (parent.width - 8) / 2
                                                height: 36
                                                label: "ПЕРЕБРОС"
                                                onClicked: backend.reroll(card.slotIndex)
                                            }
                                        }
                                        MouseArea {
                                            id: cardHover
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            acceptedButtons: Qt.NoButton
                                        }
                                        SequentialAnimation {
                                            id: perkReveal
                                            running: false
                                            PauseAnimation { duration: backend.animationsEnabled ? card.slotIndex * 85 : 0 }
                                            ParallelAnimation {
                                                NumberAnimation {
                                                    target: card
                                                    property: "opacity"
                                                    from: 0.2
                                                    to: 1
                                                    duration: backend.animationsEnabled ? 260 : 0
                                                    easing.type: Easing.OutCubic
                                                }
                                                NumberAnimation {
                                                    target: card
                                                    property: "scale"
                                                    from: 0.985
                                                     to: 1
                                                     duration: backend.animationsEnabled ? 150 : 0
                                                     easing.type: Easing.OutCubic
                                                }
                                            }
                                        }
                                        Connections {
                                            target: backend
                                            function onBuildRevisionChanged() {
                                                if (backend.animationsEnabled)
                                                    perkReveal.restart()
                                                else {
                                                    perkReveal.stop()
                                                    card.opacity = 1
                                                    card.scale = 1
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                            Row {
                                width: parent.width
                                spacing: 8
                                UiButton {
                                    width: parent.width * 0.46 - 6
                                    label: "Сгенерировать"
                                    iconName: "dice"
                                    prominent: true
                                    onClicked: backend.generate()
                                }
                                UiButton {
                                    width: parent.width * 0.30 - 6
                                    label: "Перебросить свободные"
                                    onClicked: backend.rerollPerks()
                                }
                                UiButton {
                                    width: parent.width * 0.24 - 4
                                    label: "Копировать"
                                    onClicked: backend.copyBuild()
                                }
                            }
                            Row {
                                width: parent.width
                                spacing: 8
                                UiButton {
                                    width: (parent.width - 8) / 2
                                    height: 34
                                    label: "ЗАКРЕПИТЬ ВСЕ НАВЫКИ"
                                    onClicked: backend.setAllPerkLocks(true)
                                }
                                UiButton {
                                    width: (parent.width - 8) / 2
                                    height: 34
                                    label: "СНЯТЬ ВСЕ ЗАКРЕПЛЕНИЯ"
                                    onClicked: backend.setAllPerkLocks(false)
                                }
                            }
                            Text {
                                width: parent.width
                                text: "Закреплённые перки сохраняются при полной генерации, если они не запрещены челленджем и настройками."
                                wrapMode: Text.WordWrap
                                color: "#8394a9"
                                font.pixelSize: 11
                            }
                            Rectangle {
                                width: parent.width; height: 86; radius: 12; color: win.surface; border.color: win.stroke
                                Column { anchors.fill: parent; anchors.margins: 15; spacing: 9
                                    Text { text: "ИСТОРИЯ"; color: win.muted; font.pixelSize: 11; font.bold: true }
                                    Text { text: backend.history.length ? backend.history[0] : "Здесь появится последний билд"; width: parent.width; elide: Text.ElideRight; color: win.colors.text; font.pixelSize: 12 }
                                }
                            }
                        }
                        Column {
                            id: makerPage
                            objectName: "builderPage"
                            visible: win.page === "Конструктор"
                            width: parent.width
                            spacing: 14
                            property string makerSide: "SURVIVOR"
                            property int perkSlot: 0
                            property int addonSlot: 0
                            property string perkFilter: "all"
                            property int hoverSlot: -1
                            property bool draggingPerk: false
                            property string draggedPerkName: ""
                            property int dragFromSlot: -1
                            property real dragPointerX: 0
                            property real dragPointerY: 0
                            onVisibleChanged: { if (!visible) cancelPerkDrag(); }
                            function slotFromPointer(x, y) {
                                // Reject offscreen slots before accepting a drop.
                                var local = work.mapFromItem(win.contentItem, x, y);
                                if (local.x < 0 || local.y < 0 ||
                                        local.x >= work.width || local.y >= work.height) return -1;
                                for (var i = 0; i < 4; i++) {
                                    var slot = makerSlotRepeater.itemAt(i);
                                    if (!slot) continue;
                                    var p = slot.mapFromItem(win.contentItem, x, y);
                                    if (p.x >= 0 && p.x < slot.width &&
                                            p.y >= 0 && p.y < slot.height) return i;
                                }
                                return -1;
                            }
                            function updatePerkPointer(source, localX, localY) {
                                if (!draggingPerk) return;
                                var p = source.mapToItem(win.contentItem, localX, localY);
                                dragPointerX = p.x;
                                dragPointerY = p.y;
                                hoverSlot = slotFromPointer(p.x, p.y);
                            }
                            function beginPerkDrag(name, fromSlot, source, localX, localY) {
                                if (!name) return;
                                draggedPerkName = name;
                                dragFromSlot = fromSlot;
                                draggingPerk = true;
                                updatePerkPointer(source, localX, localY);
                            }
                            function cancelPerkDrag() {
                                draggingPerk = false;
                                draggedPerkName = "";
                                dragFromSlot = -1;
                                hoverSlot = -1;
                            }
                            function finishPerkDrag() {
                                if (!draggingPerk) return;
                                var name = draggedPerkName;
                                var from = dragFromSlot;
                                var to = hoverSlot;
                                cancelPerkDrag();
                                if (to < 0) return;
                                if (from >= 0) movePerk(from, to);
                                else assignPerk(name, to);
                            }
                            function perkFields() {
                                return [makerPerk1, makerPerk2, makerPerk3, makerPerk4];
                            }
                            function perkNameAt(i) {
                                var fields = perkFields();
                                return i >= 0 && i < 4 ? fields[i].text : "";
                            }
                            function clearPerk(i) {
                                if (i < 0 || i >= 4) return;
                                perkFields()[i].text = "";
                                perkSlot = i;
                            }
                            // Moving a chosen perk swaps destinations instead of duplicating it.
                            function assignPerk(name, target) {
                                if (!name || target < 0 || target >= 4) return;
                                var fields = perkFields();
                                var from = -1;
                                for (var i = 0; i < 4; i++) {
                                    if (fields[i].text === name) { from = i; break; }
                                }
                                if (from === target) { perkSlot = target; return; }
                                var displaced = fields[target].text;
                                fields[target].text = name;
                                if (from >= 0) fields[from].text = displaced;
                                perkSlot = target;
                            }
                            function movePerk(from, to) {
                                if (from < 0 || from >= 4 || to < 0 || to >= 4 || from === to) return;
                                var fields = perkFields();
                                var moving = fields[from].text;
                                if (!moving) return;
                                var displaced = fields[to].text;
                                fields[to].text = moving;
                                fields[from].text = displaced;
                                perkSlot = to;
                            }
                            function changeSide(side) {
                                if (makerSide === side) return;
                                makerSide = side;
                                makerChar.text = "";
                                makerItem.text = "";
                                makerAddon1.text = "";
                                makerAddon2.text = "";
                                makerPerk1.text = "";
                                makerPerk2.text = "";
                                makerPerk3.text = "";
                                makerPerk4.text = "";
                                perkSearch.text = "";
                                addonSearch.text = "";
                                perkSlot = 0;
                                perkFilter = "all";
                                cancelPerkDrag();
                                addonSlot = 0;
                            }
                            function pickPerk(name) {
                                var fields = perkFields();
                                for (var i = 0; i < 4; i++) {
                                    if (fields[i].text === name) { perkSlot = i; return; }
                                }
                                var target = perkSlot;
                                assignPerk(name, target);
                                var next = (target + 1) % 4;
                                for (var j = 0; j < 4; j++) {
                                    var slot = (next + j) % 4;
                                    if (!fields[slot].text) { perkSlot = slot; return; }
                                }
                            }
                            function pickAddon(name) {
                                if (makerAddon1.text === name) { addonSlot = 0; return; }
                                if (makerAddon2.text === name) { addonSlot = 1; return; }
                                if (addonSlot === 0) makerAddon1.text = name;
                                else makerAddon2.text = name;
                                addonSlot = 1 - addonSlot;
                            }
                            Text { text: "Визуальный конструктор билдов"; color: win.colors.text; font.pixelSize: 18; font.bold: true }
                            Text {
                                text: "Нажми на навык для добавления или перетащи его в слот. Навыки в слотах можно переставлять перетаскиванием."
                                width: parent.width; wrapMode: Text.WordWrap; font.pixelSize: 11; color: win.muted
                            }
                            Row {
                                width: parent.width; spacing: 9
                                UiButton {
                                    width: (parent.width - 9) / 2
                                    label: "ВЫЖИВШИЙ"
                                    iconName: "character"
                                    primary: makerPage.makerSide === "SURVIVOR"
                                    onClicked: makerPage.changeSide("SURVIVOR")
                                }
                                UiButton {
                                    width: (parent.width - 9) / 2
                                    label: "МАНЬЯК"
                                    iconName: "class"
                                    primary: makerPage.makerSide === "KILLER"
                                    onClicked: makerPage.changeSide("KILLER")
                                }
                            }
                            Rectangle {
                                width: parent.width; height: 244; radius: 13; color: win.surface; border.color: win.stroke
                                Column {
                                    anchors.fill: parent; anchors.margins: 13; spacing: 8
                                    Text { text: "01 · ПЕРСОНАЖ"; font.pixelSize: 11; font.bold: true; color: win.colors.muted }
                                    UiField { id: makerChar; width: parent.width; placeholderText: "Найти персонажа..." }
                                    ListView {
                                        ScrollBar.vertical: QuickScrollBar {  }
                                        id: makerCharacters
                                        reuseItems: true
                                        cacheBuffer: 96
                                        width: parent.width
                                        height: 151
                                        spacing: 5
                                        clip: true
                                        model: backend.searchCharacters(makerPage.makerSide, makerChar.text)
                                        delegate: Rectangle {
                                            width: makerCharacters.width; height: 49; radius: 8
                                            color: makerCharHover.containsMouse ? win.colors.stroke : win.colors.panel
                                            border.color: makerChar.text === modelData.name ? win.accent : win.colors.stroke
                                            ArtThumb { x: 5; y: 4; pixels: 41; iconKey: modelData.name; placeholder: "DBD" }
                                            Text { text: modelData.name; x: 55; anchors.verticalCenter: parent.verticalCenter; color: win.colors.text; font.pixelSize: 12; width: parent.width - 66; elide: Text.ElideRight }
                                            MouseArea { id: makerCharHover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: makerChar.text = modelData.name }
                                        }
                                    }
                                }
                            }
                            Rectangle {
                                width: parent.width; height: makerPage.makerSide === "SURVIVOR" ? 477 : 367; radius: 13; color: win.surface; border.color: win.stroke
                                Column {
                                    anchors.fill: parent; anchors.margins: 13; spacing: 9
                                    Text { text: "02 · ПРЕДМЕТ И АДДОНЫ"; font.pixelSize: 11; font.bold: true; color: win.colors.muted }
                                    UiField {
                                        id: makerItem
                                        width: parent.width
                                        enabled: makerPage.makerSide === "SURVIVOR"
                                        placeholderText: makerPage.makerSide === "KILLER" ? "Сила маньяка подбирается автоматически" : "Найти предмет выжившего..."
                                    }
                                    ListView {
                                        ScrollBar.vertical: QuickScrollBar {  }
                                        id: makerItems
                                        reuseItems: true
                                        cacheBuffer: 96
                                        visible: makerPage.makerSide === "SURVIVOR"
                                        width: parent.width
                                        height: visible ? 100 : 0
                                        spacing: 5
                                        clip: true
                                        model: backend.searchItems(makerItem.text)
                                        delegate: Rectangle {
                                            width: makerItems.width; height: 48; radius: 8
                                            color: makerItemHover.containsMouse ? win.colors.stroke : win.colors.panel
                                            border.color: makerItem.text === modelData.name ? win.accent : win.colors.stroke
                                            ArtThumb { x: 5; y: 4; pixels: 40; iconKey: modelData.name; placeholder: "ITEM" }
                                            Text { text: modelData.name; x: 55; y: 7; width: parent.width-65; elide: Text.ElideRight; font.pixelSize: 12; color: win.colors.text }
                                            Text { text: modelData.category; x: 55; y: 28; width: parent.width-65; elide: Text.ElideRight; font.pixelSize: 10; color: "#91a5b6" }
                                            MouseArea {
                                                id: makerItemHover; anchors.fill: parent; hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: { makerItem.text = modelData.name; makerAddon1.text = ""; makerAddon2.text = "" }
                                            }
                                        }
                                    }
                                    Row {
                                        width: parent.width; spacing: 8
                                        UiField { id: makerAddon1; width: (parent.width - 8) / 2; placeholderText: "Аддон 1" }
                                        UiField { id: makerAddon2; width: (parent.width - 8) / 2; placeholderText: "Аддон 2" }
                                    }
                                    Row {
                                        spacing: 8
                                        UiButton { width: 116; height: 34; label: "АДДОН 1"; primary: makerPage.addonSlot === 0; onClicked: makerPage.addonSlot = 0 }
                                        UiButton { width: 116; height: 34; label: "АДДОН 2"; primary: makerPage.addonSlot === 1; onClicked: makerPage.addonSlot = 1 }
                                    }
                                    UiField { id: addonSearch; width: parent.width; placeholderText: "Поиск доступных аддонов по названию..." }
                                    ListView {
                                        ScrollBar.vertical: QuickScrollBar {  }
                                        id: makerAddons
                                        reuseItems: true
                                        cacheBuffer: 96
                                        width: parent.width; height: 136; spacing: 5; clip: true
                                        model: backend.searchAddons(makerPage.makerSide, makerChar.text, makerItem.text, addonSearch.text)
                                        delegate: Rectangle {
                                            width: makerAddons.width; height: 49; radius: 8
                                            color: addonPickHover.containsMouse ? win.colors.stroke : win.colors.panel
                                            border.color: win.colors.stroke
                                            ArtThumb { x: 5; y: 4; pixels: 41; iconKey: modelData.name; placeholder: "ADD" }
                                            Text { text: modelData.name; x: 55; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 140; elide: Text.ElideRight; font.pixelSize: 12; color: "#ecf1f6" }
                                            MouseArea { id: addonPickHover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: makerPage.pickAddon(modelData.name) }
                                            UiButton {
                                                x: parent.width - 81; y: 8
                                                width: 73; height: 32
                                                label: "ЭФФЕКТ"
                                                onClicked: {
                                                    var category = "";
                                                    if (makerPage.makerSide === "SURVIVOR") {
                                                        var items = backend.searchItems(makerItem.text);
                                                        if (items.length && items[0].name === makerItem.text)
                                                            category = items[0].category;
                                                    }
                                                    backend.selectAddonEffect(makerPage.makerSide,
                                                        makerChar.text, category, modelData.name);
                                                    addonPopup.open();
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                            Rectangle {
                                width: parent.width; height: 630; radius: 13
                                color: win.surface; border.color: win.stroke
                                Column {
                                    anchors.fill: parent; anchors.margins: 13; spacing: 8
                                    Text {
                                        text: "03 · ЧЕТЫРЕ НАВЫКА · ПЕРЕТАСКИВАНИЕ"
                                        font.pixelSize: 11; font.bold: true; color: win.colors.muted
                                    }
                                    // Backing fields preserve the strict buildCustom validation contract.
                                    Item {
                                        width: 1; height: 0; visible: false
                                        UiField { id: makerPerk1; objectName: "builderValue0" }
                                        UiField { id: makerPerk2; objectName: "builderValue1" }
                                        UiField { id: makerPerk3; objectName: "builderValue2" }
                                        UiField { id: makerPerk4; objectName: "builderValue3" }
                                    }
                                    Grid {
                                        id: makerSlots
                                        objectName: "builderSlots"
                                        width: parent.width; height: 188
                                        columns: 2; spacing: 8
                                        Repeater {
                                            id: makerSlotRepeater
                                            model: 4
                                            delegate: Item {
                                                id: slotHolder
                                                objectName: "builderSlot" + index
                                                property int slotIndex: index
                                                width: (makerSlots.width - 8) / 2; height: 90
                                                Rectangle {
                                                    id: slotVisual
                                                    x: 0; y: 0
                                                    width: slotHolder.width; height: slotHolder.height
                                                    property string dragName: makerPage.perkNameAt(slotHolder.slotIndex)
                                                    radius: 10
                                                    color: makerPage.hoverSlot === slotHolder.slotIndex ?
                                                        win.colors.navActive :
                                                        (makerPage.perkSlot === slotHolder.slotIndex ? win.colors.buttonHover : win.colors.panel)
                                                    border.width: 1
                                                    border.color: makerPage.hoverSlot === slotHolder.slotIndex ||
                                                        makerPage.perkSlot === slotHolder.slotIndex ? win.accent : win.colors.stroke
                                                    ArtThumb {
                                                        x: 8; y: 25; pixels: 52
                                                        iconKey: slotVisual.dragName
                                                        placeholder: "0" + (slotHolder.slotIndex + 1)
                                                    }
                                                    Text {
                                                        x: 8; y: 5
                                                        text: "СЛОТ 0" + (slotHolder.slotIndex + 1)
                                                        font.pixelSize: 10; font.bold: true; color: win.colors.muted
                                                    }
                                                    Text {
                                                        x: 69; y: 33
                                                        width: parent.width - 134
                                                        text: slotVisual.dragName || "Перетащи навык сюда"
                                                        elide: Text.ElideRight; font.pixelSize: 12
                                                        color: slotVisual.dragName ? win.colors.text : win.colors.muted
                                                    }
                                                    MouseArea {
                                                        id: slotDrag
                                                        objectName: "builderSlotArea" + slotHolder.slotIndex
                                                        anchors.fill: parent
                                                        preventStealing: true
                                                        cursorShape: slotVisual.dragName ? Qt.OpenHandCursor : Qt.PointingHandCursor
                                                        property real pressX: 0
                                                        property real pressY: 0
                                                        property bool moved: false
                                                        onPressed: function(mouse) {
                                                            pressX = mouse.x;
                                                            pressY = mouse.y;
                                                            moved = false;
                                                            makerPage.perkSlot = slotHolder.slotIndex;
                                                        }
                                                        onPositionChanged: function(mouse) {
                                                            if (!pressed || !slotVisual.dragName) return;
                                                            if (!moved && Math.abs(mouse.x - pressX) + Math.abs(mouse.y - pressY) >= 10) {
                                                                moved = true;
                                                                makerPage.beginPerkDrag(slotVisual.dragName,
                                                                    slotHolder.slotIndex, slotDrag, mouse.x, mouse.y);
                                                            }
                                                            if (moved) makerPage.updatePerkPointer(slotDrag, mouse.x, mouse.y);
                                                        }
                                                        onReleased: function(mouse) {
                                                            if (moved) {
                                                                makerPage.updatePerkPointer(slotDrag, mouse.x, mouse.y);
                                                                makerPage.finishPerkDrag();
                                                            }
                                                        }
                                                        onCanceled: makerPage.cancelPerkDrag()
                                                    }
                                                    UiButton {
                                                        x: parent.width - 64; y: 30
                                                        width: 56; height: 30
                                                        label: "УБР."
                                                        visible: !!slotVisual.dragName
                                                        onClicked: makerPage.clearPerk(slotHolder.slotIndex)
                                                    }
                                                }
                                            }
                                        }
                                    }
                                    Text {
                                        width: parent.width
                                        text: "Выбрано: " + makerPage.perkFields().filter(function(f) { return !!f.text; }).length +
                                            " / 4 · повторные навыки не добавляются"
                                        color: win.colors.muted; font.pixelSize: 11
                                    }
                                    Row {
                                        width: parent.width; spacing: 6
                                        Repeater {
                                            model: [
                                                {key:"all", label:"ВСЕ", icon:"all"},
                                                {key:"common", label:"ОБЩИЕ", icon:"common"},
                                                {key:"unique", label:"УНИКАЛЬНЫЕ", icon:"unique"},
                                                {key:"character", label:"ПЕРСОНАЖА", icon:"character"}
                                            ]
                                            UiButton {
                                                width: (parent.width - 18) / 4; height: 32
                                                label: modelData.label
                                                iconName: modelData.icon
                                                primary: makerPage.perkFilter === modelData.key
                                                onClicked: makerPage.perkFilter = modelData.key
                                            }
                                        }
                                    }
                                    UiField {
                                        id: perkSearch; width: parent.width
                                        placeholderText: "Поиск по названию навыка или персонажу..."
                                    }
                                    Text {
                                        width: parent.width
                                        height: makerPage.perkFilter === "character" && !makerChar.text ? 17 : 0
                                        visible: height > 0
                                        color: win.colors.muted; font.pixelSize: 11
                                        text: "Сначала выбери персонажа в блоке 01."
                                    }
                                    ListView {
                                        ScrollBar.vertical: QuickScrollBar { id: builderScrollBar; objectName: "builderPerkScrollBar" }
                                        id: makerPerks
                                        reuseItems: true
                                        cacheBuffer: 96
                                        objectName: "builderPerkList"
                                        width: parent.width; height: 218
                                        spacing: 6; clip: true
                                        model: backend.searchPerks(makerPage.makerSide, perkSearch.text,
                                                                    makerPage.perkFilter, makerChar.text)
                                        delegate: Item {
                                            width: makerPerks.width; height: 56
                                            Rectangle {
                                                id: perkTile
                                                objectName: "builderPerkTile" + index
                                                x: 0; y: 0
                                                width: parent.width; height: parent.height
                                                property string dragName: modelData.name
                                                radius: 9
                                                color: perkPickHover.containsMouse ? win.colors.buttonHover : win.colors.panel
                                                border.width: 1
                                                border.color: win.colors.stroke
                                                ArtThumb { x: 6; y: 5; pixels: 46; iconKey: modelData.name; placeholder: "PERK" }
                                                Text {
                                                    x: 61; y: 8; width: parent.width - 146
                                                    text: modelData.name; color: win.colors.text
                                                    elide: Text.ElideRight; font.pixelSize: 12; font.bold: true
                                                }
                                                Text {
                                                    x: 61; y: 31; width: parent.width - 146
                                                    text: modelData.owner || modelData.kind
                                                    color: win.colors.muted; elide: Text.ElideRight; font.pixelSize: 10
                                                }
                                                Text {
                                                    anchors.right: parent.right; anchors.rightMargin: 23
                                                    anchors.verticalCenter: parent.verticalCenter
                                                    text: "ВЫБРАН"
                                                    visible: makerPage.perkFields().some(function(f) {
                                                        return f.text === modelData.name;
                                                    })
                                                    color: win.colors.accentSoft; font.pixelSize: 10; font.bold: true
                                                }
                                                ToolTip.visible: perkPickHover.containsMouse
                                                ToolTip.delay: 700
                                                ToolTip.text: modelData.name + "\n" +
                                                              (modelData.description || "Справка недоступна")
                                                MouseArea {
                                                    id: perkPickHover
                                                    objectName: "builderPerkArea" + index
                                                    anchors.fill: parent
                                                    hoverEnabled: true
                                                    preventStealing: true
                                                    cursorShape: Qt.PointingHandCursor
                                                    property real pressX: 0
                                                    property real pressY: 0
                                                    property bool moved: false
                                                    onPressed: function(mouse) {
                                                        pressX = mouse.x;
                                                        pressY = mouse.y;
                                                        moved = false;
                                                    }
                                                    onPositionChanged: function(mouse) {
                                                        if (!pressed) return;
                                                        if (!moved && Math.abs(mouse.x - pressX) + Math.abs(mouse.y - pressY) >= 10) {
                                                            moved = true;
                                                            makerPage.beginPerkDrag(modelData.name, -1,
                                                                perkPickHover, mouse.x, mouse.y);
                                                        }
                                                        if (moved) makerPage.updatePerkPointer(perkPickHover, mouse.x, mouse.y);
                                                    }
                                                    onClicked: { if (!moved) makerPage.pickPerk(modelData.name); }
                                                    onReleased: function(mouse) {
                                                        if (moved) {
                                                            makerPage.updatePerkPointer(perkPickHover, mouse.x, mouse.y);
                                                            makerPage.finishPerkDrag();
                                                        }
                                                    }
                                                    onCanceled: makerPage.cancelPerkDrag()
                                                }
                                            }
                                        }
                                    }
                                    Text {
                                        visible: makerPerks.count === 0
                                        text: "Навыки не найдены — измени фильтр или поисковый запрос."
                                        font.pixelSize: 11; color: win.colors.muted
                                    }
                                }
                            }
                            UiButton {
                                width: parent.width
                                label: "СОБРАТЬ БИЛД И ОТКРЫТЬ КАРТОЧКУ"
                                primary: true
                                onClicked: {
                                    if (backend.buildCustom(makerPage.makerSide, makerChar.text, makerItem.text,
                                        makerAddon1.text, makerAddon2.text, makerPerk1.text,
                                        makerPerk2.text, makerPerk3.text, makerPerk4.text))
                                        win.page = "Билд";
                                }
                            }
                        }
                        Column {
                            visible: win.page === "Билды сообщества"
                            width: parent.width; spacing: 14
                            Text { text: "Билды, опубликованные игроками"; color: win.muted; font.pixelSize: 12 }
                            Row { spacing: 9
                                UiButton { width: 172; label: "ОБНОВИТЬ СПИСОК"; primary: true; onClicked: backend.refreshCommunity() }
                                UiButton { width: 188; label: "ОПУБЛИКОВАТЬ МОЙ БИЛД"; onClicked: backend.publishCurrent() }
                            }
                            Text { text: "Публикация через Firebase — без GitHub-токена"; color: win.muted; font.pixelSize: 11 }
                            UiField { id: nickEntry; width: parent.width; text: backend.preferences.nickname; placeholderText: "Ваш ник для публикации"; onEditingFinished: backend.setPublishPref("nickname", text) }
                            UiButton { width: parent.width; label: "ОПУБЛИКОВАТЬ ТЕКУЩИЙ БИЛД"; primary: true; onClicked: { backend.setPublishPref("nickname", nickEntry.text); backend.publishCurrent() } }
                            Text { text: "Найдено билдов: " + backend.community.length; color: "#b1becc"; font.pixelSize: 12 }
                            ListView {
                                ScrollBar.vertical: QuickScrollBar {  }
                                id: buildsList
                                width: parent.width; height: 430; clip: true; spacing: 7
                                model: backend.community
                                delegate: Rectangle {
                                    width: buildsList.width; height: 90
                                    color: win.colors.panel; radius: 9; border.color: win.stroke
                                    Text { text: modelData.title; x: 14; y: 11; width: parent.width - 174; elide: Text.ElideRight; font.bold: true; color: "#f2f4f7"; font.pixelSize: 13 }
                                    Text { text: modelData.character + " · " + modelData.author; x: 14; y: 34; width: parent.width - 174; elide: Text.ElideRight; color: "#9ca9b8"; font.pixelSize: 11 }
                                    Text { text: modelData.date; x: 14; y: 57; color: "#69798a"; font.pixelSize: 10 }
                                    UiButton { x: parent.width - 153; y: 8; width: 140; height: 34; label: "В КАРТОЧКУ"; onClicked: { backend.useCommunity(modelData.index); win.page = "Билд" } }
                                    UiButton { x: parent.width - 153; y: 47; width: 140; height: 33; label: "СКОПИРОВАТЬ"; onClicked: backend.copyCommunity(modelData.index) }
                                }
                            }
                        }
                        Column {
                            id: charactersPage
                            visible: win.page === "Персонажи"
                            width: parent.width
                            spacing: 13
                            property var characterCatalog: backend.characters
                            property string searchNeedle: charSearch.text.trim().toLowerCase()
                            Text { text: "Выбор доступных персонажей"; color: win.colors.text; font.pixelSize: 18; font.bold: true }
                            Text {
                                width: parent.width
                                text: "Маньяки и выжившие — отдельно, как в оригинале. Портреты загружаются в кэш автоматически."
                                color: win.muted; font.pixelSize: 11; wrapMode: Text.WordWrap
                            }
                            UiField { id: charSearch; width: parent.width; placeholderText: "Поиск по персонажам (русское имя)" }
                            Row {
                                width: parent.width; spacing: 12
                                Repeater {
                                    model: [
                                        { side: "K", title: "МАНЬЯКИ", color: "#f2726d" },
                                        { side: "S", title: "ВЫЖИВАЮЩИЕ", color: "#7eaefa" }
                                    ]
                                    Rectangle {
                                        id: sideCard
                                        property string sideKey: modelData.side
                                        property var sideEntries: charactersPage.characterCatalog.filter(function(c) {
                                            return c.side === sideCard.sideKey;
                                        })
                                        property var filtered: sideEntries.filter(function(c) {
                                            return c.name.toLowerCase().indexOf(charactersPage.searchNeedle) >= 0;
                                        })
                                        property int ownedCount: sideEntries.filter(function(c) { return c.owned; }).length
                                        width: (charactersPage.width - 12) / 2
                                        height: 570
                                        radius: 14
                                        color: win.colors.surface
                                        border.width: 1
                                        border.color: win.stroke
                                        Column {
                                            anchors.fill: parent
                                            anchors.margins: 12
                                            spacing: 11
                                            Row {
                                                width: parent.width
                                                spacing: 7
                                                Rectangle { width: 4; height: 28; radius: 2; color: modelData.color }
                                                Column {
                                                    spacing: 3
                                                    Text { text: modelData.title; font.bold: true; font.pixelSize: 13; color: win.colors.text; font.letterSpacing: 0.5 }
                                                    Text {
                                                        text: sideCard.ownedCount + " из " + sideCard.sideEntries.length + " выбрано"
                                                        color: "#92a2b5"; font.pixelSize: 10
                                                    }
                                                }
                                            }
                                            Row {
                                                width: parent.width
                                                spacing: 5
                                                UiButton { width: (parent.width - 10) / 3; height: 33; label: "ВСЕ"; onClicked: backend.setCharactersBulk(sideCard.sideKey, "all", charSearch.text) }
                                                UiButton { width: (parent.width - 10) / 3; height: 33; label: "НИКОГО"; onClicked: backend.setCharactersBulk(sideCard.sideKey, "none", charSearch.text) }
                                                UiButton { width: (parent.width - 10) / 3; height: 33; label: "ИНВЕРСИЯ"; onClicked: backend.setCharactersBulk(sideCard.sideKey, "invert", charSearch.text) }
                                            }
                                            Rectangle { width: parent.width; height: 1; color: "#2f3947" }
                                            ListView {
                                                ScrollBar.vertical: QuickScrollBar {  }
                                                id: characterList
                                        reuseItems: true
                                        cacheBuffer: 96
                                                objectName: "charactersCatalog"
                                                width: parent.width
                                                height: sideCard.height - 128
                                                model: sideCard.filtered
                                                clip: true
                                                spacing: 7
                                                boundsBehavior: Flickable.StopAtBounds
                                                delegate: CatalogRow {
                                                    id: characterRow
                                                    width: characterList.width
                                                    title: modelData.name
                                                    artKey: modelData.name
                                                    artLabel: sideCard.sideKey
                                                    subtitle: modelData.owned ? "ВКЛЮЧЁН В РАНДОМ" : "НЕ ВЫБРАН"
                                                    selected: modelData.owned
                                                    onActivated: backend.setCharacter(modelData.name, sideCard.sideKey)
                                                }
                                                Text {
                                                    anchors.centerIn: parent
                                                    visible: characterList.count === 0
                                                    text: "Ничего не найдено"
                                                    color: win.muted
                                                    font.pixelSize: 12
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                            Text { text: "Выбор сохраняется автоматически. Кнопки «Все / Никого / Инверсия» работают только с найденными персонажами."; width: parent.width; wrapMode: Text.WordWrap; color: "#78899d"; font.pixelSize: 10 }
                        }
                        Column {
                            id: skinPage
                            visible: win.page === "Внешность"
                            width: parent.width
                            spacing: 12
                            property string sideKey: "S"
                            property int selectedSkinId: -1
                            function pickPreview(id, catalog) {
                                for (var i = 0; i < catalog.length; ++i) {
                                    if (catalog[i].id === id)
                                        return catalog[i];
                                }
                                return catalog.length ? catalog[0] : null;
                            }
                            property var previewSkin: pickPreview(selectedSkinId, backend.skins)
                            Text { text: "Галерея внешности"; color: win.colors.text; font.pixelSize: 18; font.bold: true }
                            Text { text: "Настоящие превью из базы wiki.gg. Отмеченные наборы участвуют в генерации билдов."; width: parent.width; color: win.muted; wrapMode: Text.WordWrap; font.pixelSize: 11 }
                            Row {
                                width: parent.width
                                spacing: 9
                                UiButton {
                                    width: (parent.width - 9) / 2; label: "ВЫЖИВАЮЩИЕ"; primary: skinPage.sideKey === "S"
                                    onClicked: {
                                        skinPage.sideKey = "S"; skinPage.selectedSkinId = -1
                                        var available = backend.skinCharacters.filter(function(c) { return c.side === "S" })
                                        if (available.length && backend.skinCharacter !== available[0].name)
                                            backend.setSkinCharacter(available[0].name)
                                    }
                                }
                                UiButton {
                                    width: (parent.width - 9) / 2; label: "МАНЬЯКИ"; primary: skinPage.sideKey === "K"
                                    onClicked: {
                                        skinPage.sideKey = "K"; skinPage.selectedSkinId = -1
                                        var available = backend.skinCharacters.filter(function(c) { return c.side === "K" })
                                        if (available.length && backend.skinCharacter !== available[0].name)
                                            backend.setSkinCharacter(available[0].name)
                                    }
                                }
                            }
                            Row {
                                width: parent.width
                                spacing: 12
                                Rectangle {
                                    id: skinCharactersCard
                                    width: 230
                                    height: 564
                                    radius: 14
                                    color: win.colors.surface
                                    border.color: win.stroke
                                    Column {
                                        anchors.fill: parent
                                        anchors.margins: 10
                                        spacing: 9
                                        Text { text: "ПЕРСОНАЖИ"; color: "#ced7e3"; font.pixelSize: 11; font.bold: true; font.letterSpacing: 1 }
                                        UiField { id: skinCharSearch; width: parent.width; placeholderText: "Поиск героя" }
                                        ListView {
                                            ScrollBar.vertical: QuickScrollBar {  }
                                            id: skinCharList
                                        reuseItems: true
                                        cacheBuffer: 96
                                            objectName: "outfitCharactersCatalog"
                                            width: parent.width
                                            height: skinCharactersCard.height - 78
                                            clip: true
                                            spacing: 6
                                            model: backend.skinCharacters.filter(function(c) {
                                                return c.side === skinPage.sideKey
                                                    && c.name.toLowerCase().indexOf(skinCharSearch.text.toLowerCase()) >= 0;
                                            })
                                            delegate: CatalogRow {
                                                width: skinCharList.width
                                                height: 57
                                                title: modelData.name
                                                subtitle: modelData.translated + " из " + modelData.count + " RU-названий"
                                                artKey: modelData.name
                                                artLabel: modelData.side
                                                selected: backend.skinCharacter === modelData.name
                                                showCheck: false
                                                onActivated: {
                                                    skinPage.selectedSkinId = -1
                                                    backend.setSkinCharacter(modelData.name)
                                                }
                                            }
                                        }
                                    }
                                }
                                Rectangle {
                                    id: skinContent
                                    width: skinPage.width - skinCharactersCard.width - 12
                                    height: 564
                                    radius: 14
                                    color: win.colors.surface
                                    border.color: win.stroke
                                    Column {
                                        anchors.fill: parent
                                        anchors.margins: 12
                                        spacing: 10
                                        Text { text: backend.skinCharacter || "Выберите персонажа"; color: "#eef2f7"; font.pixelSize: 15; font.bold: true }
                                        Text {
                                            text: backend.skinStats.owned + " из " + backend.skinStats.total + " выбрано · RU: " + backend.skinStats.translated + " · без RU: " + backend.skinStats.missingRussian
                                            color: win.muted; font.pixelSize: 11
                                        }
                                        Rectangle {
                                            width: parent.width
                                            height: 140
                                            radius: 11
                                            color: "#212a35"
                                            border.color: "#3e4c5e"
                                            Row {
                                                anchors.fill: parent
                                                anchors.margins: 9
                                                spacing: 13
                                                ArtThumb {
                                                    pixels: 120
                                                    iconKey: skinPage.previewSkin ? "skin:" + skinPage.previewSkin.id : ""
                                                    placeholder: "ПРЕВЬЮ"
                                                }
                                                Column {
                                                    width: parent.width - 133
                                                    spacing: 9
                                                    Text {
                                                        text: skinPage.previewSkin ? skinPage.previewSkin.name : "Набор не выбран"
                                                        color: win.colors.text; font.pixelSize: 13; font.bold: true
                                                        wrapMode: Text.WordWrap; width: parent.width; maximumLineCount: 3; elide: Text.ElideRight
                                                    }
                                                    Text {
                                                        text: skinPage.previewSkin ? (skinPage.previewSkin.rarity + " · " + skinPage.previewSkin.type) : ""
                                                        color: "#c69b96"; width: parent.width; font.pixelSize: 10; wrapMode: Text.WordWrap
                                                    }
                                                    Text {
                                                        text: skinPage.previewSkin ? skinPage.previewSkin.russianSource : ""
                                                        color: "#aeb9c9"; font.pixelSize: 9
                                                        width: parent.width; elide: Text.ElideRight
                                                    }
                                                    Text {
                                                        text: skinPage.previewSkin && skinPage.previewSkin.owned ? "ЕСТЬ В КОЛЛЕКЦИИ" : "НЕ В КОЛЛЕКЦИИ"
                                                        color: skinPage.previewSkin && skinPage.previewSkin.owned ? "#dfb3a2" : "#8d9bad"
                                                        font.pixelSize: 9; font.bold: true
                                                    }
                                                }
                                            }
                                        }
                                        Row {
                                            width: parent.width; spacing: 5
                                            UiButton { width: (parent.width - 15) / 4; height: 32; label: "СЛУЧАЙНО"; primary: true; onClicked: skinPage.selectedSkinId = backend.randomSkinId() }
                                            UiButton { width: (parent.width - 15) / 4; height: 32; label: "ВСЕ"; onClicked: backend.setSkinsOwned("all") }
                                            UiButton { width: (parent.width - 15) / 4; height: 32; label: "НИКОГО"; onClicked: backend.setSkinsOwned("none") }
                                            UiButton { width: (parent.width - 15) / 4; height: 32; label: "ИНВЕРСИЯ"; onClicked: backend.setSkinsOwned("invert") }
                                        }
                                        Timer {
                                            id: skinSearchDebounce
                                            interval: 160
                                            repeat: false
                                            onTriggered: backend.filterSkins(skinSearch.text)
                                        }
                                        UiField {
                                            id: skinSearch
                                            width: parent.width
                                            placeholderText: "Поиск по RU/EN названию, редкости, дате"
                                            onTextChanged: skinSearchDebounce.restart()
                                        }
                                        Row {
                                            width: parent.width
                                            spacing: 5
                                            UiButton {
                                                width: (parent.width - 10) / 3; height: 30
                                                label: "ВСЕ НАЗВАНИЯ"; primary: backend.skinNameFilter === "all"
                                                onClicked: { skinPage.selectedSkinId = -1; backend.setSkinNameFilter("all") }
                                            }
                                            UiButton {
                                                width: (parent.width - 10) / 3; height: 30
                                                label: "С RU"; primary: backend.skinNameFilter === "ru"
                                                onClicked: { skinPage.selectedSkinId = -1; backend.setSkinNameFilter("ru") }
                                            }
                                            UiButton {
                                                width: (parent.width - 10) / 3; height: 30
                                                label: "БЕЗ RU"; primary: backend.skinNameFilter === "missing"
                                                onClicked: { skinPage.selectedSkinId = -1; backend.setSkinNameFilter("missing") }
                                            }
                                        }
                                        ListView {
                                            ScrollBar.vertical: QuickScrollBar { id: outfitScrollBar; objectName: "outfitScrollBar" }
                                            id: skinsList
                                        reuseItems: true
                                        cacheBuffer: 96
                                            objectName: "outfitsCatalog"
                                            width: parent.width
                                            height: skinContent.height - 368
                                            clip: true
                                            spacing: 7
                                            model: backend.skins
                                            delegate: Rectangle {
                                                id: skinRow
                                                width: skinsList.width
                                                height: 67
                                                radius: 11
                                                color: skinPage.previewSkin && skinPage.previewSkin.id === modelData.id
                                                       ? win.colors.navActive
                                                       : skinHover.containsMouse ? win.colors.buttonHover : win.colors.panel
                                                border.color: skinPage.previewSkin && skinPage.previewSkin.id === modelData.id ? win.accent : win.colors.stroke
                                                Behavior on color { ColorAnimation { duration: backend.animationsEnabled ? 150 : 0 } }
                                                Behavior on border.color { ColorAnimation { duration: backend.animationsEnabled ? 150 : 0 } }
                                                Rectangle {
                                                    x: 0; y: 8; width: 3; height: parent.height - 16
                                                    radius: 2
                                                    visible: skinPage.previewSkin && skinPage.previewSkin.id === modelData.id
                                                    color: win.accent
                                                }
                                                ArtThumb {
                                                    x: 7; y: 6; pixels: 55
                                                    iconKey: "skin:" + modelData.id
                                                    placeholder: "SKIN"
                                                }
                                                Column {
                                                    x: 70; y: 7
                                                    width: parent.width - 107
                                                    spacing: 3
                                                    Text { text: modelData.name; width: parent.width; elide: Text.ElideRight; color: "#f1f3f9"; font.pixelSize: 11; font.bold: true }
                                                    Text {
                                                        text: modelData.hasRussian ? "EN: " + modelData.english : "Нет русского названия в базе"
                                                        width: parent.width; elide: Text.ElideRight; color: modelData.hasRussian ? "#97aac2" : "#d7b7a2"; font.pixelSize: 9
                                                    }
                                                    Text { text: modelData.rarity + " · " + modelData.type; width: parent.width; elide: Text.ElideRight; color: "#9aaabe"; font.pixelSize: 10 }
                                                    Text { text: modelData.date; color: "#7d8b9e"; font.pixelSize: 9 }
                                                }
                                                MouseArea {
                                                    id: skinHover
                                                    anchors.fill: parent
                                                    hoverEnabled: true
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: skinPage.selectedSkinId = modelData.id
                                                }
                                                Rectangle {
                                                    width: 25; height: 25; radius: 6
                                                    anchors.right: parent.right
                                                    anchors.rightMargin: 22
                                                    anchors.verticalCenter: parent.verticalCenter
                                                    color: modelData.owned ? win.accent : win.colors.buttonHover
                                                    border.color: modelData.owned ? win.accent : "#63758a"
                                                    Text { anchors.centerIn: parent; text: modelData.owned ? "✓" : "+"; color: "white"; font.pixelSize: 14; font.bold: true }
                                                    MouseArea {
                                                        anchors.fill: parent
                                                        cursorShape: Qt.PointingHandCursor
                                                        onClicked: { skinPage.selectedSkinId = modelData.id; backend.toggleSkin(modelData.id) }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        Column {
                            id: favoritesPage
                            visible: win.page === "Избранное"
                            width: parent.width
                            spacing: 14
                            property var filteredFavorites: backend.favorites
                            Text {
                                text: "Библиотека избранных билдов"
                                font.pixelSize: 20
                                font.bold: true
                                color: win.colors.text
                            }
                            Text {
                                text: "Сохраняй свои сборки по коллекциям, добавляй заметки, находи и загружай обратно. Всё остаётся на этом компьютере."
                                color: "#98a8bb"
                                font.pixelSize: 12
                                wrapMode: Text.Wrap
                                width: parent.width
                            }
                            Row {
                                width: parent.width
                                spacing: 9
                                UiButton {
                                    width: (parent.width - 9) * 0.55
                                    primary: true
                                    label: "СОХРАНИТЬ ТЕКУЩИЙ БИЛД"
                                    onClicked: favoriteEditor.openNew()
                                }
                                Rectangle {
                                    width: (parent.width - 9) * 0.45
                                    height: 44
                                    radius: 10
                                    color: win.colors.button
                                    border.color: win.stroke
                                    Text {
                                        text: "В БИБЛИОТЕКЕ: " + backend.favoriteCount + " / 180"
                                        anchors.centerIn: parent
                                        color: "#d1dbe8"
                                        font.pixelSize: 12
                                        font.bold: true
                                    }
                                }
                            }
                            Timer {
                                id: favoriteSearchDebounce
                                interval: 160
                                repeat: false
                                onTriggered: backend.setFavoriteSearch(favoriteSearch.text)
                            }
                            UiField {
                                id: favoriteSearch
                                width: parent.width
                                placeholderText: "Поиск по названию, коллекции, персонажу, навыкам и заметкам..."
                                onTextChanged: favoriteSearchDebounce.restart()
                            }
                            Row {
                                width: parent.width
                                spacing: 7
                                Repeater {
                                    model: [
                                        {side:"ALL",label:"ВСЕ"},
                                        {side:"SURVIVOR",label:"ВЫЖИВШИЕ"},
                                        {side:"KILLER",label:"МАНЬЯКИ"}
                                    ]
                                    UiButton {
                                        width: (favoritesPage.width - 14) / 3
                                        height: 37
                                        primary: backend.favoriteSide === modelData.side
                                        label: modelData.label
                                        onClicked: backend.setFavoriteSide(modelData.side)
                                    }
                                }
                            }
                            Text {
                                text: "КОЛЛЕКЦИЯ"
                                color: "#9aaec1"
                                font.pixelSize: 11
                                font.bold: true
                            }
                            ComboBox {
                                id: favoriteCollectionChoice
                                width: parent.width
                                height: 42
                                model: backend.favoriteCollections
                                currentIndex: Math.max(0, backend.favoriteCollections.indexOf(backend.favoriteCollection))
                                onActivated: backend.setFavoriteCollection(currentText)
                                font.pixelSize: 12
                                contentItem: Text {
                                    text: favoriteCollectionChoice.displayText
                                    color: "#e6edf5"
                                    verticalAlignment: Text.AlignVCenter
                                    leftPadding: 13
                                    font.pixelSize: 12
                                }
                                background: Rectangle {
                                    radius: 9
                                    color: "#242d39"
                                    border.color: win.stroke
                                }
                            }
                            Text {
                                text: "НАЙДЕНО: " + favoritesPage.filteredFavorites.length
                                color: "#b8c5d5"
                                font.pixelSize: 11
                                font.bold: true
                            }
                            Rectangle {
                                visible: favoritesPage.filteredFavorites.length === 0
                                width: parent.width
                                height: 130
                                radius: 12
                                color: win.surface
                                border.color: win.stroke
                                Column {
                                    anchors.centerIn: parent
                                    spacing: 7
                                    Text {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        text: backend.favoriteCount ? "НИЧЕГО НЕ НАЙДЕНО" : "ИЗБРАННЫХ БИЛДОВ ПОКА НЕТ"
                                        color: "#f0f2f6"
                                        font.bold: true
                                        font.pixelSize: 13
                                    }
                                    Text {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        text: backend.favoriteCount ? "Измени фильтр или строку поиска." : "Создай билд и сохрани его одной кнопкой."
                                        color: "#9dadc0"
                                        font.pixelSize: 12
                                    }
                                }
                            }
                            ListView {
                                ScrollBar.vertical: QuickScrollBar {  }
                                id: favoriteList
                                        reuseItems: true
                                        cacheBuffer: 96
                                objectName: "favoritesCatalog"
                                width: parent.width
                                height: Math.min(600, Math.max(120, favoritesPage.filteredFavorites.length * 182))
                                visible: favoritesPage.filteredFavorites.length > 0
                                clip: true
                                spacing: 10
                                boundsBehavior: Flickable.StopAtBounds
                                model: favoritesPage.filteredFavorites
                                delegate: Rectangle {
                                    id: favoriteCard
                                    property var entry: modelData
                                    width: favoriteList.width
                                    height: Math.max(172, favoriteActions.y + favoriteActions.height + 14)
                                    radius: 13
                                    color: win.colors.panel
                                    border.color: favoriteHover.hovered ? win.accent : win.colors.stroke
                                    Behavior on border.color { ColorAnimation { duration: backend.animationsEnabled ? 140 : 0 } }
                                    HoverHandler { id: favoriteHover }
                                    Rectangle { x: 0; y: 10; width: 3; height: parent.height - 20; radius: 2; color: win.accent }
                                    ArtThumb {
                                        x: 12
                                        y: 14
                                        pixels: 64
                                        iconKey: favoriteCard.entry.char
                                        placeholder: "DBD"
                                    }
                                    Column {
                                        id: favoriteTextBlock
                                        x: 89
                                        y: 13
                                        width: parent.width - 102
                                        spacing: 6
                                        Text {
                                            width: parent.width
                                            text: favoriteCard.entry.title
                                            color: win.colors.text
                                            font.pixelSize: 15
                                            font.bold: true
                                            elide: Text.ElideRight
                                        }
                                        Text {
                                            width: parent.width
                                            text: (favoriteCard.entry.side === "KILLER" ? "МАНЬЯК" : "ВЫЖИВШИЙ") +
                                                " · " + favoriteCard.entry.char +
                                                " · " + favoriteCard.entry.collection
                                            color: win.colors.accentSoft
                                            font.pixelSize: 11
                                            elide: Text.ElideRight
                                        }
                                        Text {
                                            width: parent.width
                                            text: favoriteCard.entry.perks.join("  /  ")
                                            color: "#c3d0e0"
                                            font.pixelSize: 11
                                            elide: Text.ElideRight
                                        }
                                        Text {
                                            width: parent.width
                                            text: favoriteCard.entry.note || "Без заметки"
                                            color: "#90a0b3"
                                            font.pixelSize: 11
                                            wrapMode: Text.Wrap
                                        }
                                    }
                                    Text {
                                        id: favoriteSavedAt
                                        x: 13
                                        y: Math.max(100, favoriteTextBlock.y + favoriteTextBlock.implicitHeight + 7)
                                        text: "Сохранено " + favoriteCard.entry.saved_at
                                        color: "#7c8c9e"
                                        font.pixelSize: 10
                                    }
                                    Row {
                                        id: favoriteActions
                                        x: 12; y: favoriteSavedAt.y + favoriteSavedAt.implicitHeight + 12
                                        width: parent.width - 24
                                        height: 36
                                        spacing: 8
                                        UiButton {
                                            width: (parent.width - 24) / 4
                                            height: 36
                                            primary: true
                                            label: "ЗАГРУЗИТЬ"
                                            onClicked: {
                                                if (backend.loadFavorite(favoriteCard.entry.id))
                                                    win.page = "Билд";
                                            }
                                        }
                                        UiButton {
                                            width: (parent.width - 24) / 4
                                            height: 36
                                            label: "КОПИРОВАТЬ"
                                            onClicked: backend.copyFavorite(favoriteCard.entry.id)
                                        }
                                        UiButton {
                                            width: (parent.width - 24) / 4
                                            height: 36
                                            label: "ИЗМЕНИТЬ"
                                            onClicked: favoriteEditor.openEdit(favoriteCard.entry)
                                        }
                                        UiButton {
                                            width: (parent.width - 24) / 4
                                            height: 36
                                            label: "УДАЛИТЬ"
                                            onClicked: {
                                                deleteFavoriteDialog.favoriteId = favoriteCard.entry.id;
                                                deleteFavoriteDialog.favoriteTitle = favoriteCard.entry.title;
                                                deleteFavoriteDialog.open();
                                            }
                                        }
                                    }
                                }
                            }
                            Text {
                                width: parent.width
                                color: "#8899ad"
                                font.pixelSize: 11
                                wrapMode: Text.Wrap
                                text: "Билды сохраняются в настройках приложения. Загрузка из избранного не меняет статистику генераций и шансы ротации. Если в DBD переименуют или удалят навык, программа предупредит об устаревшей сборке."
                            }
                        }

                        Column {
                            id: appearancePage
                            visible: win.page === "Оформление"
                            width: parent.width
                            spacing: 18
                            Text { text: "Персонализация интерфейса"; color: win.colors.text; font.pixelSize: 20; font.bold: true }
                            Text {
                                width: parent.width; wrapMode: Text.WordWrap
                                text: "Цвет, масштаб и движение на твой вкус. Настройки меняются сразу и сохраняются после перезапуска."
                                color: win.muted; font.pixelSize: 12
                            }
                            Text { text: "ЦВЕТОВЫЕ ТЕМЫ"; color: win.colors.text; font.pixelSize: 12; font.bold: true; font.letterSpacing: 1 }
                            Row {
                                width: parent.width; spacing: 10
                                Repeater {
                                    model: [
                                        {key:"crimson", title:"CRIMSON", note:"Оригинальный красный", accent:"#ea5753", background:win.colors.surface},
                                        {key:"frost", title:"FROST", note:"Холодный синий", accent:"#4298e5", background:"#172231"},
                                        {key:"violet", title:"VIOLET", note:"Неоновый фиолетовый", accent:"#ad73dc", background:"#221d30"}
                                    ]
                                    Rectangle {
                                        id: themeTile
                                        property var item: modelData
                                        property bool selected: backend.appearanceTheme === themeTile.item.key
                                        width: (appearancePage.width - 20) / 3; height: 185
                                        radius: 13
                                        color: themeTile.item.background
                                        border.width: selected ? 2 : 1
                                        border.color: selected ? themeTile.item.accent : win.stroke
                                        Behavior on border.color { ColorAnimation { duration: backend.animationsEnabled ? 190 : 0 } }
                                        Rectangle {
                                            x: 12; y: 13; width: parent.width - 24; height: 65
                                            radius: 8; color: "#121923"
                                            Rectangle { x: 10; y: 11; width: 19; height: 44; radius: 5; color: themeTile.item.accent }
                                            Column {
                                                x: 39; y: 12; spacing: 8
                                                Rectangle { width: 60; height: 8; radius: 4; color: "#6b7b91" }
                                                Rectangle { width: 80; height: 8; radius: 4; color: "#46586b" }
                                                Rectangle { width: 51; height: 8; radius: 4; color: themeTile.item.accent }
                                            }
                                        }
                                        Text { x: 12; y: 86; text: themeTile.item.title; font.pixelSize: 14; font.bold: true; color: "white" }
                                        Text { x: 12; y: 110; text: themeTile.item.note; width: parent.width - 24; font.pixelSize: 10; color: "#b6c2d2"; elide: Text.ElideRight }
                                        Rectangle {
                                            x: 12; y: 140; width: parent.width - 24; height: 32
                                            radius: 7; color: themeTile.selected ? themeTile.item.accent : "#344252"
                                            Text {
                                                anchors.centerIn: parent
                                                text: themeTile.selected ? "ВЫБРАНО" : "ВЫБРАТЬ"
                                                font.pixelSize: 11; font.bold: true; color: "white"
                                            }
                                        }
                                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: backend.setAppearanceTheme(themeTile.item.key) }
                                    }
                                }
                            }
                            Rectangle { width: parent.width; height: 1; color: win.stroke }
                            Text { text: "МАСШТАБ ОКНА"; font.pixelSize: 12; font.bold: true; color: win.colors.text; font.letterSpacing: 1 }
                            Text {
                                width: parent.width; wrapMode: Text.WordWrap
                                text: "Увеличивает навигацию, карточки и содержимое вкладок. Минимальный размер окна тоже изменяется."
                                color: win.muted; font.pixelSize: 11
                            }
                            Row {
                                width: parent.width; spacing: 9
                                Repeater {
                                    model: [
                                        {value:0.9, label:"90%"},
                                        {value:1.0, label:"100%"},
                                        {value:1.1, label:"110%"},
                                        {value:1.2, label:"120%"}
                                    ]
                                    UiButton {
                                        width: (appearancePage.width - 27) / 4
                                        height: 41
                                        label: modelData.label
                                        primary: Math.abs(backend.appearanceScale - modelData.value) < 0.01
                                        onClicked: backend.setAppearanceScale(modelData.value)
                                    }
                                }
                            }
                            Rectangle { width: parent.width; height: 1; color: win.stroke }
                            Text { text: "АНИМАЦИИ"; font.pixelSize: 12; font.bold: true; color: win.colors.text; font.letterSpacing: 1 }
                            Row {
                                width: parent.width; spacing: 10
                                UiButton {
                                    width: (parent.width - 10) / 2
                                    label: "ПЛАВНЫЕ ПЕРЕХОДЫ"
                                    primary: backend.animationsEnabled
                                    onClicked: backend.setAnimationsEnabled(true)
                                }
                                UiButton {
                                    width: (parent.width - 10) / 2
                                    label: "БЕЗ АНИМАЦИЙ"
                                    primary: !backend.animationsEnabled
                                    onClicked: backend.setAnimationsEnabled(false)
                                }
                            }
                            Text {
                                width: parent.width; wrapMode: Text.WordWrap
                                text: "Можно отключить движение в меню и карточках, сохранив все функции рандомизатора."
                                font.pixelSize: 11; color: win.muted
                            }
                            Row {
                                width: parent.width; spacing: 10
                                UiButton {
                                    width: (parent.width - 10) / 2; label: "СБРОСИТЬ ОФОРМЛЕНИЕ"
                                    onClicked: appearanceReset.open()
                                }
                                UiButton {
                                    width: (parent.width - 10) / 2; primary: true
                                    label: "К ГЕНЕРАТОРУ"
                                    onClicked: win.page = "Билд"
                                }
                            }
                        }

                        Column {
                            id: statsPage
                            visible: win.page === "Статистика"
                            width: parent.width
                            spacing: 14
                            property var stat: backend.statistics
                            Text {
                                text: "Аналитика генераций"
                                color: "#eff3f9"
                                font.pixelSize: 19
                                font.bold: true
                            }
                            Text {
                                text: "Графики по персонажам, навыкам и аддонам в обоих режимах. Выбирай период для сравнения выпадений."
                                width: parent.width
                                wrapMode: Text.Wrap
                                font.pixelSize: 11
                                color: "#90a3b9"
                            }
                            Row {
                                width: parent.width
                                spacing: 9
                                UiButton {
                                    width: (parent.width - 9) / 2
                                    label: "ВЫЖИВАЮЩИЕ"
                                    primary: backend.statisticsSide === "SURVIVOR"
                                    onClicked: backend.setStatisticsSide("SURVIVOR")
                                }
                                UiButton {
                                    width: (parent.width - 9) / 2
                                    label: "МАНЬЯКИ"
                                    primary: backend.statisticsSide === "KILLER"
                                    onClicked: backend.setStatisticsSide("KILLER")
                                }
                            }
                            Text { text: "ПЕРИОД СТАТИСТИКИ"; color: "#cad6e4"; font.pixelSize: 11; font.bold: true; font.letterSpacing: 1 }
                            Row {
                                width: parent.width
                                spacing: 7
                                Repeater {
                                    model: [
                                        {days:0, label:"ВСЁ ВРЕМЯ"},
                                        {days:1, label:"СЕГОДНЯ"},
                                        {days:7, label:"7 ДНЕЙ"},
                                        {days:30, label:"30 ДНЕЙ"}
                                    ]
                                    UiButton {
                                        width: (parent.width - 21) / 4
                                        height: 37
                                        label: modelData.label
                                        primary: backend.statisticsPeriod === modelData.days
                                        onClicked: backend.setStatisticsPeriod(modelData.days)
                                    }
                                }
                            }
                            Text {
                                width: parent.width
                                text: backend.statisticsPeriod === 0 ?
                                    "Полные счётчики с Beta 9. Ротация ведёт собственную историю отдельно." :
                                    "Данные по датам собираются с Beta 10; более ранние генерации в периодные графики не входят."
                                font.pixelSize: 10
                                color: "#a5b2c4"
                                wrapMode: Text.Wrap
                            }
                            GridLayout {
                                width: parent.width
                                columns: 2
                                columnSpacing: 10
                                rowSpacing: 10
                                Repeater {
                                    model: [
                                        {title:"СГЕНЕРИРОВАНО БИЛДОВ", number: statsPage.stat.overview.generated, detail:"За всё время наблюдения"},
                                        {title:"ПЕРСОНАЖИ", number: statsPage.stat.overview.seen + " / " + statsPage.stat.overview.total, detail:"Разных персонажей"},
                                        {title:"ОБЫЧНЫЙ / РОТАЦИЯ", number: statsPage.stat.overview.classic + " / " + statsPage.stat.overview.balanced, detail:"По режимам генерации"},
                                        {title:"ПЕРЕБРОСЫ ПЕРКОВ", number: statsPage.stat.overview.rerolls, detail:"Отдельные обновления слотов"}
                                    ]
                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 97
                                        radius: 12
                                        color: win.surface
                                        border.color: win.stroke
                                        Column {
                                            anchors.fill: parent
                                            anchors.margins: 11
                                            spacing: 6
                                            Text {
                                                text: modelData.title
                                                font.pixelSize: 10
                                                font.bold: true
                                                font.letterSpacing: 0.7
                                                color: "#a6b5c8"
                                            }
                                            Text {
                                                text: "" + modelData.number
                                                font.pixelSize: 24
                                                font.bold: true
                                                color: "#f2b3a6"
                                            }
                                            Text { text: modelData.detail; font.pixelSize: 10; color: "#8d9daf" }
                                        }
                                    }
                                }
                            }
                            Rectangle {
                                width: parent.width
                                height: 75
                                radius: 11
                                color: win.colors.panel
                                border.color: win.stroke
                                Row {
                                    anchors.fill: parent
                                    anchors.margins: 12
                                    spacing: 12
                                    Column {
                                        width: (parent.width - 12) / 2
                                        spacing: 5
                                        Text { text: "РАЗНЫХ НАВЫКОВ"; color: win.colors.muted; font.pixelSize: 10 }
                                        Text { text: "" + statsPage.stat.overview.uniquePerks; font.pixelSize: 19; font.bold: true; color: win.colors.text }
                                    }
                                    Column {
                                        width: (parent.width - 12) / 2
                                        spacing: 5
                                        Text { text: "РАЗНЫХ АДДОНОВ"; color: win.colors.muted; font.pixelSize: 10 }
                                        Text { text: "" + statsPage.stat.overview.uniqueAddons; font.pixelSize: 19; font.bold: true; color: win.colors.text }
                                    }
                                }
                            }
                            Text { text: "ПОКАЗАТЬ СТАТИСТИКУ"; color: "#c9d4e0"; font.pixelSize: 11; font.bold: true }
                            Row {
                                width: parent.width
                                spacing: 7
                                Repeater {
                                    model: [
                                        {id:"characters", label:"ПЕРСОНАЖИ"},
                                        {id:"perks", label:"ПЕРКИ"},
                                        {id:"addons", label:"АДДОНЫ"},
                                        {id:"items", label:"ПРЕДМЕТЫ"}
                                    ]
                                    UiButton {
                                        width: (parent.width - 21) / 4
                                        height: 38
                                        label: modelData.label
                                        enabled: modelData.id !== "items" || backend.statisticsSide === "SURVIVOR"
                                        opacity: enabled ? 1 : 0.35
                                        primary: backend.statisticsGroup === modelData.id
                                        onClicked: backend.setStatisticsGroup(modelData.id)
                                    }
                                }
                            }
                            Rectangle {
                                width: parent.width
                                visible: statsPage.stat.overview.generated === 0
                                height: 94
                                radius: 12
                                color: win.surface
                                border.color: win.stroke
                                Column {
                                    anchors.centerIn: parent
                                    spacing: 7
                                    Text { text: "ПОКА НЕТ ГЕНЕРАЦИЙ"; font.pixelSize: 13; font.bold: true; color: "#e9edf3"; anchors.horizontalCenter: parent.horizontalCenter }
                                    Text { text: "Нет данных за выбранный период. Сгенерируй билд или переключи период."; font.pixelSize: 11; color: "#9baabb"; anchors.horizontalCenter: parent.horizontalCenter }
                                }
                            }
                            Row {
                                width: parent.width
                                spacing: 12
                                Repeater {
                                    model: [
                                        {title:"ЧАЩЕ ВСЕГО", kind:"top", color:"#de6e69"},
                                        {title:"РЕЖЕ ВСЕГО", kind:"least", color:"#77a5e2"}
                                    ]
                                    Rectangle {
                                        id: rankingCard
                                        property var selectedRows: modelData.kind === "top" ? statsPage.stat.top : statsPage.stat.least
                                        property color rankingFill: modelData.kind === "top" ? win.colors.chart : win.colors.chartAlt
                                        width: (statsPage.width - 12) / 2
                                        height: Math.max(576, rankingBody.implicitHeight + 22)
                                        radius: 13
                                        color: win.colors.surface
                                        border.color: win.stroke
                                        Column {
                                            id: rankingBody
                                            x: 11; y: 11
                                            width: parent.width - 22
                                            spacing: 9
                                            Text {
                                                text: modelData.title
                                                color: "#e3ebf5"
                                                font.pixelSize: 12
                                                font.bold: true
                                                font.letterSpacing: 0.8
                                            }
                                            Text {
                                                text: modelData.kind === "least" ? "Включая ни разу не выпавших" : "Самые частые выпадения"
                                                color: "#8da0b6"; font.pixelSize: 10
                                                elide: Text.ElideRight
                                            }
                                            Repeater {
                                                model: rankingCard.selectedRows.slice(0, 8)
                                                StatRow {
                                                    width: rankingCard.width - 22
                                                    rowData: modelData
                                                    fillColor: rankingCard.rankingFill
                                                    showIcon: backend.statisticsGroup === "characters"
                                                }
                                            }
                                            Text {
                                                visible: rankingCard.selectedRows.length === 0
                                                text: "Пока нет данных"
                                                color: win.muted
                                                font.pixelSize: 12
                                            }
                                        }
                                    }
                                }
                            }
                            Rectangle {
                                id: staleCard
                                width: parent.width
                                height: 350
                                radius: 13
                                color: win.colors.surface
                                border.color: win.stroke
                                Column {
                                    anchors.fill: parent
                                    anchors.margins: 12
                                    spacing: 10
                                    Text { text: "ДАВНО НЕ ВЫПАДАЛИ"; font.pixelSize: 12; font.bold: true; color: "#e5ecf6" }
                                    Text { text: "За всё время · количество действий с последнего выпадения"; font.pixelSize: 10; color: "#94a4b9" }
                                    Repeater {
                                        model: statsPage.stat.stale.slice(0, 5)
                                        Rectangle {
                                            width: staleCard.width - 24
                                            height: 45
                                            radius: 8
                                            color: win.colors.button
                                            border.color: win.colors.stroke
                                            Text {
                                                x: 10; anchors.verticalCenter: parent.verticalCenter
                                                width: parent.width - 125
                                                elide: Text.ElideRight
                                                text: modelData.name
                                                color: "#edf2f7"; font.pixelSize: 12
                                            }
                                            Text {
                                                anchors.right: parent.right
                                                anchors.rightMargin: 12
                                                anchors.verticalCenter: parent.verticalCenter
                                                text: modelData.since + " действий назад"
                                                color: "#ddbaa1"; font.pixelSize: 10
                                            }
                                        }
                                    }
                                    Text {
                                        visible: statsPage.stat.stale.length === 0
                                        text: "Пока недостаточно данных"
                                        color: win.muted; font.pixelSize: 12
                                    }
                                }
                            }
                            Rectangle {
                                id: recentCard
                                width: parent.width
                                height: 420
                                radius: 13
                                color: win.colors.surface
                                border.color: win.stroke
                                Column {
                                    anchors.fill: parent
                                    anchors.margins: 12
                                    spacing: 10
                                    Text { text: "ИСТОРИЯ ВЫПАДЕНИЙ"; color: "#e5edf5"; font.pixelSize: 12; font.bold: true }
                                    Text { text: "Хранятся последние 100 событий, показаны до 28 за выбранный период"; color: "#92a4b7"; font.pixelSize: 10 }
                                    ListView {
                                        ScrollBar.vertical: QuickScrollBar {  }
                                        id: statsHistory
                                        width: recentCard.width - 24
                                        height: 343
                                        clip: true
                                        spacing: 7
                                        boundsBehavior: Flickable.StopAtBounds
                                        model: statsPage.stat.recent
                                        delegate: Rectangle {
                                            width: statsHistory.width
                                            height: 63
                                            radius: 9
                                            color: win.colors.button
                                            border.color: "#3a4657"
                                            Column {
                                                x: 11
                                                y: 9
                                                width: parent.width - 22
                                                spacing: 7
                                                Row {
                                                    width: parent.width
                                                    spacing: 8
                                                    Text { text: modelData.kind === "reroll" ? "ПЕРЕБРОС" : "БИЛД"; color: "#ec9f98"; font.pixelSize: 10; font.bold: true }
                                                    Text { text: modelData.mode === "balanced" ? "РОТАЦИЯ" : "ОБЫЧНЫЙ"; color: "#9fb1c5"; font.pixelSize: 10 }
                                                    Item { width: 1; height: 1 }
                                                    Text { text: modelData.time; color: "#7e91a5"; font.pixelSize: 10 }
                                                }
                                                Text {
                                                    width: parent.width
                                                    text: modelData.character + " · " + (modelData.perks || []).join(" / ")
                                                    elide: Text.ElideRight
                                                    font.pixelSize: 11
                                                    color: "#eef2f6"
                                                }
                                            }
                                        }
                                    }
                                    Text {
                                        visible: statsHistory.count === 0
                                        text: "Генераций пока нет"
                                        color: win.muted
                                        font.pixelSize: 11
                                    }
                                }
                            }
                            Row {
                                width: parent.width
                                spacing: 10
                                UiButton {
                                    width: (parent.width - 10) / 2
                                    label: "СКОПИРОВАТЬ ОТЧЁТ"
                                    onClicked: backend.copyStatistics()
                                }
                                UiButton {
                                    width: (parent.width - 10) / 2
                                    label: "ОЧИСТИТЬ СТАТИСТИКУ"
                                    onClicked: resetStatsDialog.open()
                                }
                            }
                            Text {
                                width: parent.width
                                text: "Статистика и ротация хранятся отдельно. Очистка этого раздела не меняет шансы выпадений."
                                wrapMode: Text.Wrap
                                font.pixelSize: 11
                                color: "#8fa0b4"
                            }
                        }

                        Column {
                            visible: win.page === "Клики и тайминги"
                            width: parent.width; spacing: 11
                            Text { text: "Калибровка ввода для меню снаряжения"; color: win.muted; font.pixelSize: 12 }
                            Text { text: "Заполните координаты под ваше разрешение и масштаб Windows."; wrapMode: Text.WordWrap; width: parent.width; color: "#d4a59b"; font.pixelSize: 12 }
                            Repeater {
                                model: backend.coordinates
                                delegate: Rectangle {
                                    width: parent.width; height: 45; radius: 8; color: win.surface; border.color: win.stroke
                                    Row {
                                        x: 9; y: 5; spacing: 5
                                        Text { text: modelData.title; width: 170; anchors.verticalCenter: parent.verticalCenter; elide: Text.ElideRight; color: "#aeb9c7"; font.pixelSize: 11 }
                                        UiField { width: 54; text: modelData.x; placeholderText: "X"; onEditingFinished: backend.editCoord(modelData.key, "x", text) }
                                        UiField { width: 54; text: modelData.y; placeholderText: "Y"; onEditingFinished: backend.editCoord(modelData.key, "y", text) }
                                        UiField { visible: modelData.key === "ocr_region"; width: 41; text: modelData.w; placeholderText: "W"; onEditingFinished: backend.editCoord(modelData.key, "w", text) }
                                        UiField { visible: modelData.key === "ocr_region"; width: 41; text: modelData.h; placeholderText: "H"; onEditingFinished: backend.editCoord(modelData.key, "h", text) }
                                        UiButton { width: 82; height: 34; label: "ЗАХВАТ"; onClicked: backend.captureCoord(modelData.key) }
                                    }
                                }
                            }
                            Text { text: "ТАЙМИНГИ"; color: "#d8dfe8"; font.bold: true; font.pixelSize: 12; font.letterSpacing: 1 }
                            Repeater {
                                model: backend.timings
                                delegate: Row {
                                    width: parent.width; height: 38; spacing: 10
                                    Text { text: modelData.title; width: parent.width - 113; elide: Text.ElideRight; anchors.verticalCenter: parent.verticalCenter; color: "#c2cad4"; font.pixelSize: 11 }
                                    UiField { text: modelData.value; width: 103; onEditingFinished: backend.editTiming(modelData.key, text) }
                                }
                            }
                            UiButton { width: parent.width; label: "СОХРАНИТЬ КООРДИНАТЫ И ТАЙМИНГИ"; primary: true; onClicked: backend.saveSettings() }
                            UiButton { width: parent.width; label: "ПРОВЕРИТЬ БАЗУ ДАННЫХ"; onClicked: backend.dataCheck() }
                            UiButton { width: parent.width; label: "КОПИРОВАТЬ ЖУРНАЛ"; onClicked: backend.copyLog() }
                            UiButton { width: parent.width; label: "ОЧИСТИТЬ ЖУРНАЛ"; onClicked: backend.clearLog() }
                            Text { width: parent.width; text: backend.logText; wrapMode: Text.Wrap; color: win.muted; font.pixelSize: 10 }
                        }
                        Column {
                            id: classesPage
                            visible: win.page === "Классы 2v8"
                            width: parent.width; spacing: 12
                            Text {
                                width: parent.width
                                text: "Случайные классы режима 2 против 8"
                                color: win.muted; font.pixelSize: 12
                                wrapMode: Text.Wrap
                            }
                            UiButton { width: parent.width; label: "СГЕНЕРИРОВАТЬ КЛАССЫ"; primary: true; onClicked: backend.rollClasses() }
                            Repeater {
                                id: classCardsRepeater
                                model: backend.classDetails
                                delegate: Rectangle {
                                    id: classCard
                                    width: classesPage.width
                                    property real requiredHeight: classBody.implicitHeight + 28
                                    height: Math.max(126, requiredHeight)
                                    radius: 13
                                    color: win.surface
                                    border.color: win.stroke
                                    Column {
                                        id: classBody
                                        x: 17; y: 14
                                        width: parent.width - 34
                                        spacing: 10
                                        Text {
                                            text: modelData.side === "KILLER" ? "МАНЬЯК" : "ВЫЖИВШИЙ"
                                            width: parent.width
                                            color: win.accent; font.bold: true; font.pixelSize: 10
                                        }
                                        Text {
                                            text: modelData.title
                                            width: parent.width
                                            wrapMode: Text.Wrap
                                            color: win.colors.text; font.bold: true; font.pixelSize: 17
                                        }
                                        Text {
                                            text: modelData.skills
                                            width: parent.width
                                            wrapMode: Text.Wrap
                                            textFormat: Text.PlainText
                                            color: "#b2c0d0"; font.pixelSize: 11
                                        }
                                    }
                                }
                            }
                            UiButton {
                                id: classesCopyButton
                                width: parent.width
                                label: "СКОПИРОВАТЬ КЛАССЫ"
                                onClicked: backend.copyClass()
                            }
                        }

                    }
                }
                Rectangle {
                    Layout.preferredWidth: 320
                    Layout.fillHeight: true
                    color: "#11161e"
                    border.color: "#222b37"
                    Flickable {
                        ScrollBar.vertical: QuickScrollBar {  }
                        anchors.fill: parent
                        contentWidth: width
                        contentHeight: settingsColumn.implicitHeight + 48
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        Column {
                            id: settingsColumn
                            x: 19; y: 26; width: parent.width - 38; spacing: 13
                        Text { text: "НАСТРОЙКИ"; color: "#edf1f5"; font.pixelSize: 16; font.bold: true }
                        Text { text: "Тип генерации"; color: win.muted; font.pixelSize: 11 }
                        Repeater {
                            model: [
                                { key: "mixed", label: "Смешанные" },
                                { key: "unique", label: "Уникальные" },
                                { key: "any", label: "Случайные" },
                                { key: "general", label: "Общие" }
                            ]
                            Rectangle {
                                width: parent.width; height: 38; radius: 8
                                color: backend.mode === modelData.key ? "#35272d" : modeArea.containsMouse ? win.colors.button : "#1b212b"
                                border.color: backend.mode === modelData.key ? win.accent : "#343e4a"
                                Text { text: modelData.label; anchors.verticalCenter: parent.verticalCenter; x: 13; font.pixelSize: 12; color: "#e4e9ee" }
                                Rectangle { width: 7; height: 7; radius: 4; color: win.accent; anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter; visible: backend.mode === modelData.key }
                                MouseArea { id: modeArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: backend.setMode(modelData.key) }
                            }
                        }
                        Item { width: 1; height: 4 }
                        Rectangle { width: parent.width; height: 1; color: win.stroke }
                        OptionRow { title: "Подбирать аддоны"; keyName: "addons" }
                        OptionRow {
                            visible: backend.role === "survivor"
                            title: "Ивентовые предметы (выжившие)"
                            keyName: "event_items"
                        }
                        OptionRow { title: "Случайная внешность"; keyName: "appearance" }
                        OptionRow { title: "Случайный челлендж"; keyName: "challenge" }
                        OptionRow { title: "Только отмеченные навыки и аддоны"; keyName: "owned" }
                        OptionRow { title: "Класс режима 2v8"; keyName: "classes" }
                        OptionRow { title: "Сухой прогон (без кликов)"; keyName: "dry" }
                        OptionRow { title: "Проверять текст результата (нужна область OCR)"; keyName: "ocr" }
                        OptionRow { title: "Выбирать персонажа в игре"; keyName: "select_char" }
                        Rectangle { width: parent.width; height: 1; color: win.stroke }
                        Text { text: "ПАРАМЕТРЫ ПОИСКА И КУРСОРА"; color: "#d8dfe8"; font.pixelSize: 11; font.bold: true }
                        Repeater {
                            model: [
                                { key: "clear", title: "Кликать кнопку очистки" },
                                { key: "verifyclipboard", title: "Проверять буфер обмена" },
                                { key: "restoreclipboard", title: "Восстанавливать буфер" },
                                                                { key: "hoververify", title: "Проверять точность курсора" },
                                { key: "hoverretry", title: "Повторять наведение" }
                            ]
                            Rectangle {
                                width: parent.width; height: 39; radius: 8
                                color: optionMouse.containsMouse ? win.colors.button : "#191f28"
                                Text { x: 10; width: parent.width-53; anchors.verticalCenter: parent.verticalCenter; text: modelData.title; elide: Text.ElideRight; font.pixelSize: 11; color: "#d2dbe5" }
                                Rectangle {
                                    width: 32; height: 18; radius: 9; x: parent.width-43; anchors.verticalCenter: parent.verticalCenter
                                    color: backend.advanced[modelData.key] ? win.accent : "#454e5b"
                                    Rectangle { width: 12; height: 12; radius: 6; y: 3; x: backend.advanced[modelData.key] ? 17 : 3; color: "#ffffff" }
                                }
                                MouseArea { id: optionMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: backend.toggleAdvanced(modelData.key) }
                            }
                        }
                        Text { text: "Номер иконки результата (1–9)"; color: win.muted; font.pixelSize: 11 }
                        UiField { width: parent.width; text: backend.advanced.resultIndex; onEditingFinished: backend.setAdvanced("resultIndex", text) }
                        Text { text: "Клавиша аварийного стопа"; color: win.muted; font.pixelSize: 11 }
                        UiField { width: parent.width; text: backend.advanced.abortKey; onEditingFinished: backend.setAdvanced("abortKey", text) }
                        Text { text: "Тип челленджей"; color: win.muted; font.pixelSize: 11 }
                        Row {
                            width: parent.width
                            spacing: 5
                            Repeater {
                                model: [
                                    { key: "mixed", text: "Смешанные", icon: "mixed" },
                                    { key: "general", text: "Обычные", icon: "general" },
                                    { key: "power", text: "Способности", icon: "power" }
                                ]
                                UiButton {
                                    width: (parent.width - 10) / 3
                                    height: 34; label: modelData.text
                                    iconName: modelData.icon
                                    primary: backend.advanced.challengeType === modelData.key
                                    onClicked: backend.setAdvanced("challengeType", modelData.key)
                                }
                            }
                        }
                        Text {
                            width: parent.width
                            text: "Задания на силы привязаны к конкретному маньяку. Для выживших используются обычные челленджи."
                            color: win.muted; font.pixelSize: 10; wrapMode: Text.Wrap
                        }
                        Text { text: "Сложность челленджа"; color: win.muted; font.pixelSize: 11 }
                        Row {
                            spacing: 5
                            Repeater {
                                model: [
                                    { key: "any", text: "Любая" },
                                    { key: "easy", text: "Лёгкая" },
                                    { key: "medium", text: "Средняя" },
                                    { key: "hard", text: "Тяжёлая" }
                                ]
                                UiButton {
                                    width: 65; height: 34; label: modelData.text
                                    primary: backend.advanced.challengeDiff === modelData.key
                                    onClicked: backend.setAdvanced("challengeDiff", modelData.key)
                                }
                            }
                        }

                        Rectangle { width: parent.width; height: 1; color: win.stroke }
                        UiButton { width: parent.width; enabled: !backend.running; label: backend.running ? "ЭКИПИРОВКА ВЫПОЛНЯЕТСЯ..." : "ЭКИПИРОВАТЬ В ИГРЕ"; onClicked: backend.equip() }
                        UiButton { width: parent.width; label: "СТОП АВТОМАТИЗАЦИИ (" + backend.advanced.abortKey.toUpperCase() + ")"; onClicked: backend.stop() }
                        Rectangle { width: parent.width; height: 1; color: win.stroke }
                        Text { text: "ОБНОВЛЕНИЯ"; color: "#d8dfe8"; font.pixelSize: 11; font.bold: true; font.letterSpacing: 1 }
                        UiButton { width: parent.width; enabled: !backend.updateBusy; label: backend.updateBusy ? "ПОДОЖДИТЕ..." : "ПРОВЕРИТЬ ОБНОВЛЕНИЯ"; onClicked: backend.checkUpdate() }
                        Text { width: parent.width; text: backend.updateText || ("Версия " + backend.installedVersion); wrapMode: Text.Wrap; color: win.muted; font.pixelSize: 11 }
                        UiButton { visible: backend.updateAvailable; enabled: !backend.updateBusy; width: parent.width; label: "СКАЧАТЬ И УСТАНОВИТЬ"; primary: true; onClicked: backend.installUpdate() }

                        Rectangle {
                            width: parent.width
                            height: Math.max(83, settingsWarningText.implicitHeight + 26)
                            color: "#251f24"; radius: 10; border.color: "#49353e"
                            Text {
                                id: settingsWarningText
                                x: 13; y: 13; width: parent.width - 26
                                wrapMode: Text.Wrap
                                text: "Нажми «Экипировать» и вручную переключись в DBD во время отсчёта (не меньше 3 секунд). Поиск процесса игры отключён. При переключении в другое окно клики остановятся. Стоп: " + backend.advanced.abortKey.toUpperCase() + "."
                                color: "#dec0bf"; font.pixelSize: 11
                            }
                        }
                    }
                    }
                }
            }
        }
    }
    Rectangle {
        anchors.bottom: parent.bottom
        width: parent.width; height: 30
        color: "#121720"
        border.color: "#28323d"
        Text { anchors.left: parent.left; anchors.leftMargin: 19; anchors.verticalCenter: parent.verticalCenter; text: backend.status; color: "#9aa8ba"; font.pixelSize: 11; elide: Text.ElideRight; width: parent.width - 45 }
    }
    Popup {
        id: addonPopup
        parent: Overlay.overlay
        x: Math.max(20, (win.width - width) / 2)
        y: Math.max(50, (win.height - height) / 2)
        width: Math.min(480, win.width - 48)
        height: Math.min(472, win.height - 90)
        modal: true
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle {
            radius: 16
            color: "#1a222e"
            border.color: "#556277"
            border.width: 1
        }
        contentItem: Flickable {
            ScrollBar.vertical: QuickScrollBar {  }
            contentWidth: width
            contentHeight: infoBody.implicitHeight + 16
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            Column {
                id: infoBody
                x: 10; y: 10
                width: parent.width - 20
                spacing: 15
                Row {
                    width: parent.width
                    spacing: 11
                    ArtThumb {
                        pixels: 88
                        iconKey: backend.addonEffect.name
                        placeholder: "ADD"
                    }
                    Column {
                        width: parent.width - 105
                        spacing: 8
                        Text { text: "СПРАВКА ПО АДДОНУ"; color: "#a7b6c8"; font.pixelSize: 10; font.bold: true }
                        Text {
                            text: backend.addonEffect.name
                            width: parent.width
                            wrapMode: Text.Wrap
                            font.pixelSize: 17
                            font.bold: true
                            color: "#f6f8fb"
                        }
                        Text {
                            text: backend.addonEffect.english || ""
                            width: parent.width
                            wrapMode: Text.Wrap
                            font.pixelSize: 11
                            color: "#98aaba"
                        }
                    }
                }
                Rectangle { width: parent.width; height: 1; color: "#364255" }
                Text {
                    text: backend.addonEffect.verified ? "КРАТКОЕ ОПИСАНИЕ ЭФФЕКТА" : "КАТЕГОРИИ ЭФФЕКТА"
                    color: backend.addonEffect.verified ? "#e6a59c" : win.colors.muted
                    font.pixelSize: 11
                    font.bold: true
                }
                Text {
                    text: backend.addonEffect.effect ||
                        (backend.addonEffect.summary ?
                          backend.addonEffect.summary + ". Точные значения и условия действия смотри в справочнике wiki.gg." :
                          "Проверенное описание пока отсутствует. Открой справочник wiki.gg для актуальных механик.")
                    width: parent.width
                    font.pixelSize: 13
                    color: "#edf0f6"
                    wrapMode: Text.Wrap
                }
                Text { text: "ОБЛАСТИ ВЛИЯНИЯ"; color: win.colors.muted; font.pixelSize: 11; font.bold: true }
                Text {
                    text: backend.addonEffect.categories.length > 0 ?
                        backend.addonEffect.categories.join(" · ") :
                        "Нет данных в локальном кэше. Категории wiki.gg подгружаются при наличии интернета."
                    width: parent.width
                    font.pixelSize: 12
                    color: win.colors.muted
                    wrapMode: Text.Wrap
                }
                Text {
                    text: "Данные могут измениться после патча DBD. Категории — не замена точному описанию игрового эффекта."
                    width: parent.width
                    font.pixelSize: 11
                    color: "#8497aa"
                    wrapMode: Text.Wrap
                }
                UiButton {
                    width: parent.width
                    primary: true
                    label: "ОТКРЫТЬ ПОДРОБНУЮ СПРАВКУ WIKI.GG"
                    onClicked: backend.openAddonSource()
                }
                UiButton {
                    width: parent.width
                    label: "ЗАКРЫТЬ"
                    onClicked: addonPopup.close()
                }
            }
        }
    }

    Popup {
        id: resetRotationPopup
        parent: Overlay.overlay
        x: Math.max(20, (win.width - width) / 2)
        y: Math.max(50, (win.height - height) / 2)
        width: Math.min(410, win.width - 40)
        height: 212
        modal: true
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle {
            radius: 14
            color: win.colors.panel
            border.color: "#754e53"
            border.width: 1
        }
        contentItem: Column {
            spacing: 14
            padding: 14
            Text {
                text: "СБРОСИТЬ ИСТОРИЮ РОТАЦИИ?"
                color: "#f2f4f8"
                font.bold: true
                font.pixelSize: 15
            }
            Text {
                width: resetRotationPopup.width - 35
                text: "Будет очищена статистика только для выбранной стороны (маньяки или выжившие). Настройки и история билдов останутся."
                color: win.colors.muted
                font.pixelSize: 12
                wrapMode: Text.Wrap
            }
            Row {
                spacing: 10
                UiButton {
                    width: (resetRotationPopup.width - 48) / 2
                    label: "ОТМЕНА"
                    onClicked: resetRotationPopup.close()
                }
                UiButton {
                    width: (resetRotationPopup.width - 48) / 2
                    primary: true
                    label: "СБРОСИТЬ"
                    onClicked: {
                        backend.resetRotation();
                        resetRotationPopup.close();
                    }
                }
            }
        }
    }
    Popup {
        id: perkPopup
        property var info: ({ slot: 0, name: "", owner: "", kind: "", filled: false, locked: false })
        parent: Overlay.overlay
        x: Math.max(16, (win.width - width) / 2)
        y: Math.max(45, (win.height - height) / 2)
        width: Math.min(462, win.width - 40)
        height: Math.min(480, win.height - 90)
        modal: true
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle {
            radius: 16
            color: "#1a2430"
            border.color: "#536173"
            border.width: 1
        }
        contentItem: Flickable {
            ScrollBar.vertical: QuickScrollBar {  }
            contentWidth: width
            contentHeight: perkInfoBody.implicitHeight + 34
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            Column {
                id: perkInfoBody
                x: 17
                y: 17
                width: parent.width - 34
                spacing: 13
            Row {
                spacing: 14
                ArtThumb {
                    pixels: 98
                    iconKey: perkPopup.info.filled ? perkPopup.info.name : ""
                    placeholder: "PERK"
                }
                Column {
                    spacing: 8
                    width: perkPopup.width - 140
                    Text {
                        text: "ПОДРОБНОСТИ · СЛОТ " + perkPopup.info.slot
                        color: "#92a5b9"
                        font.pixelSize: 10
                        font.bold: true
                    }
                    Text {
                        text: perkPopup.info.name
                        width: parent.width
                        color: win.colors.text
                        font.pixelSize: 18
                        font.bold: true
                        wrapMode: Text.Wrap
                    }
                    Text {
                        text: perkPopup.info.kind
                        width: parent.width
                        color: "#e2b09b"
                        font.pixelSize: 12
                    }
                }
            }
            Rectangle {
                width: parent.width
                height: 1
                color: "#354456"
            }
            Text {
                text: "ПЕРСОНАЖ / ИСТОЧНИК НАВЫКА"
                color: "#95a8bc"
                font.pixelSize: 11
                font.bold: true
            }
            Text {
                text: perkPopup.info.owner || "Общий навык без привязки к персонажу"
                color: "#eef1f7"
                width: parent.width
                wrapMode: Text.Wrap
                font.pixelSize: 13
            }
            Text {
                text: "КРАТКОЕ ОПИСАНИЕ ЭФФЕКТА"
                color: win.colors.accentSoft
                font.pixelSize: 11
                font.bold: true
            }
            Text {
                text: perkPopup.info.description || "Для этого навыка краткая справка пока недоступна."
                color: "#8c9eaf"
                font.pixelSize: 11
                width: parent.width
                wrapMode: Text.Wrap
            }
            Text {
                text: "Краткая справка без патч-зависимых чисел. Точные значения и условия проверяйте в игре или на DBD Wiki."
                color: "#8094a9"
                width: parent.width
                wrapMode: Text.Wrap
                font.pixelSize: 10
            }
            Row {
                width: parent.width
                spacing: 9
                UiButton {
                    width: (parent.width - 9) / 2
                    height: 37
                    primary: perkPopup.info.locked
                    label: perkPopup.info.locked ? "СНЯТЬ ФИКСАЦИЮ" : "ЗАКРЕПИТЬ"
                    onClicked: {
                        backend.toggleLock(perkPopup.info.slot - 1);
                        perkPopup.info = backend.perkInfo(perkPopup.info.slot - 1);
                    }
                }
                UiButton {
                    width: (parent.width - 9) / 2
                    height: 37
                    label: "ПЕРЕБРОСИТЬ"
                    onClicked: {
                        backend.reroll(perkPopup.info.slot - 1);
                        perkPopup.info = backend.perkInfo(perkPopup.info.slot - 1);
                    }
                }
            }
            UiButton {
                width: parent.width
                height: 37
                label: "СПРАВОЧНИК НАВЫКОВ DBD WIKI"
                onClicked: backend.openPerkReference()
            }
            UiButton {
                width: parent.width
                height: 32
                label: "ЗАКРЫТЬ"
                onClicked: perkPopup.close()
            }
            }
        }
    }

    Popup {
        id: resetStatsDialog
        parent: Overlay.overlay
        x: Math.max(16, (win.width - width) / 2)
        y: Math.max(42, (win.height - height) / 2)
        width: Math.min(415, win.width - 40)
        height: 202
        modal: true
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle { color: win.colors.panel; radius: 15; border.color: "#78545c" }
        contentItem: Column {
            padding: 15
            spacing: 14
            Text { text: "ОЧИСТИТЬ СТАТИСТИКУ?"; font.bold: true; font.pixelSize: 16; color: "#f0f3f9" }
            Text {
                text: "Счётчики и историю выбранной стороны нельзя будет восстановить. Настройки и веса сбалансированной ротации не изменятся."
                width: resetStatsDialog.width - 36
                wrapMode: Text.Wrap
                color: "#a9b9ca"; font.pixelSize: 11
            }
            Row {
                spacing: 10
                UiButton { width: (resetStatsDialog.width - 44) / 2; height: 39; label: "ОТМЕНА"; onClicked: resetStatsDialog.close() }
                UiButton {
                    width: (resetStatsDialog.width - 44) / 2
                    height: 39
                    primary: true
                    label: "ОЧИСТИТЬ"
                    onClicked: { backend.resetStatistics(); resetStatsDialog.close() }
                }
            }
        }
    }

    Popup {
        id: favoriteEditor
        property string editingId: ""
        function openNew() {
            if (!backend.detail.hasBuild) {
                backend.saveFavorite("", "", "");
                return;
            }
            editingId = "";
            favoriteTitle.text = backend.detail.char + " — мой билд";
            favoriteGroup.text = "Мои сборки";
            favoriteNote.text = "";
            open();
        }
        function openEdit(entry) {
            editingId = entry.id;
            favoriteTitle.text = entry.title;
            favoriteGroup.text = entry.collection;
            favoriteNote.text = entry.note;
            open();
        }
        parent: Overlay.overlay
        x: Math.max(16, (win.width - width) / 2)
        y: Math.max(40, (win.height - height) / 2)
        width: Math.min(460, win.width - 40)
        height: 365
        modal: true
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle {
            color: win.colors.panel
            radius: 15
            border.color: "#6b4d57"
        }
        contentItem: Column {
            padding: 14
            spacing: 10
            Text {
                text: favoriteEditor.editingId ? "РЕДАКТИРОВАТЬ ИЗБРАННОЕ" : "СОХРАНИТЬ БИЛД"
                color: win.colors.text
                font.pixelSize: 16
                font.bold: true
            }
            Text { text: "НАЗВАНИЕ"; font.pixelSize: 10; font.bold: true; color: win.colors.muted }
            UiField { id: favoriteTitle; width: favoriteEditor.width - 34; maximumLength: 72; placeholderText: "Название билда" }
            Text { text: "КОЛЛЕКЦИЯ"; font.pixelSize: 10; font.bold: true; color: win.colors.muted }
            UiField { id: favoriteGroup; width: favoriteEditor.width - 34; maximumLength: 48; placeholderText: "Например: любимые / маньяки / эксперименты" }
            Text { text: "ЗАМЕТКА"; font.pixelSize: 10; font.bold: true; color: win.colors.muted }
            UiField { id: favoriteNote; width: favoriteEditor.width - 34; maximumLength: 240; placeholderText: "Почему нравится этот билд?" }
            Row {
                width: favoriteEditor.width - 34
                spacing: 9
                UiButton {
                    width: (parent.width - 9) / 2
                    height: 37
                    label: "ОТМЕНА"
                    onClicked: favoriteEditor.close()
                }
                UiButton {
                    width: (parent.width - 9) / 2
                    height: 37
                    primary: true
                    label: favoriteEditor.editingId ? "СОХРАНИТЬ" : "ДОБАВИТЬ В ИЗБРАННОЕ"
                    onClicked: {
                        var success = favoriteEditor.editingId ?
                            backend.editFavorite(favoriteEditor.editingId, favoriteTitle.text, favoriteGroup.text, favoriteNote.text) :
                            backend.saveFavorite(favoriteTitle.text, favoriteGroup.text, favoriteNote.text);
                        if (success)
                            favoriteEditor.close();
                    }
                }
            }
        }
    }

    Popup {
        id: deleteFavoriteDialog
        property string favoriteId: ""
        property string favoriteTitle: ""
        parent: Overlay.overlay
        x: Math.max(16, (win.width - width) / 2)
        y: Math.max(40, (win.height - height) / 2)
        width: Math.min(430, win.width - 40)
        height: 190
        modal: true
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle {
            color: win.colors.panel
            radius: 14
            border.color: "#80545d"
        }
        contentItem: Column {
            padding: 14
            spacing: 14
            Text { text: "УДАЛИТЬ ИЗБРАННЫЙ БИЛД?"; color: "#f3f5fa"; font.pixelSize: 15; font.bold: true }
            Text {
                width: deleteFavoriteDialog.width - 36
                text: deleteFavoriteDialog.favoriteTitle + " будет удалён из библиотеки. Отменить это действие не получится."
                color: "#a9bacd"
                wrapMode: Text.Wrap
                font.pixelSize: 12
            }
            Row {
                width: deleteFavoriteDialog.width - 34
                spacing: 9
                UiButton {
                    width: (parent.width - 9) / 2
                    height: 37
                    label: "ОТМЕНА"
                    onClicked: deleteFavoriteDialog.close()
                }
                UiButton {
                    width: (parent.width - 9) / 2
                    height: 37
                    primary: true
                    label: "УДАЛИТЬ"
                    onClicked: {
                        backend.deleteFavorite(deleteFavoriteDialog.favoriteId);
                        deleteFavoriteDialog.close();
                    }
                }
            }
        }
    }

    Popup {
        id: appearanceReset
        parent: Overlay.overlay
        x: Math.max(16, (win.width - width) / 2)
        y: Math.max(40, (win.height - height) / 2)
        width: Math.min(430, win.width - 40)
        height: 200
        focus: true; modal: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle { color: win.colors.panel; radius: 14; border.color: win.stroke }
        contentItem: Column {
            padding: 14; spacing: 16
            Text { text: "СБРОС ОФОРМЛЕНИЯ"; font.pixelSize: 16; font.bold: true; color: win.colors.text }
            Text {
                width: appearanceReset.width - 34; wrapMode: Text.WordWrap
                text: "Вернуть красную тему, 100% масштаб и плавные анимации? Игровые настройки не изменятся."
                color: win.muted; font.pixelSize: 12
            }
            Row {
                width: appearanceReset.width - 34; spacing: 9
                UiButton { width: (parent.width - 9) / 2; height: 36; label: "ОТМЕНА"; onClicked: appearanceReset.close() }
                UiButton {
                    width: (parent.width - 9) / 2; height: 36
                    label: "СБРОСИТЬ"; primary: true
                    onClicked: { backend.resetAppearance(); appearanceReset.close() }
                }
            }
        }
    }


    // Preview stays above the clipped catalog and scrollable workspace.
    // No MouseArea here: the actual source keeps pointer grab until release.
    Item {
        id: builderDragOverlay
        anchors.fill: parent
        z: 1000
        visible: makerPage.visible && makerPage.draggingPerk
        Rectangle {
            x: Math.max(0, Math.min(parent.width - width,
                                   makerPage.dragPointerX + 14))
            y: Math.max(0, Math.min(parent.height - height,
                                   makerPage.dragPointerY + 14))
            width: 245
            height: 56
            radius: 10
            color: win.colors.panel
            border.color: win.accent
            border.width: 2
            opacity: 0.95
            ArtThumb { x: 6; y: 5; pixels: 46; iconKey: makerPage.draggedPerkName; placeholder: "PERK" }
            Text {
                x: 61; anchors.verticalCenter: parent.verticalCenter
                width: parent.width - 70
                text: makerPage.draggedPerkName
                font.pixelSize: 12
                color: win.colors.text
                elide: Text.ElideRight
            }
        }
    }

    property bool layoutSmokePassed: false
    property string layoutSmokeError: ""
    function verifyClassLayout() {
        layoutSmokePassed = false;
        layoutSmokeError = "";
        if (classCardsRepeater.count < 2) {
            layoutSmokeError = "Two classes were not rendered";
            return;
        }
        var lowest = -1;
        for (var i = 0; i < classCardsRepeater.count; ++i) {
            var card = classCardsRepeater.itemAt(i);
            if (!card || card.height + 0.5 < card.requiredHeight) {
                layoutSmokeError = "Class card " + i + " does not fit its complete text";
                return;
            }
            var top = card.mapToItem(classesPage, 0, 0).y;
            if (top < lowest - 0.5) {
                layoutSmokeError = "Class card " + i + " overlaps the previous card";
                return;
            }
            lowest = top + card.height;
        }
        if (classesCopyButton.y < lowest + 8) {
            layoutSmokeError = "Copy button overlaps the last class";
            return;
        }
        layoutSmokePassed = true;
    }

    // Real Qt-Quick geometry check for the redesigned, content-led build view.
    property bool designSmokePassed: false
    property string designSmokeError: ""
    function verifyDesignLayout() {
        designSmokePassed = false;
        designSmokeError = "";
        if (page !== "Билд") {
            designSmokeError = "Build page not selected";
            return;
        }
        if (generatedHero.width < 300 || heroBody.width < 250 ||
            generatedHero.height + 1 < heroBody.height + 36) {
            designSmokeError = "Hero size: card=" + generatedHero.width + "x" +
                generatedHero.height + " inner=" + heroBody.width + "x" +
                heroBody.height + " implicit=" + heroBody.implicitHeight;
            return;
        }
        if (Math.abs(generatedHero.width - content.width) > 1.0) {
            designSmokeError = "Hero card is not aligned to content grid";
            return;
        }
        if (sidebarContents.width < 180 || work.width < 360) {
            designSmokeError = "Navigation or page collapsed";
            return;
        }
        designSmokePassed = true;
    }

    // QML state transitions exercised by CI without using game input.
    function runBuilderSmoke() {
        builderSmokeStatus = 0;
        builderSmokeError = "";
        try {
            makerPage.changeSide("SURVIVOR");
            var rows = backend.searchPerks("SURVIVOR", "");
            if (rows.length < 4) throw new Error("Too few perks");
            var a = rows[0].name, b = rows[1].name, c = rows[2].name;
            makerPage.assignPerk(a, 0);
            makerPage.assignPerk(b, 1);
            makerPage.assignPerk(c, 2);
            makerPage.movePerk(0, 1);
            if (makerPage.perkNameAt(0) !== b || makerPage.perkNameAt(1) !== a)
                throw new Error("Perk swap failed");
            makerPage.assignPerk(a, 2);
            if (makerPage.perkNameAt(2) !== a || makerPage.perkNameAt(1) !== c)
                throw new Error("Move must swap, not duplicate");
            makerPage.clearPerk(0);
            if (makerPage.perkNameAt(0) !== "")
                throw new Error("Clear slot failed");
            makerPage.cancelPerkDrag();
            if (makerPage.draggingPerk || makerPage.hoverSlot !== -1)
                throw new Error("Drag cancellation failed");
            makerPage.changeSide("KILLER");
            if (makerPage.perkNameAt(1) !== "" || makerPage.perkNameAt(2) !== "")
                throw new Error("Side change did not clear selected perks");
            makerPage.changeSide("SURVIVOR");
            makerPage.assignPerk(a, 0);
            makerPage.assignPerk(b, 1);
            builderSmokeExpectedA = a;
            builderSmokeExpectedB = b;
            builderSmokeStatus = 1;
        } catch (e) {
            builderSmokeError = "" + e;
            builderSmokeStatus = -1;
        }
    }

    // Two-step geometry capture: a side change schedules Qt Quick layout work.
    // Scroll first, then measure slot coordinates after the event loop polishes.
    function prepareBuilderDrag() {
        var firstSlot = makerSlotRepeater.itemAt(0);
        if (!firstSlot) {
            builderSmokeStatus = -1;
            builderSmokeError = "No slot delegate";
            return;
        }
        var slotLocation = firstSlot.mapToItem(work.contentItem, 0, 0);
        work.contentY = Math.max(0, slotLocation.y - 120);
    }

    function captureBuilderDrag() {
        var first = makerSlotRepeater.itemAt(0);
        var second = makerSlotRepeater.itemAt(1);
        if (!first || !second) {
            builderSmokeStatus = -1;
            builderSmokeError = "Slots unavailable after polish";
            return;
        }
        var start = first.mapToItem(win.contentItem, 105, 43);
        var target = second.mapToItem(win.contentItem, 105, 43);
        if (makerPage.slotFromPointer(start.x, start.y) !== 0) {
            builderSmokeStatus = -1;
            builderSmokeError = "Slot hit-test failed after layout";
            return;
        }
        if (makerPage.slotFromPointer(-100, -100) !== -1) {
            builderSmokeStatus = -1;
            builderSmokeError = "Outside viewport accepted";
            return;
        }
        builderSmokeStartX = start.x;
        builderSmokeStartY = start.y;
        builderSmokeTargetX = target.x;
        builderSmokeTargetY = target.y;
    }

    function evaluateBuilderDrag() {
        builderSmokeDragPassed =
            makerPage.perkNameAt(0) === builderSmokeExpectedB &&
            makerPage.perkNameAt(1) === builderSmokeExpectedA;
        if (!builderSmokeDragPassed) {
            builderSmokeError = "Pointer swap failed: " +
                makerPage.perkNameAt(0) + " | " + makerPage.perkNameAt(1);
        }
    }

    function captureBuilderCatalogDrag() {
        var data = backend.searchPerks("SURVIVOR", "");
        var row = makerPerks.itemAtIndex(2);
        var targetSlot = makerSlotRepeater.itemAt(2);
        if (!row || !targetSlot || data.length < 3) {
            builderSmokeStatus = -1;
            builderSmokeError = "Builder catalog row unavailable";
            return;
        }
        var start = row.mapToItem(win.contentItem, 105, 28);
        var target = targetSlot.mapToItem(win.contentItem, 105, 43);
        var withinScroll = work.mapFromItem(win.contentItem, start.x, start.y);
        if (withinScroll.x < 0 || withinScroll.y < 0 ||
                withinScroll.x >= work.width || withinScroll.y >= work.height) {
            builderSmokeStatus = -1;
            builderSmokeError = "Catalog row is outside viewport";
            return;
        }
        if (makerPage.slotFromPointer(target.x, target.y) !== 2) {
            builderSmokeStatus = -1;
            builderSmokeError = "Catalog target slot not hit-tested";
            return;
        }
        builderSmokeCatalogX = start.x;
        builderSmokeCatalogY = start.y;
        builderSmokeCatalogTargetX = target.x;
        builderSmokeCatalogTargetY = target.y;
        builderSmokeCatalogExpected = data[2].name;
    }

    function evaluateBuilderCatalogDrag() {
        builderSmokeCatalogPassed = makerPage.perkNameAt(2) === builderSmokeCatalogExpected;
        if (!builderSmokeCatalogPassed)
            builderSmokeError = "Catalog drop failed: " + makerPage.perkNameAt(2) +
                " expected " + builderSmokeCatalogExpected;
    }

    Shortcut { sequence: "F5"; onActivated: backend.generate() }
    Shortcut { sequence: "F6"; onActivated: backend.copyBuild() }
    Shortcut { sequence: "F9"; onActivated: backend.placeholder("STOP") }
}
