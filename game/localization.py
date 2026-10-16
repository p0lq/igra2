"""Локализация: вставки казахских/узбекских слов в русский текст.

Все тексты игры (предметы, диалоги, задания, радио) лежат в таблицах data/*.json —
их можно перевести, не трогая код.

В текстах слово из глоссария записывается так: [[Рахмет]].
Первый раз игрок видит его с переводом в скобках, и слово попадает в словарик.
Дальше оно показывается без перевода, но выделено цветом.
"""
import re
from .data import GLOSSARY
from .config import COL_TEXT, COL_TURQ

_MARK = re.compile(r"\[\[(.+?)\]\]")
# Поиск без учёта регистра: «балам» и «Балам» — одно слово
_LOOKUP = {k.casefold(): k for k in GLOSSARY}


def glossary_key(word):
    return _LOOKUP.get(word.casefold())


def parse_markup(text, known, on_new=None, base_color=COL_TEXT):
    """Разбить текст на куски [(строка, цвет)].

    known  — множество уже изученных слов (ключи глоссария);
    on_new — функция, которую вызываем для нового слова (добавить в словарик).
    """
    parts = []
    pos = 0
    for m in _MARK.finditer(text):
        if m.start() > pos:
            parts.append((text[pos:m.start()], base_color))
        word = m.group(1)
        key = glossary_key(word)
        if key is None:
            parts.append((word, base_color))
        elif key in known:
            parts.append((word, COL_TURQ))
        else:
            parts.append((word, COL_TURQ))
            parts.append((" (" + GLOSSARY[key]["ru"].lower() + ")", COL_TURQ))
            known.add(key)
            if on_new:
                on_new(key)
        pos = m.end()
    if pos < len(text):
        parts.append((text[pos:], base_color))
    return parts


def strip_markup(text):
    """Текст без разметки — для коротких подписей."""
    return _MARK.sub(lambda m: m.group(1), text)
