"""Human-readable (Russian) wording for the GUI. Pure functions, easy to test.

Sign convention (same in every game adapter, confirmed in EVO/AC/ACC/LMU tests):
  Pitch < 0 = nose down = seat tilts FORWARD (braking); Pitch > 0 = BACKWARD.
  Roll  < 0 = left side down = tilts LEFT (right-hand turn); Roll > 0 = RIGHT.
  Heave > 0 = UP.
  lateral_g  < 0 = right-hand turn,  > 0 = left-hand turn.
  longitudinal_g > 0 = acceleration, < 0 = braking.
"""
from __future__ import annotations

DEAD = 0.05  # below this the word is replaced by "в центре"

GAME_NAMES = {
    "auto": "Авто (определить запущенную)",
    "acevo": "Assetto Corsa EVO",
    "ac": "Assetto Corsa",
    "acc": "Assetto Corsa Competizione",
    "lmu": "Le Mans Ultimate",
}
STATE_NAMES = {
    "idle": "остановлено",
    "waiting": "ожидание игры (сядьте в машину на трассе)",
    "connected": "подключено",
    "stale": "данные не поступают (пауза/меню)",
    "test": "тест движения (без игры)",
    "error": "ошибка",
}


def pitch_text(pitch_deg: float) -> str:
    if abs(pitch_deg) < DEAD:
        return "Наклон вперёд/назад: в центре"
    word = "вперёд" if pitch_deg < 0 else "назад"
    return f"Наклон вперёд/назад: {abs(pitch_deg):.1f}° {word}"


def roll_text(roll_deg: float) -> str:
    if abs(roll_deg) < DEAD:
        return "Наклон влево/вправо: в центре"
    word = "влево" if roll_deg < 0 else "вправо"
    return f"Наклон влево/вправо: {abs(roll_deg):.1f}° {word}"


def heave_text(heave_norm: float) -> str:
    pct = abs(heave_norm) * 100
    if pct < 1.0:
        return "Подъём/опускание: в центре"
    word = "вверх" if heave_norm > 0 else "вниз"
    return f"Подъём/опускание: {pct:.0f}% {word}"


def long_g_text(g: float) -> str:
    if abs(g) < 0.05:
        return "Разгон/торможение: нет"
    return f"Разгон/торможение: {abs(g):.2f} g {'разгон' if g > 0 else 'торможение'}"


def lat_g_text(g: float) -> str:
    if abs(g) < 0.05:
        return "Боковая перегрузка: нет"
    return f"Боковая перегрузка: {abs(g):.2f} g {'влево' if g > 0 else 'вправо'}"


def vert_g_text(g: float) -> str:
    return f"Вертикальная перегрузка: {g:+.2f} g"


def stats_text(loop_hz: float, max_ms: float, samples: int, missed: int) -> str:
    return (f"Цикл: {loop_hz:.0f} Гц | макс. интервал {max_ms:.1f} мс | "
            f"кадров: {samples} | повторных опросов: {missed}")
