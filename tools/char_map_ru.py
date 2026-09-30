# -*- coding: utf-8 -*-
"""Карта «английское имя персонажа из Module:Datatable -> русское имя из dbd_data.py».

Зачем отдельный файл
--------------------
`tools/char_names_ru_en.py` хранит обратную карту (RU -> EN) и нужна для иконок.
Для скинов сопоставление по «нормализованному EN имени» ненадёжно: в вики
`Detective David Tapp`, `William "Bill" Overbeck`, `Ashley J. Williams`,
`Lee Yun-jin`, `Aestri Yazar & Baermar Uraz` не совпадают с ключами
SURVIVOR_RU_EN буквально, а часть убийц там вообще отсутствует.

Вторая причина — номера. `Module:Datatable/Cosmetics` ссылается на персонажей
ЧИСЛОМ (`killer = 18`), и это число = id из `Module:Datatable` (p.killers /
p.survivors), то есть внутренний id игры. Он НЕ равен номеру спрайт-файла
`K18 TheOni Portrait` (у спрайта Hag/Shape идут в другом порядке, чем id 5/6),
поэтому старый генератор скинов путал Тень и Ведьму. Здесь связь
«id -> EN имя -> RU имя» строится через саму вики и проверяется по dbd_data.

Служебный файл для tools/resolve_skins.py; в рантайме не используется.
Проверено по патчу 10.1.2_live (44 убийцы, 54 выживших).
"""

# Убийцы: EN имя из Module:Datatable (p.killers) -> RU имя из dbd_data.KILLERS.
KILLER_EN_RU = {
    "Trapper": "Охотник",
    "Wraith": "Призрак",
    "Hillbilly": "Деревенщина",
    "Nurse": "Медсестра",
    "Shape": "Тень",
    "Hag": "Ведьма",
    "Doctor": "Доктор",
    "Huntress": "Охотница",
    "Cannibal": "Каннибал",
    "Nightmare": "Кошмар",
    "Pig": "Свинья",
    "Clown": "Клоун",
    "Spirit": "Дух",
    "Legion": "Легион",
    "Plague": "Чума",
    "Ghost Face": "Гоуст Фейс",
    "Demogorgon": "Демогоргон",
    "Oni": "Они",
    "Deathslinger": "Стрелок",
    "Executioner": "Палач",
    "Blight": "Мор",
    "Twins": "Близнецы",
    "Trickster": "Трюкач",
    "Nemesis": "Немезис",
    "Cenobite": "Сенобит",
    "Artist": "Художница",
    "Onryō": "Онрё",
    "Dredge": "Грязь",
    "Mastermind": "Кукловод",
    "Knight": "Рыцарь",
    "Skull Merchant": "Торговка черепами",
    "Singularity": "Сингулярность",
    "Xenomorph": "Ксеноморф",
    "Good Guy": "Хороший парень",
    "Unknown": "Неведомое",
    "Lich": "Лич",
    "Dark Lord": "Тёмный властелин",
    "Houndmaster": "Егерь",
    "Ghoul": "Гуль",
    "Animatronic": "Аниматроник",
    "Krasue": "Красу",
    "First": "Первый",
    "Slasher": "Слэшер",
    "Judgment": "Правосудие",
}

# Выжившие: EN имя из Module:Datatable (p.survivors) -> RU имя из dbd_data.SURVIVORS.
SURVIVOR_EN_RU = {
    "Dwight Fairfield": "Дуайт Фэйрфилд",
    "Meg Thomas": "Мэг Томас",
    "Claudette Morel": "Клодетт Морель",
    "Jake Park": "Джейк Парк",
    "Nea Karlsson": "Нея Карлссон",
    "Laurie Strode": "Лори Строуд",
    "Ace Visconti": "Эйс Висконти",
    'William "Bill" Overbeck': "Уильям Овербек",
    "Feng Min": "Фенг Мин",
    "David King": "Дэвид Кинг",
    "Quentin Smith": "Квентин Смит",
    "Detective David Tapp": "Детектив Тэпп",
    "Kate Denson": "Кейт Денсон",
    "Adam Francis": "Адам Фрэнсис",
    'Jeffrey "Jeff" Johansen': "Джефф Йохансен",
    "Jane Romero": "Джейн Ромеро",
    "Ashley J. Williams": "Эшли Уильямс",
    "Nancy Wheeler": "Нэнси Уиллер",
    "Steve Harrington": "Стив Харрингтон",
    "Yui Kimura": "Юи Кимура",
    "Zarina Kassir": "Зарина Кассир",
    "Cheryl Mason": "Шерил Мейсон",
    "Felix Richter": "Феликс Рихтер",
    "Élodie Rakoto": "Элоди Ракото",
    "Lee Yun-jin": "Ли Юнчин",
    "Jill Valentine": "Джилл Валентайн",
    "Leon Scott Kennedy": "Леон С. Кеннеди",
    "Mikaela Reid": "Микаэла Рид",
    "Jonah Vasquez": "Хонас Васкес",
    "Yoichi Asakawa": "Ёити Асакава",
    "Haddie Kaur": "Хэдди Каур",
    "Ada Wong": "Ада Вонг",
    "Rebecca Chambers": "Ребекка Чемберс",
    "Vittorio Toscano": "Витторио Тоскано",
    "Thalita Lyra": "Талита Лира",
    "Renato Lyra": "Ренато Лира",
    "Gabriel Soma": "Габриэль Сома",
    "Nicolas Cage": "Николас Кейдж",
    "Ellen Ripley": "Эллен Рипли",
    "Alan Wake": "Алан Уэйк",
    "Sable Ward": "Сейбл Уорд",
    "Aestri Yazar & Baermar Uraz": "Аэстри Язар",
    "Lara Croft": "Лара Крофт",
    "Trevor Belmont": "Тревор Бельмонт",
    "Taurie Cain": "Тори Кейн",
    "Orela Rose": "Орела Роуз",
    "Rick Grimes": "Рик Граймс",
    "Michonne Grimes": "Мишон Граймс",
    "Vee Boonyasak": "Ви Бунясак",
    "Dustin Henderson": "Дастин Хендерсон",
    "Eleven": "Одиннадцать",
    "Kwon Tae-young": "Квон Тхэён",
    "Shane Wiigwaas": "Шейн Уиигваас",
    "Aurora Stardotter": "Аврора",
}

# Редкости: номер из вики -> (EN ярлык, RU ярлык как в русском клиенте).
# Список номеров приведён в комментарии Module:Datatable/Cosmetics.
RARITIES = {
    1: ("Common", "обычный"),
    2: ("Uncommon", "необычный"),
    3: ("Rare", "редкий"),
    4: ("Very Rare", "очень редкий"),
    5: ("Ultra Rare", "крайне редкий"),
    6: ("Teachable", "обучаемый"),
    7: ("Legendary", "легендарный"),
    8: ("Special Event", "ивентовый"),
    9: ("Artifact", "артефакт"),
    10: ("Limited", "лимитированный"),
    12: ("Ascended", "вознесённый"),
    13: ("Visceral", "висцеральный"),
}
