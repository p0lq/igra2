"""Вся графика игры рисуется кодом (pygame.draw) — без чужих картинок.

Здесь при запуске создаются спрайты: тайлы земли, стены, мебель, растения.
Персонажи рисуются каждый кадр функциями draw_human / draw_dog (так проще анимировать).
Позже любой спрайт можно заменить на свой нарисованный PNG — достаточно подменить
словарь SPRITES в одном месте.
"""
import math
import random
import pygame

from .config import TILE_W, TILE_H, HALF_W, HALF_H, WALL_H
from . import tiles

GROUND_TILES = {}   # тип земли -> список вариантов Surface (64x32)
SPRITES = {}        # id объекта -> (Surface, anchor_x, anchor_y)
WALL_SPRITES = {}   # id стены -> Surface; ключ + "_a" -> полупрозрачная версия
LIGHT_CACHE = {}


def shade(col, k):
    """Осветлить (k>1) или затемнить (k<1) цвет."""
    return tuple(max(0, min(255, int(c * k))) for c in col[:3])


def _inside_diamond(x, y):
    return abs(x - HALF_W + 0.5) / HALF_W + abs(y - HALF_H + 0.5) / HALF_H <= 1.0


# ---------------------------------------------------------------- земля

def _make_ground(kind, rnd):
    info = tiles.GROUND[kind]
    s = pygame.Surface((TILE_W, TILE_H), pygame.SRCALPHA)
    diamond = [(HALF_W, 0), (TILE_W, HALF_H), (HALF_W, TILE_H), (0, HALF_H)]
    pygame.draw.polygon(s, info["color"], diamond)
    spots = info["spots"]
    # крапинки — «шум», чтобы земля не выглядела плоской заливкой
    for _ in range(70):
        x, y = rnd.randrange(TILE_W), rnd.randrange(TILE_H)
        if _inside_diamond(x, y):
            s.set_at((x, y), rnd.choice(spots))
    if kind == tiles.STEPPE:
        for _ in range(6):  # пучки сухой травы
            x, y = rnd.randrange(8, 56), rnd.randrange(6, 26)
            if _inside_diamond(x, y):
                c = rnd.choice([(118, 120, 70), (170, 150, 90)])
                pygame.draw.line(s, c, (x, y), (x - 1, y - 3))
                pygame.draw.line(s, c, (x, y), (x + 2, y - 3))
    elif kind == tiles.ASPHALT:
        for _ in range(2):  # трещины
            x, y = rnd.randrange(14, 50), rnd.randrange(8, 24)
            pygame.draw.line(s, (60, 58, 56), (x, y), (x + rnd.randint(-8, 8), y + rnd.randint(-4, 4)))
    elif kind == tiles.WOOD:
        for i in range(-4, 5):  # доски по диагонали
            x = HALF_W + i * 8
            pygame.draw.line(s, (100, 70, 46), (x - 16, HALF_H - 8), (x + 16, HALF_H + 8))
        _clip_diamond(s)
    elif kind == tiles.BUNKER or kind == tiles.LINO:
        pygame.draw.line(s, shade(info["color"], 0.8), (HALF_W, 0), (HALF_W, TILE_H))
        pygame.draw.line(s, shade(info["color"], 0.8), (0, HALF_H), (TILE_W, HALF_H))
        _clip_diamond(s)
    elif kind == tiles.RAIL:
        # Рельсы идут вдоль оси Y карты. Точка клетки (u, v) на спрайте:
        # px = (u - v) * HALF_W + HALF_W, py = (u + v) * HALF_H
        for i in range(4):  # шпалы
            v = (i + 0.5) / 4
            px, py = (0.5 - v) * HALF_W + HALF_W, (0.5 + v) * HALF_H
            pygame.draw.line(s, (90, 64, 40), (px - 14, py - 7), (px + 14, py + 7), 3)
        for u in (0.28, 0.72):  # два рельса
            ax, ay = u * HALF_W + HALF_W, u * HALF_H
            bx, by = (u - 1) * HALF_W + HALF_W, (u + 1) * HALF_H
            pygame.draw.line(s, (150, 150, 150), (ax, ay), (bx, by), 2)
        _clip_diamond(s)
    elif kind == tiles.FIELD:
        for i in range(5):  # борозды
            t = (i + 0.5) / 5
            ax, ay = (t - 0) * HALF_W + HALF_W, (t + 0) * HALF_H
            bx, by = (t - 1) * HALF_W + HALF_W, (t + 1) * HALF_H
            pygame.draw.line(s, (108, 90, 60), (ax, ay), (bx, by), 2)
        _clip_diamond(s)
    elif kind == tiles.WATER:
        for _ in range(3):  # блики на мутной воде
            x, y = rnd.randrange(16, 48), rnd.randrange(8, 24)
            pygame.draw.line(s, (130, 140, 110), (x, y), (x + 6, y))
    elif kind == tiles.RIVERBED or kind == tiles.SALT:
        for _ in range(4):  # трещины в высохшей земле
            x, y = rnd.randrange(12, 52), rnd.randrange(6, 26)
            c = (130, 104, 74) if kind == tiles.RIVERBED else (176, 170, 150)
            pygame.draw.lines(s, c, False, [(x, y), (x + 4, y + 2), (x + 7, y), (x + 10, y + 3)])
        _clip_diamond(s)
    return s


