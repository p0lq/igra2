"""ИИ: заражённые («Серые»), степные собаки, бандиты и мирные жители колхоза.

Враг — простой конечный автомат:
  idle        — бродит возле «дома»;
  investigate — услышал шум и идёт проверить;
  chase       — видит игрока и преследует;
  search      — потерял игрока из виду, идёт к месту, где видел его в последний раз.
Заражённые реагируют на шум и свет (концепт, раздел 8): фонарик ночью выдаёт игрока.
"""
import math
import random

from . import physics, tiles
from .data import obj as objinfo, NPCS

ENEMY_TYPES = {
    # speed — клеток/с, vision — дальность зрения днём, reach — дальность удара
    "cougher": {"name": "Кашляющий", "hp": 30, "speed": 0.9, "dmg": 5, "cd": 1.5, "vision": 6, "reach": 0.85,
                "hurt": "infected", "breaker": True, "loot": "corpse_infected", "look": "infected"},
    "walker":  {"name": "Бродяга", "hp": 45, "speed": 1.35, "dmg": 7, "cd": 1.3, "vision": 7, "reach": 0.85,
                "hurt": "infected", "breaker": True, "loot": "corpse_infected", "look": "infected"},
    "brute":   {"name": "Громила", "hp": 120, "speed": 1.05, "dmg": 16, "cd": 1.8, "vision": 7, "reach": 1.0,
                "hurt": "brute", "breaker": True, "loot": "corpse_infected", "look": "brute", "scale": 1.35},
    "dog":     {"name": "Степная собака", "hp": 25, "speed": 3.4, "dmg": 7, "cd": 0.9, "vision": 9, "reach": 0.8,
                "hurt": "dog", "loot": "corpse_dog", "look": "dog"},
    "bandit":  {"name": "«Волк степи»", "hp": 60, "speed": 2.3, "dmg": 10, "cd": 1.0, "vision": 9, "reach": 0.9,
                "hurt": "bandit", "opener": True, "loot": "corpse_bandit", "look": "bandit",
                "gun": {"range": 7, "cd": 1.7, "dmg": 12, "acc": 0.45}},
}

LOOKS = {
    "infected": [{"body": (96, 104, 90), "legs": (60, 62, 56), "skin": (150, 160, 140)},
                 {"body": (120, 90, 80), "legs": (70, 64, 60), "skin": (140, 150, 132)},
                 {"body": (90, 96, 120), "legs": (56, 56, 64), "skin": (156, 162, 146)}],
    "brute": [{"body": (80, 84, 70), "legs": (50, 50, 46), "skin": (130, 142, 120)}],
    "bandit": [{"body": (40, 38, 36), "legs": (50, 54, 70), "skin": (190, 145, 110), "hat": "bandana"}],
}


