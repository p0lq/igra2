"""Карта мира: класс Zone и генерация двух зон — района «Сарыкудук» и бункера «Подземка».

Карта состоит из двух слоёв:
  ground[y][x] — тип земли (см. tiles.py),
  obj[y][x]    — объект на клетке (стена, дверь, шкаф, дерево...) или None.
Здания описаны текстовыми шаблонами (ASCII): так их легко читать и править.
Генерация детерминированная (фиксированное зерно random), поэтому мир всегда одинаковый.
"""
import math
import random

from . import tiles
from .data import obj as objinfo

# --------------------------------------------------------------- класс зоны


class Zone:
    def __init__(self, zid, name, w, h, fill=tiles.STEPPE, dark=False):
        self.id = zid
        self.name = name
        self.w, self.h = w, h
        self.ground = [[fill] * w for _ in range(h)]
        self.obj = [[None] * w for _ in range(h)]
        self.dark = dark              # подземелье: всегда темно
        self.containers = {}          # "x,y" -> {"kind": ..., "items": [...] или None (ещё не обыскан)}
        self.fires = {}               # "x,y" -> сколько минут ещё горит
        self.collectors = {}          # "x,y" -> литров воды в сборщике
        self.obj_hp = {}              # "x,y" -> оставшаяся прочность двери/окна
        self.markers = {}             # особые точки: места NPC, вход, выход
        self.spawns = []              # [вид врага, x, y] — стартовые враги
        self.safe_rect = None         # прямоугольник «безопасной зоны» (колхоз)

    # ---- доступ к клеткам
    def inside(self, x, y):
        return 0 <= x < self.w and 0 <= y < self.h

    def get(self, x, y):
        if not self.inside(x, y):
            return "wall"
        return self.obj[y][x]

    def set(self, x, y, oid):
        self.obj[y][x] = oid
        info = objinfo(oid)
        key = f"{x},{y}"
        if "container" in info and key not in self.containers:
            self.containers[key] = {"kind": info["container"], "items": None}
        if info.get("collector") and key not in self.collectors:
            self.collectors[key] = 0

    def remove(self, x, y):
        self.obj[y][x] = None
        self.containers.pop(f"{x},{y}", None)
        self.fires.pop(f"{x},{y}", None)

    def solid(self, x, y):
        """Можно ли пройти через клетку."""
        if not self.inside(x, y):
            return True
        if tiles.is_solid(self.ground[y][x]):
            return True
        return objinfo(self.obj[y][x]).get("solid", False)

    def blocks_sight(self, x, y):
        if not self.inside(x, y):
            return True
        return objinfo(self.obj[y][x]).get("sight", False)

    def indoor(self, x, y):
        if self.dark:
            return True
        if not self.inside(x, y):
            return False
        return tiles.is_indoor(self.ground[y][x])

    def in_safe(self, x, y):
        r = self.safe_rect
        return r is not None and r[0] <= x <= r[2] and r[1] <= y <= r[3]

    # ---- сохранение
    def to_dict(self):
        return {"id": self.id, "ground": self.ground, "obj": self.obj, "containers": self.containers,
                "fires": self.fires, "collectors": self.collectors, "obj_hp": self.obj_hp}

    def load_dict(self, d):
        self.ground = d["ground"]
        self.obj = d["obj"]
        self.containers = d["containers"]
        self.fires = d["fires"]
        self.collectors = d["collectors"]
        self.obj_hp = d.get("obj_hp", {})


# --------------------------------------------------------------- шаблоны зданий
# '#' стена  'w' окно  'd' дверь  '.' пол  ' ' не трогать
# 'b' кровать  'c' шкаф  'f' холодильник  'k' плита  't' стол  's' книжная полка
# 'x' ящик  'S' сейф  'm' медшкаф  'l' лабораторный стол  'h' прилавок  'L' армейский шкафчик
# 'W' верстак  'p' шкаф насосной  'r' бочка  'D' гермодверь  'A' лестница наверх
# '1'..'8' — пол с меткой (места жителей колхоза по расписанию)

LEGEND = {"b": "bed", "c": "cupboard", "f": "fridge", "k": "kitchen_stove", "t": "table",
          "s": "bookshelf", "x": "crate", "S": "safe", "m": "med_cabinet", "l": "lab_table",
          "h": "shop_shelf", "L": "locker", "W": "workbench", "p": "pump_box", "r": "barrel",
          "D": "door_metal", "A": "ladder", "w": "window", "d": "door"}

