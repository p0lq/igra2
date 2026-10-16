"""Консоль разработчика (клавиша ` / Ё). Нужна для тестирования: выдать предметы,
включить режим бога, перенестись в нужное место, сменить погоду.

Каждая команда — обычная функция cmd_<имя>(game, args). Чтобы добавить команду,
достаточно написать новую функцию: список команд собирается автоматически.
"""
import math

from .data import ITEMS, QUESTS, SKILLS
from . import ai, inventory as inv

OK = (200, 220, 160)
ERR = (230, 110, 90)
INFO = (200, 190, 160)

# Места для команды tp
PLACES = {
    "start": ("Стартовый дом", "sarykuduk", (19.5, 28.5)),
    "zarya": ("Колхоз «Заря»", "sarykuduk", (74.5, 26.5)),
    "pump": ("Насосная станция", "sarykuduk", (86.5, 81.5)),
    "hatch": ("Люк «Подземки»", "sarykuduk", (52.5, 98.5)),
    "camp": ("Лагерь «Волков степи»", "sarykuduk", (10.5, 62.5)),
    "station": ("Железнодорожная станция", "sarykuduk", (98.5, 42.5)),
    "ship": ("Корабль в солончаке", "sarykuduk", (18.5, 99.5)),
    "bunker": ("Бункер «Подземка»", "bunker", (3.5, 3.5)),
}


class Console:
    def __init__(self):
        self.text = ""
        self.lines = [("Консоль «Границы-99». Введи help — список команд.", INFO)]
        self.history = []
        self.hist_i = 0
        self.skip_char = False   # первый символ ` после открытия не печатаем

    def print(self, text, col=INFO):
        for line in str(text).split("\n"):
            self.lines.append((line, col))
        self.lines = self.lines[-200:]

    def submit(self, game):
        cmd = self.text.strip()
        self.text = ""
        if not cmd:
            return
        self.history.append(cmd)
        self.hist_i = len(self.history)
        self.print("> " + cmd, (255, 230, 160))
        parts = cmd.split()
        fn = globals().get("cmd_" + parts[0].lower())
        if fn is None:
            self.print(f"Нет такой команды: {parts[0]}. Введи help.", ERR)
            return
        try:
            res = fn(game, parts[1:])
            if res:
                self.print(res, OK)
        except Exception as ex:   # ошибка в команде не должна ронять игру
            self.print(f"Ошибка: {ex}", ERR)

    def history_step(self, d):
        if not self.history:
            return
        self.hist_i = max(0, min(len(self.history), self.hist_i + d))
        self.text = self.history[self.hist_i] if self.hist_i < len(self.history) else ""


# ------------------------------------------------------------------ команды

def cmd_help(game, args):
    """help — список команд"""
    out = ["Команды:"]
    for name, fn in sorted(globals().items()):
        if name.startswith("cmd_"):
            out.append("  " + (fn.__doc__ or name[4:]).strip())
    return "\n".join(out)


def cmd_god(game, args):
    """god — режим бога вкл/выкл (бессмертие, враги не замечают, каталог предметов)"""
    game.toggle_god()
    return "Режим бога: " + ("ВКЛ" if game.player.god else "выкл")


def cmd_noclip(game, args):
    """noclip — ходить сквозь стены вкл/выкл"""
    p = game.player
    p.noclip = not p.noclip
    return "Noclip: " + ("ВКЛ" if p.noclip else "выкл")


def _find_item(query):
    q = query.lower()
    if q in ITEMS:
        return q
    found = [i for i, it in ITEMS.items() if q in i or q in it["name"].lower()]
    return found[0] if found else None


def cmd_give(game, args):
    """give <id или часть названия> [кол-во] — выдать предмет (пример: give тушёнка 5)"""
    if not args:
        return "Укажи предмет: give pm 1"
    n = 1
    if len(args) > 1 and args[-1].isdigit():
        n = int(args[-1])
        args = args[:-1]
    iid = _find_item(" ".join(args))
    if iid is None:
        raise ValueError("предмет не найден, посмотри список: items")
    game.give_item(iid, n)
    return f"Выдано: {ITEMS[iid]['name']} ×{n}"


def cmd_items(game, args):
    """items [фильтр] — список предметов и их id"""
    q = " ".join(args).lower()
    rows = [f"{i:16} {it['name']}" for i, it in ITEMS.items() if not q or q in i or q in it["name"].lower()]
    return "\n".join(rows) if rows else "Ничего не найдено"


