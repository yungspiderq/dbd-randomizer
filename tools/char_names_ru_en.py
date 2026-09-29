# -*- coding: utf-8 -*-
"""Таблицы «русское имя (как в dbd_data.py) -> английское имя на wiki.gg»
для портретов персонажей, иконок сил и иконок предметов.

Служебный файл для tools/resolve_char_icons.py; в рантайме не используется.
Сверено с Module:Datatable/Icons и Module:Datatable/Loadout wiki.gg (патч 10.1.2a).
"""

# Выжившие: RU имя -> EN полное имя (ключ Module:Datatable/Icons, файл Survivor*.png).
# Ли Юнчин отсутствует: портрета на вики нет (разрешённое исключение в тестах).
SURVIVOR_RU_EN = {
    "Аврора": "Aurora Stardotter", "Орела Роуз": "Orela Rose", "Рик Граймс": "Rick Grimes",
    "Мишон Граймс": "Michonne Grimes", "Ви Бунясак": "Vee Boonyasak",
    "Дастин Хендерсон": "Dustin Henderson", "Одиннадцать": "Eleven", "Квон Тхэён": "Kwon Tae-young",
    "Ренато Лира": "Renato Lyra", "Габриэль Сома": "Gabriel Soma", "Николас Кейдж": "Nicolas Cage",
    "Эллен Рипли": "Ellen Ripley", "Алан Уэйк": "Alan Wake", "Сейбл Уорд": "Sable Ward",
    "Аэстри Язар": "Troupe", "Лара Крофт": "Lara Croft", "Тревор Бельмонт": "Trevor Belmont",
    "Тори Кейн": "Taurie Cain", "Леон С. Кеннеди": "Leon Scott Kennedy",
    "Джилл Валентайн": "Jill Valentine", "Микаэла Рид": "Mikaela Reid",
    "Хонас Васкес": "Jonah Vasquez", "Хэдди Каур": "Haddie Kaur", "Ада Вонг": "Ada Wong",
    "Ребекка Чемберс": "Rebecca Chambers", "Витторио Тоскано": "Vittorio Toscano",
    "Талита Лира": "Thalita Lyra", "Джейн Ромеро": "Jane Romero", "Эшли Уильямс": "Ash Williams",
    "Стив Харрингтон": "Steve Harrington", "Нэнси Уиллер": "Nancy Wheeler", "Юи Кимура": "Yui Kimura",
    "Зарина Кассир": "Zarina Kassir", "Шерил Мейсон": "Cheryl Mason", "Феликс Рихтер": "Felix Richter",
    "Элоди Ракото": "Élodie Rakoto", "Лори Строуд": "Laurie Strode", "Эйс Висконти": "Ace Visconti",
    "Уильям Овербек": "Bill Overbeck", "Фенг Мин": "Feng Min", "Дэвид Кинг": "David King",
    "Квентин Смит": "Quentin Smith", "Детектив Тэпп": "David Tapp", "Кейт Денсон": "Kate Denson",
    "Адам Фрэнсис": "Adam Francis", "Джефф Йохансен": "Jeff Johansen",
    "Дуайт Фэйрфилд": "Dwight Fairfield", "Мэг Томас": "Meg Thomas",
    "Клодетт Морель": "Claudette Morel", "Джейк Парк": "Jake Park", "Нея Карлссон": "Nea Karlsson",
    "Шейн Уиигваас": "Shane Wiigwaas", "Ёити Асакава": "Yoichi Asakawa",
    "Ли Юнчин": "Yun-Jin Lee",
}

