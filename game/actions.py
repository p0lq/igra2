"""Действия игрока: использование предметов, обыск контейнеров, двери, окна,
колодцы, костры, сон, торговля. Здесь «что происходит, когда игрок что-то делает»."""
import math
import random

from .data import ITEMS, LOOT, OBJECTS
from . import inventory as inv

# ====================================================================== предметы


def use_item(game, st):
    """Главное действие предмета (съесть, выпить, надеть, прочитать...)."""
    p = game.player
    it = ITEMS[st["id"]]
    t = it["type"]
    if t in ("food", "drink"):
        _consume(game, st, it)
    elif t == "medical":
        med = it["med"]
        if med == "painkiller":
            p.painkiller = 240
            p.mood = min(100, p.mood + 5)
            game.log("Принял анальгин. Боль отступает.", "good")
        elif med == "charcoal":
            p.poison = max(0, p.poison - 50)
            game.log("Выпил уголь. Тошнота проходит.", "good")
        elif med == "antidote":
            p.disease = max(0, p.disease - 60)
            game.log("Укол антидота. Голова проясняется.", "good")
        else:
            game.open_window("health")
            return
        inv.remove_stack(p.items, st)
    elif t in ("clothing", "weapon", "gun"):
        equip(game, st)
    elif t == "book":
        read_book(game, st)
    elif t == "note":
        game.open_note(st)
    elif it.get("radio"):
        game.open_radio()
    elif "refill" in it:
        face = p.equip["face"]
        if face and face["id"] == "gasmask":
            face["filter"] = min(900, face.get("filter", 0) + it["refill"])
            inv.remove_stack(p.items, st)
            game.log("Вставил фильтр в противогаз.", "good")
        else:
            game.log("Сначала надень противогаз.", "bad")
    elif "recharge" in it:
        light = p.equip["light"] or inv.find(p.items, "flashlight")
        if light:
            light["battery"] = ITEMS["flashlight"]["battery"]
            inv.remove_stack(p.items, st)
            game.log("Поменял батарейки в фонарике.", "good")
        else:
            game.log("Нет фонарика.", "bad")
    else:
        game.log("Это нельзя использовать.", "info")


def _consume(game, st, it):
    p = game.player
    p.hunger = max(0, min(100, p.hunger + it.get("hunger", 0)))
    p.thirst = max(0, min(100, p.thirst + it.get("thirst", 0)))
    p.mood = max(0, min(100, p.mood + it.get("mood", 0)))
    p.temp += it.get("temp", 0)
    if "disease" in it:
        p.disease = max(0, p.disease + it["disease"])
    if it.get("smoke"):
        p.since_smoke = 0
    if "poison" in it:
        chance = it.get("poison_chance", 1.0)
        amount = it["poison"]
        if p.has("stomach"):
            chance /= 2
            amount /= 2
        if random.random() < chance:
            p.poison = min(100, p.poison + amount)
            game.log("Живот скрутило... Похоже на отравление.", "bad")
    verb = "Выпил" if it["type"] == "drink" else ("Выкурил" if it.get("smoke") else "Съел")
    game.log(f"{verb}: {it['name']}.", "info")
    game.sound.play("eat")
    inv.remove_stack(p.items, st)
    if "leaves" in it:
        inv.add(p.items, it["leaves"])


def quick_use(game, st):
    """ПКМ в инвентаре: съесть/надеть/прочитать без лишних кликов."""
    if st in game.player.items:
        use_item(game, st)


def equip(game, st):
    p = game.player
    it = ITEMS[st["id"]]
    slot = "weapon" if it["type"] in ("weapon", "gun") else it["slot"]
    if st in p.items:
        p.items.remove(st)
    old = p.equip[slot]
    if old:
        p.items.append(old)
    p.equip[slot] = st
    game.log(f"{'Взял в руки' if slot == 'weapon' else 'Надел'}: {it['name']}.", "info")
    if game.sel_item is st:
        game.sel_item = None