def _clip_diamond(s):
    """Стереть всё, что вылезло за пределы ромба."""
    mask = pygame.Surface(s.get_size(), pygame.SRCALPHA)
    pygame.draw.polygon(mask, (255, 255, 255, 255), [(HALF_W, 0), (TILE_W, HALF_H), (HALF_W, TILE_H), (0, HALF_H)])
    s.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)


# ---------------------------------------------------------------- стены

def _face_point(face, u, v, h):
    """Точка на боковой грани блока. face 'L' — левая (юго-западная), 'R' — правая.
    u — вдоль грани (0..1), v — сверху вниз (0..1)."""
    if face == "L":
        return (0 + HALF_W * u, HALF_H + HALF_H * u + h * v)
    return (HALF_W + HALF_W * u, TILE_H - HALF_H * u + h * v)


def _face_quad(face, u0, u1, v0, v1, h):
    return [_face_point(face, u0, v0, h), _face_point(face, u1, v0, h),
            _face_point(face, u1, v1, h), _face_point(face, u0, v1, h)]


def _make_block(top, left, right, h=WALL_H):
    s = pygame.Surface((TILE_W, TILE_H + h), pygame.SRCALPHA)
    pygame.draw.polygon(s, left, _face_quad("L", 0, 1, 0, 1, h))
    pygame.draw.polygon(s, right, _face_quad("R", 0, 1, 0, 1, h))
    pygame.draw.polygon(s, top, [(HALF_W, 0), (TILE_W, HALF_H), (HALF_W, TILE_H), (0, HALF_H)])
    return s


def _wall(kind):
    h = WALL_H
    if kind == "wall_brick":
        s = _make_block((150, 96, 70), (140, 84, 60), (112, 66, 48))
        for face in "LR":
            for i in range(1, 8):
                v = i / 8
                pygame.draw.line(s, (100, 60, 44), _face_point(face, 0, v, h), _face_point(face, 1, v, h))
    elif kind == "wall_concrete":
        s = _make_block((150, 148, 140), (138, 136, 128), (110, 108, 102))
        for face in "LR":
            pygame.draw.line(s, (96, 94, 90), _face_point(face, 0.5, 0, h), _face_point(face, 0.5, 1, h))
    elif kind == "wall_bunker":
        s = _make_block((92, 98, 92), (84, 90, 84), (64, 70, 64))
        for face in "LR":
            pygame.draw.polygon(s, (150, 130, 40), _face_quad(face, 0, 1, 0.82, 0.92, h))
    elif kind == "wall_rust":
        s = _make_block((150, 84, 50), (132, 70, 40), (100, 52, 32))
        rnd = random.Random(7)
        for face in "LR":
            for _ in range(10):
                u, v = rnd.random(), rnd.random()
                pygame.draw.circle(s, (90, 46, 28), _face_point(face, u, v, h), rnd.randint(1, 3))
    else:
        # побелённая саманная стена с синей полосой снизу — как в степных посёлках
        s = _make_block((214, 208, 192), (200, 194, 178), (170, 164, 150))
        for face in "LR":
            pygame.draw.polygon(s, (70, 110, 150), _face_quad(face, 0, 1, 0.78, 1, h))
    return s


def _window(state):
    s = _wall("wall")
    h = WALL_H
    for face in "LR":
        pygame.draw.polygon(s, (90, 70, 50), _face_quad(face, 0.18, 0.82, 0.18, 0.66, h))
        if state == "window":
            pygame.draw.polygon(s, (90, 130, 150), _face_quad(face, 0.24, 0.76, 0.24, 0.6, h))
            pygame.draw.line(s, (180, 210, 220), _face_point(face, 0.3, 0.3, h), _face_point(face, 0.45, 0.3, h))
        elif state == "window_broken":
            pygame.draw.polygon(s, (30, 30, 34), _face_quad(face, 0.24, 0.76, 0.24, 0.6, h))
            pygame.draw.polygon(s, (90, 130, 150), [_face_point(face, 0.24, 0.24, h), _face_point(face, 0.5, 0.24, h), _face_point(face, 0.3, 0.45, h)])
        else:  # заколочено
            pygame.draw.polygon(s, (30, 30, 34), _face_quad(face, 0.24, 0.76, 0.24, 0.6, h))
            for v in (0.3, 0.42, 0.54):
                pygame.draw.polygon(s, (150, 110, 70), _face_quad(face, 0.14, 0.86, v - 0.04, v + 0.04, h))
    return s