HOUSE_SMALL = [
    "##w##w##",
    "#b...kf#",
    "w......#",
    "#c..t..w",
    "#......#",
    "###d####",
]

HOUSE_BIG = [
    "###w###w###",
    "#b..#...kf#",
    "#...d.....w",
    "w.c.#..t..#",
    "#####.....#",
    "    #s....#",
    "    ###d###",
]

SHOP = [
    "#####w#####",
    "#hhh...hhh#",
    "#.........w",
    "w.........#",
    "#..t......#",
    "#x.......x#",
    "####d######",
]

CLUB = [
    "###w####w####",
    "#....s.....k#",
    "w...........#",
    "#..t..t..t..w",
    "#...........#",
    "#x.........f#",
    "######d######",
]

PANEL = [
    "##w####w####w##",
    "#b.c#b..c#b..k#",
    "#...d....d....#",
    "#...#....#..t.#",
    "##d######d#####",
]

STATION = [
    "##w###w###w##",
    "#t.........L#",
    "d...........d",
    "#h..t....b..#",
    "##w###w###w##",
]

PUMP = [
    "#####",
    "#prp#",
    "d...#",
    "#x..#",
    "#####",
]

OFFICE = [
    "###w###w###",
    "#....s..S.#",
    "w..1......w",
    "#b.2.t....#",
    "####d######",
]

WORKSHOP = [
    "#####w#####",
    "#W..x..x..#",
    "w...5.....#",
    "#x...t..b6#",
    "####d######",
]

GALYA_HOUSE = [
    "###w#####",
    "#hh....b#",
    "w..3...4#",
    "#x......#",
    "###d#####",
]

BUNKER = [
    "####################################",
    "#A.....#...........#......L..L....#",
    "#......#...........#..............#",
    "#......D...........D......b..b....#",
    "#......#...........#..............#",
    "####D###...t...t...#####D##########",
    "#......#...........#......#.......#",
    "#.L..L.#...........#..m...#..l..l.#",
    "#......#####D#######..m...D.......#",
    "#......#.........#........#..S....#",
    "###D####.........#..###D###.......#",
    "#........x...x...#........#..l....#",
    "#................D........#########",
    "#..r.r...........#........#.......#",
    "#................#........D...b...#",
    "##################........#.......#",
    "                 ####################",
]


def stamp(zone, x0, y0, layout, wall="wall", floor=tiles.WOOD, flip=False):
    """Перенести шаблон здания на карту. Возвращает метки {символ: [(x, y), ...]}."""
    rows = list(reversed(layout)) if flip else layout
    marks = {}
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch == " ":
                continue
            x, y = x0 + i, y0 + j
            if not zone.inside(x, y):
                continue
            zone.ground[y][x] = floor
            zone.obj[y][x] = None
            if ch == "#":
                zone.set(x, y, wall)
            elif ch in LEGEND:
                zone.set(x, y, LEGEND[ch])
            if ch != "." and ch != "#":
                marks.setdefault(ch, []).append((x, y))
    return marks


# --------------------------------------------------------------- вспомогательное


def value_noise(rnd, w, h, cell):
    """Плавный шум: случайные значения в узлах сетки + билинейная интерполяция.
    Нужен для пятен песка и солончаков."""
    gw, gh = w // cell + 2, h // cell + 2
    grid = [[rnd.random() for _ in range(gw)] for _ in range(gh)]

    def at(x, y):
        gx, gy = x / cell, y / cell
        ix, iy = int(gx), int(gy)
        fx, fy = gx - ix, gy - iy
        a = grid[iy][ix] * (1 - fx) + grid[iy][ix + 1] * fx
        b = grid[iy + 1][ix] * (1 - fx) + grid[iy + 1][ix + 1] * fx
        return a * (1 - fy) + b * fy
    return at


def fill_rect(zone, x0, y0, x1, y1, ground):
    for y in range(max(0, y0), min(zone.h, y1 + 1)):
        for x in range(max(0, x0), min(zone.w, x1 + 1)):
            zone.ground[y][x] = ground


