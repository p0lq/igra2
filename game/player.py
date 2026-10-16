"""Игрок: потребности, здоровье, раны, болезни, навыки и черты.

Шкалы потребностей идут от 0 (всё хорошо) до 100 (смертельно):
  hunger — голод, thirst — жажда, fatigue — усталость.
mood — настроение, наоборот: 100 — отлично, 0 — депрессия.
temp — температура тела в °C (норма 36.6).
disease — «пыльная болезнь» (заражение штаммом) 0..100, на 100 — смерть.
poison — отравление 0..100.
Все скорости указаны «за игровую минуту».
"""
import math
import random

from .data import ITEMS, TRAITS, SKILLS
from . import inventory as inv

BODY_PARTS = ["голова", "торс", "левая рука", "правая рука", "левая нога", "правая нога"]

WOUND_INFO = {
    # bleed — кровотечение до перевязки, heal — минут до заживления
    "Порез":   {"bleed": True,  "heal": 24 * 60, "pain": 15},
    "Укус":    {"bleed": True,  "heal": 36 * 60, "pain": 20},
    "Ушиб":    {"bleed": False, "heal": 12 * 60, "pain": 10},
    "Перелом": {"bleed": False, "heal": 7 * 24 * 60, "pain": 45},
}


class Player:
    def __init__(self, name="Выживший", traits=(), mode="normal"):
        self.name = name
        self.traits = list(traits)
        self.mode = mode                 # "normal" или "hard" (одна жизнь)
        self.x, self.y = 0.0, 0.0
        self.fx, self.fy = 1.0, 0.0      # направление взгляда (в клетках)
        self.face_right = True
        self.walk_phase = 0.0
        self.moving = False

        self.hunger = 10.0
        self.thirst = 15.0
        self.fatigue = 10.0
        self.mood = 60.0
        self.temp = 36.6
        self.health = 100.0
        self.disease = 0.0
        self.poison = 0.0
        self.pain = 0.0
        self.painkiller = 0.0            # минут действия анальгина
        self.wounds = []
        self.since_smoke = 0.0

        self.skills = {s: {"lvl": 0, "xp": 0} for s in SKILLS}
        for t in self.traits:
            for s, lv in TRAITS[t].get("skills", {}).items():
                self.skills[s]["lvl"] += lv

        self.items = []
        self.equip = {"weapon": None, "body": None, "head": None, "face": None, "back": None, "light": None}
        self.known_recipes = set()
        self.read_books = set()
        self.flashlight_on = False
        self.sneaking = False
        self.running = False
        self.sleeping = False
        self.attack_cd = 0.0
        self.attack_anim = 0.0
        self.action = None               # долгое действие: {"name", "time", "left", "done"}
        self.kills = 0
        self.hit_flash = 0.0
        self.god = False                 # режим бога: бессмертие, враги не замечают
        self.noclip = False              # проход сквозь стены (команда консоли)
        self.sleep_bed = False

    # ------------------------------------------------ черты и навыки
    def has(self, trait):
        return trait in self.traits

    def lvl(self, skill):
        return self.skills[skill]["lvl"]

    def add_xp(self, skill, amount):
        """Навыки растут от использования. Возвращает текст, если уровень вырос."""
        s = self.skills[skill]
        if s["lvl"] >= 10:
            return None
        s["xp"] += amount
        need = 60 * (s["lvl"] + 1)
        if s["xp"] >= need:
            s["xp"] -= need
            s["lvl"] += 1
            return f"Навык «{SKILLS[skill]}» вырос до {s['lvl']}!"
        return None

    # ------------------------------------------------ вес и экипировка
    def carry_limit(self):
        if self.god:
            return 999.0
        lim = 10.0
        for t in self.traits:
            lim += TRAITS[t].get("carry", 0)
        back = self.equip["back"]
        if back:
            lim += ITEMS[back["id"]].get("capacity", 0)
        return lim

    def weight(self):
        w = inv.weight(self.items)
        for st in self.equip.values():
            if st:
                w += ITEMS[st["id"]]["w"] * 0.5   # надетое весит вдвое меньше
        return w

    def warmth(self):
        return sum(ITEMS[st["id"]].get("warmth", 0) for st in self.equip.values() if st)

    def protection(self):
        return min(0.6, sum(ITEMS[st["id"]].get("protect", 0) for st in self.equip.values() if st))

    def has_filter(self):
        """Надет респиратор/противогаз с живым фильтром."""
        st = self.equip["face"]
        return st is not None and st.get("filter", 0) > 0

    def weapon(self):
        st = self.equip["weapon"]
        return (st, ITEMS[st["id"]]) if st else (None, None)

    def has_light(self):
        st = self.equip["light"]
        return self.flashlight_on and st is not None and st.get("battery", 0) > 0

    # ------------------------------------------------ влияние состояния
    def speed_mult(self):
        k = 1.0
        if self.fatigue > 80:
            k *= 0.75
        for w in self.wounds:
            if w["type"] == "Перелом" and "нога" in w["part"]:
                k *= 0.85 if w.get("splinted") else 0.6
        over = self.weight() / self.carry_limit()
        if over > 1.5:
            k *= 0.4
        elif over > 1.0:
            k *= 0.7
        return k

    def melee_mult(self):
        k = 1.0 + 0.08 * self.lvl("melee")
        if self.fatigue > 80:
            k *= 0.7
        if self.has("weak"):
            k *= 0.8
        if self.pain > 60 and self.painkiller <= 0:
            k *= 0.8
        return k

    def noise_mult(self):
        k = 1.3 if self.has("clumsy") else 1.0
        if self.sneaking:
            k *= max(0.25, 0.55 - 0.04 * self.lvl("sneak"))
        if self.running:
            k *= 1.8
        return k

    def bleeding(self):
        return any(w["bleeding"] for w in self.wounds)

    # ------------------------------------------------ ежеминутное обновление
    def update_needs(self, mins, env, log):
        """Изменить потребности за mins игровых минут. env — состояние окружения от игры."""
        sleeping = self.sleeping
        k_sleep = 0.5 if sleeping else 1.0

        hunger_rate = 0.065 * (1.3 if self.has("glutton") else 1.0)
        self.hunger = min(100, self.hunger + hunger_rate * k_sleep * mins)

        thirst_rate = 0.09
        if env["hot"] and not env["indoor"]:
            thirst_rate *= 1.6
        if self.running:
            thirst_rate *= 1.5
        if self.poison > 20:
            thirst_rate *= 1.3
        self.thirst = min(100, self.thirst + thirst_rate * k_sleep * mins)

        if sleeping:
            self.fatigue = max(0, self.fatigue - (0.4 if env["bed"] else 0.25) * mins)
        else:
            rate = 0.055
            if self.running:
                rate *= 2.2 if self.has("asthma") else 1.8
            self.fatigue = min(100, self.fatigue + rate * mins)

        self._update_temp(mins, env)
        self._update_disease(mins, env, log)
        self._update_wounds(mins, log)

        # отравление проходит само
        self.poison = max(0, self.poison - 0.05 * mins)
        self.painkiller = max(0, self.painkiller - mins)

        # курильщику без сигарет плохо
        self.since_smoke += mins
        mood_delta = 0.0
        if self.has("smoker") and self.since_smoke > 12 * 60:
            mood_delta -= 0.03
        if self.hunger > 60:
            mood_delta -= 0.02
        if self.thirst > 60:
            mood_delta -= 0.02
        if self.pain > 30 and self.painkiller <= 0:
            mood_delta -= 0.02
        if env["near_fire"]:
            mood_delta += 0.03
        if mood_delta == 0 and self.mood < 60:
            mood_delta = 0.01
        self.mood = max(0, min(100, self.mood + mood_delta * mins))

        # урон и восстановление здоровья
        dmg = 0.0
        if self.hunger >= 90:
            dmg += 0.03
        if self.thirst >= 90:
            dmg += 0.06
        dmg += 0.035 * sum(1 for w in self.wounds if w["bleeding"])
        if self.poison > 50:
            dmg += 0.02
        if self.disease >= 70:
            dmg += 0.02
        if self.temp < 35.0 or self.temp > 39.0:
            dmg += 0.02
        if any(w.get("inflamed") for w in self.wounds):
            dmg += 0.01
        if dmg > 0:
            self.health -= dmg * mins
        elif self.hunger < 70 and self.thirst < 70 and self.poison < 30:
            self.health = min(100, self.health + (0.06 if sleeping else 0.02) * mins)

        # боль складывается из ран
        target_pain = sum(WOUND_INFO[w["type"]]["pain"] * (0.5 if w.get("bandaged") or w.get("splinted") else 1) for w in self.wounds)
        self.pain += (min(100, target_pain) - self.pain) * min(1, 0.1 * mins)

    def _update_temp(self, mins, env):
        """Температура тела тянется к «ощущаемой»: степь днём жарит, ночью морозит."""
        felt = env["air_temp"] + self.warmth() * 4
        if env["near_fire"]:
            felt += 14
        if env["indoor"]:
            felt += 4
        target = 36.6
        if felt < 12:
            target = 36.6 - (12 - felt) * 0.12
        elif felt > 30 and env["hot"] and not env["indoor"]:
            sun = sum(ITEMS[st["id"]].get("sun", 0) for st in self.equip.values() if st)
            target = 36.6 + (felt - 30) * 0.08 * (1 - 0.6 * min(1, sun))
        if any(w.get("inflamed") for w in self.wounds) or 40 <= self.disease < 70:
            target += 1.2
        self.temp += (target - self.temp) * min(1, 0.01 * mins)

    def _update_disease(self, mins, env, log):
        exposure = env["dust"]
        if exposure > 0 and self.has_filter():
            # фильтр защищает, но тратится
            self.equip["face"]["filter"] = max(0, self.equip["face"]["filter"] - mins * (3 if exposure > 0.05 else 1))
            if self.equip["face"]["filter"] <= 0:
                log("Фильтр забился! Нужен новый.", "bad")
            exposure = 0
        if self.has("asthma"):
            exposure *= 1.5
        before = self.disease
        if exposure > 0:
            self.disease += exposure * mins
        elif self.disease >= 40:
            self.disease += 0.006 * mins      # болезнь развивается сама
        else:
            self.disease = max(0, self.disease - 0.004 * mins)
        for th, txt in ((15, "Ты закашлялся. Горло дерёт пылью."), (40, "Тебя лихорадит. Пыльная болезнь развивается."),
                        (70, "Голова плывёт. Голоса... Нужен антидот!")):
            if before < th <= self.disease:
                log(txt, "bad")
        self.disease = min(100, self.disease)

    def _update_wounds(self, mins, log):
        for w in list(self.wounds):
            # грязная перевязка без обработки может воспалиться
            if w.get("dirty") and not w.get("disinfected") and not w.get("inflamed"):
                if random.random() < 0.0008 * mins:
                    w["inflamed"] = True
                    log(f"Рана ({w['part']}) воспалилась. Нужна зелёнка!", "bad")
            speed = 1.0
            if w.get("bandaged"):
                speed *= 1.5
            if w.get("splinted"):
                speed *= 2.0
            if w.get("inflamed"):
                speed *= 0.2
            speed *= 1 + 0.1 * self.lvl("firstaid")
            w["left"] -= mins * speed
            if w["left"] <= 0:
                self.wounds.remove(w)
                log(f"Рана зажила: {w['type'].lower()} ({w['part']}).", "good")

    # ------------------------------------------------ урон
    def hurt(self, dmg, kind, log):
        """Получить удар. kind: infected / dog / bandit / brute / fall."""
        if self.god:
            return
        self.hit_flash = 0.3
        prot = self.protection()
        dmg *= (1 - prot * 0.5)
        self.health -= dmg
        self.sleeping = False
        self.action = None
        if random.random() < 0.55:
            part = random.choice(BODY_PARTS)
            if kind in ("infected", "dog"):
                wt = "Укус" if random.random() < 0.6 else "Порез"
            elif kind == "brute":
                wt = "Перелом" if random.random() < 0.2 else "Ушиб"
            elif kind == "bullet":
                wt = "Порез"
            else:
                wt = random.choice(["Порез", "Ушиб"])
            self.wounds.append({"type": wt, "part": part, "bleeding": WOUND_INFO[wt]["bleed"],
                                "left": WOUND_INFO[wt]["heal"]})
            log(f"{wt}: {part}!", "bad")
            # укус заражённого может передать штамм
            if kind == "infected" and wt in ("Укус", "Порез") and random.random() < 0.35 * (1 - prot):
                self.disease = min(100, self.disease + random.uniform(8, 16))
                log("Рана жжёт... Штамм попал в кровь.", "bad")

    # ------------------------------------------------ лечение
    def treat(self, wound, med):
        """Применить медицинское средство к ране. Возвращает текст результата."""
        fa = self.lvl("firstaid") + (3 if self.has("doctor") else 0)
        if med in ("bandage", "bandage_dirty"):
            if wound.get("bandaged"):
                return "Рана уже перевязана."
            wound["bandaged"] = True
            wound["bleeding"] = False
            wound["dirty"] = med == "bandage_dirty"
            wound["left"] -= 60 * fa
            return "Перевязал рану." + (" Тряпка грязная — лучше обработать." if wound["dirty"] else "")
        if med == "disinfect":
            wound["disinfected"] = True
            if wound.get("inflamed"):
                wound["inflamed"] = False
                return "Обработал воспалённую рану. Жжёт, но поможет."
            return "Обработал рану."
        if med == "splint":
            if wound["type"] != "Перелом":
                return "Шина нужна только при переломе."
            wound["splinted"] = True
            return "Наложил шину."
        return "Не помогает."

    # ------------------------------------------------ состояния для HUD
    def moodles(self, overweight=False):
        """Список состояний (текст, уровень 1..3) — как «муды» в Project Zomboid."""
        out = []

        def add(val, ths, names):
            best = None
            for i, th in enumerate(ths):
                if val >= th:
                    best = (names[i], i + 1)
            if best:
                out.append(best)

        add(self.hunger, (40, 70, 90), ("Голод", "Сильный голод", "Истощение"))
        add(self.thirst, (40, 70, 90), ("Жажда", "Сильная жажда", "Обезвоживание"))
        add(self.fatigue, (50, 80, 95), ("Усталость", "Изнеможение", "Валится с ног"))
        add(self.disease, (15, 40, 70), ("Кашель", "Лихорадка", "Бред"))
        add(self.poison, (20, 50, 80), ("Тошнота", "Отравление", "Сильное отравление"))
        if self.painkiller <= 0:
            add(self.pain, (25, 50, 80), ("Боль", "Сильная боль", "Невыносимая боль"))
        if self.temp > 37.4:
            out.append(("Жар" if self.temp < 38.8 else "Тепловой удар", 1 if self.temp < 38.8 else 3))
        elif self.temp < 35.9:
            out.append(("Озноб" if self.temp > 35.0 else "Переохлаждение", 1 if self.temp > 35.0 else 3))
        if self.bleeding():
            out.append(("Кровотечение", 3))
        if self.mood < 30:
            out.append(("Тоска" if self.mood > 12 else "Депрессия", 1 if self.mood > 12 else 2))
        if overweight:
            out.append(("Перегруз", 1))
        return out

    def dead(self):
        if self.god:
            return False
        return self.health <= 0 or self.disease >= 100

    def to_dict(self):
        d = dict(self.__dict__)
        d["known_recipes"] = sorted(self.known_recipes)
        d["read_books"] = sorted(self.read_books)
        d["action"] = None
        return d

    def load_dict(self, d):
        for k, v in d.items():
            setattr(self, k, v)
        self.known_recipes = set(d["known_recipes"])
        self.read_books = set(d["read_books"])