def unequip(game, slot):
    p = game.player
    st = p.equip[slot]
    if st:
        p.equip[slot] = None
        p.items.append(st)
        if slot == "light":
            p.flashlight_on = False


def read_book(game, st):
    p = game.player
    it = ITEMS[st["id"]]
    if st["id"] in p.read_books:
        game.log("Уже прочитано.", "info")
        return

    def done():
        p.read_books.add(st["id"])
        from .dialogue import apply
        for r in it.get("unlock", []):
            apply(game, f"learn:{r}")
        if "xp" in it:
            apply(game, f"xp:{it['xp'][0]}:{it['xp'][1]}")
        for w in it.get("glossary", []):
            apply(game, f"glossary:{w}")
        p.mood = min(100, p.mood + 8)
        game.log(f"Прочитал: {it['name']}.", "good")
    game.close_window()
    game.start_action(f"Читаю: {it['name']}", 6, done)


def reload_gun(game):
    p = game.player
    st, it = p.weapon()
    if not it or it["type"] != "gun":
        return
    need = it["mag"] - st.get("loaded", 0)
    have = inv.count(p.items, it["ammo"])
    if need <= 0:
        game.log("Оружие заряжено.", "info")
        return
    if have <= 0:
        game.log("Нет патронов.", "bad")
        return

    def done():
        n = min(need, inv.count(p.items, it["ammo"]))
        inv.remove(p.items, it["ammo"], n)
        st["loaded"] = st.get("loaded", 0) + n
        game.log(f"Зарядил: {st['loaded']}/{it['mag']}.", "info")
    game.start_action("Перезарядка", 1.6, done, noise=2)


def drop(game, st):
    p = game.player
    if st in p.items:
        p.items.remove(st)
    key = game.ground_pile(int(p.x), int(p.y))
    if key is None:
        p.items.append(st)
        game.log("Здесь некуда положить.", "bad")
        return
    inv.add(game.zone.containers[key]["items"], st["id"], st["n"], stack=st)
    game.sel_item = None


def rip(game, st):
    p = game.player
    p.items.remove(st)
    inv.add(p.items, "rag", 3)
    game.log("Порвал одежду на тряпки (3 шт.).", "info")
    game.sel_item = None


def item_actions(game, st, where):
    """Кнопки для выбранного предмета в окне инвентаря."""
    p = game.player
    it = ITEMS[st["id"]]
    t = it["type"]
    out = []
    if where == "container":
        out.append(("Взять", lambda: take_from_container(game, st, st["n"])))
        return out
    if t == "food":
        out.append(("Выкурить" if it.get("smoke") else "Съесть", lambda: use_item(game, st)))
    elif t == "drink":
        out.append(("Выпить", lambda: use_item(game, st)))
    elif t == "medical":
        out.append(("Лечиться" if it["med"] in ("bandage", "bandage_dirty", "disinfect", "splint") else "Принять", lambda: use_item(game, st)))
    elif t in ("weapon", "gun"):
        out.append(("Взять в руки", lambda: equip(game, st)))
    elif t == "clothing":
        out.append(("Надеть", lambda: equip(game, st)))
        out.append(("Порвать на тряпки", lambda: rip(game, st)))
    elif t in ("book", "note"):
        out.append(("Читать", lambda: use_item(game, st)))
    elif it.get("radio"):
        out.append(("Слушать эфир", lambda: use_item(game, st)))
    elif "refill" in it or "recharge" in it:
        out.append(("Использовать", lambda: use_item(game, st)))
    if game.container_items() is not None:
        out.append(("Положить в контейнер", lambda: move_to_container(game, st, st["n"])))
    elif not it.get("quest_item"):
        out.append(("Выбросить", lambda: drop(game, st)))
    return out


# ====================================================================== контейнеры


def roll_loot(kind, rnd=random):
    """Сгенерировать содержимое контейнера по таблице добычи."""
    table = LOOT.get(kind, LOOT["none"])
    items = []
    if not table["items"]:
        return items
    weights = [row[1] for row in table["items"]]
    for _ in range(rnd.randint(*table["rolls"])):
        iid, _, a, b = rnd.choices(table["items"], weights)[0]
        inv.add(items, iid, rnd.randint(a, b))
    return items


