"""Отрисовка мира: земля, объекты и персонажи с сортировкой по глубине, свет и погода.

Порядок отрисовки в изометрии: чем больше (x + y), тем ближе к зрителю,
поэтому всё сортируется по сумме координат и рисуется от дальнего к ближнему.
"""
import math
import random

import pygame

from .config import TILE_W, TILE_H, HALF_W, HALF_H, WALL_H
from . import config as cfg
from .iso import to_screen, to_tile
from .data import OBJECTS
from . import art, ai

_dark = None
_tint = None
_particles = [(random.uniform(0, cfg.SCREEN_W), random.uniform(0, cfg.SCREEN_H), random.uniform(0.6, 1.4)) for _ in range(160)]


def visible_range(game):
    """Какие клетки попадают на экран (с запасом для высоких спрайтов)."""
    cam = game.cam
    corners = [to_tile(0, -120, cam), to_tile(cfg.SCREEN_W, -120, cam), to_tile(0, cfg.SCREEN_H + 60, cam), to_tile(cfg.SCREEN_W, cfg.SCREEN_H + 60, cam)]
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    z = game.zone
    return (max(0, int(min(xs)) - 1), max(0, int(min(ys)) - 1), min(z.w - 1, int(max(xs)) + 1), min(z.h - 1, int(max(ys)) + 1))


