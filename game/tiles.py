"""Типы земли (нижний слой карты). Номер типа хранится в массиве zone.ground."""

STEPPE, SAND, SALT, ASPHALT, DIRT, WOOD, CONCRETE, RAIL, WATER, FIELD, BUNKER, RIVERBED, LINO = range(13)

# color — основной цвет, spots — цвета крапинок, indoor — пол внутри помещения
# (крыша над головой: нет солнца, пыли и дождя), solid — нельзя пройти.
GROUND = {
    STEPPE:   {"name": "Степь",         "color": (150, 138, 88),  "spots": [(128, 120, 72), (170, 156, 100), (118, 124, 78)]},
    SAND:     {"name": "Песок",         "color": (196, 172, 122), "spots": [(180, 156, 108), (210, 188, 140)]},
    SALT:     {"name": "Солончак",      "color": (206, 202, 186), "spots": [(226, 224, 214), (180, 172, 150)]},
    ASPHALT:  {"name": "Асфальт",       "color": (88, 86, 82),    "spots": [(70, 68, 66), (104, 100, 94)]},
    DIRT:     {"name": "Грунтовка",     "color": (148, 120, 84),  "spots": [(128, 102, 70), (164, 136, 98)]},
    WOOD:     {"name": "Дощатый пол",   "color": (122, 88, 58),   "spots": [(104, 74, 48)], "indoor": True},
    CONCRETE: {"name": "Бетон",         "color": (128, 126, 118), "spots": [(112, 110, 104), (140, 138, 130)], "indoor": True},
    RAIL:     {"name": "Железная дорога", "color": (110, 96, 78), "spots": [(96, 84, 68)]},
    WATER:    {"name": "Арык",          "color": (84, 98, 72),    "spots": [(70, 86, 62), (104, 116, 84)], "solid": True, "water": True},
    FIELD:    {"name": "Хлопковое поле", "color": (132, 112, 76), "spots": [(116, 98, 66)]},
    BUNKER:   {"name": "Пол бункера",   "color": (72, 78, 72),    "spots": [(62, 68, 62), (84, 90, 84)], "indoor": True},
    RIVERBED: {"name": "Высохшее русло", "color": (164, 134, 96), "spots": [(140, 112, 80)]},
    LINO:     {"name": "Линолеум",      "color": (112, 122, 104), "spots": [(98, 108, 92)], "indoor": True},
}


def is_indoor(g):
    return GROUND[g].get("indoor", False)


def is_solid(g):
    return GROUND[g].get("solid", False)
