"""Общие настройки игры: размеры экрана, тайлов, цвета, пути к файлам."""
import os
import sys

TITLE = "Граница-99"
VERSION = "0.2.0"

# Логическое разрешение, в котором рисуется игра. Меняется в настройках
# (settings.apply_display), поэтому модули читают его как cfg.SCREEN_W, а не копируют.
SCREEN_W, SCREEN_H = 1280, 720

# Размер изометрического тайла (ромб 2:1) и высота стены в пикселях
TILE_W, TILE_H = 64, 32
HALF_W, HALF_H = TILE_W // 2, TILE_H // 2
WALL_H = 50

START_HOUR = 7

# «Пыльная» палитра из концепта: охра, ржавчина, серо-зелёный, выцветшая бирюза
COL_BG = (24, 20, 16)
COL_PANEL = (46, 42, 34)
COL_PANEL_DARK = (30, 27, 22)
COL_PANEL_EDGE = (110, 98, 70)
COL_TEXT = (226, 214, 186)
COL_TEXT_DIM = (150, 140, 118)
COL_ACCENT = (214, 160, 60)      # охра — выделение
COL_RED = (200, 60, 45)          # аварийный красный
COL_GREEN = (120, 170, 90)
COL_TURQ = (110, 170, 160)       # бирюза — казахские/узбекские слова
COL_BAD = (210, 90, 70)


def resource_path(*parts):
    """Путь к файлу ресурсов. Внутри .exe (PyInstaller) файлы лежат в sys._MEIPASS."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, *parts)


def save_dir():
    """Папка для сохранений: %APPDATA%/Granica99/saves (не рядом с .exe, чтобы не нужны были права)."""
    root = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(root, "Granica99", "saves")
    os.makedirs(path, exist_ok=True)
    return path
