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
    title: "DBD Ultimate Search Randomizer | Qt Beta 3"
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
                Rectangle {
                    width: 43; height: 43; radius: 11
                    color: "#332126"
                    anchors.horizontalCenter: parent.horizontalCenter
                    Canvas {
                        anchors.fill: parent
                        onPaint: {
                            let c = getContext("2d");
                            c.strokeStyle = "#ec605b"; c.lineWidth = 2.7; c.lineCap="round";
                            c.beginPath(); c.moveTo(12,12); c.lineTo(31,31);
                            c.moveTo(31,12); c.lineTo(12,31);
                            c.moveTo(20,8); c.lineTo(22,35); c.stroke();
                        }
                    }
                }
                Item { width: 1; height: 12 }
                Text { anchors.horizontalCenter: parent.horizontalCenter; text: "DBD RANDOMIZER"; color: "#f0f2f5"; font.pixelSize: 13; font.weight: Font.Bold; font.letterSpacing: 1.1 }
                Text { anchors.horizontalCenter: parent.horizontalCenter; text: "QT QUICK • BETA 3"; color: "#7e8999"; font.pixelSize: 10; font.letterSpacing: 1 }
                Item { height: 24 }
                NavItem { ordinal: 1; label: "Билд"; onClicked: win.page = label }
                NavItem { ordinal: 2; label: "Конструктор"; onClicked: win.page = label }
                NavItem { ordinal: 3; label: "Билды сообщества"; onClicked: win.page = label }
                NavItem { ordinal: 4; label: "Персонажи"; onClicked: win.page = label }
                NavItem { ordinal: 5; label: "Внешность"; onClicked: win.page = label }
                NavItem { ordinal: 6; label: "Клики и тайминги"; onClicked: win.page = label }
                NavItem { ordinal: 7; label: "Классы 2v8"; onClicked: win.page = label }
                Item { height: 23 }
                Rectangle { width: parent.width; height: 1; color: "#26303d" }
                Item { height: 10 }
                UiButton { width: parent.width; label: "Новый билд"; onClicked: { win.page = "Билд"; backend.generate() } }
                UiButton { width: parent.width; label: "Копировать билд"; onClicked: backend.copyBuild() }
                Item { height: 20 }
                Rectangle {
                    width: parent.width; height: 95; radius: 10; color: "#25232a"
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
                                                ToolTip.text: addonCard.addonInfo.name
                                                MouseArea {
                                                    id: addonHover
                                                    anchors.fill: parent
                                                    hoverEnabled: true
                                                    acceptedButtons: Qt.NoButton
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
                            GridLayout {
                                width: parent.width
                                columns: 2
                                rowSpacing: 12
                                columnSpacing: 12
                                Repeater {
                                    model: 4
                                    Rectangle {
                                        id: card
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 202
                                        radius: 14
                                        color: "#1b222d"
                                        border.width: 1
                                        border.color: backend.perks[index].locked ? "#c49b6a" : win.stroke
                                        property var perkInfo: backend.perks[index]
                                        Rectangle { width: 6; height: 6; radius: 3; x: 18; y: 20; color: card.perkInfo.filled ? win.accent : "#606d7b" }
                                        Text { text: "НАВЫК " + ("0" + (index + 1)); x: 33; y: 16; color: "#a4b1c2"; font.pixelSize: 11; font.bold: true; font.letterSpacing: 1 }
                                        Image {
                                            id: perkIcon
                                            width: 76
                                            height: 76
                                            y: 41
                                            anchors.horizontalCenter: parent.horizontalCenter
                                            fillMode: Image.PreserveAspectFit
                                            source: backend.iconVersion >= 0 ? backend.iconPath(card.perkInfo.raw) : ""
                                            asynchronous: true
                                            smooth: true
                                        }
                                        Canvas {
                                            visible: perkIcon.status !== Image.Ready
                                            width: 67; height: 67
                                            anchors.horizontalCenter: parent.horizontalCenter
                                            y: 46
                                            onPaint: {
                                                let ctx = getContext("2d");
                                                ctx.lineWidth = 2.4;
                                                ctx.strokeStyle = "#d6b6a1";
                                                ctx.lineCap = "round"; ctx.lineJoin = "round";
                                                ctx.beginPath();
                                                let k = index % 4;
                                                if (k === 0) { ctx.moveTo(36,4); ctx.lineTo(14,34); ctx.lineTo(28,35); ctx.lineTo(22,61); ctx.lineTo(54,27); ctx.lineTo(39,28); ctx.closePath(); }
                                                else if (k === 1) { ctx.arc(34,33,25,0,Math.PI*2); ctx.moveTo(34,8); ctx.lineTo(34,58); ctx.moveTo(9,33); ctx.lineTo(59,33); }
                                                else if (k === 2) { ctx.moveTo(34,5); ctx.lineTo(57,21); ctx.lineTo(51,47); ctx.lineTo(34,62); ctx.lineTo(17,47); ctx.lineTo(11,21); ctx.closePath(); }
                                                else {ctx.moveTo(12,13);ctx.lineTo(55,56);ctx.moveTo(55,13);ctx.lineTo(12,56);ctx.moveTo(34,4);ctx.lineTo(34,64);}
                                                ctx.stroke();
                                            }
                                        }
                                        Text { x: 18; y: 125; width: parent.width - 36; text: card.perkInfo.name; elide: Text.ElideRight; color: "#f3f5f6"; font.pixelSize: 15; font.weight: Font.DemiBold }
                                        Text { x: 18; y: 151; text: card.perkInfo.locked ? "ЗАКРЕПЛЕНО" : "НАВЫК"; color: card.perkInfo.locked ? "#edb979" : "#8d99a8"; font.pixelSize: 10; font.letterSpacing: .5 }
                                        Row {
                                            anchors.right: parent.right
                                            anchors.top: parent.top
                                            anchors.rightMargin: 10
                                            anchors.topMargin: 10
                                            spacing: 5
                                            UiButton { width: 70; height: 30; label: card.perkInfo.locked ? "Откреп." : "Замок"; onClicked: backend.toggleLock(index) }
                                            UiButton { width: 69; height: 30; label: "Переброс"; onClicked: backend.reroll(index) }
                                        }
                                    }
                                }
                            }
                            Row {
                                width: parent.width; spacing: 10
                                UiButton { width: parent.width * .6 - 5; label: "СГЕНЕРИРОВАТЬ БИЛД"; primary: true; onClicked: backend.generate() }
                                UiButton { width: parent.width * .4 - 5; label: "КОПИРОВАТЬ"; onClicked: backend.copyBuild() }
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
                            }
                            function pickPerk(name) {
                                var fields = [makerPerk1, makerPerk2, makerPerk3, makerPerk4];
                                fields[perkSlot].text = name;
                                perkSlot = (perkSlot + 1) % 4;
                            }
                            function pickAddon(name) {
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
                                            Text { text: modelData.name; x: 55; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 65; elide: Text.ElideRight; font.pixelSize: 12; color: "#ecf1f6" }
                                            MouseArea { id: addonPickHover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: makerPage.pickAddon(modelData.name) }
                                        }
                                    }
                                }
                            }
                            Rectangle {
                                width: parent.width; height: 433; radius: 13; color: win.surface; border.color: win.stroke
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
                                            Text { text: modelData.name; x: 55; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 65; font.pixelSize: 12; elide: Text.ElideRight; color: "#eef2f8" }
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
                                    backend.buildCustom(makerPage.makerSide, makerChar.text, makerItem.text,
                                        makerAddon1.text, makerAddon2.text, makerPerk1.text,
                                        makerPerk2.text, makerPerk3.text, makerPerk4.text);
                                    if (backend.detail.hasBuild && backend.detail.char === makerChar.text)
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
                        Text { width: parent.width; text: backend.updateText || "Версия v2.28.0-qt-beta.3"; wrapMode: Text.Wrap; color: win.muted; font.pixelSize: 11 }
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
    Shortcut { sequence: "F5"; onActivated: backend.generate() }
    Shortcut { sequence: "F6"; onActivated: backend.copyBuild() }
    Shortcut { sequence: "F9"; onActivated: backend.placeholder("STOP") }
}
