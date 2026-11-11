import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

ApplicationWindow {
    id: win
    visible: true
    width: 1350
    height: 800
    minimumWidth: 1000
    minimumHeight: 650
    color: "#0c0f14"
    title: "DBD Ultimate Search Randomizer | Qt Beta 11"
    property string page: "Билд"
    property color surface: "#171d26"
    property color stroke: "#2f3947"
    property color muted: "#8995a5"
    property color accent: "#ea5753"
    font.family: "Segoe UI"
    onClosing: backend.close()

    component UiButton: Rectangle {
        id: button
        property string label: ""
        property bool primary: false
        signal clicked()
        implicitHeight: 44
        radius: 10
        color: primary ? (over.containsMouse ? "#fa6d66" : win.accent) :
                         (over.containsMouse ? "#2d3645" : "#242b36")
        border.width: primary ? 0 : 1
        border.color: win.stroke
        Behavior on color { ColorAnimation { duration: 140 } }
        Text {
            anchors.centerIn: parent
            text: button.label
            font.pixelSize: 13
            font.weight: Font.DemiBold
            color: "white"
        }
        MouseArea {
            id: over
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: button.clicked()
        }
    }

    component UiField: TextField {
        color: "#e6ebf3"
        font.pixelSize: 12
        height: 39
        padding: 9
        selectByMouse: true
        placeholderTextColor: "#657385"
        selectionColor: "#87413f"
        background: Rectangle {
            radius: 8
            color: "#1e2631"
            border.color: parent.activeFocus ? "#dd5956" : "#374251"
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
        color: "#252e39"
        border.width: 1
        border.color: "#435065"
        clip: true
        Image {
            id: portrait
            anchors.fill: parent
            anchors.margins: 3
            fillMode: Image.PreserveAspectFit
            asynchronous: true
            smooth: true
            source: backend.iconVersion >= 0 ? backend.iconPath(art.iconKey) : ""
        }
        Text {
            anchors.centerIn: parent
            visible: portrait.status !== Image.Ready
            text: art.placeholder
            font.pixelSize: art.pixels > 100 ? 18 : 10
            color: "#899aac"
            font.bold: true
        }
    }

    component NavItem: Rectangle {
        id: nav
        property string label: ""
        property int ordinal: 0
        signal clicked()
        width: parent.width
        height: 48
        radius: 9
        color: win.page === label ? "#262e3a" : hover.containsMouse ? "#1c222c" : "transparent"
        Rectangle { width: 3; height: parent.height - 16; anchors.verticalCenter: parent.verticalCenter; color: win.accent; visible: win.page === nav.label; radius: 2 }
        Row {
            anchors.verticalCenter: parent.verticalCenter
            x: 16
            spacing: 14
            Text { text: (nav.ordinal < 10 ? "0" : "") + nav.ordinal; color: win.page === nav.label ? win.accent : "#67768a"; font.pixelSize: 11; font.weight: Font.Bold; anchors.verticalCenter: parent.verticalCenter }
            Text { text: nav.label; color: win.page === nav.label ? "white" : "#a9b3c2"; font.pixelSize: 13; font.weight: win.page === nav.label ? Font.Bold : Font.Normal }
        }
        MouseArea { id: hover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: nav.clicked() }
    }

    component StatRow: Rectangle {
        id: statLine
        property var rowData: ({name:"", count:0, fraction:0, since:-1})
        property color fillColor: "#e46b67"
        property bool showIcon: false
        width: parent.width
        height: 56
        radius: 9
        color: "#202a36"
        border.color: "#354252"
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
            color: "#edf2f9"
            font.pixelSize: 11
            font.bold: true
            elide: Text.ElideRight
        }
        Text {
            anchors.right: parent.right
            anchors.rightMargin: 12
            y: 6
            text: statLine.rowData.count + "×"
            color: "#f0c4ae"
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
                Behavior on width { NumberAnimation { duration: 230; easing.type: Easing.OutCubic } }
            }
        }
    }

    component OptionRow: Rectangle {
        id: option
        property string title: ""
        property string keyName: ""
        height: 47
        width: parent.width
        color: pointer.containsMouse ? "#232a35" : "transparent"
        radius: 8
        Text {
            x: 12
            width: parent.width - 84
            anchors.verticalCenter: parent.verticalCenter
            text: option.title
            elide: Text.ElideRight
            color: "#d9dfe8"
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
                Behavior on x { NumberAnimation { duration: 120 } }
            }
        }
        MouseArea { id: pointer; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: backend.toggleOption(option.keyName) }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0
        Rectangle {
            Layout.preferredWidth: 228
            Layout.fillHeight: true
            color: "#11151c"
            border.color: "#202734"
            Column {
                x: 18
                y: 25
                width: parent.width - 36
                spacing: 8
                Image {
                    width: 51; height: 51
                    source: "assets/app_icon.png"
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                    anchors.horizontalCenter: parent.horizontalCenter
                }
                Item { width: 1; height: 12 }
                Text { anchors.horizontalCenter: parent.horizontalCenter; text: "DBD RANDOMIZER"; color: "#f0f2f5"; font.pixelSize: 13; font.weight: Font.Bold; font.letterSpacing: 1.1 }
                Text { anchors.horizontalCenter: parent.horizontalCenter; text: "QT QUICK • BETA 11"; color: "#7e8999"; font.pixelSize: 10; font.letterSpacing: 1 }
                Item { height: 10 }
                NavItem { ordinal: 1; label: "Билд"; onClicked: win.page = label }
                NavItem { ordinal: 2; label: "Конструктор"; onClicked: win.page = label }
                NavItem { ordinal: 3; label: "Избранное"; onClicked: win.page = label }
                NavItem { ordinal: 4; label: "Билды сообщества"; onClicked: win.page = label }
                NavItem { ordinal: 5; label: "Персонажи"; onClicked: win.page = label }
                NavItem { ordinal: 6; label: "Внешность"; onClicked: win.page = label }
                NavItem { ordinal: 7; label: "Статистика"; onClicked: win.page = label }
                NavItem { ordinal: 8; label: "Клики и тайминги"; onClicked: win.page = label }
                NavItem { ordinal: 9; label: "Классы 2v8"; onClicked: win.page = label }
                Item { height: 10 }
                Rectangle { width: parent.width; height: 1; color: "#26303d" }
                Item { height: 10 }
                UiButton { width: parent.width; label: "Новый билд"; onClicked: { win.page = "Билд"; backend.generate() } }
                UiButton { width: parent.width; label: "Копировать билд"; onClicked: backend.copyBuild() }
                Item { height: 10 }
                Rectangle {
                    width: parent.width; height: 74; radius: 10; color: "#25232a"
                    border.color: "#534046"
                    Column {
                        anchors.centerIn: parent; spacing: 8
                        Text { text: "QT ИНТЕРФЕЙС"; color: "#f2b2a7"; font.pixelSize: 10; font.weight: Font.Bold }
                        Text { text: "Оригинальные игровые данные\nи Qt-интерфейс"; color: "#c1b9bc"; font.pixelSize: 11 }
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
                    id: work
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    contentWidth: width
                    contentHeight: content.implicitHeight + 60
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    Column {
                        id: content
                        x: 26; y: 25
                        width: work.width - 52
                        spacing: 18
                        Text { text: win.page === "Билд" ? "Генератор билда" : win.page; font.pixelSize: 27; font.weight: Font.Bold; color: "#f3f5f8" }
                        Text { text: "Новый интерфейс с оригинальной базой DBD и автоматизацией"; font.pixelSize: 12; color: win.muted }
                        Rectangle { width: parent.width; height: 1; color: win.stroke }
                        Column {
                            visible: win.page === "Билд"
                            width: parent.width
                            spacing: 18
                            Row {
                                width: parent.width; spacing: 10
                                UiButton { width: (parent.width - 10) / 2; label: "ВЫЖИВШИЙ"; primary: backend.role === "survivor"; onClicked: backend.setRole("survivor") }
                                UiButton { width: (parent.width - 10) / 2; label: "МАНЬЯК"; primary: backend.role === "killer"; onClicked: backend.setRole("killer") }
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
                                height: 168
                                radius: 13
                                color: "#1c2430"
                                border.width: 1
                                border.color: backend.rotationEnabled ? "#b45e62" : win.stroke
                                Column {
                                    anchors.fill: parent
                                    anchors.margins: 12
                                    spacing: 9
                                    Row {
                                        width: parent.width
                                        spacing: 8
                                        Text {
                                            text: "РЕЖИМ РАНДОМИЗАТОРА"
                                            color: "#cad6e5"
                                            font.pixelSize: 11
                                            font.bold: true
                                            font.letterSpacing: 1
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                        Item { width: 1; height: 1 }
                                        Text {
                                            text: backend.rotationEnabled ? "РОТАЦИЯ АКТИВНА" : "КЛАССИКА"
                                            color: backend.rotationEnabled ? "#efa7a3" : "#8493a5"
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
                                        color: "#9cacbf"
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
                                            color: "#dfb0a9"
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
                            Text { text: "ВАШ БИЛД"; color: win.muted; font.pixelSize: 11; font.bold: true; font.letterSpacing: 1.5 }
                            Rectangle {
                                width: parent.width
                                height: 146
                                radius: 13
                                color: win.surface
                                border.color: win.stroke
                                Row {
                                    anchors.fill: parent
                                    anchors.margins: 12
                                    spacing: 14
                                    ArtThumb {
                                        pixels: 120
                                        iconKey: backend.detail.char
                                        placeholder: "DBD"
                                    }
                                    Column {
                                        width: parent.width - 135
                                        spacing: 11
                                        Text {
                                            text: backend.detail.char || "Персонаж ещё не выбран"
                                            width: parent.width
                                            elide: Text.ElideRight
                                            color: "#f4f6fa"
                                            font.pixelSize: 17
                                            font.bold: true
                                        }
                                        Row {
                                            spacing: 10
                                            ArtThumb { pixels: 48; iconKey: backend.detail.power; placeholder: "ITEM" }
                                            Column {
                                                spacing: 4
                                                Text { text: backend.role === "killer" ? "СИЛА МАНЬЯКА" : "ПРЕДМЕТ ВЫЖИВШЕГО"; color: "#8394a7"; font.pixelSize: 10; font.bold: true }
                                                Text {
                                                    text: backend.detail.power || "Не выбрано"
                                                    width: 350
                                                    elide: Text.ElideRight
                                                    color: "#e1e7ef"
                                                    font.pixelSize: 13
                                                }
                                            }
                                        }
                                        Text {
                                            text: [backend.detail.skin, backend.detail["class"]].filter(Boolean).join(" · ")
                                            width: parent.width
                                            elide: Text.ElideRight
                                            color: "#d4a9a1"; font.pixelSize: 11
                                        }
                                    }
                                }
                            }
                            Rectangle {
                                width: parent.width
                                height: 144
                                radius: 13
                                color: win.surface
                                border.color: win.stroke
                                Column {
                                    anchors.fill: parent
                                    anchors.margins: 13
                                    spacing: 10
                                    Text {
                                        text: "АДДОНЫ · НАЗВАНИЯ"
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
                                                height: 91
                                                radius: 10
                                                color: "#222b36"
                                                border.color: addonInfo.disabled ? "#a35d5b" : "#3a4656"
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
                                                        width: parent.width - 74
                                                        spacing: 6
                                                        Text {
                                                            text: "АДДОН " + addonCard.addonInfo.slot
                                                            color: "#8d9eaf"
                                                            font.pixelSize: 10
                                                            font.bold: true
                                                        }
                                                        Text {
                                                            text: addonCard.addonInfo.filled ? addonCard.addonInfo.name : "Нет аддона"
                                                            width: parent.width
                                                            color: "#edf2f8"
                                                            font.pixelSize: 12
                                                            font.bold: true
                                                            wrapMode: Text.Wrap
                                                            maximumLineCount: 3
                                                            elide: Text.ElideRight
                                                        }
                                                        Text {
                                                            visible: addonCard.addonInfo.disabled
                                                            text: "ЗАПРЕЩЁН ЧЕЛЛЕНДЖЕМ"
                                                            color: "#f19b94"
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
                                radius: 13
                                color: "#221f29"
                                border.color: "#6c4149"
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
                                            text: "УСЛОВИЕ ЧЕЛЛЕНДЖА"
                                            color: "#f2aca6"
                                            font.pixelSize: 11
                                            font.bold: true
                                            font.letterSpacing: 1
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                        Text {
                                            text: backend.detail.challengeDifficulty ? "· " + backend.detail.challengeDifficulty.toUpperCase() : ""
                                            color: "#c9a8ab"
                                            font.pixelSize: 10
                                            font.bold: true
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                    }
                                    Text {
                                        text: backend.detail.challenge
                                        width: parent.width
                                        color: "#f6ebee"
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
                                        color: "#a995a6"
                                        font.pixelSize: 11
                                        font.italic: true
                                        wrapMode: Text.Wrap
                                    }
                                    Repeater {
                                        model: backend.detail.challengeRestrictions || []
                                        Text {
                                            width: challengeContent.width
                                            text: "ОГРАНИЧЕНИЕ: " + modelData
                                            color: "#f1a5a0"
                                            font.pixelSize: 11
                                            font.bold: true
                                            wrapMode: Text.Wrap
                                        }
                                    }
                                    UiButton {
                                        width: Math.min(230, parent.width)
                                        height: 34
                                        label: "ДРУГОЙ ЧЕЛЛЕНДЖ + БИЛД"
                                        onClicked: backend.rerollChallenge()
                                    }
                                }
                            }
                            Row {
                                width: parent.width
                                spacing: 8
                                Text {
                                    text: "НАВЫКИ · 4 СЛОТА"
                                    color: "#b9c6d6"
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
                                        color: "#1b2430"
                                        border.width: 1
                                        border.color: card.perkInfo.locked ? "#d6a667" : cardHover.containsMouse ? "#7c5f68" : "#384556"
                                        clip: true

                                        Rectangle {
                                            width: 4; height: parent.height
                                            color: card.perkInfo.locked ? "#efbf7e" : win.accent
                                        }
                                        Rectangle {
                                            x: 4; y: 0; width: parent.width - 4; height: 35
                                            color: "#222d3a"
                                        }
                                        Text {
                                            x: 15; y: 11
                                            text: "СЛОТ 0" + (card.slotIndex + 1)
                                            color: "#aab9ca"
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
                                            color: "#28323e"
                                            border.color: "#404e60"
                                            Image {
                                                id: perkIcon
                                                anchors.fill: parent
                                                anchors.margins: 5
                                                fillMode: Image.PreserveAspectFit
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
                                            color: card.perkInfo.filled ? "#f4f6fa" : "#8693a3"
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
                                            PauseAnimation { duration: card.slotIndex * 85 }
                                            ParallelAnimation {
                                                NumberAnimation {
                                                    target: card
                                                    property: "opacity"
                                                    from: 0.2
                                                    to: 1
                                                    duration: 260
                                                    easing.type: Easing.OutCubic
                                                }
                                                NumberAnimation {
                                                    target: card
                                                    property: "scale"
                                                    from: 0.94
                                                    to: 1
                                                    duration: 300
                                                    easing.type: Easing.OutBack
                                                }
                                            }
                                        }
                                        Connections {
                                            target: backend
                                            function onBuildRevisionChanged() {
                                                perkReveal.restart();
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
                                    label: "СГЕНЕРИРОВАТЬ"
                                    primary: true
                                    onClicked: backend.generate()
                                }
                                UiButton {
                                    width: parent.width * 0.30 - 6
                                    label: "ПЕРЕБРОСИТЬ СВОБОДНЫЕ"
                                    onClicked: backend.rerollPerks()
                                }
                                UiButton {
                                    width: parent.width * 0.24 - 4
                                    label: "КОПИРОВАТЬ"
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
                                    Text { text: backend.history.length ? backend.history[0] : "Здесь появится последний билд"; width: parent.width; elide: Text.ElideRight; color: "#cdd5df"; font.pixelSize: 12 }
                                }
                            }
                        }
                        Column {
                            id: makerPage
                            visible: win.page === "Конструктор"
                            width: parent.width
                            spacing: 14
                            property string makerSide: "SURVIVOR"
                            property int perkSlot: 0
                            property int addonSlot: 0
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
                                addonSlot = 0;
                            }
                            function pickPerk(name) {
                                var fields = [makerPerk1, makerPerk2, makerPerk3, makerPerk4];
                                for (var i = 0; i < 4; i++) {
                                    if (fields[i].text === name) {
                                        perkSlot = i;
                                        return;
                                    }
                                }
                                fields[perkSlot].text = name;
                                var next = (perkSlot + 1) % 4;
                                for (var j = 0; j < 4; j++) {
                                    var slot = (next + j) % 4;
                                    if (!fields[slot].text) {
                                        perkSlot = slot;
                                        return;
                                    }
                                }
                                perkSlot = next;
                            }
                            function pickAddon(name) {
                                if (makerAddon1.text === name) { addonSlot = 0; return; }
                                if (makerAddon2.text === name) { addonSlot = 1; return; }
                                if (addonSlot === 0) makerAddon1.text = name;
                                else makerAddon2.text = name;
                                addonSlot = 1 - addonSlot;
                            }
                            Text { text: "Визуальный конструктор билдов"; color: "#f0f3f8"; font.pixelSize: 18; font.bold: true }
                            Text {
                                text: "Выбирай настоящие навыки, аддоны и персонажей из базы — больше не нужно вводить названия вручную."
                                width: parent.width; wrapMode: Text.WordWrap; font.pixelSize: 11; color: win.muted
                            }
                            Row {
                                width: parent.width; spacing: 9
                                UiButton {
                                    width: (parent.width - 9) / 2
                                    label: "ВЫЖИВШИЙ"
                                    primary: makerPage.makerSide === "SURVIVOR"
                                    onClicked: makerPage.changeSide("SURVIVOR")
                                }
                                UiButton {
                                    width: (parent.width - 9) / 2
                                    label: "МАНЬЯК"
                                    primary: makerPage.makerSide === "KILLER"
                                    onClicked: makerPage.changeSide("KILLER")
                                }
                            }
                            Rectangle {
                                width: parent.width; height: 244; radius: 13; color: win.surface; border.color: win.stroke
                                Column {
                                    anchors.fill: parent; anchors.margins: 13; spacing: 8
                                    Text { text: "01 · ПЕРСОНАЖ"; font.pixelSize: 11; font.bold: true; color: "#adbccd" }
                                    UiField { id: makerChar; width: parent.width; placeholderText: "Найти персонажа..." }
                                    ListView {
                                        id: makerCharacters
                                        width: parent.width
                                        height: 151
                                        spacing: 5
                                        clip: true
                                        model: backend.searchCharacters(makerPage.makerSide, makerChar.text)
                                        delegate: Rectangle {
                                            width: makerCharacters.width; height: 49; radius: 8
                                            color: makerCharHover.containsMouse ? "#313d4b" : "#202934"
                                            border.color: makerChar.text === modelData.name ? win.accent : "#344152"
                                            ArtThumb { x: 5; y: 4; pixels: 41; iconKey: modelData.name; placeholder: "DBD" }
                                            Text { text: modelData.name; x: 55; anchors.verticalCenter: parent.verticalCenter; color: "#f1f4f8"; font.pixelSize: 12; width: parent.width - 66; elide: Text.ElideRight }
                                            MouseArea { id: makerCharHover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: makerChar.text = modelData.name }
                                        }
                                    }
                                }
                            }
                            Rectangle {
                                width: parent.width; height: makerPage.makerSide === "SURVIVOR" ? 477 : 367; radius: 13; color: win.surface; border.color: win.stroke
                                Column {
                                    anchors.fill: parent; anchors.margins: 13; spacing: 9
                                    Text { text: "02 · ПРЕДМЕТ И АДДОНЫ"; font.pixelSize: 11; font.bold: true; color: "#adbccd" }
                                    UiField {
                                        id: makerItem
                                        width: parent.width
                                        enabled: makerPage.makerSide === "SURVIVOR"
                                        placeholderText: makerPage.makerSide === "KILLER" ? "Сила маньяка подбирается автоматически" : "Найти предмет выжившего..."
                                    }
                                    ListView {
                                        id: makerItems
                                        visible: makerPage.makerSide === "SURVIVOR"
                                        width: parent.width
                                        height: visible ? 100 : 0
                                        spacing: 5
                                        clip: true
                                        model: backend.searchItems(makerItem.text)
                                        delegate: Rectangle {
                                            width: makerItems.width; height: 48; radius: 8
                                            color: makerItemHover.containsMouse ? "#313d4b" : "#202934"
                                            border.color: makerItem.text === modelData.name ? win.accent : "#344152"
                                            ArtThumb { x: 5; y: 4; pixels: 40; iconKey: modelData.name; placeholder: "ITEM" }
                                            Text { text: modelData.name; x: 55; y: 7; width: parent.width-65; elide: Text.ElideRight; font.pixelSize: 12; color: "#eff3f8" }
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
                                        id: makerAddons
                                        width: parent.width; height: 136; spacing: 5; clip: true
                                        model: backend.searchAddons(makerPage.makerSide, makerChar.text, makerItem.text, addonSearch.text)
                                        delegate: Rectangle {
                                            width: makerAddons.width; height: 49; radius: 8
                                            color: addonPickHover.containsMouse ? "#313d4b" : "#202934"
                                            border.color: "#344152"
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
                                width: parent.width; height: 455; radius: 13; color: win.surface; border.color: win.stroke
                                Column {
                                    anchors.fill: parent; anchors.margins: 13; spacing: 8
                                    Text { text: "03 · ЧЕТЫРЕ НАВЫКА"; font.pixelSize: 11; font.bold: true; color: "#adbccd" }
                                    Row {
                                        width: parent.width; spacing: 8
                                        UiField { id: makerPerk1; width: (parent.width - 8) / 2; placeholderText: "Навык 1" }
                                        UiField { id: makerPerk2; width: (parent.width - 8) / 2; placeholderText: "Навык 2" }
                                    }
                                    Row {
                                        width: parent.width; spacing: 8
                                        UiField { id: makerPerk3; width: (parent.width - 8) / 2; placeholderText: "Навык 3" }
                                        UiField { id: makerPerk4; width: (parent.width - 8) / 2; placeholderText: "Навык 4" }
                                    }
                                    Row {
                                        width: parent.width; spacing: 6
                                        Repeater {
                                            model: 4
                                            UiButton {
                                                width: (parent.width - 18) / 4
                                                height: 32
                                                label: "СЛОТ " + (index + 1)
                                                primary: makerPage.perkSlot === index
                                                onClicked: makerPage.perkSlot = index
                                            }
                                        }
                                    }
                                    Text {
                                        width: parent.width
                                        text: "Навыков выбрано: " +
                                            [makerPerk1.text, makerPerk2.text, makerPerk3.text, makerPerk4.text].filter(Boolean).length +
                                            " / 4 · повторные навыки не добавляются"
                                        color: "#8fa1b4"; font.pixelSize: 10
                                    }
                                    UiField { id: perkSearch; width: parent.width; placeholderText: "Поиск навыков по названию..." }
                                    ListView {
                                        id: makerPerks
                                        width: parent.width; height: 205
                                        spacing: 5; clip: true
                                        model: backend.searchPerks(makerPage.makerSide, perkSearch.text)
                                        delegate: Rectangle {
                                            width: makerPerks.width; height: 48; radius: 8
                                            color: perkPickHover.containsMouse ? "#303b49" : "#202934"
                                            border.color: "#344152"
                                            ArtThumb { x: 5; y: 4; pixels: 40; iconKey: modelData.name; placeholder: "PERK" }
                                            Text { text: modelData.name; x: 55; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 145; font.pixelSize: 12; elide: Text.ElideRight; color: "#eef2f8" }
                                            Text {
                                                text: "ВЫБРАН"
                                                visible: [makerPerk1.text, makerPerk2.text, makerPerk3.text, makerPerk4.text].indexOf(modelData.name) >= 0
                                                anchors.right: parent.right
                                                anchors.rightMargin: 11
                                                anchors.verticalCenter: parent.verticalCenter
                                                font.pixelSize: 10
                                                font.bold: true
                                                color: "#ed9f96"
                                            }
                                            MouseArea { id: perkPickHover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: makerPage.pickPerk(modelData.name) }
                                        }
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
                                id: buildsList
                                width: parent.width; height: 430; clip: true; spacing: 7
                                model: backend.community
                                delegate: Rectangle {
                                    width: buildsList.width; height: 90
                                    color: "#1b232d"; radius: 9; border.color: win.stroke
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
                            Text { text: "Выбор доступных персонажей"; color: "#e9edf5"; font.pixelSize: 18; font.bold: true }
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
                                        property var filtered: backend.characters.filter(function(c) {
                                            return c.side === sideKey && c.name.toLowerCase().indexOf(charSearch.text.toLowerCase()) >= 0
                                        })
                                        width: (charactersPage.width - 12) / 2
                                        height: 570
                                        radius: 14
                                        color: "#171e27"
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
                                                    Text { text: modelData.title; font.bold: true; font.pixelSize: 13; color: "#eff3f8"; font.letterSpacing: 0.5 }
                                                    Text {
                                                        text: backend.characters.filter(function(c){return c.side === sideCard.sideKey && c.owned}).length
                                                            + " из " + backend.characters.filter(function(c){return c.side === sideCard.sideKey}).length + " выбрано"
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
                                                id: characterList
                                                width: parent.width
                                                height: sideCard.height - 128
                                                model: sideCard.filtered
                                                clip: true
                                                spacing: 7
                                                boundsBehavior: Flickable.StopAtBounds
                                                delegate: Rectangle {
                                                    id: characterRow
                                                    width: characterList.width
                                                    height: 64
                                                    radius: 10
                                                    color: rowHover.containsMouse ? "#283342" : "#202833"
                                                    border.width: 1
                                                    border.color: modelData.owned ? "#6e5157" : "#364353"
                                                    ArtThumb {
                                                        x: 7; y: 6
                                                        pixels: 52
                                                        iconKey: modelData.name
                                                        placeholder: sideCard.sideKey
                                                    }
                                                    Text {
                                                        text: modelData.name
                                                        x: 69; y: 13
                                                        width: parent.width - 115
                                                        elide: Text.ElideRight
                                                        font.pixelSize: 12
                                                        color: modelData.owned ? "#eef3fa" : "#8996a7"
                                                    }
                                                    Text {
                                                        text: modelData.owned ? "ДОСТУПЕН" : "НЕ ВЫБРАН"
                                                        x: 69; y: 36
                                                        font.pixelSize: 9
                                                        font.letterSpacing: 0.4
                                                        color: modelData.owned ? "#d1a3a3" : "#788797"
                                                    }
                                                    Rectangle {
                                                        width: 20; height: 20; radius: 5
                                                        anchors.right: parent.right
                                                        anchors.rightMargin: 11
                                                        anchors.verticalCenter: parent.verticalCenter
                                                        color: modelData.owned ? win.accent : "#2c3847"
                                                        border.width: 1
                                                        border.color: modelData.owned ? win.accent : "#667586"
                                                        Text { anchors.centerIn: parent; text: modelData.owned ? "✓" : ""; color: "white"; font.pixelSize: 13; font.bold: true }
                                                    }
                                                    MouseArea {
                                                        id: rowHover; anchors.fill: parent
                                                        hoverEnabled: true
                                                        cursorShape: Qt.PointingHandCursor
                                                        onClicked: backend.setCharacter(modelData.name, sideCard.sideKey)
                                                    }
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
                            Text { text: "Галерея внешности"; color: "#e9edf5"; font.pixelSize: 18; font.bold: true }
                            Text { text: "Настоящие превью из базы wiki.gg. Отмеченные наборы участвуют в генерации билдов."; width: parent.width; color: win.muted; wrapMode: Text.WordWrap; font.pixelSize: 11 }
                            Row {
                                width: parent.width
                                spacing: 9
                                UiButton {
                                    width: (parent.width - 9) / 2; label: "ВЫЖИВАЮЩИЕ"; primary: skinPage.sideKey === "S"
                                    onClicked: { skinPage.sideKey = "S"; skinPage.selectedSkinId = -1 }
                                }
                                UiButton {
                                    width: (parent.width - 9) / 2; label: "МАНЬЯКИ"; primary: skinPage.sideKey === "K"
                                    onClicked: { skinPage.sideKey = "K"; skinPage.selectedSkinId = -1 }
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
                                    color: "#171e27"
                                    border.color: win.stroke
                                    Column {
                                        anchors.fill: parent
                                        anchors.margins: 10
                                        spacing: 9
                                        Text { text: "ПЕРСОНАЖИ"; color: "#ced7e3"; font.pixelSize: 11; font.bold: true; font.letterSpacing: 1 }
                                        UiField { id: skinCharSearch; width: parent.width; placeholderText: "Поиск героя" }
                                        ListView {
                                            id: skinCharList
                                            width: parent.width
                                            height: skinCharactersCard.height - 78
                                            clip: true
                                            spacing: 6
                                            model: backend.skinCharacters.filter(function(c) {
                                                return c.side === skinPage.sideKey
                                                    && c.name.toLowerCase().indexOf(skinCharSearch.text.toLowerCase()) >= 0;
                                            })
                                            delegate: Rectangle {
                                                width: skinCharList.width
                                                height: 57
                                                radius: 9
                                                color: backend.skinCharacter === modelData.name ? "#39303a" : charHover.containsMouse ? "#293442" : "#202936"
                                                border.color: backend.skinCharacter === modelData.name ? win.accent : "#354252"
                                                ArtThumb {
                                                    x: 5; y: 5
                                                    pixels: 47
                                                    iconKey: modelData.name
                                                    placeholder: modelData.side
                                                }
                                                Column {
                                                    x: 60; y: 11
                                                    width: parent.width - 67
                                                    spacing: 5
                                                    Text { text: modelData.name; width: parent.width; elide: Text.ElideRight; color: "#eef3f8"; font.pixelSize: 11; font.bold: backend.skinCharacter === modelData.name }
                                                    Text { text: modelData.count + " наборов"; color: "#9bacbe"; font.pixelSize: 9 }
                                                }
                                                MouseArea {
                                                    id: charHover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                                    onClicked: { skinPage.selectedSkinId = -1; backend.setSkinCharacter(modelData.name) }
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
                                    color: "#171e27"
                                    border.color: win.stroke
                                    Column {
                                        anchors.fill: parent
                                        anchors.margins: 12
                                        spacing: 10
                                        Text { text: backend.skinCharacter || "Выберите персонажа"; color: "#eef2f7"; font.pixelSize: 15; font.bold: true }
                                        Text {
                                            text: backend.skinStats.owned + " из " + backend.skinStats.total + " наборов выбрано"
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
                                                        color: "#f0f4fa"; font.pixelSize: 13; font.bold: true
                                                        wrapMode: Text.WordWrap; width: parent.width; maximumLineCount: 3; elide: Text.ElideRight
                                                    }
                                                    Text {
                                                        text: skinPage.previewSkin ? (skinPage.previewSkin.rarity + " · " + skinPage.previewSkin.type) : ""
                                                        color: "#c69b96"; width: parent.width; font.pixelSize: 10; wrapMode: Text.WordWrap
                                                    }
                                                    Text { text: skinPage.previewSkin ? skinPage.previewSkin.date : ""; color: win.muted; font.pixelSize: 10 }
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
                                        UiField { id: skinSearch; width: parent.width; placeholderText: "Поиск по RU/EN названию, редкости, дате"; onTextChanged: backend.filterSkins(text) }
                                        ListView {
                                            id: skinsList
                                            width: parent.width
                                            height: skinContent.height - 330
                                            clip: true
                                            spacing: 7
                                            model: backend.skins
                                            delegate: Rectangle {
                                                id: skinRow
                                                width: skinsList.width
                                                height: 67
                                                radius: 9
                                                color: skinPage.previewSkin && skinPage.previewSkin.id === modelData.id ? "#323140" : "#202936"
                                                border.color: skinPage.previewSkin && skinPage.previewSkin.id === modelData.id ? win.accent : "#354252"
                                                ArtThumb {
                                                    x: 7; y: 6; pixels: 55
                                                    iconKey: "skin:" + modelData.id
                                                    placeholder: "SKIN"
                                                }
                                                Column {
                                                    x: 70; y: 10
                                                    width: parent.width - 107
                                                    spacing: 5
                                                    Text { text: modelData.name; width: parent.width; elide: Text.ElideRight; color: "#f1f3f9"; font.pixelSize: 11; font.bold: true }
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
                                                    anchors.rightMargin: 9
                                                    anchors.verticalCenter: parent.verticalCenter
                                                    color: modelData.owned ? win.accent : "#2c3847"
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
                            Text {
                                text: "Библиотека избранных билдов"
                                font.pixelSize: 20
                                font.bold: true
                                color: "#eef2f8"
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
                                    color: "#212a36"
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
                            UiField {
                                id: favoriteSearch
                                width: parent.width
                                placeholderText: "Поиск по названию, коллекции, персонажу, навыкам и заметкам..."
                                onTextChanged: backend.setFavoriteSearch(text)
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
                                text: "НАЙДЕНО: " + backend.favorites.length
                                color: "#b8c5d5"
                                font.pixelSize: 11
                                font.bold: true
                            }
                            Rectangle {
                                visible: backend.favorites.length === 0
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
                                id: favoriteList
                                width: parent.width
                                height: Math.min(600, Math.max(120, backend.favorites.length * 182))
                                visible: backend.favorites.length > 0
                                clip: true
                                spacing: 10
                                boundsBehavior: Flickable.StopAtBounds
                                model: backend.favorites
                                delegate: Rectangle {
                                    id: favoriteCard
                                    property var entry: modelData
                                    width: favoriteList.width
                                    height: 172
                                    radius: 13
                                    color: "#1b2530"
                                    border.color: "#3c4a5b"
                                    ArtThumb {
                                        x: 12
                                        y: 14
                                        pixels: 64
                                        iconKey: favoriteCard.entry.char
                                        placeholder: "DBD"
                                    }
                                    Column {
                                        x: 89
                                        y: 13
                                        width: parent.width - 102
                                        spacing: 6
                                        Text {
                                            width: parent.width
                                            text: favoriteCard.entry.title
                                            color: "#f2f5fa"
                                            font.pixelSize: 15
                                            font.bold: true
                                            elide: Text.ElideRight
                                        }
                                        Text {
                                            width: parent.width
                                            text: (favoriteCard.entry.side === "KILLER" ? "МАНЬЯК" : "ВЫЖИВШИЙ") +
                                                " · " + favoriteCard.entry.char +
                                                " · " + favoriteCard.entry.collection
                                            color: "#e3a7a1"
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
                                            elide: Text.ElideRight
                                        }
                                    }
                                    Text {
                                        x: 13; y: 100
                                        text: "Сохранено " + favoriteCard.entry.saved_at
                                        color: "#7c8c9e"
                                        font.pixelSize: 10
                                    }
                                    Row {
                                        x: 12; y: 122
                                        width: parent.width - 24
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
                                color: "#1e2834"
                                border.color: win.stroke
                                Row {
                                    anchors.fill: parent
                                    anchors.margins: 12
                                    spacing: 12
                                    Column {
                                        width: (parent.width - 12) / 2
                                        spacing: 5
                                        Text { text: "РАЗНЫХ НАВЫКОВ"; color: "#9cacbe"; font.pixelSize: 10 }
                                        Text { text: "" + statsPage.stat.overview.uniquePerks; font.pixelSize: 19; font.bold: true; color: "#f1f5fa" }
                                    }
                                    Column {
                                        width: (parent.width - 12) / 2
                                        spacing: 5
                                        Text { text: "РАЗНЫХ АДДОНОВ"; color: "#9cacbe"; font.pixelSize: 10 }
                                        Text { text: "" + statsPage.stat.overview.uniqueAddons; font.pixelSize: 19; font.bold: true; color: "#f1f5fa" }
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
                                        property color rankingFill: modelData.kind === "top" ? "#e56c69" : "#7b9fde"
                                        width: (statsPage.width - 12) / 2
                                        height: 576
                                        radius: 13
                                        color: "#171f2a"
                                        border.color: win.stroke
                                        Column {
                                            anchors.fill: parent
                                            anchors.margins: 11
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
                                color: "#171f2a"
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
                                            color: "#232c38"
                                            border.color: "#394455"
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
                                color: "#171f2a"
                                border.color: win.stroke
                                Column {
                                    anchors.fill: parent
                                    anchors.margins: 12
                                    spacing: 10
                                    Text { text: "ИСТОРИЯ ВЫПАДЕНИЙ"; color: "#e5edf5"; font.pixelSize: 12; font.bold: true }
                                    Text { text: "Хранятся последние 100 событий, показаны до 28 за выбранный период"; color: "#92a4b7"; font.pixelSize: 10 }
                                    ListView {
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
                                            color: "#222c38"
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
                            visible: win.page === "Классы 2v8"
                            width: parent.width; spacing: 12
                            Text { text: "Случайные классы режима 2 против 8"; color: win.muted; font.pixelSize: 12 }
                            UiButton { width: parent.width; label: "СГЕНЕРИРОВАТЬ КЛАССЫ"; primary: true; onClicked: backend.rollClasses() }
                            Repeater {
                                model: backend.classDetails
                                delegate: Rectangle {
                                    width: parent.width; height: 126; radius: 13; color: win.surface; border.color: win.stroke
                                    Column { x: 17; y: 14; width: parent.width - 34; spacing: 10
                                        Text { text: modelData.side === "KILLER" ? "МАНЬЯК" : "ВЫЖИВШИЙ"; color: win.accent; font.bold: true; font.pixelSize: 10 }
                                        Text { text: modelData.title; color: "#f3f5f8"; font.bold: true; font.pixelSize: 17 }
                                        Text { text: modelData.skills; width: parent.width; height: 57; wrapMode: Text.Wrap; color: "#b2c0d0"; font.pixelSize: 11 }
                                    }
                                }
                            }
                            UiButton { width: parent.width; label: "СКОПИРОВАТЬ КЛАССЫ"; onClicked: backend.copyClass() }
                        }

                    }
                }
                Rectangle {
                    Layout.preferredWidth: 320
                    Layout.fillHeight: true
                    color: "#11161e"
                    border.color: "#222b37"
                    Flickable {
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
                                color: backend.mode === modelData.key ? "#35272d" : modeArea.containsMouse ? "#222a36" : "#1b212b"
                                border.color: backend.mode === modelData.key ? win.accent : "#343e4a"
                                Text { text: modelData.label; anchors.verticalCenter: parent.verticalCenter; x: 13; font.pixelSize: 12; color: "#e4e9ee" }
                                Rectangle { width: 7; height: 7; radius: 4; color: win.accent; anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter; visible: backend.mode === modelData.key }
                                MouseArea { id: modeArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: backend.setMode(modelData.key) }
                            }
                        }
                        Item { width: 1; height: 4 }
                        Rectangle { width: parent.width; height: 1; color: win.stroke }
                        OptionRow { title: "Подбирать аддоны"; keyName: "addons" }
                        OptionRow { title: "Случайная внешность"; keyName: "appearance" }
                        OptionRow { title: "Случайный челлендж"; keyName: "challenge" }
                        OptionRow { title: "Только открытые навыки"; keyName: "owned" }
                        OptionRow { title: "Класс режима 2v8"; keyName: "classes" }
                        OptionRow { title: "Сухой прогон (без кликов)"; keyName: "dry" }
                        OptionRow { title: "Проверка OCR"; keyName: "ocr" }
                        OptionRow { title: "Выбирать персонажа в игре"; keyName: "select_char" }
                        Rectangle { width: parent.width; height: 1; color: win.stroke }
                        Text { text: "ПАРАМЕТРЫ ПОИСКА И КУРСОРА"; color: "#d8dfe8"; font.pixelSize: 11; font.bold: true }
                        Repeater {
                            model: [
                                { key: "clear", title: "Кликать кнопку очистки" },
                                { key: "verifyclipboard", title: "Проверять буфер обмена" },
                                { key: "restoreclipboard", title: "Восстанавливать буфер" },
                                { key: "focusgame", title: "Поднимать окно игры" },
                                { key: "hoververify", title: "Проверять точность курсора" },
                                { key: "hoverretry", title: "Повторять наведение" }
                            ]
                            Rectangle {
                                width: parent.width; height: 39; radius: 8
                                color: optionMouse.containsMouse ? "#222a36" : "#191f28"
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
                        UiButton { width: parent.width; label: "ЭКИПИРОВАТЬ В ИГРЕ"; onClicked: backend.equip() }
                        UiButton { width: parent.width; label: "СТОП АВТОМАТИЗАЦИИ (F9)"; onClicked: backend.stop() }
                        Rectangle { width: parent.width; height: 1; color: win.stroke }
                        Text { text: "ОБНОВЛЕНИЯ"; color: "#d8dfe8"; font.pixelSize: 11; font.bold: true; font.letterSpacing: 1 }
                        UiButton { width: parent.width; label: backend.updateBusy ? "ПОДОЖДИТЕ..." : "ПРОВЕРИТЬ ОБНОВЛЕНИЯ"; onClicked: backend.checkUpdate() }
                        Text { width: parent.width; text: backend.updateText || "Версия v2.28.0-qt-beta.11"; wrapMode: Text.Wrap; color: win.muted; font.pixelSize: 11 }
                        UiButton { visible: backend.updateAvailable; width: parent.width; label: "СКАЧАТЬ И УСТАНОВИТЬ"; primary: true; onClicked: backend.installUpdate() }

                        Rectangle {
                            width: parent.width; height: 83; color: "#251f24"; radius: 10; border.color: "#49353e"
                            Text { anchors.fill: parent; anchors.margins: 13; wrapMode: Text.WordWrap; text: "Qt оболочка с оригинальным движком. Перед автоэкипировкой проверьте координаты, сухой прогон и стоп-клавишу F9."; color: "#dec0bf"; font.pixelSize: 11 }
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
                    color: backend.addonEffect.verified ? "#e6a59c" : "#a0b0c2"
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
                Text { text: "ОБЛАСТИ ВЛИЯНИЯ"; color: "#a0b0c2"; font.pixelSize: 11; font.bold: true }
                Text {
                    text: backend.addonEffect.categories.length > 0 ?
                        backend.addonEffect.categories.join(" · ") :
                        "Нет данных в локальном кэше. Категории wiki.gg подгружаются при наличии интернета."
                    width: parent.width
                    font.pixelSize: 12
                    color: "#b8c4d3"
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
            color: "#1b2430"
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
                color: "#b8c4d3"
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
                        color: "#f2f5f9"
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
                text: "Описание игровых эффектов пока не хранится в базе приложения. Для актуальных значений открой справочник перков DBD."
                color: "#8c9eaf"
                font.pixelSize: 11
                width: parent.width
                wrapMode: Text.Wrap
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
        background: Rectangle { color: "#1b2430"; radius: 15; border.color: "#78545c" }
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
            color: "#1a2531"
            radius: 15
            border.color: "#6b4d57"
        }
        contentItem: Column {
            padding: 14
            spacing: 10
            Text {
                text: favoriteEditor.editingId ? "РЕДАКТИРОВАТЬ ИЗБРАННОЕ" : "СОХРАНИТЬ БИЛД"
                color: "#f2f5f9"
                font.pixelSize: 16
                font.bold: true
            }
            Text { text: "НАЗВАНИЕ"; font.pixelSize: 10; font.bold: true; color: "#a9b9cc" }
            UiField { id: favoriteTitle; width: favoriteEditor.width - 34; maximumLength: 72; placeholderText: "Название билда" }
            Text { text: "КОЛЛЕКЦИЯ"; font.pixelSize: 10; font.bold: true; color: "#a9b9cc" }
            UiField { id: favoriteGroup; width: favoriteEditor.width - 34; maximumLength: 48; placeholderText: "Например: любимые / маньяки / эксперименты" }
            Text { text: "ЗАМЕТКА"; font.pixelSize: 10; font.bold: true; color: "#a9b9cc" }
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
            color: "#1a2531"
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

    Shortcut { sequence: "F5"; onActivated: backend.generate() }
    Shortcut { sequence: "F6"; onActivated: backend.copyBuild() }
    Shortcut { sequence: "F9"; onActivated: backend.placeholder("STOP") }
}