def fence_rect(zone, x0, y0, x1, y1, kind="fence", gaps=()):
    for x in range(x0, x1 + 1):
        for y in (y0, y1):
            if (x, y) not in gaps:
                zone.set(x, y, kind)
    for y in range(y0, y1 + 1):
        for x in (x0, x1):
            if (x, y) not in gaps:
                zone.set(x, y, kind)


# --------------------------------------------------------------- район «Сарыкудук»

W, H = 120, 120
KX, KY = 60, 6          # левый верхний угол колхоза «Заря»
START_POS = (19.5, 28.5)  # игрок приходит в себя в доме на окраине посёлка
HATCH_POS = (52, 104)


def make_sarykuduk():
    rnd = random.Random(1999)
    z = Zone("sarykuduk", "Сарыкудук", W, H)
    reserved = []  # прямоугольники, где не ставим деревья и камни

    # 1. Рельеф: песок, солончаки, высохшее русло
    sand = value_noise(rnd, W, H, 9)
    salt = value_noise(rnd, W, H, 14)
    for y in range(H):
        for x in range(W):
            if x < 50 and y > 80 and salt(x, y) > 0.45:
                z.ground[y][x] = tiles.SALT
            elif sand(x, y) > 0.64:
                z.ground[y][x] = tiles.SAND
    for x in range(W):
        cy = int(88 + 6 * math.sin(x / 9.0))
        for dy in range(-1, 2):
            if 0 <= cy + dy < H:
                z.ground[cy + dy][x] = tiles.RIVERBED

    # 2. Арык с мостиками-переходами
    bridges = {14, 30, 52, 53, 66, 84, 98}
    for y in range(4, 110):
        z.ground[y][57] = tiles.DIRT if y in bridges else tiles.WATER

    # 3. Трасса и железная дорога
    fill_rect(z, 0, 52, W - 1, 53, tiles.ASPHALT)
    for y in range(H):
        z.ground[y][100] = tiles.RAIL
    for x in range(0, W, 7):
        if x != 57 and x != 100:
            z.set(x, 51, "pole")

    # 4. Посёлок Сарыкудук: улицы, потом дома поверх
    fill_rect(z, 25, 24, 25, 51, tiles.DIRT)
    fill_rect(z, 39, 24, 39, 51, tiles.DIRT)
    fill_rect(z, 14, 34, 52, 34, tiles.DIRT)
    fill_rect(z, 14, 42, 52, 42, tiles.DIRT)
    fill_rect(z, 26, 54, 26, 64, tiles.DIRT)
    reserved.append((12, 22, 54, 66))
    stamp(z, 16, 26, HOUSE_SMALL)                       # стартовый дом
    stamp(z, 27, 25, HOUSE_BIG)
    stamp(z, 41, 26, HOUSE_SMALL)
    stamp(z, 16, 36, SHOP, wall="wall_brick", floor=tiles.LINO)
    stamp(z, 30, 36, PANEL, wall="wall_concrete", floor=tiles.LINO)  # «двухэтажка»
    z.set(47, 38, "yurt")                               # юрта рядом с панелькой
    stamp(z, 20, 44, CLUB, wall="wall_brick")
    stamp(z, 36, 43, HOUSE_BIG)
    stamp(z, 18, 57, HOUSE_SMALL, flip=True)
    stamp(z, 30, 58, HOUSE_SMALL, flip=True)
    stamp(z, 40, 57, HOUSE_BIG, flip=True)
    z.set(35, 41, "well")
    for x, y in ((24, 33), (38, 33), (13, 30), (50, 45)):
        z.set(x, y, "crate")
    # в стартовом доме — ящик с молотком и досками: можно сразу заколотить окна
    z.containers["20,30"] = {"kind": "crate", "items": [{"id": "hammer", "n": 1, "dur": 100},
                                                        {"id": "planks", "n": 3}, {"id": "nails", "n": 4}]}
    z.obj[30][20] = "crate"
    z.containers["21,27"] = {"kind": "kitchen", "items": [{"id": "matches", "n": 1}, {"id": "bottle_empty", "n": 1},
                                                          {"id": "suhari", "n": 1}]}

    # 5. Колхоз «Заря» (безопасная зона)
    kw, kh = 30, 24
    fill_rect(z, KX, KY, KX + kw - 1, KY + kh - 1, tiles.DIRT)
    fence_rect(z, KX, KY, KX + kw - 1, KY + kh - 1, "fence",
               gaps={(KX + 14, KY + kh - 1), (KX + 15, KY + kh - 1), (KX, KY + 12), (KX, KY + 13)})
    marks = {}
    marks.update(stamp(z, KX + 2, KY + 2, OFFICE, wall="wall"))
    marks.update(stamp(z, KX + 17, KY + 2, WORKSHOP, wall="wall_brick", floor=tiles.CONCRETE))
    marks.update(stamp(z, KX + 2, KY + 11, GALYA_HOUSE))
    z.set(KX + 21, KY + 13, "yurt")
    marks["7"] = [(KX + 19, KY + 15)]
    marks["8"] = [(KX + 22, KY + 15)]
    z.set(KX + 14, KY + 11, "well")
    fire = (KX + 13, KY + 16)
    z.set(*fire, "campfire")
    z.fires[f"{fire[0]},{fire[1]}"] = 10 ** 9  # общий костёр колхоза не гаснет
    for x, y in ((KX + 25, KY + 18), (KX + 26, KY + 18), (KX + 3, KY + 20)):
        z.set(x, y, "crate")
    z.set(KX + 9, KY + 19, "car_uaz")
    for k in "12345678":
        if k in marks:
            z.markers[k] = list(marks[k][0])
    z.safe_rect = (KX, KY, KX + kw - 1, KY + kh - 1)
    reserved.append((KX - 1, KY - 1, KX + kw, KY + kh))
    # хлопковое поле к югу от колхоза
    fill_rect(z, 62, 32, 88, 44, tiles.FIELD)
    for y in range(32, 45, 2):
        for x in range(62, 89):
            if rnd.random() < 0.7:
                z.set(x, y, "cotton")
    reserved.append((61, 31, 89, 45))

    # 6. Железнодорожная станция
    fill_rect(z, 98, 36, 99, 50, tiles.ASPHALT)
    stamp(z, 102, 40, STATION, wall="wall_brick", floor=tiles.CONCRETE)
    z.set(98, 38, "crate")
    z.set(98, 47, "crate")
    reserved.append((96, 34, 116, 50))

    # 7. Насосная станция — сюда ведёт квест «Колодец»
    fill_rect(z, 84, 76, 94, 86, tiles.DIRT)
    pm = stamp(z, 88, 79, PUMP, wall="wall_concrete", floor=tiles.CONCRETE)
    px, py = pm["p"][0]
    z.containers[f"{px},{py}"] = {"kind": "pump", "items": [{"id": "note_uz", "n": 1}, {"id": "mask", "n": 1}]}
    for x, y in ((85, 77), (86, 77), (85, 84), (93, 83), (92, 77)):
        z.set(x, y, "barrel")
    fence_rect(z, 83, 75, 95, 87, "fence_metal", gaps={(83, 81), (83, 80)})
    reserved.append((82, 74, 96, 88))

    # 8. Лагерь бандитов «Волки степи»
    fill_rect(z, 4, 64, 16, 76, tiles.DIRT)
    for x, y in ((5, 65), (15, 66), (4, 74), (14, 75)):
        z.set(x, y, "car_zhiguli" if (x + y) % 2 else "car_uaz")
    for x, y in ((7, 68), (12, 68), (8, 73)):
        z.set(x, y, "tent")
    z.set(10, 71, "campfire")
    z.fires["10,71"] = 10 ** 9
    z.set(11, 73, "crate")
    reserved.append((3, 63, 17, 77))

    # 9. Люк «Подземки» за сеткой с табличками
    hx, hy = HATCH_POS
    fill_rect(z, hx - 4, hy - 4, hx + 4, hy + 4, tiles.DIRT)
    fence_rect(z, hx - 4, hy - 4, hx + 4, hy + 4, "fence_metal", gaps={(hx, hy - 4), (hx + 1, hy - 4)})
    z.set(hx, hy, "hatch")
    z.set(hx - 2, hy - 5, "sign_danger")
    z.set(hx + 3, hy - 5, "sign_danger")
    z.set(hx + 2, hy + 2, "crate")
    reserved.append((hx - 6, hy - 6, hx + 6, hy + 6))

    # 10. Корабельное кладбище в солончаке — ржавое судно, память об Арале
    ship = [
        "   ######   ",
        " ##......## ",
        "#....x.....#",
        "#..........#",
        " ##.....x## ",
        "   ######   ",
    ]
    stamp(z, 12, 96, ship, wall="wall_rust", floor=tiles.SAND)
    reserved.append((10, 94, 26, 103))

    # 11. Кудуки в степи, брошенные машины на трассе
    for x, y in ((30, 72), (72, 62), (8, 30), (95, 105)):
        z.set(x, y, "well")
    for x, y, k in ((10, 52, "car_zhiguli"), (47, 53, "car_uaz"), (70, 52, "car_zhiguli"), (92, 53, "car_zhiguli")):
        z.set(x, y, k)

    # 12. Растительность и камни — только на свободной степи
    def free(x, y):
        for (a, b, c, d) in reserved:
            if a <= x <= c and b <= y <= d:
                return False
        return z.obj[y][x] is None and z.ground[y][x] in (tiles.STEPPE, tiles.SAND, tiles.SALT, tiles.RIVERBED)

    for y in range(H):
        for x in range(W):
            if not free(x, y):
                continue
            r = rnd.random()
            if r < 0.012:
                z.set(x, y, "saxaul")
            elif r < 0.032:
                z.set(x, y, "bush")
            elif r < 0.042 or (z.ground[y][x] == tiles.RIVERBED and r < 0.08):
                z.set(x, y, "thorn_bush")
            elif r < 0.046:
                z.set(x, y, "rock")
    # граница карты — непроходимая сетка («контрольно-следовая полоса» — в следующих актах)
    fence_rect(z, 0, 0, W - 1, H - 1, "fence_metal")

    # 13. Стартовые враги: [вид, x, y]
    sp = z.spawns
    village = [(x, y) for y in range(24, 66) for x in range(14, 53) if not z.solid(x, y) and not tiles.is_indoor(z.ground[y][x])]
    rnd.shuffle(village)
    for i in range(14):
        sp.append(["cougher" if i % 2 else "walker", *village[i]])
    sp.append(["brute", 26, 52])
    for x, y in ((96, 44), (97, 49), (108, 50), (104, 47)):
        sp.append(["walker", x, y])
    for x, y in ((86, 79), (92, 85), (90, 76)):
        sp.append(["cougher", x, y])
    for x, y in ((hx - 2, hy - 7), (hx + 3, hy - 7)):
        sp.append(["walker", x, y])
    for x, y in ((9, 69), (13, 70), (6, 71), (11, 66)):
        sp.append(["bandit", x, y])
    for cx, cy in ((40, 86), (104, 80), (110, 14), (80, 100)):
        for k in range(3):
            sp.append(["dog", cx + k, cy + (k % 2)])
    z.markers["hatch"] = [hx, hy]
    return z


