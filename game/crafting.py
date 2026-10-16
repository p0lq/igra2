"""Крафт: проверка рецепта, трата ресурсов, создание предмета или постройки.

Рецепты лежат в data/recipes.json. Станции:
  fire      — рядом горящий костёр или буржуйка (до 2.5 клеток),
  workbench — рядом верстак.
"""
import math

from .data import RECIPES, ITEMS, OBJECTS, SKILLS
from . import inventory as inv

FUEL = {"campfire": 180, "burzhuika": 240}   # сколько минут горит после розжига


def stations_near(game):
    p = game.player
    zone = game.zone
    found = set()
    for y in range(int(p.y) - 3, int(p.y) + 4):
        for x in range(int(p.x) - 3, int(p.x) + 4):
            o = zone.get(x, y)
            if o is None or math.hypot(x + 0.5 - p.x, y + 0.5 - p.y) > 2.5:
                continue
            info = OBJECTS.get(o, {})
            if info.get("fire") and zone.fires.get(f"{x},{y}", 0) > 0:
                found.add("fire")
            if info.get("workbench"):
                found.add("workbench")
    return found


def missing(player, rid, stations):
    """Чего не хватает для рецепта (список строк). Пустой список — можно делать."""
    r = RECIPES[rid]
    out = []
    for iid, n in r["in"].items():
        have = inv.count(player.items, iid)
        if have < n:
            out.append(f"{ITEMS[iid]['name']} ({have}/{n})")
    for t in r.get("tools", []):
        if inv.count(player.items, t) == 0 and not _equipped(player, t):
            out.append(ITEMS[t]["name"])
    st = r.get("station")
    if st and st not in stations:
        out.append("рядом нужен " + ("огонь" if st == "fire" else "верстак"))
    return out


def _equipped(player, iid):
    return any(s and s["id"] == iid for s in player.equip.values())


def describe(rid):
    r = RECIPES[rid]
    parts = [f"{ITEMS[i]['name']} ×{n}" for i, n in r["in"].items()]
    if r.get("tools"):
        parts.append("инструмент: " + ", ".join(ITEMS[t]["name"] for t in r["tools"]))
    if r.get("station"):
        parts.append("у огня" if r["station"] == "fire" else "у верстака")
    if "out" in r:
        res = ", ".join(f"{ITEMS[i]['name']} ×{n}" for i, n in r["out"].items())
    else:
        res = OBJECTS[r["place"]]["name"] + " (постройка)"
    return res, "; ".join(parts)


def start(game, rid):
    """Начать крафт: это «долгое действие», игрок стоит и работает несколько секунд."""
    p = game.player
    stations = stations_near(game)
    miss = missing(p, rid, stations)
    if miss:
        game.log("Не хватает: " + ", ".join(miss), "bad")
        return False
    r = RECIPES[rid]
    t = r.get("time", 3) * max(0.4, 1 - 0.07 * p.lvl(r.get("skill", "survival")))
    game.start_action(f"Делаю: {r['name']}", t, lambda: finish(game, rid), noise=3)
    return True


def finish(game, rid):
    p = game.player
    r = RECIPES[rid]
    if missing(p, rid, stations_near(game)):
        game.log("Не получилось — чего-то не хватает.", "bad")
        return
    if "place" in r:
        spot = game.free_spot_in_front()
        if spot is None:
            game.log("Здесь некуда поставить.", "bad")
            return
    for iid, n in r["in"].items():
        inv.remove(p.items, iid, n)
    if "out" in r:
        for iid, n in r["out"].items():
            inv.add(p.items, iid, n)
        game.log(f"Готово: {RECIPES[rid]['name']}.", "good")
    else:
        x, y = spot
        game.zone.set(x, y, r["place"])
        if r["place"] in FUEL:
            game.zone.fires[f"{x},{y}"] = FUEL[r["place"]]
        game.log(f"Построено: {OBJECTS[r['place']]['name']}.", "good")
    # «Фильтр для воды» изнашивается
    if "water_filter" in r.get("tools", []) and r["in"].get("water_dirty"):
        game.wear_tool("water_filter", 0.1)
    msg = p.add_xp(r.get("skill", "survival"), 15)
    if msg:
        game.log(msg, "good")
    game.sound.play("craft")
