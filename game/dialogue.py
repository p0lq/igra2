"""Диалоги в стиле Fallout 2: дерево узлов, варианты ответов с условиями и последствиями.

Условия (поле "if"), все должны выполняться:
  quest:water=1   quest:bunker>=1   item:water_clean>=3   skill:trade>=2
  flag:имя  !flag:имя  recipe:plov  !recipe:plov  trait:doctor  has_untranslated
Эффекты (поле "do"):
  give:id:n  take:id:n  quest_adv:квест:стадия  rep:фракция:число  flag:имя
  learn:рецепт  xp:навык:число  glossary:слово  trade  translate  chapter_end
"""
import re

from .data import DIALOGUES, ITEMS, QUESTS, RECIPES, GLOSSARY
from .localization import parse_markup, glossary_key
from . import inventory as inv

_CMP = re.compile(r"^(\w+):([\w']+)(>=|<=|=|<|>)(-?\d+)$")


def check(game, cond):
    p = game.player
    neg = cond.startswith("!")
    c = cond[1:] if neg else cond
    res = False
    m = _CMP.match(c)
    if m:
        kind, name, op, val = m.group(1), m.group(2), m.group(3), int(m.group(4))
        if kind == "quest":
            cur = game.quests.get(name, 0)
        elif kind == "item":
            cur = inv.count(p.items, name)
        elif kind == "skill":
            cur = p.lvl(name)
        elif kind == "rep":
            cur = game.rep.get(name, 0)
        else:
            cur = 0
        res = {"=": cur == val, ">=": cur >= val, "<=": cur <= val, "<": cur < val, ">": cur > val}[op]
    elif c.startswith("flag:"):
        res = c[5:] in game.flags
    elif c.startswith("recipe:"):
        res = c[7:] in p.known_recipes
    elif c.startswith("trait:"):
        res = p.has(c[6:])
    elif c == "has_untranslated":
        res = any(st for st in p.items if ITEMS[st["id"]]["type"] == "note" and not st.get("read"))
    return (not res) if neg else res


def apply(game, effect):
    """Выполнить эффект. Используется и диалогами, и записками, и радио."""
    p = game.player
    parts = effect.split(":")
    cmd = parts[0]
    if cmd == "give":
        inv.add(p.items, parts[1], int(parts[2]))
        game.log(f"Получено: {ITEMS[parts[1]]['name']} ×{parts[2]}", "good")
    elif cmd == "take":
        inv.remove(p.items, parts[1], int(parts[2]))
        game.log(f"Отдано: {ITEMS[parts[1]]['name']} ×{parts[2]}", "info")
    elif cmd == "quest_adv":
        game.advance_quest(parts[1], int(parts[2]))
    elif cmd == "rep":
        game.rep[parts[1]] = game.rep.get(parts[1], 0) + int(parts[2])
        game.log("Репутация в колхозе «Заря» выросла.", "good")
    elif cmd == "flag":
        game.flags.add(parts[1])
    elif cmd == "learn":
        if parts[1] not in p.known_recipes:
            p.known_recipes.add(parts[1])
            game.log(f"Новый рецепт: {RECIPES[parts[1]]['name']}", "good")
    elif cmd == "xp":
        msg = p.add_xp(parts[1], int(parts[2]))
        if msg:
            game.log(msg, "good")
    elif cmd == "glossary":
        key = glossary_key(parts[1])
        if key and key not in game.glossary:
            game.glossary.add(key)
            game.log(f"Новое слово в словарике: {key} — {GLOSSARY[key]['ru']}", "lang")
    elif cmd == "trade":
        game.pending_trade = True
    elif cmd == "translate":
        for st in p.items:
            if ITEMS[st["id"]]["type"] == "note" and not st.get("read"):
                game.mark_note_read(st)
    elif cmd == "chapter_end":
        game.flags.add("act2_done")
        game.pending_chapter = True


class Dialogue:
    """Текущий разговор с NPC."""

    def __init__(self, game, npc):
        self.game = game
        self.npc = npc
        self.tree = DIALOGUES[npc.data["dialog"]]
        self.goto(self.tree["start"])

    def goto(self, node_id):
        if node_id == "end":
            self.node = None
            return
        self.node_id = node_id
        self.node = self.tree["nodes"][node_id]
        for e in self.node.get("do", []):
            apply(self.game, e)
        # Разметку разбираем один раз при входе в узел: так перевод слова
        # показывается только при первой встрече.
        self.text = parse_markup(self.node["text"], self.game.glossary, self.game.on_new_word)
        self.options = []
        for opt in self.node["options"]:
            if all(check(self.game, c) for c in opt.get("if", [])):
                self.options.append((opt, parse_markup(opt["text"], self.game.glossary, self.game.on_new_word)))

    def choose(self, i):
        if i >= len(self.options):
            return
        opt = self.options[i][0]
        for e in opt.get("do", []):
            apply(self.game, e)
        self.goto(opt.get("next", "end"))

    @property
    def finished(self):
        return self.node is None
