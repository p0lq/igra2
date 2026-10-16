"""Интерфейс в ретро-стиле советской техники: панели, стрелочные индикаторы, окна.

Используется подход «immediate mode GUI»: каждый кадр окна рисуются заново,
а функция button() сразу возвращает True, если по кнопке кликнули в этом кадре.
Так не нужно хранить дерево виджетов — код окна читается сверху вниз.
"""
import math

import pygame

from .config import (COL_PANEL, COL_PANEL_DARK, COL_PANEL_EDGE, COL_TEXT, COL_TEXT_DIM, COL_ACCENT,
                     COL_RED, COL_GREEN, COL_TURQ, COL_BAD, TITLE, VERSION)
from . import config as cfg
from .data import ITEMS, RECIPES, SKILLS, TRAITS, QUESTS, GLOSSARY, CHARACTER, OBJECTS
from .localization import parse_markup
from . import inventory as inv
from . import crafting, actions, save, icons
from . import settings as settings_mod

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
        self.release = None      # где отпустили левую кнопку (для перетаскивания)
        self.shift = False
        self.active = None       # ползунок, который сейчас тянут мышью

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
        self.release = None
        self.wheel = 0
        self.shift = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
        for e in events:
            if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                self.release = e.pos
            elif e.type == pygame.MOUSEBUTTONDOWN:
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


    def slider(self, surf, key, rect, value, lo=0, hi=100):
        """Ползунок. Тянуть можно, даже если мышь ушла за его пределы, пока кнопка зажата."""
        r = pygame.Rect(rect)
        if self.click and r.inflate(0, 14).collidepoint(self.click):
            self.active = key
            self.click = None
        if self.active == key:
            if pygame.mouse.get_pressed()[0]:
                value = lo + (hi - lo) * max(0.0, min(1.0, (self.mouse[0] - r.x) / r.w))
            else:
                self.active = None
        frac = (value - lo) / (hi - lo)
        pygame.draw.rect(surf, (30, 26, 20), r)
        pygame.draw.rect(surf, COL_ACCENT, (r.x, r.y, int(r.w * frac), r.h))
        pygame.draw.rect(surf, COL_PANEL_EDGE, r, 1)
        kx = r.x + int(r.w * frac)
        pygame.draw.rect(surf, (230, 214, 170), (kx - 4, r.y - 5, 8, r.h + 10))
        return int(round(value))

    def selector(self, surf, rect, text):
        """Переключатель «◄ значение ►». Возвращает -1, 0 или +1."""
        r = pygame.Rect(rect)
        d = 0
        if self.button(surf, (r.x, r.y, 32, r.h), "◄"):
            d = -1
        if self.button(surf, (r.right - 32, r.y, 32, r.h), "►"):
            d = 1
        pygame.draw.rect(surf, COL_PANEL_DARK, (r.x + 36, r.y, r.w - 72, r.h))
        self.text(surf, text, (r.centerx, r.y + r.h // 2 - 10), COL_TEXT, 15, center=True)
        return d

    def checkbox(self, surf, rect, label, value):
        r = pygame.Rect(rect)
        box = pygame.Rect(r.x, r.y + (r.h - 20) // 2, 20, 20)
        pygame.draw.rect(surf, COL_PANEL_DARK, box)
        pygame.draw.rect(surf, COL_PANEL_EDGE, box, 1)
        if value:
            pygame.draw.rect(surf, COL_ACCENT, box.inflate(-8, -8))
        self.text(surf, label, (box.right + 10, r.y + r.h // 2 - 10), COL_TEXT, 15)
        if self.clicked(r):
            return not value
        return value


# ====================================================================== HUD

def draw_hud(screen, ui, game):
    p = game.player
    clock = game.clock
    # --- приборная панель внизу слева
    ui.panel(screen, (0, cfg.SCREEN_H - 112, 560, 112))
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
            ui.gauge(screen, cx, cfg.SCREEN_H - 66, 30, frac, lab, val, danger_high=True)
        else:
            ui.gauge(screen, cx, cfg.SCREEN_H - 66, 30, frac, lab, val, danger_high=high)

    # --- состояния («муды»)
    over = p.weight() > p.carry_limit()
    x, y = 572, cfg.SCREEN_H - 108
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
    if p.god or p.noclip:
        tag = " + ".join(t for t, on in (("РЕЖИМ БОГА", p.god), ("NOCLIP", p.noclip)) if on)
        ui.text(screen, tag + "  (F10)", (cfg.SCREEN_W // 2, 44), (255, 215, 90), 18, bold=True, center=True)
    if game.settings["show_fps"]:
        ui.text(screen, f"FPS {game.clock_fps.get_fps():.0f}", (cfg.SCREEN_W - 10, 72), COL_GREEN, 14, right=True)
    if clock.front:
        if int(game.time_real * 2) % 2:
            ui.text(screen, "ПЫЛЬНЫЙ ФРОНТ!", (cfg.SCREEN_W // 2, 12), COL_RED, 24, bold=True, center=True)

    # --- оружие и режимы сверху справа
    ui.panel(screen, (cfg.SCREEN_W - 300, 0, 300, 66))
    st, it = p.weapon()
    wname = inv.label(st) if st else "Голые руки"
    ui.text(screen, wname, (cfg.SCREEN_W - 286, 8), COL_TEXT, 15)
    modes = []
    if p.sneaking:
        modes.append("крадусь")
    if p.running:
        modes.append("бег")
    if p.equip["light"]:
        modes.append("фонарь: " + ("вкл" if p.has_light() else "выкл"))
    if p.equip["face"]:
        modes.append("фильтр %d ч" % (p.equip["face"].get("filter", 0) // 60))
    ui.text(screen, " · ".join(modes) if modes else "Z — красться, Shift — бег", (cfg.SCREEN_W - 286, 34), COL_TEXT_DIM, 13)

    # --- журнал сообщений (на полупрозрачной подложке, чтобы читался поверх карты)
    recent = [m for m in game.messages[-7:] if m["t"] > 0]
    if recent:
        back = pygame.Surface((560, 20 * len(recent) + 8), pygame.SRCALPHA)
        back.fill((14, 12, 10, 150))
        screen.blit(back, (4, cfg.SCREEN_H - 116 - 20 * len(recent)))
    y = cfg.SCREEN_H - 132
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
        ui.text(screen, a["name"], (cfg.SCREEN_W // 2, cfg.SCREEN_H - 168), COL_TEXT, 16, center=True)
        ui.bar(screen, (cfg.SCREEN_W // 2 - 120, cfg.SCREEN_H - 146, 240, 12), frac, COL_ACCENT)
    elif game.hint and not game.window and game.settings["hints"]:
        img = ui.font(17).render(game.hint, True, (240, 220, 160))
        back = pygame.Surface((img.get_width() + 20, img.get_height() + 6), pygame.SRCALPHA)
        back.fill((14, 12, 10, 160))
        hx, hy = cfg.SCREEN_W // 2 - back.get_width() // 2, cfg.SCREEN_H // 2 + 70
        screen.blit(back, (hx, hy))
        screen.blit(img, (hx + 10, hy + 3))

    pygame.draw.rect(screen, COL_PANEL_DARK, (cfg.SCREEN_W - 560, cfg.SCREEN_H - 26, 560, 26))
    ui.text(screen, "I инвентарь · C крафт · H здоровье · J журнал · G словарик · Esc меню · F1 помощь",
            (cfg.SCREEN_W - 10, cfg.SCREEN_H - 22), COL_TEXT_DIM, 13, right=True)


# ====================================================================== окна

def _win(w=980, h=560):
    """Прямоугольник окна по центру экрана (разрешение может меняться в настройках)."""
    return pygame.Rect((cfg.SCREEN_W - w) // 2, (cfg.SCREEN_H - h) // 2, w, h)


def _close_button(screen, ui, game, rect=None):
    rect = rect or _win()
    if ui.button(screen, (rect.right - 40, rect.y + 8, 28, 26), "×", size=18):
        game.close_window()


SLOT = 52
EQUIP_SLOTS = [("weapon", "Оружие"), ("body", "Одежда"), ("head", "Голова"),
               ("face", "Лицо"), ("back", "Спина"), ("light", "Свет")]
CATEGORIES = [("all", "Всё"), ("food", "Еда"), ("weapon", "Оружие"), ("medical", "Медицина"),
              ("clothing", "Одежда"), ("material", "Материалы"), ("other", "Прочее")]
CAT_TYPES = {"food": {"food", "drink"}, "weapon": {"weapon", "gun", "ammo"}, "medical": {"medical"},
             "clothing": {"clothing"}, "material": {"material"}, "other": {"book", "note", "misc"}}
_TYPE_NAMES = {"food": "еда", "drink": "питьё", "weapon": "оружие", "gun": "огнестрел", "ammo": "патроны",
               "medical": "медицина", "clothing": "одежда", "material": "материал", "book": "книга",
               "note": "записка", "misc": "разное"}


def _draw_stack(screen, ui, st, r, iid=None):
    """Иконка предмета в ячейке: количество, полоска прочности, патроны."""
    iid = iid or st["id"]
    it = ITEMS[iid]
    screen.blit(icons.get(iid), (r.x + (r.w - 40) // 2, r.y + (r.h - 40) // 2))
    if st is None:
        return
    if st["n"] > 1:
        t = str(st["n"])
        ui.text(screen, t, (r.right - 3, r.bottom - 19), (0, 0, 0), 14, bold=True, right=True)
        ui.text(screen, t, (r.right - 4, r.bottom - 20), (250, 240, 210), 14, bold=True, right=True)
    if "dur" in st and it.get("dur"):
        frac = max(0, st["dur"] / it["dur"])
        col = (90, 180, 80) if frac > 0.5 else ((220, 180, 60) if frac > 0.2 else (210, 60, 50))
        pygame.draw.rect(screen, (20, 18, 14), (r.x + 5, r.bottom - 6, r.w - 10, 3))
        pygame.draw.rect(screen, col, (r.x + 5, r.bottom - 6, int((r.w - 10) * frac), 3))
    if it["type"] == "gun":
        ui.text(screen, f"{st.get('loaded', 0)}/{it['mag']}", (r.x + 4, r.y + 2), (240, 220, 160), 11)
    if it["type"] == "note" and not st.get("read"):
        ui.text(screen, "?", (r.x + 5, r.y + 1), COL_TURQ, 14, bold=True)


def _grid(screen, ui, key, rect, entries, kind, selected=None):
    """Сетка ячеек как в Minecraft. entries — [(стопка или None, id предмета)].
    Возвращает [(прямоугольник ячейки, вид, запись)] — по ним потом ищем, куда кликнули."""
    r = pygame.Rect(rect)
    cols, rows = r.w // SLOT, r.h // SLOT
    total_rows = max(rows, -(-len(entries) // cols))
    off = ui.scroll.get(key, 0)
    if ui.hovered(r) and ui.wheel:
        off -= ui.wheel
    off = max(0, min(off, total_rows - rows))
    ui.scroll[key] = off
    hits = []
    for i in range(rows * cols):
        idx = off * cols + i
        cr = pygame.Rect(r.x + (i % cols) * SLOT, r.y + (i // cols) * SLOT, SLOT - 4, SLOT - 4)
        entry = entries[idx] if idx < len(entries) else None
        sel = entry is not None and selected is not None and entry[0] is selected
        hov = ui.hovered(cr)
        pygame.draw.rect(screen, (38, 34, 27), cr)
        pygame.draw.rect(screen, COL_ACCENT if sel else ((140, 124, 90) if hov else (74, 66, 50)), cr, 2 if sel else 1)
        if entry is not None:
            _draw_stack(screen, ui, entry[0], cr, entry[1])
            hits.append((cr, kind, entry))
    if total_rows > rows:
        frac = off / (total_rows - rows)
        pygame.draw.rect(screen, (120, 106, 76), (r.right - 3, r.y + int((r.h - 30) * frac), 3, 30))
    return hits


def _tooltip(screen, ui, iid, st):
    it = ITEMS[iid]
    lines = [inv.label(st) if st else it["name"], f"{it['w']} кг · {_TYPE_NAMES.get(it['type'], '')}"]
    w = max(ui.font(14).size(l)[0] for l in lines) + 16
    x = min(ui.mouse[0] + 16, cfg.SCREEN_W - w - 4)
    y = min(ui.mouse[1] + 12, cfg.SCREEN_H - 50)
    pygame.draw.rect(screen, (20, 18, 14), (x, y, w, 44))
    pygame.draw.rect(screen, COL_PANEL_EDGE, (x, y, w, 44), 1)
    ui.text(screen, lines[0], (x + 8, y + 4), COL_ACCENT, 14)
    ui.text(screen, lines[1], (x + 8, y + 23), COL_TEXT_DIM, 13)


def draw_inventory(screen, ui, game):
    """Инвентарь-сетка: снаряжение слева, вещи в центре, справа — контейнер/земля
    или каталог всех предметов (в режиме бога). Предметы перетаскиваются мышью."""
    p = game.player
    W = _win(1040, 640)
    ui.panel(screen, W, "Инвентарь" + ("   · РЕЖИМ БОГА: бери что угодно из каталога" if p.god else ""))
    _close_button(screen, ui, game, W)
    hits = []
    ty = W.y + 46
    gy = W.y + 70

    # --- снаряжение
    ex = W.x + 18
    ui.text(screen, "Надето", (ex, ty), COL_ACCENT, 14)
    for i, (slot, label) in enumerate(EQUIP_SLOTS):
        r = pygame.Rect(ex, gy + i * 61, SLOT, SLOT)
        st = p.equip[slot]
        pygame.draw.rect(screen, (44, 40, 30), r)
        pygame.draw.rect(screen, (140, 124, 90) if ui.hovered(r) else (96, 86, 62), r, 1)
        if st:
            _draw_stack(screen, ui, st, r)
        else:
            ui.text(screen, label, (r.centerx, r.centery - 8), (96, 88, 70), 11, center=True)
        hits.append((r, "equip", slot))

    # --- вещи игрока
    gx = ex + SLOT + 20
    items = sorted(p.items, key=inv.sort_key)
    ui.text(screen, "Вещи (колесо — прокрутка)", (gx, ty), COL_ACCENT, 14)
    pgrid = pygame.Rect(gx, gy, SLOT * 7, SLOT * 7)
    hits += _grid(screen, ui, "inv", pgrid, [(st, st["id"]) for st in items], "player", game.sel_item)
    lim = p.carry_limit()
    wt = p.weight()
    ui.bar(screen, (gx, pgrid.bottom + 6, pgrid.w - 4, 10), wt / lim if lim < 900 else 0,
           COL_BAD if wt > lim else (150, 130, 80))
    lim_text = "∞" if lim >= 900 else f"{lim:.0f}"
    ui.text(screen, f"Вес: {wt:.1f} / {lim_text} кг", (gx, pgrid.bottom + 20), COL_TEXT_DIM, 13)

    # --- правая панель: рядом (контейнер/земля) или каталог
    rx = pgrid.right + 22
    rw = W.right - 18 - rx
    if not p.god and game.inv_tab == "catalog":
        game.inv_tab = "near"
    near_title, near = game.near_container()
    if ui.button(screen, (rx, ty - 4, 200, 24), near_title, active=game.inv_tab == "near", size=13):
        game.inv_tab = "near"
    if p.god and ui.button(screen, (rx + 206, ty - 4, 200, 24), "Все предметы (бог)", active=game.inv_tab == "catalog", size=13):
        game.inv_tab = "catalog"
    rgrid = None
    if game.inv_tab == "near":
        rgrid = pygame.Rect(rx, gy, (rw // SLOT) * SLOT, SLOT * 6)
        entries = [(st, st["id"]) for st in (near or [])]
        hits += _grid(screen, ui, "near", rgrid, entries, "near", game.sel_item)
        if not entries:
            msg = "Пусто" if near is not None else "Перетащи сюда вещь, чтобы положить на землю"
            ui.text(screen, msg, (rgrid.centerx, rgrid.centery - 8), COL_TEXT_DIM, 14, center=True)
        if ui.button(screen, (rx, rgrid.bottom + 4, 180, 26), "Взять всё", enabled=bool(near), size=13):
            for st in list(near):
                actions.take_from(game, near, st)
    else:
        bx = rx
        for cid, cname in CATEGORIES:
            bw = ui.font(13).size(cname)[0] + 16
            if ui.button(screen, (bx, gy, bw, 24), cname, active=game.cat_filter == cid, size=13):
                game.cat_filter = cid
                ui.scroll["cat"] = 0
            bx += bw + 4
        ids = [i for i in ITEMS if game.cat_filter == "all" or ITEMS[i]["type"] in CAT_TYPES[game.cat_filter]]
        cgrid = pygame.Rect(rx, gy + 30, (rw // SLOT) * SLOT, SLOT * 6 - 24)
        hits += _grid(screen, ui, "cat", cgrid, [(None, i) for i in ids], "cat")
        ui.text(screen, "ЛКМ — взять 1 · Shift+ЛКМ или ПКМ — взять 10 · можно перетащить", (rx, cgrid.bottom + 6), COL_TEXT_DIM, 13)

    # --- перетаскивание и клики
    _inventory_mouse(screen, ui, game, hits, pgrid, rgrid, W)

    # --- описание выбранного предмета и действия
    _inventory_details(screen, ui, game, W)

    # --- подсказка при наведении
    if not (game.drag and game.drag["moved"]):
        for r, kind, payload in hits:
            if r.collidepoint(ui.mouse):
                st, iid = _hit_item(game, kind, payload)
                if iid:
                    _tooltip(screen, ui, iid, st)
                break


def _hit_item(game, kind, payload):
    """(стопка, id) предмета в ячейке."""
    if kind == "equip":
        st = game.player.equip[payload]
        return st, (st["id"] if st else None)
    return payload[0], payload[1]


def _inventory_mouse(screen, ui, game, hits, pgrid, rgrid, W):
    """Мышь в инвентаре: нажал на предмет — начал тащить; отпустил на месте — это клик."""
    if ui.click and not game.drag:
        for r, kind, payload in hits:
            if r.collidepoint(ui.click) and _hit_item(game, kind, payload)[1]:
                game.drag = {"kind": kind, "payload": payload, "start": ui.click, "moved": False, "shift": ui.shift}
                ui.click = None
                break
    d = game.drag
    if d and math.hypot(ui.mouse[0] - d["start"][0], ui.mouse[1] - d["start"][1]) > 6:
        d["moved"] = True
    if d and (ui.release or not pygame.mouse.get_pressed()[0]):
        game.drag = None
        pos = ui.release or ui.mouse
        if not d["moved"]:
            _inv_click(game, d)
        else:
            target = None
            for r, kind, payload in hits:
                if r.collidepoint(pos):
                    target = kind if kind != "equip" else ("equip", payload)
                    break
            if target is None:
                if pgrid.collidepoint(pos):
                    target = "player"
                elif rgrid is not None and rgrid.collidepoint(pos):
                    target = "near"
                elif not W.collidepoint(pos):
                    target = "outside"
            _inv_drop(game, d, target)
    if ui.rclick:
        for r, kind, payload in hits:
            if r.collidepoint(ui.rclick):
                _inv_click(game, {"kind": kind, "payload": payload, "shift": True}, quick=True)
                break
        ui.rclick = None
    d = game.drag
    if d and d["moved"]:
        st, iid = _hit_item(game, d["kind"], d["payload"])
        if iid:
            screen.blit(icons.get(iid), (ui.mouse[0] - 20, ui.mouse[1] - 20))


def _inv_click(game, d, quick=False):
    """Клик без перетаскивания: выбрать. С Shift или ПКМ — быстро переложить/взять/использовать."""
    kind, payload = d["kind"], d["payload"]
    shift = d.get("shift")
    _, near = game.near_container()
    if kind == "cat":
        game.give_item(payload[1], 10 if shift else 1)
        return
    if kind == "equip":
        if shift:
            actions.unequip(game, payload)
        else:
            game.sel_item, game.sel_from = game.player.equip[payload], "equip"
        return
    st = payload[0]
    if not shift:
        game.sel_item, game.sel_from = st, ("player" if kind == "player" else "container")
        return
    if kind == "player":
        if game.container_items() is not None:
            actions.put_into(game, game.container_items(), st)
        elif quick:
            actions.quick_use(game, st)
        else:
            actions.drop(game, st)
    elif kind == "near" and near is not None:
        actions.take_from(game, near, st)


def _inv_drop(game, d, target):
    """Предмет отпустили над целью: переложить, надеть, выбросить."""
    p = game.player
    kind, payload = d["kind"], d["payload"]
    _, near = game.near_container()
    st, iid = _hit_item(game, kind, payload)
    to_equip = target[1] if isinstance(target, tuple) else None
    if kind == "cat":
        if target in ("player", "near") or to_equip:
            game.give_item(iid, 10 if d.get("shift") else 1)
            if to_equip:
                new = next((s for s in reversed(p.items) if s["id"] == iid), None)
                if new and actions.fits_slot(iid, to_equip):
                    actions.equip(game, new)
        return
    if kind == "player":
        if to_equip:
            if actions.fits_slot(iid, to_equip):
                actions.equip(game, st)
            else:
                game.log("Сюда это не надеть.", "bad")
        elif target == "near":
            if game.container_items() is not None:
                actions.put_into(game, game.container_items(), st)
            else:
                actions.drop(game, st)
        elif target == "outside":
            actions.drop(game, st)
    elif kind == "near" and near is not None and st in near:
        if target == "player" or to_equip:
            actions.take_from(game, near, st)
            if to_equip and actions.fits_slot(iid, to_equip) and st in p.items:
                actions.equip(game, st)
    elif kind == "equip":
        slot = payload
        if target == "player":
            actions.unequip(game, slot)
        elif target in ("near", "outside"):
            actions.unequip(game, slot)
            if st in p.items:
                if target == "near" and game.container_items() is not None:
                    actions.put_into(game, game.container_items(), st)
                else:
                    actions.drop(game, st)


def _inventory_details(screen, ui, game, W):
    """Нижняя часть окна: большая иконка, описание, характеристики и кнопки действий."""
    p = game.player
    top = W.y + 488
    pygame.draw.line(screen, (90, 80, 60), (W.x + 16, top - 8), (W.right - 16, top - 8))
    st = game.sel_item
    _, near = game.near_container()
    valid = st is not None and (st in p.items or (near is not None and st in near) or st in p.equip.values())
    if not valid:
        game.sel_item = None
        ui.text(screen, "Клик по предмету — описание и действия. Перетаскивай мышью: в слоты снаряжения, "
                "в контейнер, за окно — выбросить.", (W.x + 20, top + 4), COL_TEXT_DIM, 13)
        ui.text(screen, "ПКМ — быстрое действие (съесть, надеть, переложить). Shift+клик — переложить.",
                (W.x + 20, top + 24), COL_TEXT_DIM, 13)
        return
    it = ITEMS[st["id"]]
    box = pygame.Rect(W.x + 20, top, 64, 64)
    pygame.draw.rect(screen, (38, 34, 27), box)
    screen.blit(icons.get(st["id"], 56), (box.x + 4, box.y + 4))
    tx = box.right + 14
    ui.text(screen, inv.label(st), (tx, top - 2), COL_ACCENT, 17, bold=True)
    h = ui.rich(screen, [(it.get("desc", ""), COL_TEXT)], tx, top + 24, 520, 14)
    ui.rich(screen, [(_item_stats(it), COL_TEXT_DIM)], tx, top + 28 + h, 520, 13)
    if game.sel_from == "equip":
        slot = next(k for k, v in p.equip.items() if v is st)
        acts = [("Снять", lambda: actions.unequip(game, slot))]
        if it["type"] == "gun":
            acts.append(("Зарядить [R]", lambda: actions.reload_gun(game)))
    elif game.sel_from == "container":
        acts = [("Взять", lambda: actions.take_from(game, near, st))] if near is not None else []
    else:
        acts = actions.item_actions(game, st, "player")
    bx, by = W.right - 380, top
    for i, (label, fn) in enumerate(acts[:6]):
        if ui.button(screen, (bx + (i % 2) * 184, by + (i // 2) * 36, 178, 30), label, size=13):
            fn()


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
    ui.panel(screen, _win(), "Крафт и ремесло")
    _close_button(screen, ui, game)
    stations = crafting.stations_near(game)
    lx, ly = _win().x + 16, _win().y + 44
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
    ui.panel(screen, _win(), "Здоровье")
    _close_button(screen, ui, game)
    lx, ly = _win().x + 20, _win().y + 48
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
    ui.text(screen, "Пыльная болезнь: кашель (15) → лихорадка (40) → бред (70) → смерть (100).", (lx, _win().bottom - 70), COL_TEXT_DIM, 13)
    ui.text(screen, "Защита — респиратор или противогаз, укрытие в помещении. Лечение — антидот, отвар колючки.", (lx, _win().bottom - 50), COL_TEXT_DIM, 13)

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
    ui.panel(screen, _win(), "Журнал")
    _close_button(screen, ui, game)
    tabs = ["Задания", "Навыки", "Персонаж"]
    for i, t in enumerate(tabs):
        if ui.button(screen, (_win().x + 20 + i * 150, _win().y + 44, 140, 28), t, active=ui.tab == i):
            ui.tab = i
    x, y = _win().x + 24, _win().y + 88
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
    ui.panel(screen, _win(), f"Словарик — казахский и узбекский ({len(game.glossary)} из {len(GLOSSARY)})")
    _close_button(screen, ui, game)
    x0, y0 = _win().x + 24, _win().y + 50
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
            (x0, _win().bottom - 34), COL_TEXT_DIM, 13)


def draw_dialogue(screen, ui, game):
    d = game.dialog
    r = pygame.Rect(140, cfg.SCREEN_H - 380, cfg.SCREEN_W - 280, 340)
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
    ui.panel(screen, _win(), f"Обмен — {npc.name}")
    _close_button(screen, ui, game)
    lx, ly = _win().x + 16, _win().y + 44
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
    if ui.button(screen, (_win().right - 220, _win().bottom - 56, 200, 36), "Обменять", enabled=ok):
        actions.do_trade(game)


def draw_note(screen, ui, game):
    st = game.note_stack
    it = ITEMS[st["id"]]
    r = _win(700, 480)
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
    r = _win(680, 380)
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
    ("F10", "режим бога: бессмертие, враги не замечают, каталог предметов в инвентаре"),
    ("` (Ё)", "консоль команд (help — список)"),
    ("F11", "полноэкранный режим (остальное — Esc → Настройки)"),
    ("Esc", "пауза, сохранение, настройки"),
]


def draw_help(screen, ui, game):
    r = _win(800, 600)
    ui.panel(screen, r, "Управление")
    _close_button(screen, ui, game, r)
    for i, (k, v) in enumerate(HELP_LINES):
        ui.text(screen, k, (r.x + 30, r.y + 52 + i * 28), COL_ACCENT, 16, bold=True)
        ui.text(screen, v, (r.x + 180, r.y + 52 + i * 28), COL_TEXT, 15)
    ui.rich(screen, [("Совет: серые идут на шум и свет. Воду кипяти на костре. В Пыльный фронт сиди дома или надень респиратор.", COL_TEXT_DIM)],
            r.x + 30, r.bottom - 66, r.w - 60, 14)


def draw_settings(screen, ui, game):
    """Окно настроек: видео (разрешение, режим, масштаб, vsync, FPS, яркость), звук, игра."""
    st = game.settings
    pv = game.pending_video
    W = _win(780, 560)
    ui.panel(screen, W, "Настройки")
    _close_button(screen, ui, game, W)
    tabs = ["Изображение", "Звук", "Игра"]
    for i, t in enumerate(tabs):
        if ui.button(screen, (W.x + 20 + i * 160, W.y + 44, 150, 28), t, active=game.settings_tab == i):
            game.settings_tab = i
    x, y = W.x + 30, W.y + 96
    lw = 250                      # ширина подписи
    cx, cw = x + lw, 360          # колонка элементов управления
    changed = False

    def row(label, yy):
        ui.text(screen, label, (x, yy + 6), COL_TEXT, 15)

    if game.settings_tab == 0:
        res_list = settings_mod.available_resolutions()
        cur = tuple(pv["resolution"])
        if cur not in res_list:
            res_list = sorted(res_list + [cur])
        row("Разрешение", y)
        d = ui.selector(screen, (cx, y, cw, 30), f"{cur[0]} × {cur[1]}")
        if d:
            pv["resolution"] = list(res_list[(res_list.index(cur) + d) % len(res_list)])
        y += 42
        modes = settings_mod.DISPLAY_MODES
        mi = [m[0] for m in modes].index(pv["display"])
        row("Режим экрана", y)
        d = ui.selector(screen, (cx, y, cw, 30), modes[mi][1])
        if d:
            pv["display"] = modes[(mi + d) % len(modes)][0]
        y += 42
        sc = settings_mod.SCALES
        row("Масштаб изображения", y)
        d = ui.selector(screen, (cx, y, cw, 30), f"{pv['scale']}%")
        if d:
            pv["scale"] = sc[(sc.index(pv["scale"]) + d) % len(sc)]
        y += 42
        pv["vsync"] = ui.checkbox(screen, (x, y, 400, 30), "Вертикальная синхронизация (без разрывов кадра)", pv["vsync"])
        y += 40
        dirty = any(pv[k] != st[k] for k in pv)
        if ui.button(screen, (cx, y, 170, 32), "Применить", enabled=dirty):
            for k in pv:
                st[k] = pv[k]
            game.apply_video()
            changed = True
        if dirty:
            ui.text(screen, "← нажми, чтобы применить", (cx + 180, y + 7), COL_ACCENT, 13)
        y += 50
        pygame.draw.line(screen, (90, 80, 60), (x, y - 8), (W.right - 30, y - 8))
        fl = settings_mod.FPS_LIMITS
        row("Ограничение FPS", y)
        d = ui.selector(screen, (cx, y, cw, 30), "без ограничения" if st["fps_limit"] == 0 else str(st["fps_limit"]))
        if d:
            st["fps_limit"] = fl[(fl.index(st["fps_limit"]) + d) % len(fl)]
            changed = True
        y += 44
        row(f"Яркость: {st['brightness']}%", y)
        v = ui.slider(screen, "bright", (cx, y + 10, cw, 10), st["brightness"], 50, 150)
        if v != st["brightness"]:
            st["brightness"] = v
            changed = True
        y += 40
        old = st["show_fps"]
        st["show_fps"] = ui.checkbox(screen, (x, y, 300, 30), "Показывать счётчик FPS", st["show_fps"])
        changed |= old != st["show_fps"]
        y += 40
        ui.text(screen, f"Сейчас игра рисуется в {cfg.SCREEN_W}×{cfg.SCREEN_H}. Масштаб 150–200% — для мониторов 2K/4K: "
                "картинка крупнее.", (x, W.bottom - 40), COL_TEXT_DIM, 13)
    elif game.settings_tab == 1:
        for key, label in (("master", "Общая громкость"), ("sfx", "Эффекты (удары, выстрелы)"),
                           ("ambient", "Фон (ветер)"), ("music", "Музыка (домбра)")):
            row(f"{label}: {st[key]}%", y)
            v = ui.slider(screen, key, (cx + 40, y + 10, cw - 40, 10), st[key])
            if v != st[key]:
                st[key] = v
                changed = True
                game.sound.update_volumes()
            y += 50
        old = st["muted"]
        st["muted"] = ui.checkbox(screen, (x, y, 300, 30), "Выключить весь звук (M)", st["muted"])
        if old != st["muted"]:
            st["muted"] = old
            game.sound.toggle_mute()
        y += 50
        if ui.button(screen, (x, y, 220, 32), "Проверить звук"):
            game.sound.play("hit")
            game.sound.play_music()
    else:
        ts = settings_mod.TIME_SPEEDS
        row("Скорость времени", y)
        speed = st["time_speed"]
        day_min = int(24 / speed)
        d = ui.selector(screen, (cx, y, cw, 30), f"{speed:g}×  (сутки — {day_min} мин)")
        if d:
            st["time_speed"] = ts[(ts.index(speed) + d) % len(ts)]
            changed = True
        y += 48
        old = st["hints"]
        st["hints"] = ui.checkbox(screen, (x, y, 400, 30), "Подсказки действий («[E] Обыскать» и т.п.)", st["hints"])
        changed |= old != st["hints"]
        y += 60
        ui.text(screen, "Режим бога — F10 или кнопка в меню паузы. Консоль — клавиша ` (Ё).", (x, y), COL_TEXT_DIM, 14)
        y += 50
        if ui.button(screen, (x, y, 260, 32), "Сбросить все настройки"):
            st.reset()
            game.pending_video = {k: st[k] for k in ("resolution", "display", "scale", "vsync")}
            game.apply_video()
            game.sound.update_volumes()
            changed = True
    if changed:
        st.save()


def draw_console(screen, ui, game):
    """Консоль разработчика (клавиша ` / Ё): ввод команд и вывод."""
    c = game.console
    h = int(cfg.SCREEN_H * 0.45)
    back = pygame.Surface((cfg.SCREEN_W, h), pygame.SRCALPHA)
    back.fill((10, 10, 8, 225))
    screen.blit(back, (0, 0))
    pygame.draw.line(screen, COL_ACCENT, (0, h), (cfg.SCREEN_W, h), 2)
    f = ui.font(15)
    line_h = 20
    max_lines = (h - 44) // line_h
    for i, (text, col) in enumerate(c.lines[-max_lines:]):
        screen.blit(f.render(text, True, col), (12, 8 + i * line_h))
    cursor = "_" if int(game.time_real * 2) % 2 else " "
    ui.text(screen, "> " + c.text + cursor, (12, h - 30), (255, 230, 160), 16)
    ui.text(screen, "help — список команд · Esc/` — закрыть", (cfg.SCREEN_W - 12, h - 28), COL_TEXT_DIM, 13, right=True)


def draw_pause(screen, ui, game):
    r = pygame.Rect(cfg.SCREEN_W // 2 - 170, cfg.SCREEN_H // 2 - 250, 340, 500)
    ui.panel(screen, r, "Пауза")
    y = r.y + 54
    hard = game.player.mode == "hard"
    items = [("Продолжить", game.close_window, True),
             ("Сохранить игру", game.save_game, not hard),
             ("Загрузить", game.load_game, save.exists()),
             ("Настройки", lambda: game.open_settings("pause"), True),
             ("Управление", lambda: game.open_window("help"), True),
             ("Режим бога: " + ("ВКЛ" if game.player.god else "выкл") + "  (F10)", game.toggle_god, True),
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
    shade = pygame.Surface((cfg.SCREEN_W, cfg.SCREEN_H), pygame.SRCALPHA)
    shade.fill((10, 8, 6, 200))
    screen.blit(shade, (0, 0))
    ui.text(screen, "АКТ II «КОЛОДЕЦ» ЗАВЕРШЁН", (cfg.SCREEN_W // 2, 200), COL_ACCENT, 34, bold=True, center=True)
    lines = [
        "Ты узнал правду: колодцы отравил бункер «Подземка», а источник беды —",
        "закрытый объект «Мелиорация-7» у самой границы.",
        "",
        "Продолжение — Акт III «Граница» и Акт IV «Объект» — в следующих версиях.",
        "А пока степь ждёт: выживай, обустраивай базу, помогай «Заре».",
    ]
    for i, l in enumerate(lines):
        ui.text(screen, l, (cfg.SCREEN_W // 2, 280 + i * 30), COL_TEXT, 18, center=True)
    if ui.button(screen, (cfg.SCREEN_W // 2 - 140, 480, 280, 42), "Продолжить выживать"):
        game.close_window()


# ====================================================================== экраны вне игры

def _menu_background(screen, t):
    """Степь на закате: пыльное небо, солнце, столбы ЛЭП и юрта на горизонте.
    Координаты считаются от размеров экрана, чтобы фон подходил под любое разрешение."""
    W, H = cfg.SCREEN_W, cfg.SCREEN_H
    hz = int(H * 0.653)          # линия горизонта
    for y in range(H):
        k = y / H
        col = (int(196 - 120 * k), int(150 - 100 * k), int(80 - 50 * k)) if y < hz else (int(70 - 20 * k), int(58 - 18 * k), int(40 - 12 * k))
        pygame.draw.line(screen, col, (0, y), (W, y))
    pygame.draw.circle(screen, (236, 190, 110), (int(W * 0.73), hz - 90), 70)
    pygame.draw.rect(screen, (60, 48, 34), (0, hz, W, H - hz))
    n = W // 170 + 3
    for i in range(n):
        x = (i * 170 - t * 12) % (n * 170) - 100
        pygame.draw.line(screen, (40, 30, 22), (x, hz), (x, hz - 110), 4)
        pygame.draw.line(screen, (40, 30, 22), (x - 20, hz - 98), (x + 20, hz - 98), 3)
        nx = x + 170
        for k in range(3):
            pts = [(x - 16 + 16 * k + (nx - x) * s / 10, hz - 96 + 18 * math.sin(math.pi * s / 10)) for s in range(11)]
            pygame.draw.lines(screen, (40, 30, 22), False, pts, 1)
    pygame.draw.ellipse(screen, (46, 36, 26), (180, hz - 70, 120, 90))    # купол юрты
    pygame.draw.rect(screen, (46, 36, 26), (180, hz - 30, 120, 32))
    pygame.draw.rect(screen, (46, 36, 26), (330, hz - 70, 90, 70))        # панелька рядом с юртой
    for k in range(3):
        for j in range(2):
            pygame.draw.rect(screen, (90, 70, 40), (342 + k * 26, hz - 58 + j * 26, 12, 14))


def draw_main_menu(screen, ui, game):
    _menu_background(screen, game.time_real)
    ui.text(screen, "ГРАНИЦА-99", (cfg.SCREEN_W // 2, 70), (40, 28, 18), 72, bold=True, center=True)
    ui.text(screen, "ГРАНИЦА-99", (cfg.SCREEN_W // 2 - 3, 67), (230, 200, 140), 72, bold=True, center=True)
    ui.text(screen, "Юг Казахстана, 1999 год. Степь, пыль и выбор.", (cfg.SCREEN_W // 2, 160), (250, 230, 190), 20, center=True)
    r = pygame.Rect(cfg.SCREEN_W // 2 - 160, 220, 320, 300)
    y = r.y
    items = [("Продолжить", game.load_game, save.exists()),
             ("Новая игра", game.to_creation, True),
             ("Настройки", lambda: game.open_settings(None), True),
             ("Управление", lambda: game.open_window("help"), True),
             ("Выход", game.quit, True)]
    for label, fn, en in items:
        if ui.button(screen, (r.x, y, r.w, 42), label, enabled=en and not game.window, size=18):
            fn()
            return
        y += 54
    ui.text(screen, f"Версия {VERSION} · вся графика и звук созданы кодом · см. CREDITS.md", (cfg.SCREEN_W // 2, cfg.SCREEN_H - 30), (200, 180, 140), 13, center=True)
    if game.window == "help":
        draw_help(screen, ui, game)
    elif game.window == "settings":
        draw_settings(screen, ui, game)


def draw_creation(screen, ui, game):
    _menu_background(screen, game.time_real)
    r = pygame.Rect(90, 40, cfg.SCREEN_W - 180, cfg.SCREEN_H - 80)
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
    shade = pygame.Surface((cfg.SCREEN_W, cfg.SCREEN_H), pygame.SRCALPHA)
    shade.fill((20, 4, 4, 210))
    screen.blit(shade, (0, 0))
    p = game.player
    days = game.clock.day - 1
    ui.text(screen, "ВЫ ПОГИБЛИ", (cfg.SCREEN_W // 2, 170), COL_RED, 48, bold=True, center=True)
    ui.text(screen, f"{p.name} прожил(а) в степи {days} {_days_word(days)}.", (cfg.SCREEN_W // 2, 250), COL_TEXT, 22, center=True)
    ui.text(screen, game.death_cause, (cfg.SCREEN_W // 2, 290), COL_TEXT_DIM, 17, center=True)
    ui.text(screen, f"Убито врагов: {p.kills} · Слов в словарике: {len(game.glossary)} · Заданий выполнено: {game.quests_done()}",
            (cfg.SCREEN_W // 2, 330), COL_TEXT_DIM, 16, center=True)
    if ui.button(screen, (cfg.SCREEN_W // 2 - 150, 400, 300, 42), "Новый персонаж", size=17):
        game.to_creation()
    if save.exists() and p.mode != "hard":
        if ui.button(screen, (cfg.SCREEN_W // 2 - 150, 452, 300, 42), "Загрузить сохранение", size=17):
            game.load_game()
    if ui.button(screen, (cfg.SCREEN_W // 2 - 150, 504, 300, 42), "Главное меню", size=17):
        game.to_menu()


def _days_word(n):
    if n % 10 == 1 and n % 100 != 11:
        return "день"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "дня"
    return "дней"