def draw_world(screen, game):
    z = game.zone
    cam = game.cam
    p = game.player
    x0, y0, x1, y1 = visible_range(game)
    t_now = game.time_real

    # --- 1. земля
    gt = art.GROUND_TILES
    for ty in range(y0, y1 + 1):
        row = z.ground[ty]
        for tx in range(x0, x1 + 1):
            sx = (tx - ty) * HALF_W - cam.x
            sy = (tx + ty) * HALF_H - cam.y
            if sx < -TILE_W or sx > cfg.SCREEN_W + TILE_W or sy < -TILE_H or sy > cfg.SCREEN_H + 10:
                continue
            screen.blit(gt[row[tx]][(tx * 7 + ty * 13) % 4], (sx - HALF_W, sy))

    # подсветка клетки, на которую можно нажать
    hov = game.hover_tile
    if hov and z.get(*hov) is not None:
        sx, sy = to_screen(hov[0], hov[1], cam)
        pygame.draw.polygon(screen, (230, 200, 120), [(sx, sy), (sx + HALF_W, sy + HALF_H), (sx, sy + TILE_H), (sx - HALF_W, sy + HALF_H)], 1)

    # --- 2. объекты и персонажи, отсортированные по глубине
    draw_list = []
    pdepth = p.x + p.y
    for ty in range(y0, y1 + 1):
        orow = z.obj[ty]
        for tx in range(x0, x1 + 1):
            o = orow[tx]
            if o is not None:
                draw_list.append((tx + ty + 1.0, 0, tx, ty, o))
    for e in game.enemies:
        draw_list.append((e.x + e.y, 1, e))
    for n in game.visible_npcs():
        draw_list.append((n.x + n.y, 2, n))
    if not p.dead():
        draw_list.append((pdepth, 3, p))
    draw_list.sort(key=lambda d: d[0])

    for d in draw_list:
        kind = d[1]
        if kind == 0:
            _, _, tx, ty, o = d
            _draw_object(screen, game, tx, ty, o, pdepth, t_now)
        elif kind == 1:
            _draw_enemy(screen, game, d[2])
        elif kind == 2:
            _draw_npc(screen, game, d[2])
        else:
            _draw_player(screen, game)

    # --- 3. эффекты: трассеры выстрелов, всплывающий текст
    for fx in game.effects:
        if fx["type"] == "tracer":
            a = to_screen(fx["x0"], fx["y0"], cam)
            b = to_screen(fx["x1"], fx["y1"], cam)
            pygame.draw.line(screen, (255, 230, 150), (a[0], a[1] - 26), (b[0], b[1] - 22), 2)
        elif fx["type"] == "blood":
            sx, sy = to_screen(fx["x"], fx["y"], cam)
            for i in range(5):
                pygame.draw.circle(screen, (130, 20, 20), (sx + math.cos(i * 1.3) * 8 * (1 - fx["t"]), sy - 20 + math.sin(i * 2.1) * 6), 2)

    _draw_light(screen, game)
    _draw_weather(screen, game)

    for f in game.floats:
        sx, sy = to_screen(f["x"], f["y"], cam)
        img = game.ui.font(14).render(f["text"], True, f["color"])
        screen.blit(img, (sx - img.get_width() // 2, sy - 64 - (1.5 - f["t"]) * 20))


def _draw_object(screen, game, tx, ty, o, pdepth, t_now):
    cam = game.cam
    sx = (tx - ty) * HALF_W - cam.x
    sy = (tx + ty) * HALF_H - cam.y
    if sx < -120 or sx > cfg.SCREEN_W + 120 or sy < -40 or sy > cfg.SCREEN_H + 140:
        return
    info = OBJECTS.get(o, {})
    if info.get("wall"):
        key = o if o in art.WALL_SPRITES else "wall"
        p = game.player
        # стена между игроком и камерой становится полупрозрачной (как в Project Zomboid)
        if tx + ty + 1 > pdepth and abs(tx + 0.5 - p.x) + abs(ty + 0.5 - p.y) < 5 and abs((tx - ty) - (p.x - p.y)) < 4.5:
            key += "_a"
        screen.blit(art.WALL_SPRITES[key], (sx - HALF_W, sy - WALL_H))
        return
    spr = art.SPRITES.get(o)
    if spr is None:
        return
    s, ax, ay = spr
    screen.blit(s, (sx - ax, sy + HALF_H - ay))
    if info.get("fire") and game.zone.fires.get(f"{tx},{ty}", 0) > 0:
        if o == "campfire":
            art.draw_flame(screen, sx, sy + HALF_H - 2, t_now + tx)
        else:
            pygame.draw.rect(screen, (255, 160, 50), (sx - 9, sy + HALF_H - 14, 6, 5))


def _flash(look, t):
    if t <= 0:
        return look
    l = dict(look)
    l["body"] = (220, 60, 50)
    l["skin"] = (230, 120, 110)
    return l


def _draw_enemy(screen, game, e):
    sx, sy = to_screen(e.x, e.y, game.cam)
    if sx < -60 or sx > cfg.SCREEN_W + 60 or sy < -40 or sy > cfg.SCREEN_H + 80:
        return
    t = e.t
    if e.kind == "dog":
        art.draw_dog(screen, sx, sy, e.face_right, e.phase, (200, 70, 60) if e.hit_flash > 0 else (120, 100, 76))
    else:
        looks = ai.LOOKS[t["look"]]
        look = _flash(looks[e.look_i % len(looks)], e.hit_flash)
        hunch = 0.0 if e.kind == "bandit" else (1.0 if e.kind == "cougher" else 0.6)
        art.draw_human(screen, sx, sy, look, e.face_right, e.phase, hunch, t.get("scale", 1.0),
                       weapon="gun" if e.kind == "bandit" else None, attack=e.attack_anim)
    # полоска здоровья у раненого врага
    if e.hp < t["hp"]:
        w = 28
        pygame.draw.rect(screen, (40, 10, 10), (sx - w // 2, sy - 62 * t.get("scale", 1), w, 4))
        pygame.draw.rect(screen, (200, 50, 40), (sx - w // 2, sy - 62 * t.get("scale", 1), int(w * e.hp / t["hp"]), 4))


def _draw_npc(screen, game, n):
    sx, sy = to_screen(n.x, n.y, game.cam)
    art.draw_human(screen, sx, sy, n.data["look"], n.face_right, n.phase if n.moving else 0)
    p = game.player
    if math.hypot(n.x - p.x, n.y - p.y) < 6:
        img = game.ui.font(13).render(n.name, True, (230, 210, 160))
        screen.blit(img, (sx - img.get_width() // 2, sy - 66))


def _draw_player(screen, game):
    p = game.player
    sx, sy = to_screen(p.x, p.y, game.cam)
    st, it = p.weapon()
    weapon = None
    if it:
        weapon = "gun" if it["type"] == "gun" else "melee"
    look = {"body": (86, 96, 110), "legs": (60, 66, 80), "skin": (214, 170, 130)}
    body = p.equip["body"]
    if body:
        look["body"] = {"vatnik": (70, 80, 70), "chapan": (130, 60, 80), "jacket": (40, 80, 130)}.get(body["id"], look["body"])
    if p.equip["face"]:
        look["hat"] = "mask"
    look = _flash(look, p.hit_flash)
    art.draw_human(screen, sx, sy, look, p.face_right, p.walk_phase if p.moving else 0,
                   weapon=weapon, attack=p.attack_anim, crouch=p.sneaking)


def _draw_light(screen, game):
    """Ночь: экран заливается тьмой, из неё «вырезаются» круги света (фонарь, костры)."""
    global _dark
    dark = game.darkness()
    if game.player.has("badsight"):
        dark = min(0.95, dark * 1.12)
    if dark <= 0.02:
        return
    if _dark is None or _dark.get_size() != (cfg.SCREEN_W, cfg.SCREEN_H):
        _dark = pygame.Surface((cfg.SCREEN_W, cfg.SCREEN_H), pygame.SRCALPHA)
    _dark.fill((6, 6, 18, int(245 * dark)))
    cam = game.cam
    p = game.player
    psx, psy = to_screen(p.x, p.y, cam)

    def cut(x, y, r):
        m = art.light_mask(r)
        _dark.blit(m, (x - r, y - r // 2), special_flags=pygame.BLEND_RGBA_SUB)

    cut(psx, psy - 10, 70)   # видно самого себя
    if p.has_light():
        lx, ly = to_screen(p.x + p.fx * 3.2, p.y + p.fy * 3.2, cam)
        cut(lx, ly, 230)
        cut(psx + (lx - psx) * 0.4, psy + (ly - psy) * 0.4, 150)
    z = game.zone
    x0, y0, x1, y1 = visible_range(game)
    flick = 1 + 0.06 * math.sin(game.time_real * 11)
    for key, fuel in z.fires.items():
        if fuel <= 0:
            continue
        fx, fy = map(int, key.split(","))
        if x0 - 6 <= fx <= x1 + 6 and y0 - 6 <= fy <= y1 + 6:
            sx, sy = to_screen(fx + 0.5, fy + 0.5, cam)
            r = OBJECTS[z.get(fx, fy)].get("light", 4) * 34 * flick if z.get(fx, fy) else 0
            if r:
                cut(sx, sy, r)
    if z.dark and "ladder" in z.markers:
        lx, ly = z.markers["ladder"]
        sx, sy = to_screen(lx + 0.5, ly + 0.5, cam)
        cut(sx, sy, 120)
    screen.blit(_dark, (0, 0))


def _draw_weather(screen, game):
    """Пыльная буря, Пыльный фронт (жёлтое небо) и ливень."""
    global _tint
    clock = game.clock
    if game.zone.dark:
        return
    indoor = game.zone.indoor(int(game.player.x), int(game.player.y))
    if _tint is None or _tint.get_size() != (cfg.SCREEN_W, cfg.SCREEN_H):
        _tint = pygame.Surface((cfg.SCREEN_W, cfg.SCREEN_H), pygame.SRCALPHA)
    col = None
    if clock.front:
        col = (220, 180, 50, 95 if not indoor else 45)
    elif clock.weather == "storm":
        col = (190, 150, 90, 110 if not indoor else 40)
    elif clock.weather == "rain":
        col = (70, 80, 100, 60)
    if col is None:
        return
    _tint.fill(col)
    screen.blit(_tint, (0, 0))
    t = game.time_real
    if clock.weather == "rain":
        for i, (x, y, s) in enumerate(_particles):
            px = (x - t * 120 * s) % cfg.SCREEN_W
            py = (y + t * 600 * s) % cfg.SCREEN_H
            pygame.draw.line(screen, (170, 180, 200), (px, py), (px - 3, py + 12))
    elif not indoor:
        c = (230, 200, 110) if clock.front else (210, 180, 120)
        for i, (x, y, s) in enumerate(_particles):
            px = (x + t * 420 * s) % cfg.SCREEN_W
            py = (y + math.sin(t * 2 + i) * 20 + t * 40 * s) % cfg.SCREEN_H
            pygame.draw.line(screen, c, (px, py), (px + 10 * s, py + 2))