# --------------------------------------------------------------- бункер «Подземка»


def make_bunker():
    z = Zone("bunker", "Бункер «Подземка»", 40, 20, fill=tiles.BUNKER, dark=True)
    for y in range(z.h):
        for x in range(z.w):
            z.obj[y][x] = "wall_bunker"
    marks = stamp(z, 1, 1, BUNKER, wall="wall_bunker", floor=tiles.BUNKER)
    # сейф с журналом лаборанта и антидотом
    sx, sy = marks["S"][0]
    z.containers[f"{sx},{sy}"] = {"kind": "safe", "items": [{"id": "lab_journal", "n": 1}, {"id": "antidote", "n": 2},
                                                           {"id": "ammo_9", "n": 6}]}
    mx, my = marks["m"][0]
    z.containers[f"{mx},{my}"] = {"kind": "medical", "items": [{"id": "antidote", "n": 1}, {"id": "bandage", "n": 2},
                                                              {"id": "gas_filter", "n": 1}]}
    ax, ay = marks["A"][0]
    z.markers["ladder"] = [ax, ay]
    z.markers["arrive"] = [ax + 1, ay + 1]
    for x, y, k in ((12, 4, "walker"), (16, 3, "cougher"), (27, 3, "walker"), (4, 8, "cougher"),
                    (12, 11, "walker"), (14, 14, "cougher"), (23, 14, "walker"), (31, 11, "brute"), (30, 14, "walker")):
        z.spawns.append([k, x + 1, y + 1])
    return z
