"""Иконки предметов для инвентаря. Каждая рисуется кодом на холсте 40×40.

Чтобы не писать 70 отдельных функций, иконки собираются из «форм»:
банка, бутылка, коробка, пиала, книга, куртка... с разными цветами.
Готовые иконки кэшируются в словаре ICONS.
"""
import math

import pygame

from .data import ITEMS

S = 40           # размер иконки
ICONS = {}


def _shade(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c)


# ------------------------------------------------------------------ формы

def can(s, label, top=(190, 190, 196)):
    pygame.draw.rect(s, (150, 150, 158), (10, 10, 20, 24), border_radius=3)
    pygame.draw.rect(s, label, (10, 15, 20, 13))
    pygame.draw.ellipse(s, top, (10, 6, 20, 8))
    pygame.draw.ellipse(s, (120, 120, 126), (10, 30, 20, 7))
    pygame.draw.line(s, _shade(label, 1.4), (13, 18), (13, 25), 2)


def bottle(s, liquid, glass=(170, 200, 190), level=0.75, label=None):
    pygame.draw.rect(s, glass, (17, 3, 6, 9))
    pygame.draw.rect(s, (90, 70, 50), (16, 2, 8, 3))
    pygame.draw.rect(s, glass, (12, 11, 16, 26), border_radius=5)
    h = int(24 * level)
    pygame.draw.rect(s, liquid, (13, 36 - h, 14, h), border_radius=4)
    if label:
        pygame.draw.rect(s, label, (12, 20, 16, 8))
    pygame.draw.line(s, (235, 245, 245), (15, 14), (15, 30), 2)


