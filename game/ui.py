"""Интерфейс в ретро-стиле советской техники: панели, стрелочные индикаторы, окна.

Используется подход «immediate mode GUI»: каждый кадр окна рисуются заново,
а функция button() сразу возвращает True, если по кнопке кликнули в этом кадре.
Так не нужно хранить дерево виджетов — код окна читается сверху вниз.
"""
import math

import pygame

from .config import (SCREEN_W, SCREEN_H, COL_PANEL, COL_PANEL_DARK, COL_PANEL_EDGE, COL_TEXT,
                     COL_TEXT_DIM, COL_ACCENT, COL_RED, COL_GREEN, COL_TURQ, COL_BAD, TITLE, VERSION)
from .data import ITEMS, RECIPES, SKILLS, TRAITS, QUESTS, GLOSSARY, CHARACTER, OBJECTS
from .localization import parse_markup
from . import inventory as inv
from . import crafting, actions, save

MSG_COLORS = {"info": COL_TEXT, "good": COL_GREEN, "bad": COL_BAD, "lang": COL_TURQ, "quest": COL_ACCENT}


class UI:
    def __init__(self):
        self._fonts = {}
        self.mouse = (0, 0)
        self.click = None
        self.rclick = None
        self.wheel = 0
        self.scroll = {}
        self.tab = 0
        self.text_input = ""

    # ------------------------------------------------------------ базовые элементы
    def font(self, size, bold=False):
        key = (size, bold)
        if key not in self._fonts:
            try:
                # шрифт берётся из системы игрока (Windows: Segoe UI / Arial — поддерживают
                # казахские буквы ә, ғ, қ, ң, ө, ұ, ү, һ, і). В игру шрифты не вшиваются.
                f = pygame.font.SysFont("segoeui,arial,dejavusans,liberationsans", size, bold=bold)
            except Exception:
                f = pygame.font.Font(None, size + 4)
            self._fonts[key] = f
        return self._fonts[key]

    def begin(self, events):
        self.mouse = pygame.mouse.get_pos()
        self.click = None
        self.rclick = None
        self.wheel = 0
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN:
                if e.button == 1:
                    self.click = e.pos
                elif e.button == 3:
                    self.rclick = e.pos
            elif e.type == pygame.MOUSEWHEEL:
                self.wheel = e.y

    def consume(self):
        self.click = None
        self.rclick = None

    def hovered(self, rect):
        return pygame.Rect(rect).collidepoint(self.mouse)

    def clicked(self, rect):
        if self.click and pygame.Rect(rect).collidepoint(self.click):
            self.click = None
            return True
        return False

    def rclicked(self, rect):
        if self.rclick and pygame.Rect(rect).collidepoint(self.rclick):
            self.rclick = None
            return True
        return False

    def text(self, surf, s, pos, color=COL_TEXT, size=16, bold=False, center=False, right=False):
        img = self.font(size, bold).render(str(s), True, color)
        x, y = pos
        if center:
            x -= img.get_width() // 2
        elif right:
            x -= img.get_width()
        surf.blit(img, (x, y))
        return img.get_width()

    def panel(self, surf, rect, title=None):
        r = pygame.Rect(rect)
        pygame.draw.rect(surf, COL_PANEL, r)
        pygame.draw.rect(surf, COL_PANEL_EDGE, r, 2)
        pygame.draw.rect(surf, COL_PANEL_DARK, r.inflate(-8, -8), 1)
        # заклёпки по углам — «металлическая панель»
        for cx, cy in ((r.left + 7, r.top + 7), (r.right - 8, r.top + 7), (r.left + 7, r.bottom - 8), (r.right - 8, r.bottom - 8)):
            pygame.draw.circle(surf, (140, 126, 92), (cx, cy), 2)
        if title:
            pygame.draw.rect(surf, COL_PANEL_DARK, (r.x + 12, r.y + 8, r.w - 24, 26))
            self.text(surf, title, (r.x + 22, r.y + 10), COL_ACCENT, 17, bold=True)
        return r

    def button(self, surf, rect, label, enabled=True, active=False, size=15):
        r = pygame.Rect(rect)
        hov = enabled and self.hovered(r)
        base = (78, 70, 52) if enabled else (52, 48, 40)
        if active:
            base = (120, 96, 50)
        if hov:
            base = (110, 96, 64)
        pygame.draw.rect(surf, base, r)
        pygame.draw.rect(surf, COL_PANEL_EDGE if enabled else (80, 74, 60), r, 1)
        self.text(surf, label, (r.centerx, r.centery - size // 2 - 2), COL_TEXT if enabled else COL_TEXT_DIM, size, center=True)
        return enabled and self.clicked(r)

    def wrap(self, segments, width, size=16):
        """Перенос по словам для «цветного» текста [(строка, цвет)]. Возвращает строки-списки."""
        f = self.font(size)
        lines = [[]]
        line_w = 0
        space = f.size(" ")[0]
        for text, col in segments:
            for k, para in enumerate(text.split("\n")):
                if k > 0:
                    lines.append([])
                    line_w = 0
                for word in para.split(" "):
                    if word == "":
                        continue
                    w = f.size(word)[0]
                    if line_w + w > width and lines[-1]:
                        lines.append([])
                        line_w = 0
                    lines[-1].append((word, col))
                    line_w += w + space
        return lines

    def rich(self, surf, segments, x, y, width, size=16, line_h=None):
        """Нарисовать цветной текст с переносами. Возвращает высоту."""
        line_h = line_h or size + 6
        f = self.font(size)
        space = f.size(" ")[0]
        lines = self.wrap(segments, width, size)
        for i, line in enumerate(lines):
            cx = x
            for word, col in line:
                img = f.render(word, True, col)
                surf.blit(img, (cx, y + i * line_h))
                cx += img.get_width() + space
        return len(lines) * line_h

    def bar(self, surf, rect, frac, col, back=(30, 26, 20)):
        r = pygame.Rect(rect)
        pygame.draw.rect(surf, back, r)
        pygame.draw.rect(surf, col, (r.x, r.y, int(r.w * max(0, min(1, frac))), r.h))
        pygame.draw.rect(surf, COL_PANEL_EDGE, r, 1)

    def gauge(self, surf, cx, cy, r, frac, label, value_text, danger_high=True):
        """Стрелочный индикатор как на советском приборе: шкала-полукруг, стрелка, красная зона."""
        pygame.draw.circle(surf, (24, 22, 18), (cx, cy), r + 3)
        pygame.draw.circle(surf, (218, 208, 180), (cx, cy), r)
        pygame.draw.circle(surf, (120, 108, 80), (cx, cy), r, 2)
        a0, a1 = math.radians(210), math.radians(-30)    # шкала от 210° до -30°
        # цветные зоны шкалы
        for i in range(40):
            t = i / 40
            ang = a0 + (a1 - a0) * t
            danger = t > 0.7 if danger_high else t < 0.3
            warn = (0.5 < t <= 0.7) if danger_high else (0.3 <= t < 0.5)
            col = (190, 50, 40) if danger else ((210, 160, 50) if warn else (90, 110, 80))
            x0, y0 = cx + math.cos(ang) * (r - 3), cy - math.sin(ang) * (r - 3)
            x1, y1 = cx + math.cos(ang) * (r - 9), cy - math.sin(ang) * (r - 9)
            pygame.draw.line(surf, col, (x0, y0), (x1, y1), 3)
        for i in range(6):
            ang = a0 + (a1 - a0) * i / 5
            pygame.draw.line(surf, (40, 36, 30), (cx + math.cos(ang) * (r - 9), cy - math.sin(ang) * (r - 9)),
                             (cx + math.cos(ang) * (r - 14), cy - math.sin(ang) * (r - 14)), 1)
        ang = a0 + (a1 - a0) * max(0, min(1, frac))
        pygame.draw.line(surf, (160, 30, 20), (cx, cy), (cx + math.cos(ang) * (r - 6), cy - math.sin(ang) * (r - 6)), 2)
        pygame.draw.circle(surf, (40, 36, 30), (cx, cy), 4)
        self.text(surf, value_text, (cx, cy + 8), (40, 36, 30), 12, bold=True, center=True)
        self.text(surf, label, (cx, cy + r + 4), COL_TEXT, 13, center=True)

    def scroll_list(self, surf, key, rect, rows, row_h=24):
        """Прокручиваемый список. rows — [(текст, цвет)]. Возвращает (индекс клика ЛКМ, индекс клика ПКМ, индекс под мышью)."""
        r = pygame.Rect(rect)
        pygame.draw.rect(surf, COL_PANEL_DARK, r)
        pygame.draw.rect(surf, (80, 72, 54), r, 1)
        visible = r.h // row_h
        off = self.scroll.get(key, 0)
        if self.hovered(r) and self.wheel:
            off -= self.wheel
        off = max(0, min(off, max(0, len(rows) - visible)))
        self.scroll[key] = off
        hit = rhit = hov = None
        clip = surf.get_clip()
        surf.set_clip(r)
        for i in range(off, min(len(rows), off + visible)):
            y = r.y + (i - off) * row_h
            rr = pygame.Rect(r.x + 2, y + 1, r.w - 4, row_h - 2)
            text, col, sel = rows[i] if len(rows[i]) == 3 else (*rows[i], False)
            if sel:
                pygame.draw.rect(surf, (96, 80, 48), rr)
            elif self.hovered(rr):
                pygame.draw.rect(surf, (64, 58, 44), rr)
                hov = i
            self.text(surf, text, (rr.x + 6, rr.y + 2), col, 15)
            if self.clicked(rr):
                hit = i
            if self.rclicked(rr):
                rhit = i
        surf.set_clip(clip)
        if len(rows) > visible:
            frac = off / max(1, len(rows) - visible)
            pygame.draw.rect(surf, (120, 106, 76), (r.right - 5, r.y + int((r.h - 30) * frac), 4, 30))
        return hit, rhit, hov


# ====================================================================== HUD

def draw_hud(screen, ui, game):
    p = game.player
    clock = game.clock
    # --- приборная панель внизу слева
    ui.panel(screen, (0, SCREEN_H - 112, 560, 112))
    gauges = [
        ("Здоровье", p.health / 100, f"{int(p.health)}", False),
        ("Голод", p.hunger / 100, f"{int(p.hunger)}", True),
        ("Жажда", p.thirst / 100, f"{int(p.thirst)}", True),
        ("Усталость", p.fatigue / 100, f"{int(p.fatigue)}", True),
        ("Темп. тела", (p.temp - 33) / 8, f"{p.temp:.1f}°", None),
        ("Болезнь", p.disease / 100, f"{int(p.disease)}", True),
        ("Настроение", p.mood / 100, f"{int(p.mood)}", False),
    ]
    for i, (lab, frac, val, high) in enumerate(gauges):
        cx = 42 + i * 79
        if high is None:   # температура: опасны оба края
            ui.gauge(screen, cx, SCREEN_H - 66, 30, frac, lab, val, danger_high=True)
        else:
            ui.gauge(screen, cx, SCREEN_H - 66, 30, frac, lab, val, danger_high=high)

    # --- состояния («муды»)
    over = p.weight() > p.carry_limit()
    x, y = 572, SCREEN_H - 108
    for name, lvl in p.moodles(over)[:10]:
        col = {1: (200, 170, 80), 2: (220, 120, 50), 3: (220, 60, 45)}[lvl]
        w = ui.font(14).size(name)[0] + 14
        if x + w > 900:
            x = 572
            y += 24
        pygame.draw.rect(screen, (30, 26, 20), (x, y, w, 21))
        pygame.draw.rect(screen, col, (x, y, w, 21), 1)
        ui.text(screen, name, (x + 7, y + 2), col, 14)
        x += w + 5

    # --- часы и погода сверху слева
    ui.panel(screen, (0, 0, 330, 66))
    ui.text(screen, clock.clock_text(), (14, 8), COL_ACCENT, 18, bold=True)
    wtxt = {"clear": "Ясно", "storm": "Пыльная буря", "rain": "Ливень"}[clock.weather]
    if game.zone.dark:
        wtxt = "Под землёй"
    air = 14 if game.zone.dark else int(clock.air_temp())
    ui.text(screen, f"{game.zone.name} · {wtxt} · {air}°C", (14, 34), COL_TEXT, 14)
    if clock.front:
        if int(game.time_real * 2) % 2:
            ui.text(screen, "ПЫЛЬНЫЙ ФРОНТ!", (SCREEN_W // 2, 12), COL_RED, 24, bold=True, center=True)

    # --- оружие и режимы сверху справа
    ui.panel(screen, (SCREEN_W - 300, 0, 300, 66))
    st, it = p.weapon()
    wname = inv.label(st) if st else "Голые руки"
    ui.text(screen, wname, (SCREEN_W - 286, 8), COL_TEXT, 15)
    modes = []
    if p.sneaking:
        modes.append("крадусь")
    if p.running:
        modes.append("бег")
    if p.equip["light"]:
        modes.append("фонарь: " + ("вкл" if p.has_light() else "выкл"))
    if p.equip["face"]:
        modes.append("фильтр %d ч" % (p.equip["face"].get("filter", 0) // 60))
    ui.text(screen, " · ".join(modes) if modes else "Z — красться, Shift — бег", (SCREEN_W - 286, 34), COL_TEXT_DIM, 13)

    # --- журнал сообщений (на полупрозрачной подложке, чтобы читался поверх карты)
    recent = [m for m in game.messages[-7:] if m["t"] > 0]
    if recent:
        back = pygame.Surface((560, 20 * len(recent) + 8), pygame.SRCALPHA)
        back.fill((14, 12, 10, 150))
        screen.blit(back, (4, SCREEN_H - 116 - 20 * len(recent)))
    y = SCREEN_H - 132
    for m in reversed(recent):
        alpha = max(0, min(1, m["t"] / 2))
        col = MSG_COLORS.get(m["kind"], COL_TEXT)
        col = tuple(int(c * (0.35 + 0.65 * alpha)) for c in col)
        ui.text(screen, m["text"], (12, y), col, 15)
        y -= 20

    # --- подсказка взаимодействия и полоска долгого действия
    if p.action:
        a = p.action
        frac = 1 - a["left"] / a["time"]
        ui.text(screen, a["name"], (SCREEN_W // 2, SCREEN_H - 168), COL_TEXT, 16, center=True)
        ui.bar(screen, (SCREEN_W // 2 - 120, SCREEN_H - 146, 240, 12), frac, COL_ACCENT)
    elif game.hint and not game.window:
        img = ui.font(17).render(game.hint, True, (240, 220, 160))
        back = pygame.Surface((img.get_width() + 20, img.get_height() + 6), pygame.SRCALPHA)
        back.fill((14, 12, 10, 160))
        hx, hy = SCREEN_W // 2 - back.get_width() // 2, SCREEN_H // 2 + 70
        screen.blit(back, (hx, hy))
        screen.blit(img, (hx + 10, hy + 3))

    pygame.draw.rect(screen, COL_PANEL_DARK, (SCREEN_W - 560, SCREEN_H - 26, 560, 26))
    ui.text(screen, "I инвентарь · C крафт · H здоровье · J журнал · G словарик · Esc меню · F1 помощь",
            (SCREEN_W - 10, SCREEN_H - 22), COL_TEXT_DIM, 13, right=True)


# ====================================================================== окна

WIN = pygame.Rect(150, 60, 980, 560)


def _close_button(screen, ui, game, rect=WIN):
    if ui.button(screen, (rect.right - 40, rect.y + 8, 28, 26), "×", size=18):
        game.close_window()


def draw_inventory(screen, ui, game):
    p = game.player
    title = "Инвентарь"
    ui.panel(screen, WIN, title)
    _close_button(screen, ui, game)
    cont = game.container_items()
    items = sorted(p.items, key=inv.sort_key)

    # --- левая колонка: вещи игрока
    lx, ly = WIN.x + 16, WIN.y + 44
    ui.text(screen, f"Вес: {p.weight():.1f} / {p.carry_limit():.0f} кг", (lx, ly), COL_BAD if p.weight() > p.carry_limit() else COL_TEXT_DIM, 14)
    rows = [(inv.label(st), COL_TEXT, st is game.sel_item) for st in items]
    hit, rhit, _ = ui.scroll_list(screen, "inv", (lx, ly + 22, 320, 440), rows)
    if hit is not None:
        game.sel_item = items[hit]
        game.sel_from = "player"
    if rhit is not None:
        st = items[rhit]
        if cont is not None:
            actions.move_to_container(game, st, st["n"])
        else:
            actions.quick_use(game, st)

    # --- средняя колонка: контейнер или экипировка
    mx = lx + 336
    if cont is not None:
        ui.text(screen, game.container_title(), (mx, ly), COL_ACCENT, 15)
        citems = list(cont)
        rows = [(inv.label(st), COL_TEXT, st is game.sel_item) for st in citems]
        if not rows:
            rows = [("— пусто —", COL_TEXT_DIM)]
        hit, rhit, _ = ui.scroll_list(screen, "cont", (mx, ly + 22, 300, 400), rows)
        if citems and hit is not None:
            game.sel_item = citems[hit]
            game.sel_from = "container"
        if citems and rhit is not None:
            actions.take_from_container(game, citems[rhit], citems[rhit]["n"])
        if ui.button(screen, (mx, ly + 430, 300, 30), "Взять всё (ПКМ — взять один предмет)", enabled=bool(citems), size=14):
            actions.take_all(game)
    else:
        ui.text(screen, "Экипировка", (mx, ly), COL_ACCENT, 15)
        slots = [("weapon", "В руках"), ("body", "Одежда"), ("head", "Голова"), ("face", "Лицо"),
                 ("back", "Спина"), ("light", "Фонарь")]
        for i, (slot, name) in enumerate(slots):
            y = ly + 24 + i * 52
            pygame.draw.rect(screen, COL_PANEL_DARK, (mx, y, 300, 46))
            pygame.draw.rect(screen, (80, 72, 54), (mx, y, 300, 46), 1)
            ui.text(screen, name, (mx + 8, y + 4), COL_TEXT_DIM, 13)
            st = p.equip[slot]
            ui.text(screen, inv.label(st) if st else "—", (mx + 8, y + 22), COL_TEXT, 14)
            if st and ui.button(screen, (mx + 226, y + 10, 66, 26), "Снять", size=13):
                actions.unequip(game, slot)
        ui.text(screen, "ПКМ по предмету — быстрое действие", (mx, ly + 350), COL_TEXT_DIM, 13)

    # --- правая колонка: описание и действия
    rx = mx + 316
    st = game.sel_item
    if st is not None and (st in p.items or (cont is not None and st in cont)):
        it = ITEMS[st["id"]]
        ui.rich(screen, [(it["name"], COL_ACCENT)], rx, ly, 280, 17)
        h = ui.rich(screen, [(it.get("desc", ""), COL_TEXT)], rx, ly + 28, 280, 14)
        info = _item_stats(it)
        ui.rich(screen, [(info, COL_TEXT_DIM)], rx, ly + 34 + h, 280, 13)
        by = ly + 250
        for label, fn in actions.item_actions(game, st, game.sel_from):
            if ui.button(screen, (rx, by, 280, 30), label, size=14):
                fn()
            by += 36
    else:
        ui.rich(screen, [("Выбери предмет слева, чтобы увидеть описание и действия.", COL_TEXT_DIM)], rx, ly, 280, 14)


def _item_stats(it):
    t = it["type"]
    parts = [f"Вес: {it['w']} кг", f"Ценность: {it.get('value', 0)}"]
    if t in ("weapon", "gun"):
        parts.append(f"Урон: {it['dmg']}" + (f" ×{it['pellets']}" if "pellets" in it else ""))
    if t == "gun":
        parts.append(f"Магазин: {it['mag']}, патроны: {ITEMS[it['ammo']]['name']}")
    for k, name in (("hunger", "Голод"), ("thirst", "Жажда"), ("mood", "Настроение"), ("disease", "Болезнь")):
        if k in it:
            parts.append(f"{name} {it[k]:+d}")
    if "warmth" in it:
        parts.append(f"Тепло: {it['warmth']}")
    if "protect" in it:
        parts.append(f"Защита от укусов: {int(it['protect'] * 100)}%")
    if "capacity" in it:
        parts.append(f"Вместимость: +{it['capacity']} кг")
    return ". ".join(parts) + "."


def draw_crafting(screen, ui, game):
    p = game.player
    ui.panel(screen, WIN, "Крафт и ремесло")
    _close_button(screen, ui, game)
    stations = crafting.stations_near(game)
    lx, ly = WIN.x + 16, WIN.y + 44
    known = [r for r in RECIPES if r in p.known_recipes]
    if game.sel_recipe not in known and known:
        game.sel_recipe = known[0]
    rows = []
    for rid in known:
        ok = not crafting.missing(p, rid, stations)
        rows.append((RECIPES[rid]["name"], COL_GREEN if ok else COL_TEXT_DIM, rid == game.sel_recipe))
    st_text = "Рядом: " + (", ".join({"fire": "огонь", "workbench": "верстак"}[s] for s in stations) if stations else "нет станций")
    ui.text(screen, st_text, (lx, ly), COL_TEXT_DIM, 14)
    hit, _, _ = ui.scroll_list(screen, "craft", (lx, ly + 22, 360, 440), rows)
    if hit is not None:
        game.sel_recipe = known[hit]
    ui.text(screen, f"Известно рецептов: {len(known)} из {len(RECIPES)}. Новые — из книг и от жителей «Зари».",
            (lx, ly + 472), COL_TEXT_DIM, 13)
    rx = lx + 380
    rid = game.sel_recipe
    if rid in known:
        res, need = crafting.describe(rid)
        ui.text(screen, RECIPES[rid]["name"], (rx, ly), COL_ACCENT, 19, bold=True)
        ui.rich(screen, [("Результат: ", COL_TEXT_DIM), (res, COL_TEXT)], rx, ly + 36, 560, 15)
        ui.rich(screen, [("Нужно: ", COL_TEXT_DIM), (need, COL_TEXT)], rx, ly + 66, 560, 15)
        miss = crafting.missing(p, rid, stations)
        if miss:
            ui.rich(screen, [("Не хватает: ", COL_BAD), (", ".join(miss), COL_BAD)], rx, ly + 130, 560, 15)
        if ui.button(screen, (rx, ly + 200, 240, 36), "Создать", enabled=not miss and not p.action):
            if crafting.start(game, rid):
                game.close_window()


def draw_health(screen, ui, game):
    p = game.player
    ui.panel(screen, WIN, "Здоровье")
    _close_button(screen, ui, game)
    lx, ly = WIN.x + 20, WIN.y + 48
    stats = [("Здоровье", f"{p.health:.0f} / 100"), ("Температура тела", f"{p.temp:.1f} °C"),
             ("Пыльная болезнь", f"{p.disease:.0f} / 100"), ("Отравление", f"{p.poison:.0f}"),
             ("Боль", f"{p.pain:.0f}" + (" (анальгин)" if p.painkiller > 0 else ""))]
    for i, (a, b) in enumerate(stats):
        ui.text(screen, a, (lx, ly + i * 24), COL_TEXT_DIM, 15)
        ui.text(screen, b, (lx + 190, ly + i * 24), COL_TEXT, 15)
    by = ly + 140
    for label, med in (("Принять анальгин", "analgin"), ("Принять активированный уголь", "charcoal"), ("Ввести антидот «ПФ-2»", "antidote")):
        if inv.count(p.items, med) > 0:
            if ui.button(screen, (lx, by, 300, 30), label, size=14):
                actions.use_item(game, inv.find(p.items, med))
            by += 36
    ui.text(screen, "Пыльная болезнь: кашель (15) → лихорадка (40) → бред (70) → смерть (100).", (lx, WIN.bottom - 70), COL_TEXT_DIM, 13)
    ui.text(screen, "Защита — респиратор или противогаз, укрытие в помещении. Лечение — антидот, отвар колючки.", (lx, WIN.bottom - 50), COL_TEXT_DIM, 13)

    rx = lx + 360
    ui.text(screen, "Раны", (rx, ly), COL_ACCENT, 17, bold=True)
    if not p.wounds:
        ui.text(screen, "Ран нет.", (rx, ly + 30), COL_GREEN, 15)
    y = ly + 30
    for w in list(p.wounds):
        status = []
        if w["bleeding"]:
            status.append("кровоточит")
        if w.get("bandaged"):
            status.append("перевязана" + (" (грязно)" if w.get("dirty") else ""))
        if w.get("disinfected"):
            status.append("обработана")
        if w.get("inflamed"):
            status.append("ВОСПАЛЕНИЕ")
        if w.get("splinted"):
            status.append("в шине")
        ui.text(screen, f"{w['type']}: {w['part']}", (rx, y), COL_BAD if w["bleeding"] or w.get("inflamed") else COL_TEXT, 15)
        ui.text(screen, ", ".join(status) or "без помощи", (rx + 200, y), COL_TEXT_DIM, 13)
        bx = rx
        y += 24
        for label, iid in actions.treatments_for(game, w):
            bw = ui.font(13).size(label)[0] + 18
            if ui.button(screen, (bx, y, bw, 24), label, size=13):
                actions.treat(game, w, iid)
            bx += bw + 6
        y += 34


def draw_journal(screen, ui, game):
    p = game.player
    ui.panel(screen, WIN, "Журнал")
    _close_button(screen, ui, game)
    tabs = ["Задания", "Навыки", "Персонаж"]
    for i, t in enumerate(tabs):
        if ui.button(screen, (WIN.x + 20 + i * 150, WIN.y + 44, 140, 28), t, active=ui.tab == i):
            ui.tab = i
    x, y = WIN.x + 24, WIN.y + 88
    if ui.tab == 0:
        active = [(q, s) for q, s in game.quests.items() if 0 < s < QUESTS[q]["final"]]
        done = [(q, s) for q, s in game.quests.items() if s >= QUESTS[q]["final"]]
        if not active and not done:
            ui.text(screen, "Пока никаких заданий.", (x, y), COL_TEXT_DIM)
        for q, s in active:
            ui.text(screen, QUESTS[q]["name"], (x, y), COL_ACCENT, 17, bold=True)
            y += 24
            y += ui.rich(screen, [(QUESTS[q]["stages"][str(s)], COL_TEXT)], x + 12, y, 900, 15) + 10
        for q, s in done:
            ui.text(screen, "✓ " + QUESTS[q]["name"], (x, y), COL_TEXT_DIM, 15)
            y += 24
    elif ui.tab == 1:
        for i, (sk, name) in enumerate(SKILLS.items()):
            s = p.skills[sk]
            yy = y + i * 40
            ui.text(screen, name, (x, yy), COL_TEXT, 16)
            for k in range(10):
                col = COL_ACCENT if k < s["lvl"] else (50, 46, 38)
                pygame.draw.rect(screen, col, (x + 230 + k * 22, yy + 2, 18, 16))
            ui.bar(screen, (x + 230, yy + 22, 218, 5), s["xp"] / (60 * (s["lvl"] + 1)), (140, 120, 80))
        ui.text(screen, "Навыки растут от использования: дерись — растёт ближний бой, кипяти воду — выживание.", (x, y + 380), COL_TEXT_DIM, 13)
    else:
        ui.text(screen, p.name, (x, y), COL_ACCENT, 20, bold=True)
        ui.text(screen, "Режим: " + ("Суровый (одна жизнь)" if p.mode == "hard" else "Обычный"), (x, y + 32), COL_TEXT, 15)
        ui.text(screen, f"Прожито дней: {game.clock.day - 1}   Убито врагов: {p.kills}", (x, y + 56), COL_TEXT, 15)
        ui.text(screen, f"Отношение колхоза «Заря»: {game.rep.get('zarya', 0)}", (x, y + 80), COL_TEXT, 15)
        ui.text(screen, "Черты:", (x, y + 116), COL_ACCENT, 16)
        for i, t in enumerate(p.traits):
            ui.text(screen, f"{TRAITS[t]['name']} — {TRAITS[t]['desc']}", (x + 12, y + 142 + i * 22), COL_TEXT, 14)


def draw_glossary(screen, ui, game):
    ui.panel(screen, WIN, f"Словарик — казахский и узбекский ({len(game.glossary)} из {len(GLOSSARY)})")
    _close_button(screen, ui, game)
    x0, y0 = WIN.x + 24, WIN.y + 50
    for col, (lang, lname) in enumerate((("kk", "Қазақша — казахский"), ("uz", "O'zbekcha — узбекский"))):
        x = x0 + col * 470
        ui.text(screen, lname, (x, y0), COL_ACCENT, 17, bold=True)
        y = y0 + 32
        words = [w for w in GLOSSARY if GLOSSARY[w]["lang"] == lang]
        for w in words:
            if w in game.glossary:
                ui.text(screen, w, (x, y), COL_TURQ, 15, bold=True)
                ui.text(screen, "— " + GLOSSARY[w]["ru"], (x + 180, y), COL_TEXT, 14)
            else:
                ui.text(screen, "· · ·", (x, y), (80, 74, 60), 15)
            y += 24
    ui.text(screen, "Слова запоминаются из разговоров, записок, радио и разговорника. Навык «Языки» помогает читать записки.",
            (x0, WIN.bottom - 34), COL_TEXT_DIM, 13)


def draw_dialogue(screen, ui, game):
    d = game.dialog
    r = pygame.Rect(140, SCREEN_H - 380, SCREEN_W - 280, 340)
    ui.panel(screen, r, f"{d.npc.name} — {d.npc.data['title']}")
    h = ui.rich(screen, d.text, r.x + 24, r.y + 48, r.w - 48, 17)
    y = r.y + 60 + h
    for i, (opt, segs) in enumerate(d.options):
        rr = pygame.Rect(r.x + 20, y - 2, r.w - 40, 26)
        if ui.hovered(rr):
            pygame.draw.rect(screen, (70, 62, 44), rr)
        num = [(f"{i + 1}. ", COL_ACCENT)]
        hh = ui.rich(screen, num + segs, r.x + 28, y, r.w - 60, 16)
        if ui.clicked(rr):
            game.choose_dialog(i)
            return
        y += max(26, hh + 4)


def draw_trade(screen, ui, game):
    p = game.player
    t = game.trade
    npc = t["npc"]
    ui.panel(screen, WIN, f"Обмен — {npc.name}")
    _close_button(screen, ui, game)
    lx, ly = WIN.x + 16, WIN.y + 44
    sell_k, buy_k = actions.trade_prices(game)
    ui.text(screen, "Твои вещи (ЛКМ — предложить, ПКМ — убрать)", (lx, ly), COL_TEXT_DIM, 13)
    mine = sorted([st for st in p.items if not ITEMS[st["id"]].get("quest_item")], key=inv.sort_key)
    rows = []
    for st in mine:
        n = t["give"].get(id(st), 0)
        rows.append((f"{inv.label(st)}  ·  {int(inv.value(st) * sell_k)}" + (f"   → {n}" if n else ""), COL_ACCENT if n else COL_TEXT))
    hit, rhit, _ = ui.scroll_list(screen, "tr_l", (lx, ly + 20, 450, 380), rows)
    if hit is not None:
        st = mine[hit]
        t["give"][id(st)] = min(st["n"], t["give"].get(id(st), 0) + 1)
        t["give_ref"][id(st)] = st
    if rhit is not None:
        st = mine[rhit]
        t["give"][id(st)] = max(0, t["give"].get(id(st), 0) - 1)

    rx = lx + 474
    ui.text(screen, f"Товар: {npc.name}", (rx, ly), COL_TEXT_DIM, 13)
    stock = [(k, n) for k, n in npc.stock.items() if n > 0]
    rows = []
    for k, n in stock:
        sel = t["take"].get(k, 0)
        rows.append((f"{ITEMS[k]['name']} ×{n}  ·  {int(ITEMS[k]['value'] * buy_k + 0.5)}" + (f"   → {sel}" if sel else ""), COL_ACCENT if sel else COL_TEXT))
    hit, rhit, _ = ui.scroll_list(screen, "tr_r", (rx, ly + 20, 470, 380), rows)
    if hit is not None:
        k, n = stock[hit]
        t["take"][k] = min(n, t["take"].get(k, 0) + 1)
    if rhit is not None:
        k, n = stock[rhit]
        t["take"][k] = max(0, t["take"].get(k, 0) - 1)

    give_v, take_v = actions.trade_totals(game)
    ok = give_v >= take_v and take_v > 0
    ui.text(screen, f"Ты даёшь: {give_v}     Ты получаешь: {take_v}", (lx, ly + 414), COL_GREEN if ok else COL_TEXT, 17, bold=True)
    ui.text(screen, "Цены зависят от навыка «Торговля» и отношения колхоза. Деньги почти ничего не стоят — меняйся.", (lx, ly + 442), COL_TEXT_DIM, 13)
    if ui.button(screen, (WIN.right - 220, WIN.bottom - 56, 200, 36), "Обменять", enabled=ok):
        actions.do_trade(game)


def draw_note(screen, ui, game):
    st = game.note_stack
    it = ITEMS[st["id"]]
    r = pygame.Rect(290, 90, 700, 480)
    ui.panel(screen, r, it["name"])
    _close_button(screen, ui, game, r)
    pygame.draw.rect(screen, (214, 204, 176), (r.x + 20, r.y + 46, r.w - 40, r.h - 70))
    ink = (40, 34, 60)
    if st.get("read") or it.get("lang") == "ru":
        segs = parse_markup(it["ru"], game.glossary, game.on_new_word, ink)
        ui.rich(screen, segs, r.x + 40, r.y + 66, r.w - 80, 17)
    else:
        lang = "узбекском" if it["lang"] == "uz" else "казахском"
        h = ui.rich(screen, [(it["orig"], ink)], r.x + 40, r.y + 66, r.w - 80, 17)
        ui.rich(screen, [(f"Текст на {lang} языке. Ты не можешь его прочесть. Нужен навык «Языки» {it['req']} или переводчик — Бахтияр в колхозе «Заря».", (130, 40, 30))],
                r.x + 40, r.y + 90 + h, r.w - 80, 15)


def draw_radio(screen, ui, game):
    r = pygame.Rect(300, 120, 680, 380)
    ui.panel(screen, r, "Радиоприёмник «Океан»")
    _close_button(screen, ui, game, r)
    st, text = game.radio_current()
    # шкала частот
    pygame.draw.rect(screen, (30, 40, 34), (r.x + 24, r.y + 48, r.w - 48, 40))
    for i in range(30):
        x = r.x + 34 + i * (r.w - 68) / 29
        pygame.draw.line(screen, (120, 160, 120), (x, r.y + 70), (x, r.y + (60 if i % 5 else 54)))
    nx = r.x + 34 + (game.radio_station + 0.5) / 3 * (r.w - 68)
    pygame.draw.line(screen, (220, 60, 40), (nx, r.y + 50), (nx, r.y + 86), 3)
    ui.text(screen, st["name"], (r.x + 24, r.y + 100), COL_ACCENT, 16, bold=True)
    ui.rich(screen, text, r.x + 24, r.y + 130, r.w - 48, 16)
    if ui.button(screen, (r.x + 24, r.bottom - 52, 160, 32), "◄ Частота"):
        game.radio_tune(-1)
    if ui.button(screen, (r.x + 196, r.bottom - 52, 160, 32), "Частота ►"):
        game.radio_tune(1)
    if ui.button(screen, (r.right - 184, r.bottom - 52, 160, 32), "Выключить"):
        game.close_window()


HELP_LINES = [
    ("WASD", "ходить (Shift — бег, Z — красться)"),
    ("ЛКМ", "удар / выстрел в сторону курсора"),
    ("E или ПКМ", "взаимодействовать: обыскать, открыть дверь, говорить, набрать воды"),
    ("R", "перезарядить оружие"),
    ("F", "включить/выключить фонарик"),
    ("B", "заколотить окно (молоток, 2 доски, 2 горсти гвоздей)"),
    ("I / Tab", "инвентарь (ПКМ по предмету — быстрое действие)"),
    ("C", "крафт"),
    ("H", "здоровье и лечение ран"),
    ("J", "журнал: задания, навыки, персонаж"),
    ("G", "словарик казахских и узбекских слов"),
    ("M", "звук вкл/выкл"),
    ("F11", "полноэкранный режим"),
    ("Esc", "пауза, сохранение"),
]


def draw_help(screen, ui, game):
    r = pygame.Rect(240, 70, 800, 560)
    ui.panel(screen, r, "Управление")
    _close_button(screen, ui, game, r)
    for i, (k, v) in enumerate(HELP_LINES):
        ui.text(screen, k, (r.x + 30, r.y + 52 + i * 28), COL_ACCENT, 16, bold=True)
        ui.text(screen, v, (r.x + 180, r.y + 52 + i * 28), COL_TEXT, 15)
    ui.rich(screen, [("Совет: серые идут на шум и свет. Воду кипяти на костре. В Пыльный фронт сиди дома или надень респиратор.", COL_TEXT_DIM)],
            r.x + 30, r.bottom - 66, r.w - 60, 14)


def draw_pause(screen, ui, game):
    r = pygame.Rect(SCREEN_W // 2 - 170, 150, 340, 400)
    ui.panel(screen, r, "Пауза")
    y = r.y + 54
    hard = game.player.mode == "hard"
    items = [("Продолжить", game.close_window, True),
             ("Сохранить игру", game.save_game, not hard),
             ("Загрузить", game.load_game, save.exists()),
             ("Управление", lambda: game.open_window("help"), True),
             ("Звук: " + ("выкл" if game.sound.muted else "вкл"), game.sound.toggle_mute, True),
             ("В главное меню", game.to_menu, True),
             ("Выйти из игры", game.quit, True)]
    for label, fn, en in items:
        if ui.button(screen, (r.x + 30, y, r.w - 60, 36), label, enabled=en):
            fn()
            return
        y += 46
    if hard:
        ui.text(screen, "Суровый режим: сохранение только во сне", (r.centerx, r.bottom - 26), COL_TEXT_DIM, 12, center=True)


def draw_chapter(screen, ui, game):
    shade = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    shade.fill((10, 8, 6, 200))
    screen.blit(shade, (0, 0))
    ui.text(screen, "АКТ II «КОЛОДЕЦ» ЗАВЕРШЁН", (SCREEN_W // 2, 200), COL_ACCENT, 34, bold=True, center=True)
    lines = [
        "Ты узнал правду: колодцы отравил бункер «Подземка», а источник беды —",
        "закрытый объект «Мелиорация-7» у самой границы.",
        "",
        "Продолжение — Акт III «Граница» и Акт IV «Объект» — в следующих версиях.",
        "А пока степь ждёт: выживай, обустраивай базу, помогай «Заре».",
    ]
    for i, l in enumerate(lines):
        ui.text(screen, l, (SCREEN_W // 2, 280 + i * 30), COL_TEXT, 18, center=True)
    if ui.button(screen, (SCREEN_W // 2 - 140, 480, 280, 42), "Продолжить выживать"):
        game.close_window()


# ====================================================================== экраны вне игры

def _menu_background(screen, t):
    """Степь на закате: пыльное небо, солнце, столбы ЛЭП и юрта на горизонте."""
    for y in range(SCREEN_H):
        k = y / SCREEN_H
        col = (int(196 - 120 * k), int(150 - 100 * k), int(80 - 50 * k)) if y < 470 else (int(70 - 20 * k), int(58 - 18 * k), int(40 - 12 * k))
        pygame.draw.line(screen, col, (0, y), (SCREEN_W, y))
    pygame.draw.circle(screen, (236, 190, 110), (930, 380), 70)
    pygame.draw.rect(screen, (60, 48, 34), (0, 470, SCREEN_W, SCREEN_H - 470))
    for i in range(9):
        x = (i * 170 - t * 12) % (SCREEN_W + 200) - 100
        pygame.draw.line(screen, (40, 30, 22), (x, 470), (x, 360), 4)
        pygame.draw.line(screen, (40, 30, 22), (x - 20, 372), (x + 20, 372), 3)
        if i < 8:
            nx = x + 170
            for k in range(3):
                pts = [(x - 16 + 16 * k + (nx - x) * s / 10, 374 + 18 * math.sin(math.pi * s / 10)) for s in range(11)]
                pygame.draw.lines(screen, (40, 30, 22), False, pts, 1)
    pygame.draw.ellipse(screen, (46, 36, 26), (180, 400, 120, 90))    # купол юрты
    pygame.draw.rect(screen, (46, 36, 26), (180, 440, 120, 32))
    pygame.draw.rect(screen, (46, 36, 26), (330, 400, 90, 70))   # панелька рядом с юртой
    for k in range(3):
        for j in range(2):
            pygame.draw.rect(screen, (90, 70, 40), (342 + k * 26, 412 + j * 26, 12, 14))


def draw_main_menu(screen, ui, game):
    _menu_background(screen, game.time_real)
    ui.text(screen, "ГРАНИЦА-99", (SCREEN_W // 2, 70), (40, 28, 18), 72, bold=True, center=True)
    ui.text(screen, "ГРАНИЦА-99", (SCREEN_W // 2 - 3, 67), (230, 200, 140), 72, bold=True, center=True)
    ui.text(screen, "Юг Казахстана, 1999 год. Степь, пыль и выбор.", (SCREEN_W // 2, 160), (250, 230, 190), 20, center=True)
    r = pygame.Rect(SCREEN_W // 2 - 160, 220, 320, 300)
    y = r.y
    items = [("Продолжить", game.load_game, save.exists()),
             ("Новая игра", game.to_creation, True),
             ("Управление", lambda: game.open_window("help"), True),
             ("Выход", game.quit, True)]
    for label, fn, en in items:
        if ui.button(screen, (r.x, y, r.w, 42), label, enabled=en, size=18):
            fn()
            return
        y += 54
    ui.text(screen, f"Версия {VERSION} · вся графика и звук созданы кодом · см. CREDITS.md", (SCREEN_W // 2, SCREEN_H - 30), (200, 180, 140), 13, center=True)
    if game.window == "help":
        draw_help(screen, ui, game)


def draw_creation(screen, ui, game):
    _menu_background(screen, game.time_real)
    r = pygame.Rect(90, 40, SCREEN_W - 180, SCREEN_H - 80)
    ui.panel(screen, r, "Новый персонаж")
    c = game.creation
    x, y = r.x + 24, r.y + 52
    ui.text(screen, "Имя:", (x, y + 6), COL_TEXT, 16)
    box = pygame.Rect(x + 60, y, 300, 32)
    pygame.draw.rect(screen, COL_PANEL_DARK, box)
    pygame.draw.rect(screen, COL_ACCENT, box, 1)
    cursor = "|" if int(game.time_real * 2) % 2 else ""
    ui.text(screen, c["name"] + cursor, (box.x + 8, box.y + 6), COL_TEXT, 16)

    ui.text(screen, "Режим:", (x + 400, y + 6), COL_TEXT, 16)
    if ui.button(screen, (x + 470, y, 140, 32), "Обычный", active=c["mode"] == "normal"):
        c["mode"] = "normal"
    if ui.button(screen, (x + 620, y, 220, 32), "Суровый (одна жизнь)", active=c["mode"] == "hard"):
        c["mode"] = "hard"

    pts = CHARACTER["start_points"] + sum(TRAITS[t]["cost"] for t in c["traits"])
    ui.text(screen, f"Черты персонажа. Очки: {pts}  (плюсы стоят очков, минусы — дают)", (x, y + 54), COL_ACCENT if pts >= 0 else COL_BAD, 16, bold=True)
    pos = [t for t in TRAITS if TRAITS[t]["cost"] < 0]
    neg = [t for t in TRAITS if TRAITS[t]["cost"] > 0]
    for col, group in enumerate((pos, neg)):
        for i, t in enumerate(group):
            tr_ = TRAITS[t]
            bx = x + col * 540
            by = y + 88 + i * 46
            on = t in c["traits"]
            label = f"{'■' if on else '□'} {tr_['name']} ({tr_['cost']:+d})"
            if ui.button(screen, (bx, by, 220, 38), label, active=on, size=14):
                if on:
                    c["traits"].remove(t)
                else:
                    c["traits"].append(t)
            ui.rich(screen, [(tr_["desc"], COL_TEXT_DIM)], bx + 230, by + 2, 290, 13, 16)
    ok = pts >= 0 and c["name"].strip() != ""
    if ui.button(screen, (r.right - 260, r.bottom - 60, 230, 40), "Начать выживание", enabled=ok, size=17):
        game.new_game()
    if ui.button(screen, (r.x + 24, r.bottom - 60, 160, 40), "Назад"):
        game.to_menu()


def draw_death(screen, ui, game):
    shade = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    shade.fill((20, 4, 4, 210))
    screen.blit(shade, (0, 0))
    p = game.player
    days = game.clock.day - 1
    ui.text(screen, "ВЫ ПОГИБЛИ", (SCREEN_W // 2, 170), COL_RED, 48, bold=True, center=True)
    ui.text(screen, f"{p.name} прожил(а) в степи {days} {_days_word(days)}.", (SCREEN_W // 2, 250), COL_TEXT, 22, center=True)
    ui.text(screen, game.death_cause, (SCREEN_W // 2, 290), COL_TEXT_DIM, 17, center=True)
    ui.text(screen, f"Убито врагов: {p.kills} · Слов в словарике: {len(game.glossary)} · Заданий выполнено: {game.quests_done()}",
            (SCREEN_W // 2, 330), COL_TEXT_DIM, 16, center=True)
    if ui.button(screen, (SCREEN_W // 2 - 150, 400, 300, 42), "Новый персонаж", size=17):
        game.to_creation()
    if save.exists() and p.mode != "hard":
        if ui.button(screen, (SCREEN_W // 2 - 150, 452, 300, 42), "Загрузить сохранение", size=17):
            game.load_game()
    if ui.button(screen, (SCREEN_W // 2 - 150, 504, 300, 42), "Главное меню", size=17):
        game.to_menu()


def _days_word(n):
    if n % 10 == 1 and n % 100 != 11:
        return "день"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "дня"
    return "дней"