class Enemy:
    def __init__(self, kind, x, y):
        t = ENEMY_TYPES[kind]
        self.kind = kind
        self.x, self.y = x + 0.5, y + 0.5
        self.home = (x + 0.5, y + 0.5)
        self.hp = t["hp"]
        self.state = "idle"
        self.target = None
        self.path = []
        self.repath = 0.0
        self.think = random.random() * 0.25
        self.cd = 0.0
        self.shot_cd = random.uniform(0.5, 1.5)
        self.wait = random.uniform(1, 5)
        self.phase = random.random() * 6
        self.face_right = True
        self.look_i = random.randrange(len(LOOKS.get(t["look"], [None])))
        self.cough = random.uniform(4, 12)
        self.hit_flash = 0.0
        self.attack_anim = 0.0

    @property
    def t(self):
        return ENEMY_TYPES[self.kind]

    # ---------------------------------------------------- восприятие
    def can_see(self, game):
        p = game.player
        if p.god:
            return False          # режим бога: игрока никто не замечает
        dist = math.hypot(p.x - self.x, p.y - self.y)
        dark = game.darkness()
        rng = self.t["vision"] * (1 - 0.6 * dark)
        if p.has_light():
            rng = max(rng, self.t["vision"] + 3)    # свет фонаря видно издалека
        if p.sneaking:
            rng *= 0.6
        if game.clock.weather == "storm" and not game.zone.dark:
            rng *= 0.6
        if dist > max(1.5, rng):
            return False
        return physics.line_of_sight(game.zone, self.x, self.y, p.x, p.y)

    def hear(self, x, y):
        if self.state != "chase":
            self.state = "investigate"
            self.target = (x, y)
            self.path = []
            self.repath = 0

    # ---------------------------------------------------- проходимость
    def solid_fn(self, zone):
        def solid(x, y):
            if zone.get(x, y) == "window_broken" and self.t.get("breaker"):
                return False   # заражённые лезут в разбитые окна
            return zone.solid(x, y)
        return solid

    def cost_fn(self, zone):
        breaker = self.t.get("breaker")
        opener = self.t.get("opener")

        def cost(x, y):
            if not zone.inside(x, y) or tiles.is_solid(zone.ground[y][x]):
                return None
            o = zone.obj[y][x]
            if o is None:
                return 1.0
            info = objinfo(o)
            if not info.get("solid"):
                return 1.0
            if o == "window_broken" and breaker:
                return 3.0
            if info.get("door"):
                if opener:
                    return 2.0
                return 8.0 if breaker else None
            if info.get("window") and breaker:
                return 10.0
            return None
        return cost

    # ---------------------------------------------------- поведение
    def update(self, dt, game):
        p = game.player
        zone = game.zone
        self.cd = max(0, self.cd - dt)
        self.shot_cd = max(0, self.shot_cd - dt)
        self.hit_flash = max(0, self.hit_flash - dt)
        self.attack_anim = max(0, self.attack_anim - dt * 3)
        self.think -= dt
        self.repath -= dt
        dist = math.hypot(p.x - self.x, p.y - self.y)

        if self.kind in ("cougher", "walker", "brute"):
            self.cough -= dt
            if self.cough <= 0:
                self.cough = random.uniform(6, 14)
                if dist < 12:
                    game.float_text(self.x, self.y, "кхе-кхе..." if self.kind == "cougher" else "ммм...", (160, 170, 150))

        if self.think <= 0:
            self.think = 0.25
            if not p.dead() and self.can_see(game):
                if self.state != "chase" and dist < 10:
                    game.on_spotted(self)
                self.state = "chase"
                self.target = (p.x, p.y)
            elif self.state == "chase":
                self.state = "search"      # target = последнее место, где видели

        speed = self.t["speed"]
        if self.state == "chase":
            self.target = (p.x, p.y)
            gun = self.t.get("gun")
            if gun and dist <= gun["range"] and dist > 1.6 and self.shot_cd <= 0:
                self.shot_cd = gun["cd"]
                game.enemy_shoot(self, gun)
                return
            if dist <= self.t["reach"]:
                self.face_right = p.x - self.x - (p.y - self.y) > 0
                if self.cd <= 0:
                    self.cd = self.t["cd"]
                    self.attack_anim = 1.0
                    game.enemy_hits_player(self)
                return
            if gun and dist < 4.5 and self.shot_cd > 0.3:
                return   # бандит держит дистанцию и перезаряжается
            self._go(self.target, speed, dt, game)
        elif self.state in ("investigate", "search"):
            if self.target is None or math.hypot(self.target[0] - self.x, self.target[1] - self.y) < 0.6:
                self.state = "idle"
                self.wait = random.uniform(3, 8)
            else:
                self._go(self.target, speed * 0.8, dt, game)
        else:
            self.wait -= dt
            if self.wait <= 0:
                self.wait = random.uniform(4, 10)
                hx, hy = self.home
                self.target = (hx + random.uniform(-5, 5), hy + random.uniform(-5, 5))
                self.path = []
            if self.target and math.hypot(self.target[0] - self.x, self.target[1] - self.y) > 0.5:
                self._go(self.target, speed * 0.5, dt, game, budget=300)
            else:
                self.target = None

    def _go(self, target, speed, dt, game, budget=1200):
        """Идти к цели: напрямую, если видно, иначе по пути A*. Ломать двери по дороге."""
        zone = game.zone
        tx, ty = target
        direct = math.hypot(tx - self.x, ty - self.y) < 7 and physics.line_of_sight(zone, self.x, self.y, tx, ty) \
            and not self._wall_between(zone, tx, ty)
        if direct:
            gx, gy = tx, ty
            self.path = []
        else:
            if self.repath <= 0 or not self.path:
                self.repath = 0.8 + random.random() * 0.4
                self.path = physics.astar((int(self.x), int(self.y)), (int(tx), int(ty)), self.cost_fn(zone), budget)
            if not self.path:
                return
            nx, ny = self.path[0]
            o = zone.get(nx, ny)
            info = objinfo(o)
            if info.get("solid") and o != "window_broken":
                # на пути закрытая дверь или окно
                if math.hypot(nx + 0.5 - self.x, ny + 0.5 - self.y) < 1.3:
                    self._bash(nx, ny, o, game)
                    return
            if math.hypot(nx + 0.5 - self.x, ny + 0.5 - self.y) < 0.35:
                self.path.pop(0)
                return
            gx, gy = nx + 0.5, ny + 0.5
        dx, dy = gx - self.x, gy - self.y
        d = math.hypot(dx, dy)
        if d < 0.01:
            return
        step = min(d, speed * dt)
        physics.move(self, dx / d * step, dy / d * step, 0.28, self.solid_fn(zone))
        self.phase += dt * speed * 5
        self.face_right = (dx - dy) > 0

    def _wall_between(self, zone, tx, ty):
        """Проверка «не упрёмся ли в стену по прямой» (у забора обзор есть, а прохода нет)."""
        steps = int(math.hypot(tx - self.x, ty - self.y) * 3) + 1
        for i in range(1, steps):
            t = i / steps
            x, y = int(self.x + (tx - self.x) * t), int(self.y + (ty - self.y) * t)
            if self.solid_fn(zone)(x, y):
                return True
        return False

    def _bash(self, x, y, o, game):
        """Ломать дверь/окно (заражённые) или открыть дверь (бандиты)."""
        zone = game.zone
        info = objinfo(o)
        if self.t.get("opener") and info.get("door"):
            zone.set(x, y, "door_open" if o == "door" else "door_metal_open")
            self.path = []
            return
        if self.cd > 0:
            return
        self.cd = self.t["cd"]
        self.attack_anim = 1.0
        key = f"{x},{y}"
        hp = zone.obj_hp.get(key, info.get("hp", 30)) - self.t["dmg"]
        game.noise(x + 0.5, y + 0.5, 10, source=self)
        game.sound.play("bang")
        if hp <= 0:
            zone.obj_hp.pop(key, None)
            if info.get("window"):
                zone.set(x, y, "window_broken")
                game.sound.play("glass")
            else:
                zone.remove(x, y)
            game.log_near(x, y, "Что-то с треском ломается!", "bad")
            self.path = []
        else:
            zone.obj_hp[key] = hp

    def to_dict(self):
        return {"kind": self.kind, "x": self.x, "y": self.y, "home": self.home, "hp": self.hp}

    @staticmethod
    def from_dict(d):
        e = Enemy(d["kind"], 0, 0)
        e.x, e.y, e.home, e.hp = d["x"], d["y"], tuple(d["home"]), d["hp"]
        return e