def _door(metal=False):
    if metal:
        s = _wall("wall_bunker")
        col, edge = (110, 116, 110), (60, 64, 60)
    else:
        s = _wall("wall")
        col, edge = (120, 80, 50), (80, 52, 32)
    h = WALL_H
    for face in "LR":
        pygame.draw.polygon(s, edge, _face_quad(face, 0.22, 0.78, 0.12, 1, h))
        pygame.draw.polygon(s, col, _face_quad(face, 0.26, 0.74, 0.16, 1, h))
        pygame.draw.circle(s, (200, 180, 90), _face_point(face, 0.66, 0.58, h), 2)
    return s


def _fence(metal=False):
    h = 22
    s = pygame.Surface((TILE_W, TILE_H + h), pygame.SRCALPHA)
    if metal:
        for face in "LR":
            pygame.draw.polygon(s, (140, 140, 140, 90), _face_quad(face, 0, 1, 0, 1, h))
            for i in range(6):
                u = i / 5
                pygame.draw.line(s, (120, 120, 120), _face_point(face, u, 0, h), _face_point(face, min(1, u + 0.2), 1, h))
            pygame.draw.line(s, (90, 90, 90), _face_point(face, 0, 0, h), _face_point(face, 1, 0, h), 2)
    else:
        for face in "LR":
            for i in range(5):
                u0 = i / 5 + 0.03
                pygame.draw.polygon(s, (134, 100, 64) if face == "L" else (110, 80, 52), _face_quad(face, u0, u0 + 0.14, 0, 1, h))
            pygame.draw.polygon(s, (90, 64, 40), _face_quad(face, 0, 1, 0.3, 0.42, h))
    return s, h


# ---------------------------------------------------------------- мебель и предметы

def iso_box(s, cx, cy, hw, hh, h, col, top=None):
    """Нарисовать изометрическую коробку. (cx, cy) — центр основания на земле,
    hw/hh — полуширина/полувысота ромба основания, h — высота коробки."""
    top = top or shade(col, 1.15)
    left, right = col, shade(col, 0.78)
    pygame.draw.polygon(s, left, [(cx - hw, cy - h), (cx, cy + hh - h), (cx, cy + hh), (cx - hw, cy)])
    pygame.draw.polygon(s, right, [(cx, cy + hh - h), (cx + hw, cy - h), (cx + hw, cy), (cx, cy + hh)])
    pygame.draw.polygon(s, top, [(cx, cy - hh - h), (cx + hw, cy - h), (cx, cy + hh - h), (cx - hw, cy - h)])


def _canvas(w=96, h=110):
    """Пустой холст под объект. Якорь (центр клетки на земле) — внизу по центру."""
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    return s, w // 2, h - 24


def _sprite(name, s, ax, ay):
    SPRITES[name] = (s, ax, ay)


