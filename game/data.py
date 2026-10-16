"""Загрузка игровых данных из папки data/ (JSON). Всё, что можно расширять без кода, лежит там."""
import json
from .config import resource_path


def _load(name):
    with open(resource_path("data", name), encoding="utf-8") as f:
        d = json.load(f)
    d.pop("_comment", None)
    return d


ITEMS = _load("items.json")
RECIPES = _load("recipes.json")
OBJECTS = _load("objects.json")
LOOT = _load("loot.json")
GLOSSARY = _load("glossary.json")
QUESTS = _load("quests.json")
DIALOGUES = _load("dialogues.json")
CHARACTER = _load("character.json")
RADIO = _load("radio.json")
NPCS = _load("npcs.json")

SKILLS = CHARACTER["skills"]
TRAITS = CHARACTER["traits"]


def item(item_id):
    return ITEMS[item_id]


def obj(obj_id):
    """Свойства объекта карты; для None возвращает пустой словарь."""
    if obj_id is None:
        return {}
    return OBJECTS.get(obj_id, {})
