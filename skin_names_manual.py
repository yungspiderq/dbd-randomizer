# -*- coding: utf-8 -*-
"""Собрано tools/ru_names_missing.py из skin_names_missing.csv — НЕ править вручную.

Русские названия, которых нет на русской вики: id набора -> официальное
название из русского клиента игры (скины персонажей, свежие коллекции,
дефолтные и «кровавые» наборы).

Порядок обновления: заполнить tools/skin_names_missing.csv ->
python tools/ru_names_missing.py -> python tools/resolve_skins.py.
"""

SKIN_RU = {
    # официальное RU-имя из русского клиента (скриншот пользователя, v2.24.0);
    # id соответствует нумерации Module:Datatable/Cosmetics после перенумерации
    # патча 10.x: K28_outfit_008.png = 667
    667: "Морозный кошмар",
}