def _make_objects():
    rnd = random.Random(42)

    s, ax, ay = _canvas()
    iso_box(s, ax, ay, 20, 10, 44, (120, 84, 54))
    pygame.draw.line(s, (80, 54, 34), (ax - 10, ay - 40), (ax - 10, ay - 4))
    _sprite("cupboard", s, ax, ay)

    s, ax, ay = _canvas()
    iso_box(s, ax, ay, 16, 8, 46, (226, 226, 218))
    pygame.draw.line(s, (120, 120, 120), (ax - 12, ay - 30), (ax - 12, ay - 20), 2)
    pygame.draw.line(s, (160, 160, 160), (ax - 16, ay - 26), (ax, ay - 18))
    _sprite("fridge", s, ax, ay)

    s, ax, ay = _canvas()
    iso_box(s, ax, ay, 18, 9, 24, (230, 228, 220))
    for dx, dy in ((-6, -26), (6, -26), (0, -29), (0, -23)):
        pygame.draw.ellipse(s, (40, 40, 40), (ax + dx - 4, ay + dy - 2, 8, 4))
    _sprite("kitchen_stove", s, ax, ay)

    s, ax, ay = _canvas()
    iso_box(s, ax, ay, 22, 11, 18, (140, 100, 62))
    _sprite("table", s, ax, ay)

    s, ax, ay = _canvas()
    iso_box(s, ax, ay, 16, 8, 20, (156, 120, 70))
    pygame.draw.line(s, (110, 80, 46), (ax - 16, ay - 12), (ax, ay - 4))
    pygame.draw.line(s, (110, 80, 46), (ax, ay - 4), (ax + 16, ay - 12))
    _sprite("crate", s, ax, ay)

    s, ax, ay = _canvas()
    iso_box(s, ax, ay, 14, 7, 26, (96, 104, 100))
    pygame.draw.circle(s, (200, 190, 120), (ax - 7, ay - 12), 3)
    _sprite("safe", s, ax, ay)

    s, ax, ay = _canvas()
    iso_box(s, ax, ay, 20, 10, 46, (110, 76, 48))
    for i in range(4):
        for j in range(5):
            c = rnd.choice([(150, 50, 40), (60, 90, 130), (190, 170, 90), (70, 110, 70)])
            x = ax - 18 + j * 3.4
            y = ay - 40 + i * 10 + j * 1.7
            pygame.draw.line(s, c, (x, y), (x, y + 7), 2)
    _sprite("bookshelf", s, ax, ay)

    s, ax, ay = _canvas()
    iso_box(s, ax, ay, 18, 9, 42, (220, 222, 216))
    pygame.draw.line(s, (200, 40, 40), (ax - 9, ay - 30), (ax - 9, ay - 18), 3)
    pygame.draw.line(s, (200, 40, 40), (ax - 14, ay - 26), (ax - 4, ay - 22), 3)
    _sprite("med_cabinet", s, ax, ay)

    s, ax, ay = _canvas()
    iso_box(s, ax, ay, 22, 11, 20, (180, 186, 180))
    pygame.draw.rect(s, (110, 160, 150), (ax - 6, ay - 34, 4, 8))
    pygame.draw.rect(s, (160, 140, 60), (ax + 4, ay - 32, 4, 7))
    _sprite("lab_table", s, ax, ay)

    s, ax, ay = _canvas()
    iso_box(s, ax, ay, 24, 12, 22, (140, 110, 80))
    for i in range(4):
        c = rnd.choice([(190, 60, 50), (200, 180, 80), (90, 120, 160)])
        pygame.draw.rect(s, c, (ax - 14 + i * 6, ay - 31 + i * 2, 4, 5))
    _sprite("shop_shelf", s, ax, ay)

    s, ax, ay = _canvas()
    iso_box(s, ax, ay, 14, 7, 44, (84, 104, 74))
    pygame.draw.line(s, (60, 76, 52), (ax - 7, ay - 40), (ax - 7, ay - 4))
    _sprite("locker", s, ax, ay)

    s, ax, ay = _canvas()
    iso_box(s, ax, ay, 26, 13, 10, (140, 100, 70))
    iso_box(s, ax - 8, ay - 4, 9, 5, 14, (220, 220, 210))
    pygame.draw.polygon(s, (110, 60, 60), [(ax + 2, ay - 14), (ax + 26, ay - 10), (ax + 10, ay - 2), (ax - 12, ay - 6)])
    _sprite("bed", s, ax, ay)

    for name, body, roof in (("car_zhiguli", (200, 192, 160), (176, 168, 140)), ("car_uaz", (92, 110, 70), (80, 96, 60))):
        s, ax, ay = _canvas(120, 100)
        iso_box(s, ax, ay, 30, 15, 14, body)
        iso_box(s, ax - 2, ay - 1, 18, 9, 26, roof)
        pygame.draw.polygon(s, (60, 80, 90), [(ax - 20, ay - 20), (ax - 2, ay - 12), (ax - 2, ay - 2), (ax - 20, ay - 10)])
        pygame.draw.polygon(s, (110, 70, 40), [(ax - 30, ay - 6), (ax - 26, ay - 4), (ax - 26, ay), (ax - 30, ay - 2)])
        for wx, wy in ((-22, 4), (4, 12), (20, 0)):
            pygame.draw.ellipse(s, (30, 30, 30), (ax + wx - 4, ay + wy - 6, 8, 8))
        _sprite(name, s, ax, ay)

    s, ax, ay = _canvas()
    for i, (dx, dy) in enumerate(((-6, -2), (6, 2))):
        x, y = ax + dx, ay + dy
        pygame.draw.rect(s, (200, 170, 40), (x - 7, y - 24, 14, 24))
        pygame.draw.ellipse(s, (220, 190, 60), (x - 7, y - 28, 14, 7))
        pygame.draw.rect(s, (40, 40, 40), (x - 7, y - 16, 14, 4))
        pygame.draw.polygon(s, (30, 30, 30), [(x, y - 11), (x - 3, y - 6), (x + 3, y - 6)])
    _sprite("barrel", s, ax, ay)

    s, ax, ay = _canvas()
    iso_box(s, ax, ay, 16, 8, 34, (120, 124, 120))
    pygame.draw.polygon(s, (220, 200, 40), [(ax - 8, ay - 24), (ax - 2, ay - 14), (ax - 14, ay - 14)])
    _sprite("pump_box", s, ax, ay)

    # юрта: белый войлок, красный орнамент, купол
    s, ax, ay = _canvas(110, 120)
    pygame.draw.ellipse(s, (60, 50, 40, 90), (ax - 38, ay - 10, 76, 26))
    pygame.draw.ellipse(s, (210, 200, 176), (ax - 34, ay - 70, 68, 72))  # купол
    pygame.draw.rect(s, (226, 218, 196), (ax - 34, ay - 34, 68, 36))
    pygame.draw.ellipse(s, (226, 218, 196), (ax - 34, ay - 6, 68, 16))
    pygame.draw.rect(s, (170, 50, 40), (ax - 34, ay - 24, 68, 5))
    pygame.draw.polygon(s, (130, 90, 50), [(ax - 8, ay + 6), (ax + 8, ay + 6), (ax + 8, ay - 18), (ax - 8, ay - 18)])
    pygame.draw.circle(s, (120, 90, 60), (ax, ay - 66), 6)
    _sprite("yurt", s, ax, ay)

    s, ax, ay = _canvas()
    pygame.draw.polygon(s, (90, 104, 64), [(ax - 28, ay), (ax, ay - 32), (ax + 6, ay + 10)])
    pygame.draw.polygon(s, (70, 82, 50), [(ax, ay - 32), (ax + 28, ay - 6), (ax + 6, ay + 10)])
    _sprite("tent", s, ax, ay)

    # саксаул — корявое дерево пустыни
    s, ax, ay = _canvas(96, 120)
    pygame.draw.lines(s, (96, 76, 56), False, [(ax, ay), (ax - 3, ay - 18), (ax + 4, ay - 30), (ax - 2, ay - 44)], 4)
    pygame.draw.line(s, (96, 76, 56), (ax + 1, ay - 24), (ax + 16, ay - 40), 3)
    pygame.draw.line(s, (96, 76, 56), (ax - 2, ay - 16), (ax - 18, ay - 32), 3)
    for dx, dy, r in ((-18, -40, 11), (16, -46, 12), (-2, -56, 14), (6, -36, 9)):
        pygame.draw.circle(s, (118, 128, 90), (ax + dx, ay + dy), r)
        pygame.draw.circle(s, (140, 148, 106), (ax + dx - 3, ay + dy - 3), r // 2)
    _sprite("saxaul", s, ax, ay)

    s, ax, ay = _canvas()
    for _ in range(14):
        a = rnd.uniform(math.pi * 1.1, math.pi * 1.9)
        l = rnd.uniform(6, 14)
        pygame.draw.line(s, (130, 104, 70), (ax, ay), (ax + math.cos(a) * l, ay + math.sin(a) * l * 0.8))
    _sprite("bush", s, ax, ay)

    s, ax, ay = _canvas()
    for _ in range(18):
        a = rnd.uniform(math.pi * 1.05, math.pi * 1.95)
        l = rnd.uniform(5, 11)
        pygame.draw.line(s, (100, 130, 70), (ax, ay), (ax + math.cos(a) * l, ay + math.sin(a) * l))
    for _ in range(5):
        pygame.draw.circle(s, (170, 110, 150), (ax + rnd.randint(-7, 7), ay - rnd.randint(3, 10)), 1)
    _sprite("thorn_bush", s, ax, ay)

    s, ax, ay = _canvas()
    pygame.draw.circle(s, (86, 110, 60), (ax, ay - 8), 8)
    for _ in range(5):
        pygame.draw.circle(s, (240, 240, 232), (ax + rnd.randint(-6, 6), ay - 8 + rnd.randint(-6, 4)), 2)
    _sprite("cotton", s, ax, ay)

    s, ax, ay = _canvas()
    pygame.draw.polygon(s, (128, 120, 108), [(ax - 16, ay + 2), (ax - 12, ay - 12), (ax + 2, ay - 18), (ax + 16, ay - 8), (ax + 14, ay + 4)])
    pygame.draw.polygon(s, (150, 142, 128), [(ax - 12, ay - 12), (ax + 2, ay - 18), (ax + 4, ay - 8)])
    _sprite("rock", s, ax, ay)

    s, ax, ay = _canvas(96, 150)
    pygame.draw.line(s, (100, 78, 56), (ax, ay), (ax, ay - 110), 5)
    pygame.draw.line(s, (100, 78, 56), (ax - 18, ay - 100), (ax + 18, ay - 100), 4)
    for dx in (-16, 0, 16):
        pygame.draw.rect(s, (200, 200, 200), (ax + dx - 2, ay - 106, 4, 5))
    _sprite("pole", s, ax, ay)

    s, ax, ay = _canvas()
    pygame.draw.line(s, (90, 90, 90), (ax, ay), (ax, ay - 30), 3)
    pygame.draw.rect(s, (230, 230, 220), (ax - 16, ay - 46, 32, 18))
    pygame.draw.rect(s, (200, 40, 30), (ax - 16, ay - 46, 32, 18), 3)
    pygame.draw.polygon(s, (30, 30, 30), [(ax, ay - 43), (ax - 6, ay - 32), (ax + 6, ay - 32)])
    _sprite("sign_danger", s, ax, ay)

    # кудук — степной колодец: каменное кольцо и ворот
    s, ax, ay = _canvas()
    pygame.draw.ellipse(s, (120, 112, 100), (ax - 18, ay - 14, 36, 20))
    pygame.draw.rect(s, (120, 112, 100), (ax - 18, ay - 20, 36, 12))
    pygame.draw.ellipse(s, (146, 138, 124), (ax - 18, ay - 28, 36, 18))
    pygame.draw.ellipse(s, (30, 36, 34), (ax - 12, ay - 25, 24, 12))
    pygame.draw.line(s, (100, 76, 50), (ax - 16, ay - 18), (ax - 16, ay - 48), 3)
    pygame.draw.line(s, (100, 76, 50), (ax + 16, ay - 18), (ax + 16, ay - 48), 3)
    pygame.draw.line(s, (120, 90, 60), (ax - 18, ay - 46), (ax + 18, ay - 46), 4)
    pygame.draw.line(s, (60, 60, 60), (ax + 2, ay - 46), (ax + 2, ay - 30))
    pygame.draw.rect(s, (110, 110, 110), (ax - 3, ay - 32, 9, 7))
    _sprite("well", s, ax, ay)

    s, ax, ay = _canvas()
    for a in range(0, 360, 45):
        x = ax + math.cos(math.radians(a)) * 12
        y = ay + math.sin(math.radians(a)) * 6
        pygame.draw.circle(s, (110, 106, 100), (x, y), 3)
    pygame.draw.line(s, (90, 60, 36), (ax - 9, ay + 2), (ax + 9, ay - 3), 3)
    pygame.draw.line(s, (90, 60, 36), (ax - 9, ay - 3), (ax + 9, ay + 2), 3)
    _sprite("campfire", s, ax, ay)
    _sprite("campfire_out", s, ax, ay)

    s, ax, ay = _canvas(96, 130)
    iso_box(s, ax, ay, 12, 6, 22, (50, 48, 46))
    pygame.draw.rect(s, (60, 58, 56), (ax + 2, ay - 70, 5, 46))
    pygame.draw.rect(s, (220, 120, 40), (ax - 9, ay - 14, 6, 5))
    _sprite("burzhuika", s, ax, ay)

    s, ax, ay = _canvas()
    iso_box(s, ax, ay, 24, 12, 18, (150, 112, 70))
    pygame.draw.line(s, (90, 90, 90), (ax - 4, ay - 26), (ax + 8, ay - 22), 3)
    pygame.draw.rect(s, (120, 80, 50), (ax - 12, ay - 30, 6, 3))
    _sprite("workbench", s, ax, ay)

    s, ax, ay = _canvas()
    for dx, dy in ((-14, 0), (14, 0), (0, -7), (0, 7)):
        pygame.draw.line(s, (110, 80, 50), (ax + dx, ay + dy), (ax + dx, ay + dy - 22), 2)
    pygame.draw.polygon(s, (60, 100, 140), [(ax, ay - 34), (ax + 16, ay - 24), (ax, ay - 16), (ax - 16, ay - 24)])
    pygame.draw.rect(s, (90, 90, 96), (ax - 6, ay - 14, 12, 14))
    _sprite("rain_collector", s, ax, ay)

    s, ax, ay = _canvas()
    pygame.draw.line(s, (180, 170, 140), (ax - 18, ay - 6), (ax + 18, ay + 4))
    for t in (0.2, 0.5, 0.8):
        x = ax - 18 + 36 * t
        y = ay - 6 + 10 * t
        pygame.draw.rect(s, (170, 170, 176), (x - 2, y, 5, 6))
    _sprite("can_alarm", s, ax, ay)

    s, ax, ay = _canvas()
    pygame.draw.ellipse(s, (70, 76, 70), (ax - 18, ay - 9, 36, 18))
    pygame.draw.ellipse(s, (100, 106, 100), (ax - 15, ay - 8, 30, 15))
    pygame.draw.ellipse(s, (60, 64, 60), (ax - 7, ay - 4, 14, 7), 2)
    pygame.draw.line(s, (60, 64, 60), (ax - 7, ay), (ax + 7, ay), 2)
    _sprite("hatch", s, ax, ay)

    s, ax, ay = _canvas(96, 130)
    pygame.draw.line(s, (130, 130, 120), (ax - 8, ay), (ax - 8, ay - 90), 3)
    pygame.draw.line(s, (130, 130, 120), (ax + 8, ay), (ax + 8, ay - 90), 3)
    for i in range(9):
        pygame.draw.line(s, (130, 130, 120), (ax - 8, ay - 8 - i * 10), (ax + 8, ay - 8 - i * 10), 2)
    pygame.draw.ellipse(s, (230, 220, 160, 70), (ax - 20, ay - 10, 40, 20))
    _sprite("ladder", s, ax, ay)

    s, ax, ay = _canvas()
    pygame.draw.ellipse(s, (90, 76, 56), (ax - 10, ay - 10, 20, 14))
    pygame.draw.ellipse(s, (120, 100, 70), (ax - 7, ay - 14, 12, 9))
    _sprite("pile", s, ax, ay)

    s, ax, ay = _canvas()
    pygame.draw.ellipse(s, (70, 20, 20, 120), (ax - 18, ay - 6, 36, 14))
    pygame.draw.ellipse(s, (80, 80, 76), (ax - 16, ay - 8, 26, 10))
    pygame.draw.circle(s, (120, 110, 100), (ax + 12, ay - 4), 5)
    _sprite("corpse", s, ax, ay)


def build():
    """Создать все спрайты. Вызывается один раз после pygame.init()."""
    rnd = random.Random(1999)
    for kind in tiles.GROUND:
        GROUND_TILES[kind] = [_make_ground(kind, rnd) for _ in range(4)]

    for k in ("wall", "wall_brick", "wall_concrete", "wall_bunker", "wall_rust"):
        WALL_SPRITES[k] = _wall(k)
    for k in ("window", "window_boarded", "window_broken"):
        WALL_SPRITES[k] = _window(k)
    WALL_SPRITES["door"] = _door()
    WALL_SPRITES["door_metal"] = _door(metal=True)
    for k in list(WALL_SPRITES):
        a = WALL_SPRITES[k].copy()
        a.set_alpha(70)  # «прозрачная стена», когда игрок за ней
        WALL_SPRITES[k + "_a"] = a

    f, h = _fence()
    SPRITES["fence"] = (f, HALF_W, HALF_H + h)
    f, h = _fence(metal=True)
    SPRITES["fence_metal"] = (f, HALF_W, HALF_H + h)

    # открытая дверь: только порог и распахнутая створка
    for name, col in (("door_open", (120, 80, 50)), ("door_metal_open", (110, 116, 110))):
        s = pygame.Surface((TILE_W, TILE_H + WALL_H), pygame.SRCALPHA)
        pygame.draw.polygon(s, shade(col, 0.6), [(HALF_W, WALL_H), (TILE_W, WALL_H + HALF_H), (HALF_W, WALL_H + TILE_H), (0, WALL_H + HALF_H)], 2)
        pygame.draw.polygon(s, col, [(6, WALL_H + 12), (20, WALL_H + 5), (20, 8), (6, 15)])
        SPRITES[name] = (s, HALF_W, WALL_H + HALF_H)

    _make_objects()


# ---------------------------------------------------------------- персонажи

def draw_shadow(surf, x, y, r=12):
    sh = pygame.Surface((r * 2, r), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (0, 0, 0, 80), (0, 0, r * 2, r))
    surf.blit(sh, (x - r, y - r // 2))


def draw_human(surf, x, y, look, face_right=True, phase=0.0, hunch=0.0, scale=1.0,
               weapon=None, attack=0.0, crouch=False, alpha=255):
    """Нарисовать человека ногами в точке (x, y).

    look   — словарь цветов: body, legs, skin, hat;
    phase  — фаза шага (для анимации ног);
    hunch  — сутулость (у заражённых);
    attack — 0..1, замах оружием.
    """
    k = scale
    tgt = surf
    if alpha < 255:
        tgt = pygame.Surface((80, 90), pygame.SRCALPHA)
        ox, oy = x - 40, y - 80
        x, y = 40, 80
    d = 1 if face_right else -1
    draw_shadow(tgt, x, y, int(11 * k))
    h_leg = (12 if not crouch else 8) * k
    step = math.sin(phase) * 4 * k
    legs = look.get("legs", (60, 60, 60))
    pygame.draw.line(tgt, legs, (x - 3 * k, y - h_leg), (x - 3 * k + step, y), max(2, int(4 * k)))
    pygame.draw.line(tgt, legs, (x + 3 * k, y - h_leg), (x + 3 * k - step, y), max(2, int(4 * k)))
    body = look.get("body", (100, 100, 100))
    top = y - h_leg - 16 * k
    bx = x + hunch * 4 * d * k
    pygame.draw.polygon(tgt, body, [(x - 6 * k, y - h_leg), (x + 6 * k, y - h_leg), (bx + 6 * k, top), (bx - 6 * k, top)])
    pygame.draw.line(tgt, shade(body, 0.7), (x, y - h_leg), (bx, top), 1)
    skin = look.get("skin", (200, 160, 120))
    hx = bx + hunch * 5 * d * k
    hy = top - 6 * k + hunch * 3 * k
    # рука с оружием: поворачивается при замахе
    ang = -0.6 + attack * 2.0 if face_right else math.pi + 0.6 - attack * 2.0
    sx, sy = bx + 4 * d * k, top + 4 * k
    ex, ey = sx + math.cos(ang) * 11 * k, sy + math.sin(ang) * 11 * k
    pygame.draw.line(tgt, body, (sx, sy), (ex, ey), max(2, int(3 * k)))
    if weapon:
        wl = 14 * k if weapon != "gun" else 8 * k
        wx, wy = ex + math.cos(ang) * wl, ey + math.sin(ang) * wl
        pygame.draw.line(tgt, (70, 70, 70) if weapon == "gun" else (150, 130, 100), (ex, ey), (wx, wy), 3 if weapon != "gun" else 4)
    pygame.draw.circle(tgt, skin, (hx, hy), int(6 * k))
    pygame.draw.circle(tgt, (30, 30, 30), (hx + 3 * d * k, hy - 1 * k), max(1, int(1 * k)))
    hat = look.get("hat")
    if hat == "kalpak":       # белый казахский калпак
        pygame.draw.polygon(tgt, (236, 232, 220), [(hx - 7 * k, hy - 3 * k), (hx + 7 * k, hy - 3 * k), (hx + 2 * k, hy - 14 * k), (hx - 2 * k, hy - 14 * k)])
        pygame.draw.line(tgt, (30, 30, 30), (hx - 7 * k, hy - 3 * k), (hx + 7 * k, hy - 3 * k), 2)
    elif hat == "doppi":      # узбекская тюбетейка
        pygame.draw.rect(tgt, (20, 20, 20), (hx - 6 * k, hy - 8 * k, 12 * k, 5 * k))
        pygame.draw.line(tgt, (240, 240, 240), (hx - 3 * k, hy - 6 * k), (hx + 3 * k, hy - 6 * k))
    elif hat == "scarf":      # платок
        pygame.draw.circle(tgt, (200, 170, 60), (hx, hy - 2 * k), int(7 * k), draw_top_left=True, draw_top_right=True)
        pygame.draw.polygon(tgt, (200, 170, 60), [(hx - 7 * k, hy - 2 * k), (hx - 9 * k, hy + 6 * k), (hx - 4 * k, hy + 2 * k)])
    elif hat == "cap":
        pygame.draw.rect(tgt, (50, 60, 80), (hx - 6 * k, hy - 8 * k, 12 * k, 4 * k))
        pygame.draw.line(tgt, (50, 60, 80), (hx, hy - 5 * k), (hx + 9 * d * k, hy - 4 * k), 2)
    elif hat == "bandana":    # «Волки степи»
        pygame.draw.rect(tgt, (170, 30, 30), (hx - 6 * k, hy - 7 * k, 12 * k, 4 * k))
    elif hat == "mask":
        pygame.draw.rect(tgt, (220, 220, 210), (hx - 1 * k + 2 * d * k, hy + 1 * k, 6 * k, 4 * k))
    if alpha < 255:
        tgt.set_alpha(alpha)
        surf.blit(tgt, (ox, oy))


def draw_dog(surf, x, y, face_right=True, phase=0.0, col=(120, 100, 76)):
    """Одичавшая степная собака."""
    d = 1 if face_right else -1
    draw_shadow(surf, x, y, 14)
    st = math.sin(phase) * 3
    for lx in (-7, 7):
        pygame.draw.line(surf, shade(col, 0.7), (x + lx, y - 8), (x + lx + st, y), 3)
    pygame.draw.ellipse(surf, col, (x - 12, y - 16, 24, 10))
    hx = x + 12 * d
    pygame.draw.circle(surf, col, (hx, y - 16), 5)
    pygame.draw.polygon(surf, shade(col, 0.8), [(hx, y - 20), (hx + 2 * d, y - 26), (hx + 4 * d, y - 19)])
    pygame.draw.line(surf, (200, 40, 30), (hx + 2 * d, y - 15), (hx + 6 * d, y - 14))
    pygame.draw.line(surf, col, (x - 12 * d, y - 12), (x - 18 * d, y - 18), 2)


def draw_flame(surf, x, y, t, size=1.0):
    """Анимированное пламя костра."""
    for i, col in enumerate(((220, 90, 30), (240, 160, 40), (255, 230, 120))):
        r = (9 - i * 3) * size
        fl = math.sin(t * 9 + i) * 2
        pts = [(x - r, y), (x + r, y), (x + fl, y - (20 - i * 5) * size)]
        pygame.draw.polygon(surf, col, pts)


def light_mask(radius):
    """Круг света с мягким краем: альфа 255 в центре и 0 по краю.
    Вычитается из слоя темноты (BLEND_RGBA_SUB)."""
    radius = int(radius)
    if radius in LIGHT_CACHE:
        return LIGHT_CACHE[radius]
    s = pygame.Surface((radius * 2, radius), pygame.SRCALPHA)
    steps = 24
    for i in range(steps, 0, -1):
        t = i / steps
        a = int(255 * (1 - t) ** 0.7)
        rect = pygame.Rect(0, 0, radius * 2 * t, radius * t)
        rect.center = (radius, radius // 2)
        pygame.draw.ellipse(s, (0, 0, 0, a), rect)
    LIGHT_CACHE[radius] = s
    return s
