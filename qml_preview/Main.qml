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
    title: "DBD Ultimate Search Randomizer | Qt Beta 2"
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
                Text { anchors.horizontalCenter: parent.horizontalCenter; text: "QT QUICK • BETA 2"; color: "#7e8999"; font.pixelSize: 10; font.letterSpacing: 1 }
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
                        Text { text: "Пока без автоэкипировки\nи игровых данных"; color: "#c1b9bc"; font.pixelSize: 11 }
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
                                width: parent.width; height: 112; radius: 11; color: win.surface; border.color: win.stroke
                                Column { anchors.fill: parent; anchors.margins: 12; spacing: 5
                                    Text { text: backend.detail.char || "Персонаж ещё не выбран"; color: "#f3f4f7"; font.pixelSize: 15; font.bold: true }
                                    Text { text: "Предмет / сила: " + (backend.detail.power || "—"); elide: Text.ElideRight; width: parent.width; color: "#aab8c8"; font.pixelSize: 11 }
                                    Text { text: "Аддоны: " + (backend.detail.addons || []).join(" · "); elide: Text.ElideRight; width: parent.width; color: "#aab8c8"; font.pixelSize: 11 }
                                    Text { text: [backend.detail.skin, backend.detail.challenge, backend.detail["class"]].filter(Boolean).join(" · "); elide: Text.ElideRight; width: parent.width; color: "#d4a39a"; font.pixelSize: 10 }
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
                            visible: win.page === "Конструктор"
                            width: parent.width
                            spacing: 12
                            Text { text: "Создайте собственный билд"; color: win.muted; font.pixelSize: 12 }
                            Row {
                                spacing: 8
                                UiButton { width: 145; label: "ВЫЖИВШИЙ"; primary: makerPage.makerSide === "SURVIVOR"; onClicked: makerPage.makerSide = "SURVIVOR" }
                                UiButton { width: 145; label: "МАНЬЯК"; primary: makerPage.makerSide === "KILLER"; onClicked: makerPage.makerSide = "KILLER" }
                            }
                            id: makerPage
                            property string makerSide: "SURVIVOR"
                            UiField { id: makerChar; width: parent.width; placeholderText: "Персонаж — точное имя из базы" }
                            UiField { id: makerItem; width: parent.width; placeholderText: "Предмет / сила (для маньяка заполняется автоматически)" }
                            Row {
                                width: parent.width; spacing: 10
                                UiField { id: makerAddon1; width: (parent.width - 10) / 2; placeholderText: "Аддон 1" }
                                UiField { id: makerAddon2; width: (parent.width - 10) / 2; placeholderText: "Аддон 2" }
                            }
                            UiField { id: makerPerk1; width: parent.width; placeholderText: "Навык 1 (точное название)" }
                            UiField { id: makerPerk2; width: parent.width; placeholderText: "Навык 2 (точное название)" }
                            UiField { id: makerPerk3; width: parent.width; placeholderText: "Навык 3 (точное название)" }
                            UiField { id: makerPerk4; width: parent.width; placeholderText: "Навык 4 (точное название)" }
                            UiButton { width: parent.width; label: "СОБРАТЬ БИЛД"; primary: true;
                                onClicked: backend.buildCustom(makerPage.makerSide, makerChar.text, makerItem.text,
                                    makerAddon1.text, makerAddon2.text, makerPerk1.text,
                                    makerPerk2.text, makerPerk3.text, makerPerk4.text) }
                            UiButton { width: parent.width; label: "ОТКРЫТЬ РАСШИРЕННЫЙ КОНСТРУКТОР"; onClicked: backend.returnToLegacy() }
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
                            visible: win.page === "Персонажи"
                            width: parent.width; spacing: 12
                            Text { text: "Белый список доступных персонажей"; color: win.muted; font.pixelSize: 12 }
                            UiField { id: charSearch; width: parent.width; placeholderText: "Поиск по имени" }
                            ListView {
                                id: charList
                                width: parent.width; height: 450; clip: true; spacing: 4
                                model: backend.characters.filter(function(c) {
                                    return c.name.toLowerCase().indexOf(charSearch.text.toLowerCase()) >= 0
                                })
                                delegate: Rectangle {
                                    width: charList.width; height: 43; color: "#1b222c"; radius: 8
                                    border.color: modelData.owned ? "#744947" : win.stroke
                                    Rectangle { x: 10; y: 11; width: 19; height: 19; radius: 5
                                        color: modelData.owned ? win.accent : "#283241"; border.color: "#536072"
                                        Text { anchors.centerIn: parent; text: modelData.owned ? "✓" : ""; color: "white"; font.pixelSize: 13 } }
                                    Text { x: 41; y: 12; width: parent.width - 136; text: modelData.name; elide: Text.ElideRight; color: "#e6edf6"; font.pixelSize: 12 }
                                    Text { anchors.right: parent.right; anchors.rightMargin: 10; y: 14; text: modelData.side === "K" ? "МАНЬЯК" : "ВЫЖИВШИЙ"; font.pixelSize: 10; color: win.muted }
                                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: backend.setCharacter(modelData.name, modelData.side) }
                                }
                            }
                        }
                        Column {
                            visible: win.page === "Внешность"
                            width: parent.width; spacing: 12
                            Text { text: "Отмечайте наборы внешности, которые у вас открыты"; color: win.muted; font.pixelSize: 12 }
                            Row {
                                width: parent.width; spacing: 8
                                UiButton { width: 172; label: "СЛЕДУЮЩИЙ ГЕРОЙ"; onClicked: backend.nextSkinCharacter() }
                                Text { width: parent.width - 180; anchors.verticalCenter: parent.verticalCenter; text: backend.skinCharacter; color: "#f1f3f7"; font.bold: true; font.pixelSize: 12; elide: Text.ElideRight }
                            }
                            UiField { id: skinSearch; width: parent.width; placeholderText: "Поиск набора"; onTextChanged: backend.filterSkins(text) }
                            Text { text: "Найдено вариантов: " + backend.skins.length; color: win.muted; font.pixelSize: 11 }
                            ListView {
                                id: skinsList
                                width: parent.width; height: 438; clip: true; spacing: 5
                                model: backend.skins
                                delegate: Rectangle {
                                    width: skinsList.width; height: 49; radius: 8
                                    color: "#1b232d"; border.color: modelData.owned ? win.accent : win.stroke
                                    Rectangle { x: 12; y: 13; width: 18; height: 18; radius: 5; color: modelData.owned ? win.accent : "#283342"; border.color: "#526075" }
                                    Text { text: modelData.name; x: 42; y: 8; width: parent.width - 54; elide: Text.ElideRight; color: "#ebf0f5"; font.pixelSize: 12 }
                                    Text { text: modelData.rarity; x: 42; y: 29; color: "#8995a7"; font.pixelSize: 10 }
                                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: backend.toggleSkin(modelData.id) }
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
                        Text { width: parent.width; text: backend.updateText || "Версия v2.28.0-qt-beta.2"; wrapMode: Text.Wrap; color: win.muted; font.pixelSize: 11 }
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
