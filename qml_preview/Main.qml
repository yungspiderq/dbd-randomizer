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
    title: "DBD Ultimate Search Randomizer | QML Preview"
    property string page: "Билд"
    property color surface: "#171d26"
    property color stroke: "#2f3947"
    property color muted: "#8995a5"
    property color accent: "#ea5753"
    font.family: "Segoe UI"

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
                Text { anchors.horizontalCenter: parent.horizontalCenter; text: "QT QUICK • PREVIEW"; color: "#7e8999"; font.pixelSize: 10; font.letterSpacing: 1 }
                Item { height: 24 }
                NavItem { ordinal: 1; label: "Билд"; onClicked: win.page = label }
                NavItem { ordinal: 2; label: "Конструктор"; onClicked: win.page = label }
                NavItem { ordinal: 3; label: "Билды сообщества"; onClicked: win.page = label }
                NavItem { ordinal: 4; label: "Персонажи"; onClicked: win.page = label }
                NavItem { ordinal: 5; label: "Внешность"; onClicked: win.page = label }
                NavItem { ordinal: 6; label: "Клики и тайминги"; onClicked: win.page = label }
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
                        Text { text: "ЭКСПЕРИМЕНТАЛЬНЫЙ UI"; color: "#f2b2a7"; font.pixelSize: 10; font.weight: Font.Bold }
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
                        Text { text: "Новый интерфейс DBD Randomizer · без эмодзи и стандартных рамок"; font.pixelSize: 12; color: win.muted }
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
                                        Canvas {
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
                                        Text { x: 18; y: 151; text: card.perkInfo.locked ? "ЗАКРЕПЛЕНО" : "ДЕМОНСТРАЦИОННЫЙ НАВЫК"; color: card.perkInfo.locked ? "#edb979" : "#8d99a8"; font.pixelSize: 10; font.letterSpacing: .5 }
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
                            visible: win.page !== "Билд"
                            width: parent.width
                            spacing: 15
                            Rectangle {
                                width: parent.width; height: 210; radius: 14; color: win.surface; border.color: win.stroke
                                Column { anchors.centerIn: parent; spacing: 15
                                    Text { text: "Раздел готовится к переносу"; anchors.horizontalCenter: parent.horizontalCenter; color: "#e4e8f0"; font.pixelSize: 19; font.bold: true }
                                    Text { text: "Оригинальные функции работают в Tkinter-версии, но ещё не подключены к Qt."; anchors.horizontalCenter: parent.horizontalCenter; color: win.muted; font.pixelSize: 12 }
                                }
                            }
                            UiButton { width: parent.width; label: "Вернуться к генератору"; primary: true; onClicked: win.page = "Билд" }
                        }
                    }
                }
                Rectangle {
                    Layout.preferredWidth: 320
                    Layout.fillHeight: true
                    color: "#11161e"
                    border.color: "#222b37"
                    Column {
                        x: 19; y: 26; width: parent.width - 38; spacing: 13
                        Text { text: "НАСТРОЙКИ"; color: "#edf1f5"; font.pixelSize: 16; font.bold: true }
                        Text { text: "Тип генерации"; color: win.muted; font.pixelSize: 11 }
                        Repeater {
                            model: [
                                { key: "mixed", label: "Смешанные" },
                                { key: "unique", label: "Уникальные" },
                                { key: "random", label: "Случайные" },
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
                        Rectangle { width: parent.width; height: 1; color: win.stroke }
                        UiButton { width: parent.width; label: "ЭКИПИРОВАТЬ В ИГРЕ"; onClicked: backend.placeholder("Автоэкипировка") }
                        Rectangle {
                            width: parent.width; height: 83; color: "#251f24"; radius: 10; border.color: "#49353e"
                            Text { anchors.fill: parent; anchors.margins: 13; wrapMode: Text.WordWrap; text: "Режим предпросмотра: используются вымышленные навыки. Автоклики, OCR, классы 2v8 и отправка билдов не реализованы."; color: "#dec0bf"; font.pixelSize: 11 }
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
