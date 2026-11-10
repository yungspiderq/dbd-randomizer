"""Interactive UI preview backend. Game automation is intentionally not connected."""
import random

from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtGui import QGuiApplication


PERKS = {
    "survivor": [
        "Рывок", "Ночной дозор", "Стойкость", "Тихий шаг", "План побега",
        "Командный дух", "Острый слух", "Решительный ход", "Второе дыхание",
        "Хладнокровие", "Бдительность", "Спасение"
    ],
    "killer": [
        "Тёмный след", "Погоня", "Засада", "Контроль", "Жестокий ритм",
        "Чутьё", "Преимущество", "Тихая охота", "Дисциплина", "Охота",
        "Ловушка", "Давление"
    ]
}


class PreviewBackend(QObject):
    perksChanged = Signal()
    roleChanged = Signal()
    modeChanged = Signal()
    statusChanged = Signal()
    historyChanged = Signal()
    optionsChanged = Signal()

    def __init__(self):
        super().__init__()
        self._role = "survivor"
        self._mode = "mixed"
        self._perks = [self._empty(i) for i in range(4)]
        self._status = "ПРЕДПРОСМОТР: автоматизация, OCR и данные DBD не подключены."
        self._history = []
        self._options = {"addons": True, "appearance": False, "challenge": False, "owned": False}

    @staticmethod
    def _empty(index):
        return {"index": index + 1, "name": "Слот не заполнен", "locked": False, "filled": False}

    @Property("QVariantList", notify=perksChanged)
    def perks(self):
        return [dict(p) for p in self._perks]

    @Property(str, notify=roleChanged)
    def role(self):
        return self._role

    @Property(str, notify=modeChanged)
    def mode(self):
        return self._mode

    @Property(str, notify=statusChanged)
    def status(self):
        return self._status

    @Property("QVariantList", notify=historyChanged)
    def history(self):
        return list(self._history)

    @Property("QVariantMap", notify=optionsChanged)
    def options(self):
        return dict(self._options)

    def _message(self, message):
        self._status = message
        self.statusChanged.emit()

    @Slot(str)
    def setRole(self, role):
        if role not in PERKS or role == self._role:
            return
        self._role = role
        self._perks = [self._empty(i) for i in range(4)]
        self.roleChanged.emit()
        self.perksChanged.emit()
        self._message("Роль переключена. Тестовые навыки сброшены.")

    @Slot(str)
    def setMode(self, mode):
        if mode not in ("mixed", "unique", "random", "general"):
            return
        self._mode = mode
        self.modeChanged.emit()
        self._message("Режим сохранён только для демонстрации.")

    @Slot(str)
    def toggleOption(self, key):
        if key not in self._options:
            return
        self._options[key] = not self._options[key]
        self.optionsChanged.emit()
        self._message("Опция изменена только в демонстрации.")

    @Slot()
    def generate(self):
        used = {p["name"] for p in self._perks if p["locked"] and p["filled"]}
        unlocked = [i for i, p in enumerate(self._perks) if not p["locked"]]
        choices = random.sample([p for p in PERKS[self._role] if p not in used], len(unlocked))
        for i, name in zip(unlocked, choices):
            self._perks[i] = {"index": i + 1, "name": name, "locked": False, "filled": True}
        self.perksChanged.emit()
        build = " / ".join(p["name"] for p in self._perks)
        self._history = [build] + self._history[:5]
        self.historyChanged.emit()
        self._message("Сгенерирован тестовый билд; названия навыков вымышлены.")

    @Slot(int)
    def toggleLock(self, index):
        if not 0 <= index < 4 or not self._perks[index]["filled"]:
            return
        self._perks[index]["locked"] = not self._perks[index]["locked"]
        self.perksChanged.emit()

    @Slot(int)
    def reroll(self, index):
        if not 0 <= index < 4 or self._perks[index]["locked"]:
            return
        taken = {p["name"] for i, p in enumerate(self._perks) if i != index and p["filled"]}
        choices = [p for p in PERKS[self._role] if p not in taken]
        self._perks[index] = {"index": index + 1, "name": random.choice(choices), "locked": False, "filled": True}
        self.perksChanged.emit()

    @Slot()
    def copyBuild(self):
        values = [p["name"] for p in self._perks if p["filled"]]
        if not values:
            self._message("Сначала создайте тестовый билд.")
            return
        QGuiApplication.clipboard().setText("DBD Randomizer PREVIEW\n" + "\n".join(values))
        self._message("Тестовый билд скопирован.")

    @Slot(str)
    def placeholder(self, action):
        self._message(action + ": функция пока недоступна в QML Preview. Оригинал не изменён.")
