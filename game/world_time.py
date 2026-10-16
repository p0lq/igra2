"""Время, погода и события мира: день/ночь, температура степи, пыльные бури, ливни
и особое событие — «Пыльный фронт» (жёлтое облако штамма, идёт волнами раз в 3–4 дня)."""
import math
import random

from .config import START_HOUR

CLEAR, STORM, RAIN = "clear", "storm", "rain"
WEATHER_NAMES = {CLEAR: "Ясно", STORM: "Пыльная буря", RAIN: "Ливень"}


class WorldClock:
    def __init__(self):
        self.minutes = START_HOUR * 60.0  # минут с полуночи первого дня
        self.weather = CLEAR
        self.weather_left = 0.0
        self.front = False                # идёт Пыльный фронт
        self.front_left = 0.0
        self.next_front_day = 3
        self.next_front_hour = 13
        self._last_hour = int(self.minutes // 60)

    # ---- календарь
    @property
    def day(self):
        return int(self.minutes // 1440) + 1

    @property
    def hour(self):
        return int(self.minutes // 60) % 24

    @property
    def minute(self):
        return int(self.minutes) % 60

    def clock_text(self):
        return f"День {self.day}, {self.hour:02d}:{self.minute:02d}"

    def hour_f(self):
        return (self.minutes / 60.0) % 24

    # ---- свет и температура
    def darkness(self):
        """0 — светлый день, 1 — кромешная тьма. Плавные рассвет и закат."""
        h = self.hour_f()
        if 7 <= h < 19:
            d = 0.0
        elif 5 <= h < 7:
            d = 0.86 * (7 - h) / 2
        elif 19 <= h < 21:
            d = 0.86 * (h - 19) / 2
        else:
            d = 0.86
        if self.weather == STORM:
            d = max(d, 0.35)
        if self.weather == RAIN:
            d = max(d, 0.25)
        return d

    def air_temp(self):
        """Температура воздуха: днём до +35, ночью до +5 (резко-континентальная степь)."""
        t = 20 + 15 * math.sin((self.hour_f() - 9) / 24 * 2 * math.pi)
        if self.weather == RAIN:
            t -= 6
        return t

    def is_night(self):
        return self.darkness() > 0.5

    def front_warning(self):
        """Предупреждать ли по радио: фронт завтра или сегодня, но ещё не начался."""
        return (self.day == self.next_front_day - 1) or (self.day == self.next_front_day and self.hour < self.next_front_hour)

    # ---- обновление
    def update(self, mins, log):
        """Продвинуть время. Возвращает список событий (например, 'new_hour', 'night')."""
        events = []
        self.minutes += mins
        self.weather_left -= mins
        if self.weather != CLEAR and self.weather_left <= 0:
            log("Погода прояснилась." if self.weather == RAIN else "Пыльная буря улеглась.", "info")
            self.weather = CLEAR

        h = int(self.minutes // 60)
        while self._last_hour < h:          # раз в игровой час — броски погоды
            self._last_hour += 1
            events.append("new_hour")
            if self._last_hour % 24 == 22:
                events.append("night")
            if self.weather == CLEAR and not self.front:
                r = random.random()
                if r < 0.03:
                    self.weather, self.weather_left = STORM, random.uniform(60, 180)
                    log("Поднимается пыльная буря! Лучше надеть респиратор.", "bad")
                elif r < 0.05:
                    self.weather, self.weather_left = RAIN, random.uniform(40, 120)
                    log("Над степью ливень. Можно собрать воду.", "info")

        if not self.front and self.day == self.next_front_day and self.hour >= self.next_front_hour:
            self.front = True
            self.front_left = random.uniform(150, 210)
            self.weather = CLEAR
            log("ПЫЛЬНЫЙ ФРОНТ! Небо желтеет. Укройся в помещении или надень респиратор!", "bad")
            events.append("front_start")
        if self.front:
            self.front_left -= mins
            if self.front_left <= 0:
                self.front = False
                self.next_front_day = self.day + random.choice((3, 4))
                self.next_front_hour = random.randint(9, 17)
                log("Пыльный фронт ушёл дальше на север.", "good")
                events.append("front_end")
        return events

    def dust_exposure(self, indoor):
        """Сколько «пыльной болезни» в минуту получает человек без фильтра."""
        if indoor:
            return 0.0
        if self.front:
            return 0.12
        if self.weather == STORM:
            return 0.02
        return 0.0

    def to_dict(self):
        return dict(self.__dict__)

    def load_dict(self, d):
        self.__dict__.update(d)