def box(s, col, w=24, h=18, stripe=None, text_col=None):
    x, y = (S - w) // 2, (S - h) // 2 + 2
    pygame.draw.rect(s, col, (x, y, w, h))
    pygame.draw.polygon(s, _shade(col, 1.25), [(x, y), (x + 6, y - 5), (x + w + 6, y - 5), (x + w, y)])
    pygame.draw.polygon(s, _shade(col, 0.7), [(x + w, y), (x + w + 6, y - 5), (x + w + 6, y + h - 5), (x + w, y + h)])
    if stripe:
        pygame.draw.rect(s, stripe, (x, y + h // 3, w, h // 3))
    if text_col:
        for i in range(3):
            pygame.draw.line(s, text_col, (x + 4, y + 4 + i * 4), (x + w - 6, y + 4 + i * 4))


def bowl(s, content):
    pygame.draw.ellipse(s, content, (7, 12, 26, 10))
    pygame.draw.polygon(s, (230, 230, 236), [(6, 17), (34, 17), (28, 31), (12, 31)])
    pygame.draw.line(s, (60, 100, 170), (9, 22), (31, 22), 2)   # синий узор пиалы
    pygame.draw.ellipse(s, _shade(content, 1.2), (10, 13, 20, 6))


def book(s, col, title_col=(220, 200, 120)):
    pygame.draw.rect(s, (230, 224, 206), (11, 7, 22, 28))
    pygame.draw.rect(s, col, (8, 5, 22, 30))
    pygame.draw.rect(s, _shade(col, 0.7), (8, 5, 4, 30))
    pygame.draw.rect(s, title_col, (15, 11, 12, 4))
    pygame.draw.rect(s, title_col, (15, 18, 9, 2))


def paper(s, ink=(60, 60, 110), col=(226, 218, 190)):
    pygame.draw.polygon(s, col, [(9, 6), (28, 5), (32, 33), (11, 35)])
    for i in range(5):
        pygame.draw.line(s, ink, (13, 11 + i * 5), (28, 10 + i * 5 + (i % 2)))


def jacket(s, col, stripes=None, quilt=False):
    pts = [(8, 12), (15, 7), (25, 7), (32, 12), (34, 22), (29, 22), (29, 35), (11, 35), (11, 22), (6, 22)]
    pygame.draw.polygon(s, col, pts)
    pygame.draw.line(s, _shade(col, 0.6), (20, 9), (20, 35), 2)
    if stripes:
        for x in range(12, 30, 4):
            pygame.draw.line(s, stripes, (x, 10), (x, 34), 2)
    if quilt:
        for y in range(14, 35, 5):
            pygame.draw.line(s, _shade(col, 0.75), (11, y), (29, y))
    pygame.draw.polygon(s, _shade(col, 0.8), pts, 1)


def blade(s, handle, metal=(190, 196, 200), length=24):
    pygame.draw.line(s, handle, (8, 32), (16, 24), 5)
    pygame.draw.polygon(s, metal, [(15, 22), (18, 25), (8 + length, 6), (6 + length, 4)])


def long_tool(s, shaft, head_fn):
    pygame.draw.line(s, shaft, (8, 34), (30, 8), 4)
    head_fn()


def first_letter(s, it):
    pygame.draw.rect(s, (90, 80, 60), (6, 6, 28, 28), border_radius=4)
    f = pygame.font.Font(None, 26)
    img = f.render(it["name"][0], True, (230, 220, 190))
    s.blit(img, (20 - img.get_width() // 2, 20 - img.get_height() // 2))


# ------------------------------------------------------------------ все предметы

def _draw(s, iid):
    it = ITEMS[iid]
    D = {
        "tushenka": lambda: can(s, (190, 60, 50)),
        "kilka": lambda: (pygame.draw.ellipse(s, (160, 160, 166), (5, 14, 30, 16)), pygame.draw.ellipse(s, (200, 70, 40), (8, 16, 24, 11)),
                          pygame.draw.line(s, (230, 220, 200), (12, 21), (28, 21), 2)),
        "condensed": lambda: can(s, (70, 120, 190), top=(220, 220, 230)),
        "lepeshka": lambda: (pygame.draw.circle(s, (200, 150, 80), (20, 20), 15), pygame.draw.circle(s, (220, 180, 110), (20, 20), 9),
                             [pygame.draw.circle(s, (150, 100, 50), (20 + int(5 * math.cos(a)), 20 + int(5 * math.sin(a))), 1) for a in range(0, 7)]),
        "suhari": lambda: [pygame.draw.rect(s, (200, 160, 100), (8 + i * 8, 14 + (i % 2) * 6, 10, 12), border_radius=2) for i in range(3)],
        "kurt": lambda: [pygame.draw.circle(s, (238, 232, 214), (12 + (i % 3) * 8, 16 + (i // 3) * 9), 5) for i in range(6)],
        "carrot": lambda: (pygame.draw.polygon(s, (230, 170, 50), [(10, 12), (16, 9), (32, 32)]), pygame.draw.line(s, (90, 140, 60), (12, 10), (7, 4), 3)),
        "rice": lambda: box(s, (230, 226, 210), stripe=(60, 130, 80)),
        "tea_dry": lambda: box(s, (60, 120, 70), stripe=(220, 200, 90)),
        "meat_raw": lambda: (pygame.draw.ellipse(s, (190, 60, 60), (7, 11, 26, 18)), pygame.draw.ellipse(s, (240, 220, 210), (21, 15, 8, 6))),
        "meat_cooked": lambda: (pygame.draw.ellipse(s, (130, 70, 40), (7, 11, 26, 18)), pygame.draw.line(s, (90, 50, 30), (12, 18), (28, 22), 2)),
        "plov": lambda: (bowl(s, (220, 160, 70)), pygame.draw.circle(s, (200, 100, 40), (17, 15), 2), pygame.draw.circle(s, (120, 70, 40), (23, 16), 2)),
        "tea_hot": lambda: (bowl(s, (170, 140, 60)), pygame.draw.lines(s, (220, 220, 220), False, [(16, 10), (18, 6), (16, 2)])),
        "thorn_tea": lambda: bowl(s, (130, 100, 60)),
        "water_clean": lambda: bottle(s, (110, 170, 220)),
        "water_dirty": lambda: bottle(s, (130, 110, 60)),
        "kumys": lambda: (pygame.draw.rect(s, (200, 200, 206), (11, 10, 18, 26), border_radius=4), pygame.draw.rect(s, (240, 240, 230), (12, 18, 16, 14))),
        "vodka": lambda: bottle(s, (230, 240, 245), glass=(200, 220, 225), level=0.85, label=(200, 60, 50)),
        "bottle_empty": lambda: bottle(s, (0, 0, 0, 0), level=0),
        "shovel": lambda: long_tool(s, (130, 95, 60), lambda: pygame.draw.polygon(s, (120, 130, 120), [(24, 6), (34, 4), (36, 14), (28, 16)])),
        "crowbar": lambda: (pygame.draw.line(s, (60, 60, 70), (10, 34), (28, 6), 4), pygame.draw.line(s, (60, 60, 70), (28, 6), (34, 9), 4),
                            pygame.draw.line(s, (180, 40, 40), (10, 34), (14, 28), 4)),
        "pipe": lambda: (pygame.draw.line(s, (140, 140, 150), (8, 32), (32, 8), 6), pygame.draw.line(s, (190, 190, 196), (9, 30), (30, 9), 2)),
        "axe": lambda: long_tool(s, (130, 95, 60), lambda: pygame.draw.polygon(s, (160, 166, 170), [(22, 6), (30, 4), (36, 14), (28, 16)])),
        "knife": lambda: blade(s, (90, 60, 40)),
        "ketmen": lambda: long_tool(s, (130, 95, 60), lambda: pygame.draw.polygon(s, (110, 110, 110), [(22, 2), (36, 8), (34, 14), (24, 10)])),
        "hammer": lambda: (pygame.draw.line(s, (130, 95, 60), (10, 34), (24, 12), 4), pygame.draw.rect(s, (90, 90, 96), (18, 5, 16, 8))),
        "nail_bat": lambda: (pygame.draw.line(s, (150, 110, 70), (8, 34), (30, 8), 7),
                             [pygame.draw.line(s, (200, 200, 200), (20 + i * 3, 16 - i * 3), (24 + i * 3, 18 - i * 3)) for i in range(3)]),
        "pm": lambda: (pygame.draw.rect(s, (50, 50, 56), (6, 13, 26, 8)), pygame.draw.polygon(s, (60, 50, 44), [(9, 21), (17, 21), (15, 33), (8, 33)])),
        "shotgun": lambda: (pygame.draw.line(s, (60, 60, 66), (14, 22), (38, 6), 4), pygame.draw.polygon(s, (120, 80, 50), [(2, 36), (6, 26), (18, 20), (16, 26)])),
        "ammo_9": lambda: [(pygame.draw.rect(s, (200, 160, 60), (10 + i * 7, 16, 5, 14)), pygame.draw.ellipse(s, (150, 120, 90), (10 + i * 7, 11, 5, 9))) for i in range(3)],
        "ammo_16": lambda: [(pygame.draw.rect(s, (180, 40, 40), (9 + i * 8, 13, 6, 16)), pygame.draw.rect(s, (200, 170, 70), (9 + i * 8, 26, 6, 5))) for i in range(3)],
        "bandage": lambda: (pygame.draw.circle(s, (240, 240, 236), (20, 20), 12), pygame.draw.circle(s, (210, 210, 206), (20, 20), 5)),
        "bandage_home": lambda: (pygame.draw.circle(s, (210, 200, 180), (20, 20), 12), pygame.draw.circle(s, (180, 170, 150), (20, 20), 5)),
        "rag": lambda: pygame.draw.polygon(s, (150, 140, 120), [(6, 14), (20, 8), (34, 14), (30, 32), (12, 30)]),
        "antiseptic": lambda: bottle(s, (40, 150, 60), glass=(200, 210, 200), level=0.6),
        "splint": lambda: ([pygame.draw.rect(s, (180, 140, 90), (10 + i * 8, 6, 6, 28)) for i in range(3)], pygame.draw.rect(s, (240, 240, 236), (8, 16, 26, 6))),
        "analgin": lambda: (pygame.draw.rect(s, (220, 220, 226), (8, 12, 24, 16), border_radius=3),
                            [pygame.draw.circle(s, (250, 250, 250), (13 + i * 7, 20), 3) for i in range(3)]),
        "charcoal": lambda: (pygame.draw.rect(s, (200, 200, 206), (8, 12, 24, 16), border_radius=3),
                             [pygame.draw.circle(s, (30, 30, 30), (13 + i * 7, 20), 3) for i in range(3)]),
        "antidote": lambda: (pygame.draw.rect(s, (220, 230, 230), (16, 6, 8, 28), border_radius=3), pygame.draw.rect(s, (230, 200, 40), (17, 16, 6, 16)),
                             pygame.draw.rect(s, (200, 40, 40), (16, 12, 8, 3))),
        "mask": lambda: (pygame.draw.ellipse(s, (236, 236, 230), (8, 10, 24, 20)), pygame.draw.line(s, (120, 160, 200), (4, 16), (10, 18), 2),
                         pygame.draw.line(s, (120, 160, 200), (36, 16), (30, 18), 2)),
        "gasmask": lambda: (pygame.draw.ellipse(s, (70, 90, 70), (8, 4, 24, 26)), pygame.draw.circle(s, (180, 200, 200), (15, 14), 4),
                            pygame.draw.circle(s, (180, 200, 200), (25, 14), 4), pygame.draw.rect(s, (60, 60, 60), (14, 26, 12, 10))),
        "gas_filter": lambda: (pygame.draw.rect(s, (90, 100, 90), (11, 10, 18, 24), border_radius=4), pygame.draw.rect(s, (50, 50, 50), (16, 6, 8, 5))),
        "gas_filter_home": lambda: can(s, (60, 60, 60)),
        "vatnik": lambda: jacket(s, (70, 80, 70), quilt=True),
        "chapan": lambda: jacket(s, (130, 50, 70), stripes=(60, 110, 70)),
        "jacket": lambda: jacket(s, (40, 80, 140)),
        "panama": lambda: (pygame.draw.ellipse(s, (200, 190, 150), (4, 20, 32, 10)), pygame.draw.ellipse(s, (210, 200, 160), (11, 10, 18, 16))),
        "doppi": lambda: (pygame.draw.rect(s, (20, 20, 20), (9, 14, 22, 14)), pygame.draw.ellipse(s, (20, 20, 20), (9, 9, 22, 10)),
                          [pygame.draw.line(s, (240, 240, 240), (12 + i * 5, 18), (14 + i * 5, 24)) for i in range(4)]),
        "helmet": lambda: (pygame.draw.ellipse(s, (230, 120, 30), (8, 9, 24, 22)), pygame.draw.rect(s, (230, 120, 30), (4, 24, 32, 5))),
        "backpack": lambda: (pygame.draw.rect(s, (110, 110, 70), (9, 8, 22, 26), border_radius=5), pygame.draw.rect(s, (90, 90, 56), (12, 20, 16, 10)),
                             pygame.draw.arc(s, (60, 60, 40), (13, 2, 14, 12), 0, math.pi, 2)),
        "bag": lambda: ([pygame.draw.rect(s, (180, 40, 40) if (i + j) % 2 else (230, 230, 230), (8 + i * 6, 12 + j * 6, 6, 6)) for i in range(4) for j in range(4)],
                        pygame.draw.arc(s, (60, 60, 60), (13, 4, 14, 14), 0, math.pi, 2)),
        "flashlight": lambda: (pygame.draw.rect(s, (60, 60, 64), (8, 12, 20, 16)), pygame.draw.rect(s, (230, 230, 170), (28, 13, 5, 14)),
                               pygame.draw.rect(s, (200, 60, 50), (13, 9, 6, 3))),
        "batteries": lambda: [(pygame.draw.rect(s, (40, 40, 44), (10 + i * 10, 10, 8, 22)), pygame.draw.rect(s, (220, 180, 50), (10 + i * 10, 10, 8, 6))) for i in range(2)],
        "planks": lambda: [pygame.draw.rect(s, (170 - i * 10, 130 - i * 8, 80), (4, 10 + i * 8, 32, 6)) for i in range(3)],
        "nails": lambda: [pygame.draw.line(s, (170, 170, 176), (8 + i * 6, 10 + (i % 2) * 3), (12 + i * 6, 32), 2) for i in range(5)],
        "scrap": lambda: (pygame.draw.polygon(s, (120, 90, 70), [(6, 28), (14, 10), (24, 16), (34, 8), (32, 30)]), pygame.draw.line(s, (150, 150, 150), (8, 32), (30, 20), 3)),
        "wire": lambda: [pygame.draw.circle(s, (180, 180, 186), (20, 20), r, 1) for r in (6, 9, 12)],
        "can_empty": lambda: can(s, (150, 150, 158)),
        "matches": lambda: box(s, (210, 190, 120), w=22, h=12, stripe=(160, 40, 30)),
        "brushwood": lambda: [pygame.draw.line(s, (110, 85, 60), (6, 26 + i * 3), (34, 14 + i * 4), 3) for i in range(3)],
        "thorn": lambda: [pygame.draw.line(s, (100, 130, 70), (20, 34), (20 + int(14 * math.cos(a)), 34 - int(16 * abs(math.sin(a)))), 2) for a in (0.3, 1.0, 1.6, 2.2, 2.8)],
        "tarp": lambda: (pygame.draw.polygon(s, (90, 110, 80), [(4, 12), (36, 8), (34, 32), (6, 30)]), pygame.draw.line(s, (70, 90, 60), (8, 20), (32, 18))),
        "twine": lambda: (pygame.draw.ellipse(s, (190, 160, 110), (8, 10, 24, 20)), [pygame.draw.line(s, (150, 120, 80), (10, 14 + i * 4), (30, 14 + i * 4)) for i in range(4)]),
        "kazan": lambda: (pygame.draw.ellipse(s, (40, 40, 40), (4, 12, 32, 22)), pygame.draw.ellipse(s, (70, 70, 70), (6, 10, 28, 8)),
                          pygame.draw.line(s, (60, 60, 60), (2, 14), (38, 14), 3)),
        "water_filter": lambda: bottle(s, (40, 40, 40), level=0.5, label=(200, 200, 200)),
        "cigarettes": lambda: box(s, (220, 220, 210), w=20, h=22, stripe=(180, 40, 40)),
        "cassette": lambda: (pygame.draw.rect(s, (40, 40, 44), (5, 10, 30, 20), border_radius=2), pygame.draw.rect(s, (220, 200, 120), (8, 12, 24, 8)),
                             pygame.draw.circle(s, (230, 230, 230), (14, 24), 3), pygame.draw.circle(s, (230, 230, 230), (26, 24), 3)),
        "radio": lambda: (pygame.draw.rect(s, (60, 50, 44), (4, 12, 32, 22), border_radius=3), pygame.draw.rect(s, (200, 190, 150), (8, 16, 16, 6)),
                          pygame.draw.circle(s, (30, 30, 30), (29, 26), 4), pygame.draw.line(s, (180, 180, 180), (30, 12), (36, 2), 2)),
        "tenge": lambda: [pygame.draw.rect(s, (110, 160, 170), (6 + i * 3, 12 + i * 3, 26, 14)) for i in range(3)],
        "dollars": lambda: (pygame.draw.rect(s, (110, 150, 90), (5, 12, 30, 16)), pygame.draw.circle(s, (80, 120, 70), (20, 20), 5)),
        "book_diy": lambda: book(s, (190, 80, 40)),
        "book_tech": lambda: book(s, (50, 90, 160)),
        "book_med": lambda: book(s, (220, 220, 214), title_col=(200, 40, 40)),
        "book_kk": lambda: book(s, (60, 150, 190), title_col=(240, 200, 60)),
        "book_cook": lambda: book(s, (120, 60, 50)),
        "note_uz": lambda: paper(s),
        "note_kk": lambda: paper(s, ink=(40, 80, 140)),
        "note_ru": lambda: paper(s, ink=(70, 70, 70)),
        "lab_journal": lambda: book(s, (40, 50, 40), title_col=(200, 200, 200)),
    }
    fn = D.get(iid)
    if fn:
        fn()
    else:
        first_letter(s, it)


def get(iid, size=S):
    """Иконка предмета нужного размера (с кэшем)."""
    key = (iid, size)
    if key not in ICONS:
        if (iid, S) not in ICONS:
            s = pygame.Surface((S, S), pygame.SRCALPHA)
            _draw(s, iid)
            ICONS[(iid, S)] = s
        ICONS[key] = ICONS[(iid, S)] if size == S else pygame.transform.smoothscale(ICONS[(iid, S)], (size, size))
    return ICONS[key]
