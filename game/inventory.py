"""Инвентарь: список «стопок» предметов.

Стопка — словарь {"id": "tushenka", "n": 3}. У некоторых предметов есть личные
свойства, и они не складываются в стопку:
  dur      — прочность оружия,
  loaded   — патронов в магазине,
  filter   — ресурс фильтра респиратора/противогаза (минуты),
  battery  — заряд фонарика (минуты),
  read     — записка прочитана/переведена.
"""
from .data import ITEMS

UNIQUE_TYPES = {"weapon", "gun", "clothing", "note"}


def stackable(item_id):
    return ITEMS[item_id]["type"] not in UNIQUE_TYPES


def new_stack(item_id, n=1):
    it = ITEMS[item_id]
    st = {"id": item_id, "n": n}
    if "dur" in it:
        st["dur"] = it["dur"]
    if it["type"] == "gun":
        st["loaded"] = 0
    if "filter" in it:
        st["filter"] = it["filter"]
    if "battery" in it:
        st["battery"] = it["battery"]
    if it["type"] == "note":
        st["read"] = it.get("lang") == "ru"
    return st


def add(inv, item_id, n=1, stack=None):
    """Положить предметы в список. stack — готовая стопка (с прочностью и т.п.)."""
    if stack is not None:
        if stackable(stack["id"]):
            return add(inv, stack["id"], stack["n"])
        inv.append(stack)
        return
    if stackable(item_id):
        for st in inv:
            if st["id"] == item_id:
                st["n"] += n
                return
        inv.append(new_stack(item_id, n))
    else:
        for _ in range(n):
            inv.append(new_stack(item_id, 1))


def count(inv, item_id):
    return sum(st["n"] for st in inv if st["id"] == item_id)


def find(inv, item_id):
    for st in inv:
        if st["id"] == item_id:
            return st
    return None


def remove(inv, item_id, n=1):
    """Убрать n штук. Возвращает True, если хватило."""
    if count(inv, item_id) < n:
        return False
    for st in list(inv):
        if st["id"] != item_id:
            continue
        take = min(n, st["n"])
        st["n"] -= take
        n -= take
        if st["n"] <= 0:
            inv.remove(st)
        if n == 0:
            break
    return True


def remove_stack(inv, st, n=1):
    st["n"] -= n
    if st["n"] <= 0 and st in inv:
        inv.remove(st)


def weight(inv):
    return sum(ITEMS[st["id"]]["w"] * st["n"] for st in inv)


def value(st):
    return ITEMS[st["id"]].get("value", 0)


def sort_key(st):
    order = ["weapon", "gun", "ammo", "food", "drink", "medical", "clothing", "material", "book", "note", "misc"]
    t = ITEMS[st["id"]]["type"]
    return (order.index(t) if t in order else 99, ITEMS[st["id"]]["name"])


def label(st):
    """Подпись стопки для списков: имя, количество, прочность."""
    it = ITEMS[st["id"]]
    s = it["name"]
    if st["n"] > 1:
        s += f" ×{st['n']}"
    if "dur" in st and it.get("dur"):
        s += f"  [{int(100 * st['dur'] / it['dur'])}%]"
    if it["type"] == "gun":
        s += f"  ({st.get('loaded', 0)}/{it['mag']})"
    if "filter" in st:
        s += f"  [фильтр {int(st['filter'] / 60)} ч]"
    if "battery" in st:
        s += f"  [заряд {int(100 * st['battery'] / it['battery'])}%]"
    return s