def take_from(game, items, st):
    """Взять стопку из списка (контейнер, куча на земле) в инвентарь."""
    p = game.player
    if items is None or st not in items:
        return
    if not p.god and ITEMS[st["id"]]["w"] * st["n"] + p.weight() > p.carry_limit() * 1.5:
        game.log("Слишком тяжело — не унести.", "bad")
        return
    items.remove(st)
    inv.add(p.items, st["id"], st["n"], stack=st)
    game.sound.play("pickup")
    from .dialogue import apply
    for e in ITEMS[st["id"]].get("on_pickup", []):
        apply(game, e)
    if game.sel_item is st:
        game.sel_item = None


def put_into(game, items, st):
    """Положить стопку из инвентаря в контейнер."""
    p = game.player
    if items is None or st not in p.items:
        return
    if ITEMS[st["id"]].get("quest_item"):
        game.log("Это лучше оставить при себе.", "info")
        return
    p.items.remove(st)
    inv.add(items, st["id"], st["n"], stack=st)
    if game.sel_item is st:
        game.sel_item = None


def fits_slot(item_id, slot):
    """Можно ли надеть предмет в этот слот снаряжения."""
    it = ITEMS[item_id]
    if slot == "weapon":
        return it["type"] in ("weapon", "gun")
    return it["type"] == "clothing" and it.get("slot") == slot


def take_from_container(game, st, n=None):
    take_from(game, game.container_items(), st)


def take_all(game):
    items = game.container_items()
    for st in list(items or []):
        take_from(game, items, st)


def move_to_container(game, st, n=None):
    put_into(game, game.container_items(), st)


# ====================================================================== лечение


def treatments_for(game, wound):
    """Какими предметами из инвентаря можно помочь этой ране."""
    p = game.player
    out = []
    if not wound.get("bandaged"):
        for iid, label in (("bandage", "Бинт"), ("bandage_home", "Самод. бинт"), ("rag", "Тряпка")):
            if inv.count(p.items, iid):
                out.append((f"Перевязать: {label}", iid))
                break
    if not wound.get("disinfected"):
        for iid, label in (("antiseptic", "зелёнка"), ("vodka", "водка")):
            if inv.count(p.items, iid):
                out.append((f"Обработать: {label}", iid))
                break
    if wound["type"] == "Перелом" and not wound.get("splinted") and inv.count(p.items, "splint"):
        out.append(("Наложить шину", "splint"))
    return out


def treat(game, wound, iid):
    p = game.player
    it = ITEMS[iid]
    med = "disinfect" if it.get("antiseptic") else it["med"]
    msg = p.treat(wound, med)
    inv.remove(p.items, iid, 1)
    game.log(msg, "good")
    x = p.add_xp("firstaid", 20)
    if x:
        game.log(x, "good")


# ====================================================================== торговля


def trade_prices(game):
    """Коэффициенты цен: за сколько NPC берёт твоё и отдаёт своё."""
    p = game.player
    lvl = p.lvl("trade")
    rep = game.rep.get("zarya", 0)
    sell_k = min(1.0, 0.6 + 0.04 * lvl + rep / 400)
    buy_k = max(1.0, 1.6 - 0.05 * lvl - rep / 200)
    return sell_k, buy_k


def trade_totals(game):
    t = game.trade
    sell_k, buy_k = trade_prices(game)
    give = sum(int(inv.value(t["give_ref"][k]) * sell_k) * n for k, n in t["give"].items() if n)
    take = sum(int(ITEMS[k]["value"] * buy_k + 0.5) * n for k, n in t["take"].items() if n)
    return give, take


