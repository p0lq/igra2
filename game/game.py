"""Главный класс игры: состояние мира, игровой цикл, управление, бой и связь всех модулей.

Состояния экрана: menu (главное меню) -> creation (создание персонажа) -> play -> dead.
"""
import math
import random

import pygame

from .config import SCREEN_W, SCREEN_H, FPS, TITLE, GAME_MIN_PER_SEC, COL_BG
from .data import ITEMS, OBJECTS, RECIPES, NPCS, QUESTS, RADIO, GLOSSARY
from .iso import Camera, to_screen, to_tile, screen_dir_to_tile
from .player import Player
from .world_time import WorldClock
from .localization import parse_markup
from . import worldgen, physics, art, render, ui as uimod, actions, crafting, save, ai, inventory as inv
from .dialogue import Dialogue, apply
from .sound import SoundSystem

# окна, во время которых время в мире стоит
PAUSING_WINDOWS = {"pause", "help", "dialogue", "trade", "note", "chapter"}
INTERACTIVE = ("door", "window", "container", "water", "chop", "pick", "bed", "fire",
               "workbench", "collector", "hatch", "ladder", "alarm")


class Game:
    def __init__(self):
        pygame.mixer.pre_init(22050, -16, 1, 512)
        pygame.init()
        pygame.display.set_caption(TITLE)
        pygame.display.set_icon(self._make_icon())
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.SCALED | pygame.RESIZABLE)
        self.clock_fps = pygame.time.Clock()
        art.build()
        self.ui = uimod.UI()
        self.sound = SoundSystem()
        self.state = "menu"
        self.window = None
        self.running = True
        self.time_real = 0.0
        self.creation = {"name": "Серик", "traits": [], "mode": "normal"}
        self._reset_world()

    @staticmethod
    def _make_icon():
        """Иконка окна: солнце над степью и юрта — тоже нарисована кодом."""
        s = pygame.Surface((32, 32))
        s.fill((196, 150, 80))
        pygame.draw.circle(s, (240, 200, 120), (22, 12), 6)
        pygame.draw.rect(s, (70, 52, 34), (0, 22, 32, 10))
        pygame.draw.ellipse(s, (226, 218, 196), (5, 13, 14, 12))
        pygame.draw.rect(s, (226, 218, 196), (5, 19, 14, 6))
        pygame.draw.rect(s, (170, 50, 40), (5, 20, 14, 2))
        return s

    # ================================================================ мир
    def _reset_world(self):
        self.zones = {"sarykuduk": worldgen.make_sarykuduk(), "bunker": worldgen.make_bunker()}
        self.zone = self.zones["sarykuduk"]
        self.enemies_by_zone = {zid: [ai.Enemy(k, x, y) for k, x, y in z.spawns] for zid, z in self.zones.items()}
        self.npcs = [ai.NPC(nid, self.zones["sarykuduk"]) for nid in NPCS]
        self.player = Player()
        self.clock = WorldClock()
        self.cam = Camera()
        self.messages = []
        self.floats = []
        self.effects = []
        self.quests = {}
        self.flags = set()
        self.rep = {"zarya": 0}
        self.glossary = set()
        self.radio_heard = set()
        self.radio_station = 0
        self._radio_cache = {}
        self.dialog = None
        self.dialog_npc = None
        self.trade = None
        self.note_stack = None
        self.container_key = None
        self.sel_item = None
        self.sel_from = "player"
        self.sel_recipe = None
        self.pending_trade = False
        self.pending_chapter = False
        self.hover_tile = None
        self.hint = ""
        self.target = None
        self.world_click = False
        self.death_cause = ""
        self.last_hurt = ("", -999)
        self.spot_cd = 0.0
        self.alarm_cd = {}
        self.step_acc = 0.0

    @property
    def enemies(self):
        return self.enemies_by_zone[self.zone.id]

    def visible_npcs(self):
        return self.npcs if self.zone.id == "sarykuduk" else []

    def darkness(self):
        if self.zone.dark:
            return 0.92
        return self.clock.darkness()

    # ================================================================ запуск
    def run(self):
        while self.running:
            dt = min(0.05, self.clock_fps.tick(FPS) / 1000.0)
            self.time_real += dt
            events = pygame.event.get()
            for e in events:
                if e.type == pygame.QUIT:
                    self.running = False
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_F11:
                    pygame.display.toggle_fullscreen()
            self.ui.begin(events)
            self.screen.fill(COL_BG)
            if self.state == "menu":
                self._menu_events(events)
                uimod.draw_main_menu(self.screen, self.ui, self)
            elif self.state == "creation":
                self._creation_events(events)
                uimod.draw_creation(self.screen, self.ui, self)
            elif self.state in ("play", "dead"):
                if self.state == "play":
                    self._play_events(events)
                    self.update(dt)
                self.draw_play()
            pygame.display.flip()
        pygame.quit()

    def quit(self):
        self.running = False

    # ================================================================ экраны меню
    def _menu_events(self, events):
        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE and self.window:
                self.window = None

    def _creation_events(self, events):
        c = self.creation
        for e in events:
            if e.type == pygame.TEXTINPUT and len(c["name"]) < 18:
                c["name"] += e.text
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_BACKSPACE:
                    c["name"] = c["name"][:-1]
                elif e.key == pygame.K_ESCAPE:
                    self.to_menu()

    def to_menu(self):
        self.state = "menu"
        self.window = None

    def to_creation(self):
        self.state = "creation"
        self.window = None
        self.creation = {"name": "Серик", "traits": [], "mode": "normal"}

    def new_game(self):
        c = self.creation
        self._reset_world()
        p = Player(c["name"].strip(), c["traits"], c["mode"])
        p.x, p.y = worldgen.START_POS
        p.known_recipes = {rid for rid, r in RECIPES.items() if r.get("known")}
        self.player = p
        p.equip["weapon"] = inv.new_stack("knife")
        inv.add(p.items, "water_clean", 1)
        inv.add(p.items, "suhari", 2)
        self.messages = []
        self.quests = {"dust": 1}
        self.cam.snap(p.x, p.y)
        self.state = "play"
        self.window = None
        self.log("Ты приходишь в себя в чужом доме. Голова гудит, во рту пыль.", "info")
        self.log("Сарыкудук, лето 1999-го. После Пыльного фронта посёлок опустел.", "info")
        self.log("Найди воду и выживших. Говорят, в колхозе «Заря» на северо-востоке есть люди.", "quest")
        self.log("F1 — управление. В доме есть ящик с инструментом — обыщи его [E].", "info")

    # ================================================================ ввод в игре
    def _play_events(self, events):
        p = self.player
        for e in events:
            if e.type != pygame.KEYDOWN:
                continue
            k = e.key
            if k == pygame.K_ESCAPE:
                if self.window:
                    self.close_window()
                else:
                    self.open_window("pause")
                continue
            if self.window == "dialogue":
                if pygame.K_1 <= k <= pygame.K_9:
                    self.choose_dialog(k - pygame.K_1)
                continue
            if self.window in ("chapter", "pause"):
                continue
            toggles = {pygame.K_i: "inventory", pygame.K_TAB: "inventory", pygame.K_c: "craft", pygame.K_h: "health",
                       pygame.K_j: "journal", pygame.K_g: "glossary", pygame.K_F1: "help"}
            if k in toggles:
                w = toggles[k]
                if self.window == w:
                    self.close_window()
                else:
                    self.close_window()
                    self.open_window(w)
                continue
            if k == pygame.K_m:
                self.sound.toggle_mute()
            elif k == pygame.K_F5 and p.mode != "hard":
                self.save_game()
            elif k == pygame.K_F9 and save.exists():
                self.load_game()
            if self.window:
                continue
            if k == pygame.K_e:
                self.do_interact()
            elif k == pygame.K_f:
                self.toggle_flashlight()
            elif k == pygame.K_r:
                actions.reload_gun(self)
            elif k == pygame.K_b:
                actions.barricade(self)
            elif k == pygame.K_z:
                p.sneaking = not p.sneaking
                self.log("Крадёшься тихо." if p.sneaking else "Идёшь обычным шагом.", "info")

    # ================================================================ окна
    def open_window(self, name):
        self.window = name
        if name == "inventory":
            self.sel_item = None

    def close_window(self):
        if self.window == "inventory" and self.container_key:
            self._cleanup_pile(self.container_key)
            self.container_key = None
        if self.window == "dialogue":
            self.dialog = None
            self.dialog_npc = None
        if self.window == "trade":
            self.trade = None
            self.dialog_npc = None
        self.window = None

    def open_container(self, key):
        self.container_key = key
        self.window = "inventory"
        self.sel_item = None

    def container_items(self):
        key = self.container_key
        if self.window != "inventory" or not key or key not in self.zone.containers:
            return None
        x, y = map(int, key.split(","))
        if math.hypot(x + 0.5 - self.player.x, y + 0.5 - self.player.y) > 2.2:
            self.container_key = None
            return None
        return self.zone.containers[key]["items"]

    def container_title(self):
        x, y = map(int, self.container_key.split(","))
        return OBJECTS.get(self.zone.get(x, y), {}).get("name", "Контейнер")

    def _cleanup_pile(self, key):
        c = self.zone.containers.get(key)
        x, y = map(int, key.split(","))
        if c and not c["items"] and OBJECTS.get(self.zone.get(x, y), {}).get("temp"):
            self.zone.remove(x, y)

    def ground_pile(self, x, y):
        for dx, dy in [(0, 0), (1, 0), (0, 1), (-1, 0), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)]:
            tx, ty = x + dx, y + dy
            o = self.zone.get(tx, ty)
            key = f"{tx},{ty}"
            if o in ("pile", "corpse") and key in self.zone.containers:
                if self.zone.containers[key]["items"] is None:
                    self.zone.containers[key]["items"] = []
                return key
            if o is None and not self.zone.solid(tx, ty):
                self.zone.set(tx, ty, "pile")
                self.zone.containers[key] = {"kind": "none", "items": []}
                return key
        return None

    def open_note(self, st):
        it = ITEMS[st["id"]]
        p = self.player
        if not st.get("read") and it.get("lang") != "ru" and p.lvl("languages") >= it.get("req", 99):
            self.log("Ты понимаешь этот текст — пригодился навык «Языки».", "lang")
            self.mark_note_read(st)
        self.note_stack = st
        self.window = "note"

    def mark_note_read(self, st):
        if st.get("read"):
            return
        st["read"] = True
        for e in ITEMS[st["id"]].get("on_read", []):
            apply(self, e)
        x = self.player.add_xp("languages", 25)
        if x:
            self.log(x, "good")

    # ---- радио
    def open_radio(self):
        self.window = "radio"
        self.sound.play("radio")

    def radio_tune(self, d):
        self.radio_station = (self.radio_station + d) % len(RADIO["stations"])
        self.sound.play("radio")

    def radio_current(self):
        st = RADIO["stations"][self.radio_station]
        best = None
        for i, m in enumerate(st["messages"]):
            if m.get("front"):
                if self.clock.front_warning():
                    best = i
                    break
                continue
            if m.get("day", 1) <= self.clock.day:
                best = i
        if best is None:
            return st, [("...только шипение...", (150, 140, 118))]
        key = (self.radio_station, best)
        if key not in self._radio_cache:
            m = st["messages"][best]
            self._radio_cache[key] = parse_markup(m["text"], self.glossary, self.on_new_word)
            heard = f"{key[0]}:{key[1]}"
            if heard not in self.radio_heard:
                self.radio_heard.add(heard)
                for e in m.get("do", []):
                    apply(self, e)
        return st, self._radio_cache[key]

    # ---- диалоги и торговля
    def start_dialog(self, npc):
        self.dialog_npc = npc
        self.dialog = Dialogue(self, npc)
        self.window = "dialogue"

    def choose_dialog(self, i):
        if not self.dialog:
            return
        self.dialog.choose(i)
        if self.pending_trade:
            self.pending_trade = False
            npc = self.dialog.npc
            self.dialog = None
            self.trade = {"npc": npc, "give": {}, "take": {}, "give_ref": {}}
            self.window = "trade"
            return
        if self.dialog.finished:
            self.dialog = None
            self.dialog_npc = None
            self.window = None
            if self.pending_chapter:
                self.pending_chapter = False
                self.window = "chapter"

    def on_new_word(self, key):
        self.log(f"Новое слово: {key} — {GLOSSARY[key]['ru']} (словарик — G)", "lang")
        x = self.player.add_xp("languages", 6)
        if x:
            self.log(x, "good")

    def advance_quest(self, q, n):
        cur = self.quests.get(q, 0)
        if n <= cur:
            return
        self.quests[q] = n
        if n >= QUESTS[q]["final"]:
            self.log(f"Задание выполнено: {QUESTS[q]['name']}", "quest")
        else:
            self.log(f"Журнал обновлён: {QUESTS[q]['name']} (J)", "quest")

    def quests_done(self):
        return sum(1 for q, s in self.quests.items() if s >= QUESTS[q]["final"])

    # ================================================================ сообщения и эффекты
    def log(self, text, kind="info"):
        self.messages.append({"text": text, "kind": kind, "t": 9.0})
        self.messages = self.messages[-40:]

    def log_near(self, x, y, text, kind="info"):
        if math.hypot(x - self.player.x, y - self.player.y) < 15:
            self.log(text, kind)

    def float_text(self, x, y, text, color):
        self.floats.append({"x": x, "y": y, "text": text, "color": color, "t": 1.5})

    def noise(self, x, y, radius, source=None):
        """Звук в мире: все враги в радиусе идут проверить (концепт 7.7)."""
        for e in self.enemies:
            if e is not source and math.hypot(e.x - x, e.y - y) <= radius:
                e.hear(x, y)

    # ================================================================ долгие действия
    def start_action(self, name, t, done, noise=0):
        p = self.player
        p.action = {"name": name, "time": t, "left": t, "done": done}
        if noise:
            self.noise(p.x, p.y, noise * p.noise_mult())

    def has_tool(self, tool):
        p = self.player
        for st in list(p.items) + [s for s in p.equip.values() if s]:
            if ITEMS[st["id"]].get("tool") == tool:
                return True
        return False

    def wear_tool(self, tool, amount):
        p = self.player
        if tool == "water_filter":
            if random.random() < 0.12:
                inv.remove(p.items, "water_filter", 1)
                self.log("Фильтр для воды забился и пришёл в негодность.", "bad")
            return
        for st in [p.equip["weapon"]] + list(p.items):
            if st and ITEMS[st["id"]].get("tool") == tool:
                self._damage_item(st, amount)
                return

    def _damage_item(self, st, amount):
        p = self.player
        st["dur"] = st.get("dur", 1) - amount
        if st["dur"] <= 0:
            self.log(f"{ITEMS[st['id']]['name']} сломался!", "bad")
            if p.equip["weapon"] is st:
                p.equip["weapon"] = None
            elif st in p.items:
                p.items.remove(st)

    def free_spot_in_front(self):
        p = self.player
        fx, fy = int(p.x + p.fx), int(p.y + p.fy)
        cands = [(fx, fy)] + [(int(p.x) + dx, int(p.y) + dy) for dx, dy in physics.NEIGHBORS]
        for x, y in cands:
            if (x, y) == (int(p.x), int(p.y)):
                continue
            if self.zone.inside(x, y) and self.zone.get(x, y) is None and not self.zone.solid(x, y):
                return x, y
        return None

    def entity_on_tile(self, x, y):
        for e in [self.player] + self.enemies + self.visible_npcs():
            if int(e.x) == x and int(e.y) == y:
                return True
        return False

    def toggle_flashlight(self):
        p = self.player
        if not p.equip["light"]:
            st = inv.find(p.items, "flashlight")
            if not st:
                self.log("У тебя нет фонарика.", "info")
                return
            actions.equip(self, st)
        if p.equip["light"].get("battery", 0) <= 0:
            self.log("Батарейки сели.", "bad")
            p.flashlight_on = False
            return
        p.flashlight_on = not p.flashlight_on
        self.sound.play("pickup")

    # ================================================================ сон и зоны
    def try_sleep(self, bed):
        p = self.player
        if any(e.state == "chase" or math.hypot(e.x - p.x, e.y - p.y) < 9 for e in self.enemies):
            self.log("Нельзя спать — рядом опасность.", "bad")
            return
        if p.fatigue < 25:
            self.log("Спать не хочется.", "info")
            return
        self.save_game(auto=True)
        p.sleeping = True
        p.sleep_bed = bed
        p.sneaking = False
        self.log("Ты засыпаешь..." + ("" if bed else " (на голой земле сон хуже)"), "info")

    def wake(self, reason=None):
        p = self.player
        p.sleeping = False
        self.log(reason or "Ты проснулся.", "bad" if reason else "info")

    def use_hatch(self):
        if "bunker_code" in self.flags or "bunker_open" in self.flags:
            self.log("Код 4-7-1. Замок щёлкает, люк поддаётся.", "info")
            self.change_zone("bunker", self.zones["bunker"].markers["arrive"])
            return
        if self.has_tool("pry"):
            def done():
                self.flags.add("bunker_open")
                self.log("Люк взломан!", "good")
            self.log("Ломаешь люк монтировкой — шум на всю степь...", "bad")
            self.start_action("Взламываю люк", 10, done, noise=18)
            return
        self.log("Кодовый замок на три цифры. Нужен код — или монтировка.", "info")

    def change_zone(self, zid, pos, offset=(0.5, 0.5)):
        p = self.player
        self.zone = self.zones[zid]
        p.x, p.y = pos[0] + offset[0], pos[1] + offset[1]
        if self.zone.solid(int(p.x), int(p.y)):
            p.x, p.y = pos[0] + 0.5, pos[1] + 1.5
        self.cam.snap(p.x, p.y)
        self.container_key = None
        self.log(f"Ты в зоне: {self.zone.name}.", "info")
        if zid == "bunker" and "bunker_visited" not in self.flags:
            self.flags.add("bunker_visited")
            self.log("Тьма и запах хлорки. Включи фонарик [F], если он есть.", "bad")
            self.advance_quest("bunker", 1)

    # ================================================================ взаимодействие
    def _find_target(self):
        """Что игрок может «использовать» сейчас: жителя рядом или объект под курсором/рядом."""
        p = self.player
        for n in self.visible_npcs():
            if math.hypot(n.x - p.x, n.y - p.y) < 1.8:
                return ("npc", n)
        cands = []
        if self.hover_tile:
            cands.append(self.hover_tile)
        fx, fy = int(p.x + p.fx * 0.9), int(p.y + p.fy * 0.9)
        cands.append((fx, fy))
        for dx, dy in physics.NEIGHBORS + [(0, 0)]:
            cands.append((int(p.x) + dx, int(p.y) + dy))
        for x, y in cands:
            o = self.zone.get(x, y)
            if o is None:
                continue
            info = OBJECTS.get(o, {})
            if not any(k in info for k in INTERACTIVE):
                continue
            if math.hypot(x + 0.5 - p.x, y + 0.5 - p.y) <= 1.75:
                return ("obj", x, y)
        return None

    def _hint_for(self, target):
        if target is None:
            return ""
        if target[0] == "npc":
            return f"[E] Говорить: {target[1].name}"
        _, x, y = target
        o = self.zone.get(x, y)
        info = OBJECTS.get(o, {})
        name = info.get("name", "")
        key = f"{x},{y}"
        if info.get("door"):
            return "[E] Открыть дверь" if info.get("solid") else "[E] Закрыть дверь"
        if info.get("window"):
            if o == "window_boarded":
                return "Заколоченное окно"
            return "[E] Пролезть в окно   [B] Заколотить"
        if key in self.zone.containers:
            c = self.zone.containers[key]
            return f"[E] {'Обыскать' if c['items'] is None else 'Открыть'}: {name}"
        if "water" in info:
            return "[E] Набрать воды" if inv.count(self.player.items, "bottle_empty") else "[E] Напиться (вода грязная!)"
        if info.get("chop"):
            return "[E] Нарубить хвороста" + ("" if self.has_tool("chop") else " (нужен топор)")
        if "pick" in info:
            return "[E] Собрать колючку"
        if info.get("bed"):
            return "[E] Спать"
        if info.get("fire"):
            return "[E] Подбросить топлива / готовить" if self.zone.fires.get(key, 0) > 0 else "[E] Разжечь (хворост + спички)"
        if info.get("workbench"):
            return "[E] Верстак: крафт"
        if info.get("collector"):
            return f"[E] Набрать дождевой воды ({self.zone.collectors.get(key, 0):.1f} л)"
        if info.get("hatch"):
            return "[E] Открыть люк"
        if info.get("ladder"):
            return "[E] Подняться наверх"
        if info.get("alarm"):
            return "[E] Снять сигнализацию"
        return name

    def do_interact(self):
        p = self.player
        if p.action or p.sleeping:
            return
        t = self.target
        if t is None:
            return
        if t[0] == "npc":
            self.start_dialog(t[1])
        else:
            actions.interact(self, t[1], t[2])

    # ================================================================ бой
    def _attack(self):
        p = self.player
        st, it = p.weapon()
        if it and it["type"] == "gun":
            if st.get("loaded", 0) <= 0:
                self.log("Щёлк. Пусто. [R] — перезарядить.", "bad")
                p.attack_cd = 0.5
                return
            st["loaded"] -= 1
            p.attack_cd = it["cd"]
            p.attack_anim = 0.6
            self.sound.play("shot")
            self.noise(p.x, p.y, it["noise"])
            spread = (0.12 if it.get("pellets") else 0.04) * max(0.3, 1 - 0.08 * p.lvl("aim"))
            hit_any = False
            for _ in range(it.get("pellets", 1)):
                ang = math.atan2(p.fy, p.fx) + random.uniform(-spread, spread)
                hit_any |= self._shoot_ray(p.x, p.y, math.cos(ang), math.sin(ang), it["range"], it["dmg"] * (1 + 0.05 * p.lvl("aim")))
            x = p.add_xp("aim", 8 if hit_any else 3)
            if x:
                self.log(x, "good")
            self._damage_item(st, 1)
            return
        dmg = (it["dmg"] if it else 4) * p.melee_mult()
        reach = it["range"] if it else 0.9
        p.attack_cd = it["cd"] if it else 0.6
        p.attack_anim = 1.0
        p.fatigue = min(100, p.fatigue + 0.25)
        self.sound.play("swing")
        self.noise(p.x, p.y, (it["noise"] if it else 2) * p.noise_mult())
        best = None
        for e in self.enemies:
            dx, dy = e.x - p.x, e.y - p.y
            d = math.hypot(dx, dy)
            if d > reach + 0.35 or d < 0.01:
                continue
            cosang = (dx * p.fx + dy * p.fy) / d
            if cosang < 0.35:
                continue
            if best is None or d < best[0]:
                best = (d, e)
        if best:
            e = best[1]
            # удар со спины по ничего не подозревающему врагу — втрое сильнее (скрытность)
            if p.sneaking and e.state != "chase":
                dmg *= 3
                self.float_text(e.x, e.y, "скрытный удар!", (240, 220, 120))
            self._hit_enemy(e, dmg, p.fx, p.fy)
            x = p.add_xp("melee", 5)
            if x:
                self.log(x, "good")
            if st:
                self._damage_item(st, 1)

    def _shoot_ray(self, x, y, dx, dy, rng, dmg):
        steps = int(rng / 0.2)
        ex, ey = x, y
        for i in range(1, steps + 1):
            ex, ey = x + dx * i * 0.2, y + dy * i * 0.2
            tx, ty = int(ex), int(ey)
            if self.zone.solid(tx, ty) and self.zone.blocks_sight(tx, ty):
                break
            for e in self.enemies:
                if math.hypot(e.x - ex, e.y - ey) < 0.45:
                    self._hit_enemy(e, dmg, dx, dy)
                    self.effects.append({"type": "tracer", "x0": x, "y0": y, "x1": ex, "y1": ey, "t": 0.08})
                    return True
        self.effects.append({"type": "tracer", "x0": x, "y0": y, "x1": ex, "y1": ey, "t": 0.08})
        return False

    def _hit_enemy(self, e, dmg, dx, dy):
        e.hp -= dmg
        e.hit_flash = 0.15
        e.state = "chase"
        physics.move(e, dx * 0.15, dy * 0.15, 0.28, e.solid_fn(self.zone))
        self.effects.append({"type": "blood", "x": e.x, "y": e.y, "t": 0.5})
        self.sound.play("hit")
        if e.hp <= 0:
            self._kill(e)

    def _kill(self, e):
        self.enemies.remove(e)
        self.player.kills += 1
        tx, ty = int(e.x), int(e.y)
        if self.zone.get(tx, ty) is None and not self.zone.solid(tx, ty):
            self.zone.set(tx, ty, "corpse")
            self.zone.containers[f"{tx},{ty}"] = {"kind": e.t["loot"], "items": None}
        self.float_text(e.x, e.y, e.t["name"] + " повержен", (220, 200, 160))

    def enemy_hits_player(self, e):
        p = self.player
        p.hurt(e.t["dmg"], e.t["hurt"], self.log)
        self.last_hurt = (e.t["name"], self.time_real)
        self.sound.play("hurt")
        self.effects.append({"type": "blood", "x": p.x, "y": p.y, "t": 0.5})
        if p.sleeping:
            self.wake("На тебя напали во сне!")

    def enemy_shoot(self, e, gun):
        p = self.player
        self.sound.play("shot")
        self.noise(e.x, e.y, 16, source=e)
        acc = gun["acc"] * (0.6 if p.sneaking else 1.0) * (1 - 0.4 * self.darkness())
        hit = random.random() < acc
        tx, ty = (p.x, p.y) if hit else (p.x + random.uniform(-1.5, 1.5), p.y + random.uniform(-1.5, 1.5))
        self.effects.append({"type": "tracer", "x0": e.x, "y0": e.y, "x1": tx, "y1": ty, "t": 0.08})
        if hit:
            p.hurt(gun["dmg"], "bullet", self.log)
            self.last_hurt = (e.t["name"], self.time_real)
            self.sound.play("hurt")

    def on_spotted(self, e):
        if e.kind == "dog":
            self.sound.play("dog")
        if self.spot_cd <= 0:
            self.spot_cd = 8
            self.log(f"Тебя заметили: {e.t['name']}!", "bad")

    # ================================================================ обновление
    def update(self, dt):
        p = self.player
        self._update_timers(dt)
        if self.window in PAUSING_WINDOWS:
            return

        mins = dt * GAME_MIN_PER_SEC * (60 if p.sleeping else 1)
        mx, my = self.ui.mouse
        mtx, mty = to_tile(mx, my, self.cam)
        self.hover_tile = (int(mtx), int(mty)) if not self.window else None

        # --- движение (WASD относительно экрана)
        keys = pygame.key.get_pressed()
        sx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        sy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
        p.moving = False
        p.running = False
        if (sx or sy) and not p.sleeping:
            if p.action:
                self.log("Действие прервано.", "info")
                p.action = None
            dx, dy = screen_dir_to_tile(sx, sy)
            d = math.hypot(dx, dy)
            dx, dy = dx / d, dy / d
            p.running = (keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]) and p.fatigue < 92 and not p.sneaking
            speed = (4.2 if p.running else (1.5 if p.sneaking else 2.6)) * p.speed_mult()
            ox, oy = p.x, p.y
            physics.move(p, dx * speed * dt, dy * speed * dt, 0.3, self.zone.solid)
            moved = math.hypot(p.x - ox, p.y - oy)
            if moved > 0:
                p.moving = True
                p.walk_phase += moved * 9
                self.step_acc += moved
                if self.step_acc > 0.6:
                    self.step_acc = 0
                    self.noise(p.x, p.y, (2.5 if not p.running else 6) * p.noise_mult())
                    if p.running:
                        self.sound.play("step", 0.6)

        # --- взгляд на курсор
        if not p.sleeping:
            vx, vy = mtx - p.x, mty - p.y
            dd = math.hypot(vx, vy)
            if dd > 0.05:
                p.fx, p.fy = vx / dd, vy / dd
                p.face_right = (vx - vy) > 0

        # --- долгое действие
        if p.action:
            p.action["left"] -= dt
            if p.action["left"] <= 0:
                done = p.action["done"]
                p.action = None
                done()

        # --- атака
        p.attack_cd = max(0, p.attack_cd - dt)
        p.attack_anim = max(0, p.attack_anim - dt * 3)
        p.hit_flash = max(0, p.hit_flash - dt)
        if self.world_click and p.attack_cd <= 0 and not p.action and not p.sleeping:
            self._attack()
        self.world_click = False

        # --- потребности и окружение
        indoor = self.zone.indoor(int(p.x), int(p.y))
        near_fire = self._near_fire(p.x, p.y)
        env = {"air_temp": self.clock.air_temp() if not self.zone.dark else 14,
               "hot": self.clock.air_temp() > 30 and self.darkness() < 0.3 and not self.zone.dark,
               "indoor": indoor, "near_fire": near_fire,
               "dust": self.clock.dust_exposure(indoor), "bed": getattr(p, "sleep_bed", False)}
        p.update_needs(mins, env, self.log)
        if p.has_light():
            p.equip["light"]["battery"] -= mins
            if p.equip["light"]["battery"] <= 0:
                p.flashlight_on = False
                self.log("Фонарик погас — сели батарейки.", "bad")
        for z in self.zones.values():
            for key in list(z.fires):
                if z.fires[key] < 10 ** 8:
                    z.fires[key] -= mins
                    if z.fires[key] <= 0:
                        z.fires[key] = 0
            if self.clock.weather == "rain":
                for key in z.collectors:
                    z.collectors[key] = min(10, z.collectors[key] + 0.02 * mins)

        for ev in self.clock.update(mins, self.log):
            if ev == "night":
                ai.spawn_wanderers(self, min(8, 2 + self.clock.day // 2))
                if len(self.enemies_by_zone["sarykuduk"]) > 70:
                    del self.enemies_by_zone["sarykuduk"][:-70]
            elif ev == "new_hour" and not p.sleeping and random.random() < 0.06:
                self.sound.play_music()

        # --- сон
        if p.sleeping:
            danger = next((e for e in self.enemies if math.hypot(e.x - p.x, e.y - p.y) < 7 and e.state in ("chase", "investigate")), None)
            if danger:
                self.wake(f"Тебя разбудил шум! Рядом {danger.t['name']}.")
            elif p.fatigue <= 0 or (p.fatigue < 30 and 6 <= self.clock.hour < 9):
                self.wake()

        # --- враги и жители
        near = [e for e in self.enemies if abs(e.x - p.x) + abs(e.y - p.y) < 45]
        for e in near:
            e.update(dt, self)
        for i, a in enumerate(near):
            for b in near[i + 1:]:
                dx, dy = b.x - a.x, b.y - a.y
                d = math.hypot(dx, dy)
                if 0.001 < d < 0.5:
                    push = (0.5 - d) / 2
                    physics.move(a, -dx / d * push, -dy / d * push, 0.28, a.solid_fn(self.zone))
                    physics.move(b, dx / d * push, dy / d * push, 0.28, b.solid_fn(self.zone))
            key = f"{int(a.x)},{int(a.y)}"
            if self.zone.get(int(a.x), int(a.y)) == "can_alarm" and self.alarm_cd.get(key, 0) <= self.time_real:
                self.alarm_cd[key] = self.time_real + 5
                self.sound.play("alarm")
                self.log_near(a.x, a.y, "Звенят банки — кто-то задел сигнализацию!", "bad")
                if p.sleeping:
                    self.wake("Звон банок! Кто-то рядом.")
        for n in self.npcs:
            n.update(dt, self)

        # --- подсказка и камера
        self.target = self._find_target() if not p.action else None
        self.hint = self._hint_for(self.target)
        self.cam.follow(p.x, p.y, dt)
        outdoor = not indoor
        self.sound.ambient(outdoor, self.clock.weather == "storm" or self.clock.front)

        if p.dead():
            self._die()

    def _update_timers(self, dt):
        self.spot_cd = max(0, self.spot_cd - dt)
        for m in self.messages:
            m["t"] -= dt
        for f in self.floats:
            f["t"] -= dt
        self.floats = [f for f in self.floats if f["t"] > 0]
        for fx in self.effects:
            fx["t"] -= dt
        self.effects = [fx for fx in self.effects if fx["t"] > 0]

    def _near_fire(self, x, y):
        for key, fuel in self.zone.fires.items():
            if fuel > 0:
                fx, fy = map(int, key.split(","))
                if math.hypot(fx + 0.5 - x, fy + 0.5 - y) < 3:
                    return True
        return False

    def _die(self):
        p = self.player
        if p.disease >= 100:
            cause = "Причина: пыльная болезнь."
        elif p.thirst >= 90:
            cause = "Причина: обезвоживание."
        elif p.hunger >= 90:
            cause = "Причина: истощение."
        elif self.time_real - self.last_hurt[1] < 5:
            cause = f"Убит: {self.last_hurt[0]}."
        elif p.bleeding():
            cause = "Причина: потеря крови."
        else:
            cause = "Тело не выдержало."
        self.death_cause = cause
        self.state = "dead"
        self.window = None
        if p.mode == "hard":
            save.delete()

    # ================================================================ отрисовка
    def draw_play(self):
        render.draw_world(self.screen, self)
        p = self.player
        if p.sleeping:
            s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            s.fill((0, 0, 0, 170))
            self.screen.blit(s, (0, 0))
            self.ui.text(self.screen, "Сон... (" + self.clock.clock_text() + ")", (SCREEN_W // 2, SCREEN_H // 2 - 20), (220, 210, 180), 26, center=True)
        if self.state == "dead":
            uimod.draw_death(self.screen, self.ui, self)
            return
        uimod.draw_hud(self.screen, self.ui, self)
        w = self.window
        draw = {"inventory": uimod.draw_inventory, "craft": uimod.draw_crafting, "health": uimod.draw_health,
                "journal": uimod.draw_journal, "glossary": uimod.draw_glossary, "dialogue": uimod.draw_dialogue,
                "trade": uimod.draw_trade, "note": uimod.draw_note, "radio": uimod.draw_radio, "help": uimod.draw_help,
                "pause": uimod.draw_pause, "chapter": uimod.draw_chapter}.get(w)
        if draw:
            if w == "dialogue" and not self.dialog:
                self.window = None
            elif w == "trade" and not self.trade:
                self.window = None
            elif w == "note" and not self.note_stack:
                self.window = None
            else:
                draw(self.screen, self.ui, self)
        # клик, который не поймал интерфейс, — это удар в мире
        if self.ui.click and not self.window:
            self.world_click = True
        if self.ui.rclick and not self.window and self.target:
            self.do_interact()

    # ================================================================ сохранение
    def save_game(self, auto=False):
        try:
            save.save(self)
            self.log("Автосохранение." if auto else "Игра сохранена.", "good")
        except OSError as ex:
            self.log(f"Не удалось сохранить: {ex}", "bad")
        if not auto:
            self.close_window()

    def load_game(self):
        try:
            data = save.load()
        except (OSError, ValueError) as ex:
            self.log(f"Не удалось загрузить: {ex}", "bad")
            return
        self._reset_world()
        for zid, zd in data["zones"].items():
            self.zones[zid].load_dict(zd)
        self.zone = self.zones[data["zone"]]
        self.player = Player()
        self.player.load_dict(data["player"])
        self.clock.load_dict(data["clock"])
        self.enemies_by_zone = {zid: [ai.Enemy.from_dict(d) for d in lst] for zid, lst in data["enemies"].items()}
        for n, nd in zip(self.npcs, data["npcs"]):
            n.x, n.y, n.stock = nd["x"], nd["y"], nd["stock"]
        self.quests = data["quests"]
        self.flags = set(data["flags"])
        self.rep = data["rep"]
        self.glossary = set(data["glossary"])
        self.radio_heard = set(data["radio_heard"])
        self.cam.snap(self.player.x, self.player.y)
        self.state = "play"
        self.window = None
        self.log("Игра загружена.", "good")