# Убийцы: RU имя -> id в Module:KillerPortraitsSprite (K38+ портретов в спрайте нет).
KILLER_RU_SPRITE = {
    "Охотник": "K01 TheTrapper Portrait", "Призрак": "K02 TheWraith Portrait",
    "Деревенщина": "K03 TheHillbilly Portrait", "Медсестра": "K04 TheNurse Portrait",
    "Ведьма": "K05 TheHag Portrait", "Тень": "K06 TheShape Portrait",
    "Доктор": "K07 TheDoctor Portrait", "Охотница": "K08 TheHuntress Portrait",
    "Каннибал": "K09 TheCannibal Portrait", "Кошмар": "K10 TheNightmare Portrait",
    "Свинья": "K11 ThePig Portrait", "Клоун": "K12 TheClown Portrait",
    "Дух": "K13 TheSpirit Portrait", "Легион": "K14 TheLegion Portrait",
    "Чума": "K15 ThePlague Portrait", "Гоуст Фейс": "K16 TheGhostface Portrait",
    "Демогоргон": "K17 TheDemogorgon Portrait", "Они": "K18 TheOni Portrait",
    "Стрелок": "K19 TheDeathslinger Portrait", "Палач": "K20 TheExecutioner Portrait",
    "Мор": "K21 TheBlight Portrait", "Близнецы": "K22 TheTwins Portrait",
    "Трюкач": "K23 TheTrickster Portrait", "Немезис": "K24 TheNemesis Portrait",
    "Сенобит": "K25 TheCenobite Portrait", "Художница": "K26 TheArtist Portrait",
    "Онрё": "K27 TheOnryo Portrait", "Грязь": "K28 TheDredge Portrait",
    "Кукловод": "K29 TheMasterMind Portrait", "Рыцарь": "K30 TheKnight Portrait",
    "Торговка черепами": "K31 TheSkullMerchant Portrait",
    "Сингулярность": "K32 TheSingularity Portrait", "Ксеноморф": "K33 TheXenomorph Portrait",
    "Хороший парень": "K34 TheYerkes Portrait", "Неведомое": "K35 TheUnknown Portrait",
    "Лич": "K36 TheLich Portrait", "Тёмный властелин": "K37 TheDracula Portrait",
}

# Предметы выживших: RU имя -> EN имя (ключ Module:Datatable/Icons, файл iconItems*).
ITEM_RU_EN = {
    "Маскарадный фонарик": "Masquerade Flashlight", "Фонарик годовщины": "Anniversary Flashlight",
    "Блуждающий огонек": "Will O' Wisp", "Фонарик": "Flashlight",
    "Спортивный фонарик": "Sport Flashlight", "Тяжелый фонарь": "Utility Flashlight",
    "Банкетный фонарик": "Banquet Flashlight",
    "Маскарадная аптечка": "Masquerade Med-Kit", "Аптечка годовщины": "Anniversary Med-Kit",
    "Походная аптечка": "Camping Aid Kit", "Ланчбокс всех святых": "All Hallows' Eve Lunchbox",
    "Аптечка": "Med-Kit", "Аптечка первой помощи": "First Aid Kit",
    "Аптечка лесничего": "Ranger Med-Kit", "Банкетная аптечка": "Banquet Med-Kit",
    "Изношенные инструменты": "Worn-Out Tools", "Ящик с инструментами": "Toolbox",
    "Инструменты механика": "Mechanic's Toolbox",
    "Вместительный ящик с инструментами": "Commodious Toolbox",
    "Инструменты инженера": "Engineer's Toolbox", "Инструменты Алекса": "Alex's Toolbox",
    "Праздничный ящик с инструментами": "Festive Toolbox",
    "Юбилейный ящик с инструментами": "Anniversary Toolbox",
    "Маскарадный ящик с инструментами": "Masquerade Toolbox",
    "Банкетный ящик с инструментами": "Banquet Toolbox",
    "Загадочная карта": "Cryptic Map", "Карта кровавого чувства": "Bloodsense Map",
    "Сломанный ключ": "Broken Key", "Потертый ключ": "Dull Key", "Ключ скелета": "Skeleton Key",
    "Флакон подмастерья с туманом": "Apprentice's Fog Vial",
    "Флакон мастерового с туманом": "Artisan's Fog Vial", "Флакон Виго с туманом": "Vigo's Fog Vial",
    "Туманный кристалл": "Fog Crystal",
    "Китайская хлопушка": "Chinese Firecracker", "Новогодняя хлопушка": "Winter Party Starter",
    "Хлопушка третьей годовщины": "Third Year Party Starter",
}

# Убийцы K38+: портреты лежат отдельными файлами (в спрайт-лист не вошли).
KILLER_RU_PORTRAIT = {
    "Егерь": "K38 TheHoundmaster Portrait.png",
    "Гуль": "K39 TheGhoul Portrait.png",
    "Аниматроник": "K40 TheAnimatronic Portrait.png",
    "Красу": "K41 TheKrasue Portrait.png",
    "Первый": "K42 TheFirst Portrait.png",
    "Слэшер": "K43 TheSlasher Portrait.png",
    "Правосудие": "K44 TheJudgment Portrait.png",
}
