"""Настройки игры: видео, звук, геймплей. Хранятся в %APPDATA%/Granica99/settings.json.

Как устроено изображение:
  * «Разрешение» — размер окна (или картинки в полноэкранном режиме).
  * «Масштаб» — во сколько раз увеличить картинку. Игра рисуется в разрешении
    (разрешение / масштаб), а pygame (флаг SCALED) растягивает её на окно видеокартой.
    На 4K-мониторе с масштабом 200% всё будет того же размера, что на 1080p.
  * Логическое разрешение не бывает меньше 1280×720 — иначе окна интерфейса не влезут.
"""
import json
import os
import warnings

import pygame

from . import config as cfg

RESOLUTIONS = [(1280, 720), (1366, 768), (1440, 900), (1600, 900), (1680, 1050), (1920, 1080),
               (1920, 1200), (2560, 1080), (2560, 1440), (3440, 1440), (3840, 2160)]
DISPLAY_MODES = [("window", "В окне"), ("borderless", "Окно без рамки"), ("fullscreen", "Полный экран")]
SCALES = [100, 125, 150, 200]
FPS_LIMITS = [30, 60, 120, 144, 240, 0]          # 0 — без ограничения
TIME_SPEEDS = [0.5, 1.0, 2.0, 3.0]
MIN_LOGICAL = (1280, 720)

DEFAULTS = {
    "resolution": [1280, 720],
    "display": "window",
    "scale": 100,
    "vsync": True,
    "fps_limit": 60,
    "brightness": 100,      # %, 50..150
    "show_fps": False,
    "master": 80,           # громкость, 0..100
    "sfx": 80,
    "ambient": 60,
    "music": 60,
    "muted": False,
    "time_speed": 1.0,      # игровых минут за реальную секунду
    "hints": True,          # подсказки «[E] Обыскать» над персонажем
}


def _path():
    root = os.environ.get("APPDATA") or os.path.expanduser("~")
    p = os.path.join(root, "Granica99")
    os.makedirs(p, exist_ok=True)
    return os.path.join(p, "settings.json")


class Settings:
    def __init__(self):
        self.data = dict(DEFAULTS)
        self.load()

    def __getitem__(self, k):
        return self.data[k]

    def __setitem__(self, k, v):
        self.data[k] = v

    def load(self):
        try:
            with open(_path(), encoding="utf-8") as f:
                saved = json.load(f)
            for k in DEFAULTS:
                if k in saved:
                    self.data[k] = saved[k]
        except (OSError, ValueError):
            pass   # нет файла или он испорчен — остаются значения по умолчанию

    def save(self):
        try:
            with open(_path(), "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def reset(self):
        self.data = dict(DEFAULTS)


def desktop_size():
    sizes = pygame.display.get_desktop_sizes()
    return sizes[0] if sizes else (1920, 1080)


def available_resolutions():
    """Разрешения, которые помещаются на монитор."""
    dw, dh = desktop_size()
    res = [r for r in RESOLUTIONS if r[0] <= dw and r[1] <= dh]
    if (dw, dh) not in res and dw >= 1280 and dh >= 720:
        res.append((dw, dh))     # «родное» разрешение монитора
    return sorted(res) or [(1280, 720)]


def logical_size(res, scale):
    """Во что рисует игра: разрешение / масштаб, но не меньше 1280×720."""
    k = scale / 100
    k = max(1.0, min(k, res[0] / MIN_LOGICAL[0], res[1] / MIN_LOGICAL[1]))
    return int(res[0] / k), int(res[1] / k)


def apply_display(st, icon=None):
    """Создать (или пересоздать) окно по настройкам.

    Возвращает (display, canvas):
      display — поверхность окна;
      canvas  — холст, на котором рисует игра, или None, если игра рисует прямо в окно.

    Три случая:
      1. Полный экран — флаг SCALED: SDL сам растягивает кадр на весь монитор (видеокартой).
      2. Окно с масштабом 100% — флаг SCALED, окно ровно размера кадра.
      3. Окно с масштабом больше 100% — обычное окно нужного размера, игра рисует на холсте
         меньшего размера, а мы каждый кадр растягиваем холст на окно (present()).
         Координаты мыши в этом случае пересчитываются через cfg.VIEW_SCALE.
    """
    desk = desktop_size()
    mode = st["display"]
    res = tuple(st["resolution"])
    if mode == "borderless":
        res = desk
    elif mode == "window":
        res = (min(res[0], desk[0]), min(res[1], desk[1]))
    size = logical_size(res, st["scale"])
    use_canvas = mode != "fullscreen" and size != res

    if pygame.display.get_surface() is not None:
        # Повторный set_mode с флагом SCALED и другим размером ломает вывод картинки:
        # окно меняется, а на экране остаётся старый застывший кадр. Поэтому дисплей
        # пересоздаём целиком. Картинки, шрифты и звук от этого не страдают.
        caption = pygame.display.get_caption()[0]
        pygame.display.quit()
        pygame.display.init()
        pygame.display.set_caption(caption)
        if icon is not None:
            pygame.display.set_icon(icon)

    if use_canvas:
        flags = pygame.NOFRAME if mode == "borderless" else 0
        win_size = res
    else:
        flags = pygame.SCALED
        if mode == "fullscreen":
            flags |= pygame.FULLSCREEN
        elif mode == "borderless":
            flags |= pygame.NOFRAME
        win_size = size
    try:
        display = pygame.display.set_mode(win_size, flags, vsync=1 if st["vsync"] else 0)
    except pygame.error:
        display = pygame.display.set_mode(win_size, flags)   # vsync недоступен — работаем без него
    if mode == "borderless":
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                pygame.Window.from_display_module().position = (0, 0)
        except (AttributeError, pygame.error):
            pass

    canvas = pygame.Surface(size).convert() if use_canvas else None
    cfg.SCREEN_W, cfg.SCREEN_H = size
    cfg.VIEW_SCALE = (display.get_width() / size[0], display.get_height() / size[1]) if use_canvas else (1.0, 1.0)
    return display, canvas


def present(display, canvas):
    """Растянуть холст на окно (случай 3). Целый масштаб — чёткими пикселями, дробный — сглаженно."""
    k = display.get_width() / canvas.get_width()
    if abs(k - round(k)) < 0.01:
        pygame.transform.scale(canvas, display.get_size(), display)
    else:
        pygame.transform.smoothscale(canvas, display.get_size(), display)