class NPC:
    """Житель колхоза. Днём (8:00–21:00) — на рабочем месте, ночью — у кровати."""

    def __init__(self, nid, zone):
        self.id = nid
        self.data = NPCS[nid]
        mx, my = zone.markers[self.data["day"]]
        self.x, self.y = mx + 0.5, my + 0.5
        self.path = []
        self.repath = 0.0
        self.phase = 0.0
        self.face_right = random.random() < 0.5
        self.moving = False
        self.stock = dict(self.data["stock"])

    @property
    def name(self):
        return self.data["name"]

    def update(self, dt, game):
        zone = game.zones["sarykuduk"]
        h = game.clock.hour
        spot = self.data["day"] if 8 <= h < 21 else self.data["night"]
        tx, ty = zone.markers[spot]
        self.moving = False
        if game.dialog_npc is self:
            p = game.player
            self.face_right = (p.x - self.x) - (p.y - self.y) > 0
            return
        if math.hypot(tx + 0.5 - self.x, ty + 0.5 - self.y) < 0.4:
            return
        self.repath -= dt
        if self.repath <= 0 or not self.path:
            self.repath = 2.0
            self.path = physics.astar((int(self.x), int(self.y)), (tx, ty),
                                      lambda x, y: None if zone.solid(x, y) and zone.get(x, y) != "door" else 1.0, 800)
        if not self.path:
            return
        nx, ny = self.path[0]
        if zone.get(nx, ny) == "door":
            zone.set(nx, ny, "door_open")   # жители открывают двери
        dx, dy = nx + 0.5 - self.x, ny + 0.5 - self.y
        d = math.hypot(dx, dy)
        if d < 0.15:
            self.path.pop(0)
            return
        step = min(d, 1.6 * dt)
        self.x += dx / d * step
        self.y += dy / d * step
        self.phase += dt * 8
        self.moving = True
        self.face_right = (dx - dy) > 0

    def to_dict(self):
        return {"id": self.id, "x": self.x, "y": self.y, "stock": self.stock}


def spawn_wanderers(game, n):
    """Ночью из степи приходят новые заражённые — подальше от игрока и не в колхозе."""
    zone = game.zones["sarykuduk"]
    p = game.player
    placed = 0
    tries = 0
    while placed < n and tries < 400:
        tries += 1
        x, y = random.randrange(2, zone.w - 2), random.randrange(2, zone.h - 2)
        if zone.solid(x, y) or zone.in_safe(x, y) or zone.indoor(x, y):
            continue
        if game.zone is zone and math.hypot(x - p.x, y - p.y) < 25:
            continue
        kind = random.choice(["walker", "walker", "cougher", "cougher", "brute"] if game.clock.day > 3 else ["walker", "cougher"])
        game.enemies_by_zone["sarykuduk"].append(Enemy(kind, x, y))
        placed += 1