def do_trade(game):
    p = game.player
    t = game.trade
    npc = t["npc"]
    give, take = trade_totals(game)
    for k, n in t["give"].items():
        if not n:
            continue
        st = t["give_ref"][k]
        if st in p.items:
            inv.remove_stack(p.items, st, n)
            npc.stock[st["id"]] = npc.stock.get(st["id"], 0) + n
    for k, n in t["take"].items():
        if n:
            npc.stock[k] -= n
            inv.add(p.items, k, n)
    t["give"].clear()
    t["take"].clear()
    t["give_ref"].clear()
    game.log("Сделка состоялась.", "good")
    msg = p.add_xp("trade", 10 + take // 5)
    if msg:
        game.log(msg, "good")
    game.sound.play("pickup")


# ====================================================================== мир


def interact(game, x, y):
    """Взаимодействие с объектом на клетке (x, y): клавиша E или правая кнопка мыши."""
    p = game.player
    z = game.zone
    o = z.get(x, y)
    info = OBJECTS.get(o, {})
    key = f"{x},{y}"

    if info.get("door"):
        if o in ("door", "door_metal"):
            z.set(x, y, "door_open" if o == "door" else "door_metal_open")
            game.noise(x + 0.5, y + 0.5, 3)
        else:
            if game.entity_on_tile(x, y):
                return
            z.set(x, y, "door" if o == "door_open" else "door_metal")
            z.obj_hp.pop(key, None)
        game.sound.play("door")
        return

    if info.get("window"):
        if o == "window_boarded":
            game.log("Окно заколочено.", "info")
            return
        climb_window(game, x, y, o)
        return

    if key in z.containers:
        c = z.containers[key]

        def opened():
            if c["items"] is None:
                c["items"] = roll_loot(c["kind"])
                x2 = p.add_xp("survival", 3)
                if x2:
                    game.log(x2, "good")
            game.open_container(key)
        t = 1.4 if c["items"] is None else 0.4
        game.start_action(f"Обыскиваю: {info.get('name', 'тайник')}", t, opened, noise=4 if c["items"] is None else 0)
        return

    if "water" in info:
        if inv.count(p.items, "bottle_empty"):
            def fill():
                n = inv.count(p.items, "bottle_empty")
                inv.remove(p.items, "bottle_empty", n)
                inv.add(p.items, "water_dirty", n)
                game.log(f"Набрал грязной воды: {n} бут. Вскипяти перед питьём!", "info")
            game.start_action("Набираю воду", 2, fill, noise=2)
        else:
            def drink():
                it = ITEMS["water_dirty"]
                p.thirst = max(0, p.thirst - 30)
                chance = it["poison_chance"] / (2 if p.has("stomach") else 1)
                if random.random() < chance:
                    p.poison = min(100, p.poison + it["poison"] / (2 if p.has("stomach") else 1))
                    game.log("Вода горчит железом... Живот болит.", "bad")
                else:
                    game.log("Напился из колодца. Повезло.", "info")
            game.start_action("Пью из колодца", 2, drink, noise=1)
        return

    if info.get("chop"):
        if not game.has_tool("chop"):
            game.log("Саксаул голыми руками не сломать — нужен топор.", "bad")
            return

        def chopped():
            inv.add(p.items, "brushwood", random.randint(2, 3))
            game.log("Нарубил хвороста.", "good")
            game.wear_tool("chop", 2)
            if random.random() < 0.35:
                z.remove(x, y)
            x2 = p.add_xp("survival", 8)
            if x2:
                game.log(x2, "good")
        game.start_action("Рублю саксаул", 4, chopped, noise=7)
        return

    if "pick" in info:
        def picked():
            inv.add(p.items, info["pick"], random.randint(1, 2))
            z.remove(x, y)
            game.log("Собрал верблюжью колючку.", "good")
        game.start_action("Собираю колючку", 1.5, picked)
        return

    if info.get("bed"):
        game.try_sleep(bed=True)
        return

    if info.get("fire"):
        fuel = z.fires.get(key, 0)
        for fuel_item, mins in (("brushwood", 90), ("planks", 120)):
            if inv.count(p.items, fuel_item):
                if fuel <= 0 and not inv.count(p.items, "matches"):
                    game.log("Нужны спички, чтобы разжечь.", "bad")
                    return
                if fuel <= 0:
                    inv.remove(p.items, "matches", 1)
                inv.remove(p.items, fuel_item, 1)
                z.fires[key] = max(0, fuel) + mins
                game.log("Подбросил топлива в огонь.", "good")
                return
        if fuel > 0:
            game.open_window("craft")
        else:
            game.log("Огонь погас. Нужен хворост или доски.", "info")
        return

    if info.get("workbench"):
        game.open_window("craft")
        return

    if info.get("collector"):
        water = z.collectors.get(key, 0)
        n = min(int(water), inv.count(p.items, "bottle_empty"))
        if n <= 0:
            game.log(f"В сборщике {water:.1f} л. Нужна пустая бутылка." if water >= 1 else "Сборщик пуст. Ждём дождя.", "info")
            return
        inv.remove(p.items, "bottle_empty", n)
        inv.add(p.items, "water_clean", n)
        z.collectors[key] = water - n
        game.log(f"Набрал дождевой воды: {n} л.", "good")
        return

    if info.get("hatch"):
        game.use_hatch()
        return

    if info.get("ladder"):
        game.change_zone("sarykuduk", game.zones["sarykuduk"].markers["hatch"], offset=(0.5, -0.5))
        return

    if info.get("alarm"):
        z.remove(x, y)
        inv.add(p.items, "can_empty", 3)
        inv.add(p.items, "twine", 1)
        game.log("Снял сигнализацию.", "info")
        return

    game.log(info.get("name", "Ничего интересного."), "info")


def climb_window(game, x, y, o):
    """Пролезть через окно на противоположную сторону."""
    p = game.player
    z = game.zone
    dx = (x + 0.5) - p.x
    dy = (y + 0.5) - p.y
    if abs(dx) > abs(dy):
        tx, ty = x + (1 if dx > 0 else -1), y
    else:
        tx, ty = x, y + (1 if dy > 0 else -1)
    if z.solid(tx, ty):
        game.log("С той стороны не пролезть.", "bad")
        return

    def done():
        p.x, p.y = tx + 0.5, ty + 0.5
        if o == "window_broken" and random.random() < 0.25:
            p.hurt(4, "glass", game.log)
            game.log("Порезался о стекло.", "bad")
    if o == "window":
        z.set(x, y, "window_broken")
        game.sound.play("glass")
        game.noise(x + 0.5, y + 0.5, 12)
        game.log("Разбил окно. Это было громко.", "bad")
    game.start_action("Лезу в окно", 1.4, done, noise=3)


def barricade(game):
    """Заколотить ближайшее окно (концепт 7.5: укрепление дома)."""
    p = game.player
    z = game.zone
    best = None
    for yy in range(int(p.y) - 1, int(p.y) + 2):
        for xx in range(int(p.x) - 1, int(p.x) + 2):
            if z.get(xx, yy) in ("window", "window_broken"):
                d = math.hypot(xx + 0.5 - p.x, yy + 0.5 - p.y)
                if best is None or d < best[0]:
                    best = (d, xx, yy)
    if best is None:
        game.log("Рядом нет окна, которое можно заколотить.", "info")
        return
    if not game.has_tool("hammer") or inv.count(p.items, "planks") < 2 or inv.count(p.items, "nails") < 2:
        game.log("Нужны молоток, 2 доски и 2 горсти гвоздей.", "bad")
        return
    _, xx, yy = best

    def done():
        inv.remove(p.items, "planks", 2)
        inv.remove(p.items, "nails", 2)
        z.set(xx, yy, "window_boarded")
        z.obj_hp.pop(f"{xx},{yy}", None)
        game.log("Окно заколочено.", "good")
        x2 = p.add_xp("carpentry", 20)
        if x2:
            game.log(x2, "good")
    t = max(2.0, 5 - 0.4 * p.lvl("carpentry"))
    game.start_action("Заколачиваю окно", t, done, noise=9)
