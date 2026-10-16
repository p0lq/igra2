"""Звук: все эффекты синтезируются кодом при запуске (шум, синусы, затухание).
Никаких чужих записей. Музыка — простая мелодия «домбры» по алгоритму
Карплуса–Стронга (щипковая струна = шум в линии задержки с усреднением).
Позже эффекты можно заменить своими записями (шаги, двери) — см. CREDITS.md.
"""
import array
import math
import random

import pygame

RATE = 22050


def _to_sound(samples, vol=0.5):
    buf = array.array("h", (int(max(-1.0, min(1.0, s * vol)) * 32767) for s in samples))
    return pygame.mixer.Sound(buffer=buf.tobytes())


def _noise(n, rnd):
    return [rnd.uniform(-1, 1) for _ in range(n)]


def _lowpass(xs, a):
    y = 0.0
    out = []
    for x in xs:
        y += a * (x - y)
        out.append(y)
    return out


def _env(n, attack=0.005, decay=6.0):
    """Огибающая: быстрая атака и экспоненциальное затухание."""
    at = max(1, int(attack * RATE))
    return [(i / at if i < at else math.exp(-decay * (i - at) / RATE)) for i in range(n)]


def _make(rnd):
    s = {}
    n = int(0.14 * RATE)
    s["swing"] = _to_sound([a * b for a, b in zip(_lowpass(_noise(n, rnd), 0.25), _env(n, 0.05, 25))], 0.5)
    n = int(0.2 * RATE)
    s["hit"] = _to_sound([math.sin(2 * math.pi * 90 * i / RATE) * e + 0.4 * r * e
                          for i, (e, r) in enumerate(zip(_env(n, 0.002, 22), _lowpass(_noise(n, rnd), 0.3)))], 0.8)
    n = int(0.45 * RATE)
    s["shot"] = _to_sound([(0.8 * r + 0.6 * math.sin(2 * math.pi * 55 * i / RATE)) * e
                           for i, (e, r) in enumerate(zip(_env(n, 0.001, 12), _lowpass(_noise(n, rnd), 0.6)))], 0.9)
    n = int(0.25 * RATE)
    s["bang"] = _to_sound([(math.sin(2 * math.pi * 60 * i / RATE) + 0.5 * r) * e
                           for i, (e, r) in enumerate(zip(_env(n, 0.002, 18), _lowpass(_noise(n, rnd), 0.2)))], 0.8)
    n = int(0.35 * RATE)
    hp = [x - y for x, y in zip(_noise(n, rnd), _lowpass(_noise(n, rnd), 0.1))]
    s["glass"] = _to_sound([x * e for x, e in zip(hp, _env(n, 0.001, 14))], 0.5)
    n = int(0.06 * RATE)
    s["pickup"] = _to_sound([math.sin(2 * math.pi * (600 + 900 * i / n) * i / RATE) * e for i, e in enumerate(_env(n, 0.002, 40))], 0.35)
    n = int(0.35 * RATE)
    s["door"] = _to_sound([math.sin(2 * math.pi * (320 - 140 * i / n) * i / RATE) * (0.5 + 0.5 * math.sin(i / 90)) * e
                           for i, e in enumerate(_env(n, 0.02, 6))], 0.3)
    craft = []
    for k in range(3):
        m = int(0.12 * RATE)
        craft += [math.sin(2 * math.pi * 180 * i / RATE) * e + 0.3 * r * e for i, (e, r) in enumerate(zip(_env(m, 0.001, 40), _noise(m, rnd)))]
        craft += [0.0] * int(0.08 * RATE)
    s["craft"] = _to_sound(craft, 0.5)
    cough = []
    for k in range(2):
        m = int(0.16 * RATE)
        cough += [r * e for r, e in zip(_lowpass(_noise(m, rnd), 0.35), _env(m, 0.01, 18))]
        cough += [0.0] * int(0.06 * RATE)
    s["cough"] = _to_sound(cough, 0.5)
    bark = []
    for k in range(2):
        m = int(0.12 * RATE)
        bark += [(1 if math.sin(2 * math.pi * (420 - 150 * i / m) * i / RATE) > 0 else -1) * 0.4 * e for i, e in enumerate(_env(m, 0.005, 20))]
        bark += [0.0] * int(0.1 * RATE)
    s["dog"] = _to_sound(_lowpass(bark, 0.4), 0.6)
    alarm = []
    for k in range(3):
        m = int(0.18 * RATE)
        alarm += [sum(math.sin(2 * math.pi * f * i / RATE) for f in (1210, 1730, 2410)) / 3 * e for i, e in enumerate(_env(m, 0.001, 20))]
    s["alarm"] = _to_sound(alarm, 0.5)
    n = int(0.22 * RATE)
    s["hurt"] = _to_sound(_lowpass([((i * 140 / RATE) % 1 * 2 - 1) * e for i, e in enumerate(_env(n, 0.01, 12))], 0.2), 0.8)
    n = int(0.3 * RATE)
    s["eat"] = _to_sound([r * (0.5 + 0.5 * math.sin(i / 300)) * e for i, (r, e) in enumerate(zip(_lowpass(_noise(n, rnd), 0.15), _env(n, 0.01, 8)))], 0.4)
    n = int(1.2 * RATE)
    s["radio"] = _to_sound([r * 0.5 * (0.7 + 0.3 * math.sin(i / 700)) * e for i, (r, e) in enumerate(zip(_noise(n, rnd), _env(n, 0.05, 2)))], 0.25)
    n = int(0.08 * RATE)
    s["step"] = _to_sound([r * e for r, e in zip(_lowpass(_noise(n, rnd), 0.1), _env(n, 0.002, 50))], 0.25)
    return s


