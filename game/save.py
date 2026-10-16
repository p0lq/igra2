"""Сохранение и загрузка в JSON-файл.

Режимы (концепт, 7.11): «Обычный» — сохранение в любой момент через меню паузы
и автосохранение при сне; «Суровый» — только автосохранение, после смерти файл удаляется.
"""
import json
import os

from .config import save_dir, VERSION

SLOT = "slot1.json"


def path(slot=SLOT):
    return os.path.join(save_dir(), slot)


def exists(slot=SLOT):
    return os.path.exists(path(slot))


def save(game, slot=SLOT):
    data = {
        "version": VERSION,
        "zone": game.zone.id,
        "player": game.player.to_dict(),
        "clock": game.clock.to_dict(),
        "zones": {zid: z.to_dict() for zid, z in game.zones.items()},
        "enemies": {zid: [e.to_dict() for e in lst] for zid, lst in game.enemies_by_zone.items()},
        "npcs": [n.to_dict() for n in game.npcs],
        "quests": game.quests,
        "flags": sorted(game.flags),
        "rep": game.rep,
        "glossary": sorted(game.glossary),
        "radio_heard": sorted(game.radio_heard),
    }
    tmp = path(slot) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path(slot))   # сначала пишем во временный файл — сейв не побьётся при сбое


def load(slot=SLOT):
    with open(path(slot), encoding="utf-8") as f:
        return json.load(f)


def delete(slot=SLOT):
    if exists(slot):
        os.remove(path(slot))