def cmd_heal(game, args):
    """heal — полностью вылечиться и насытиться"""
    p = game.player
    p.health, p.hunger, p.thirst, p.fatigue = 100, 0, 0, 0
    p.disease = p.poison = p.pain = 0
    p.temp = 36.6
    p.wounds.clear()
    return "Здоров как бык."


def cmd_time(game, args):
    """time <час> — перевести часы (пример: time 22)"""
    h = float(args[0])
    c = game.clock
    day_start = (c.day - 1) * 1440
    c.minutes = day_start + h * 60
    c._last_hour = int(c.minutes // 60)
    return f"Время: {c.clock_text()}"


def cmd_weather(game, args):
    """weather clear|storm|rain|front — сменить погоду"""
    c = game.clock
    w = args[0] if args else "clear"
    c.front = False
    if w == "front":
        c.front, c.front_left, c.weather = True, 180, "clear"
    elif w in ("clear", "storm", "rain"):
        c.weather, c.weather_left = w, 120
    else:
        raise ValueError("варианты: clear, storm, rain, front")
    return f"Погода: {w}"


def cmd_tp(game, args):
    """tp <место> или tp <x> <y> — телепорт (места: start zarya pump hatch camp station ship bunker)"""
    if len(args) == 2 and all(a.replace(".", "").isdigit() for a in args):
        x, y = float(args[0]), float(args[1])
        game.player.x, game.player.y = x, y
        game.cam.snap(x, y)
        return f"Телепорт в {x}, {y}"
    if not args or args[0] not in PLACES:
        return "Места: " + ", ".join(PLACES)
    name, zid, pos = PLACES[args[0]]
    game.change_zone(zid, (pos[0] - 0.5, pos[1] - 0.5))
    return f"Телепорт: {name}"


def cmd_pos(game, args):
    """pos — где я стою (координаты клетки)"""
    p = game.player
    return f"{game.zone.name}: x={p.x:.1f}, y={p.y:.1f}"


def cmd_kill(game, args):
    """kill [радиус] — убить врагов рядом (по умолчанию 15 клеток)"""
    r = float(args[0]) if args else 15
    p = game.player
    victims = [e for e in game.enemies if math.hypot(e.x - p.x, e.y - p.y) <= r]
    for e in victims:
        game._kill(e)
    return f"Убито врагов: {len(victims)}"


def cmd_spawn(game, args):
    """spawn <cougher|walker|brute|dog|bandit> [кол-во] — создать врага рядом"""
    kind = args[0] if args else "walker"
    if kind not in ai.ENEMY_TYPES:
        raise ValueError("виды: " + ", ".join(ai.ENEMY_TYPES))
    n = int(args[1]) if len(args) > 1 else 1
    p = game.player
    made = 0
    for i in range(n * 4):          # пробуем разные точки по кругу, пока не создадим n врагов
        if made >= n:
            break
        ang = i * 2 * math.pi / max(1, n * 4)
        x, y = int(p.x + 4 * math.cos(ang)), int(p.y + 4 * math.sin(ang))
        if not game.zone.solid(x, y):
            game.enemies.append(ai.Enemy(kind, x, y))
            made += 1
    return f"Создано: {ai.ENEMY_TYPES[kind]['name']} ×{made}"


def cmd_quest(game, args):
    """quest <id> <стадия> — выставить стадию задания (id: dust water well bunker metal)"""
    if len(args) < 2 or args[0] not in QUESTS:
        return "Задания: " + ", ".join(f"{q} (до {QUESTS[q]['final']})" for q in QUESTS)
    game.quests[args[0]] = int(args[1])
    return f"{QUESTS[args[0]]['name']}: стадия {args[1]}"


def cmd_skill(game, args):
    """skill <id> <уровень> — выставить навык (id: survival cooking firstaid carpentry melee aim sneak trade languages)"""
    if len(args) < 2 or args[0] not in SKILLS:
        return "Навыки: " + ", ".join(SKILLS)
    game.player.skills[args[0]]["lvl"] = max(0, min(10, int(args[1])))
    return f"{SKILLS[args[0]]}: {args[1]}"


def cmd_recipes(game, args):
    """recipes — выучить все рецепты"""
    from .data import RECIPES
    game.player.known_recipes = set(RECIPES)
    return f"Выучено рецептов: {len(RECIPES)}"


def cmd_flag(game, args):
    """flag <имя> — поставить сюжетный флаг (например bunker_code)"""
    if not args:
        return "Флаги: " + (", ".join(sorted(game.flags)) or "нет")
    game.flags.add(args[0])
    return f"Флаг поставлен: {args[0]}"


def cmd_clear(game, args):
    """clear — очистить консоль"""
    game.console.lines.clear()
    return ""
