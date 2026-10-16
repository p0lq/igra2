"""Изометрическая математика: перевод координат клеток в пиксели экрана и обратно.

Клетка (tx, ty) на экране — ромб. Верхний угол ромба клетки находится в точке
    sx = (tx - ty) * HALF_W,  sy = (tx + ty) * HALF_H
Отсюда обратная формула (решаем систему из двух уравнений):
    tx = (sx / HALF_W + sy / HALF_H) / 2
    ty = (sy / HALF_H - sx / HALF_W) / 2
"""
from .config import HALF_W, HALF_H, SCREEN_W, SCREEN_H


class Camera:
    def __init__(self):
        self.x = 0.0  # смещение мира в пикселях
        self.y = 0.0

    def follow(self, tx, ty, dt):
        """Плавно подвести камеру к точке (tx, ty) в клетках."""
        wx, wy = world_px(tx, ty)
        target_x = wx - SCREEN_W / 2
        target_y = wy - SCREEN_H / 2 + 40
        k = min(1.0, dt * 8)
        self.x += (target_x - self.x) * k
        self.y += (target_y - self.y) * k

    def snap(self, tx, ty):
        wx, wy = world_px(tx, ty)
        self.x = wx - SCREEN_W / 2
        self.y = wy - SCREEN_H / 2 + 40


def world_px(tx, ty):
    """Координаты в клетках -> пиксели мира (без учёта камеры)."""
    return (tx - ty) * HALF_W, (tx + ty) * HALF_H


def to_screen(tx, ty, cam):
    wx, wy = world_px(tx, ty)
    return wx - cam.x, wy - cam.y


def to_tile(sx, sy, cam):
    """Пиксель экрана -> координаты в клетках (дробные)."""
    wx = sx + cam.x
    wy = sy + cam.y
    tx = (wx / HALF_W + wy / HALF_H) / 2
    ty = (wy / HALF_H - wx / HALF_W) / 2
    return tx, ty


def screen_dir_to_tile(dx, dy):
    """Направление на экране (вправо/вверх...) -> направление в клетках.
    Нужно, чтобы клавиша W двигала персонажа вверх по экрану, а не по диагонали карты."""
    tx = dx / HALF_W + dy / HALF_H
    ty = dy / HALF_H - dx / HALF_W
    return tx, ty