def _wind(rnd):
    """Ветер степи: низкочастотный шум с медленно «дышащей» громкостью. Петля 6 секунд."""
    n = 6 * RATE
    base = _lowpass(_lowpass(_noise(n, rnd), 0.04), 0.08)
    out = [b * (0.6 + 0.4 * math.sin(2 * math.pi * i / n) ** 2) * 6 for i, b in enumerate(base)]
    fade = RATE // 2  # плавная склейка конца с началом
    for i in range(fade):
        k = i / fade
        out[i] = out[i] * k + out[n - fade + i] * (1 - k)
    return _to_sound(out[: n - fade], 0.35)


def _dombra(rnd):
    """Короткий наигрыш на «домбре»: пентатоника, щипки по Карплусу–Стронгу."""
    scale = [220.0, 261.6, 293.7, 329.6, 392.0, 440.0]
    melody = [0, 2, 3, 2, 0, None, 4, 3, 2, 0, None, 1, 2, 0, None, None,
              0, 2, 3, 5, 4, 3, 2, None, 3, 2, 1, 0, None, None, None, None]
    beat = int(0.32 * RATE)
    out = [0.0] * (beat * len(melody) + RATE)
    for k, note in enumerate(melody):
        if note is None:
            continue
        period = int(RATE / scale[note])
        buf = [rnd.uniform(-1, 1) for _ in range(period)]
        start = k * beat
        for i in range(int(RATE * 0.9)):
            j = i % period
            v = buf[j]
            buf[j] = 0.497 * (v + buf[(j + 1) % period])
            if start + i < len(out):
                out[start + i] += v * 0.6
    return _to_sound(out, 0.5)


class SoundSystem:
    def __init__(self):
        self.enabled = pygame.mixer.get_init() is not None
        self.muted = False
        self.sounds = {}
        self.wind = None
        self.music = None
        if not self.enabled:
            return
        rnd = random.Random(99)
        self.sounds = _make(rnd)
        self.wind = _wind(rnd)
        self.music = _dombra(rnd)
        self.wind_ch = None

    def play(self, name, vol=1.0):
        if not self.enabled or self.muted or name not in self.sounds:
            return
        ch = self.sounds[name].play()
        if ch:
            ch.set_volume(vol)

    def ambient(self, outdoor, storm):
        """Фоновый ветер: громче в бурю, тише в помещении."""
        if not self.enabled:
            return
        if self.wind_ch is None or not self.wind_ch.get_busy():
            self.wind_ch = self.wind.play(loops=-1)
        if self.wind_ch:
            v = 0.0 if self.muted else (0.9 if storm else 0.35) * (1.0 if outdoor else 0.3)
            self.wind_ch.set_volume(v)

    def play_music(self):
        if self.enabled and not self.muted:
            ch = self.music.play()
            if ch:
                ch.set_volume(0.35)

    def toggle_mute(self):
        self.muted = not self.muted
        if self.muted and self.enabled:
            pygame.mixer.stop()
            self.wind_ch = None
