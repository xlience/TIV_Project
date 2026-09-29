import asyncio
import math
from acevo import TelemetryCapture


# ============================================================
# НАСТРОЙКИ MOTION SYSTEM
# ============================================================

# Максимальный физический наклон нашей уменьшенной платформы
MAX_PITCH_DEG = 10.0
MAX_ROLL_DEG = 10.0

# Насколько сильно реальный наклон машины
# влияет на платформу.
#
# 1.0 = 100%
# 0.5 = 50%
# 0.2 = 20%
#
# Начинаем с небольших значений.
PITCH_SCALE = 0.50
ROLL_SCALE = 0.50


# Влияние G-force на движение кресла.
#
# Это отдельные коэффициенты.
G_PITCH_SCALE = 4.0
G_ROLL_SCALE = 4.0


# Сглаживание.
#
# 0.0 = очень медленно
# 1.0 = практически без фильтрации
FILTER_ALPHA = 0.15


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def clamp(value, minimum, maximum):
    return max(minimum, min(value, maximum))


def safe_float(value, default=0.0):
    if value is None:
        return default

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def get_acc_g(physics):
    """
    EVO accG:

        [0] = lateral
        [1] = vertical
        [2] = longitudinal
    """

    acc_g = physics.get("acc_g")

    if not isinstance(acc_g, dict):
        return 0.0, 0.0, 0.0

    lateral = safe_float(acc_g.get("x"))
    vertical = safe_float(acc_g.get("y"))
    longitudinal = safe_float(acc_g.get("z"))

    return lateral, vertical, longitudinal


# ============================================================
# LOW-PASS FILTER
# ============================================================

class LowPassFilter:

    def __init__(self, alpha):
        self.alpha = alpha
        self.value = 0.0
        self.initialized = False

    def update(self, new_value):

        if not self.initialized:
            self.value = new_value
            self.initialized = True
            return self.value

        self.value = (
            self.value
            + self.alpha * (new_value - self.value)
        )

        return self.value


# ============================================================
# MOTION CONTROLLER
# ============================================================

class MotionController:

    def __init__(self):

        self.pitch_filter = LowPassFilter(FILTER_ALPHA)
        self.roll_filter = LowPassFilter(FILTER_ALPHA)

    def update(self, physics):

        # ----------------------------------------------------
        # Реальный наклон автомобиля
        # ----------------------------------------------------

        raw_pitch_rad = safe_float(
            physics.get("pitch")
        )

        raw_roll_rad = safe_float(
            physics.get("roll")
        )

        raw_pitch_deg = math.degrees(raw_pitch_rad)
        raw_roll_deg = math.degrees(raw_roll_rad)

        # ----------------------------------------------------
        # G-force
        # ----------------------------------------------------

        lateral_g, vertical_g, longitudinal_g = get_acc_g(
            physics
        )

        # ----------------------------------------------------
        # Преобразуем данные машины
        # в движение кресла
        # ----------------------------------------------------

        #
        # Pitch:
        #
        # Реальный наклон машины
        # +
        # эффект ускорения/торможения
        #

        target_pitch = (
            raw_pitch_deg * PITCH_SCALE
            +
            longitudinal_g * G_PITCH_SCALE
        )

        #
        # Roll:
        #
        # Реальный крен машины
        # +
        # эффект бокового ускорения
        #

        target_roll = (
            raw_roll_deg * ROLL_SCALE
            +
            lateral_g * G_ROLL_SCALE
        )

        # ----------------------------------------------------
        # Ограничиваем максимальный наклон
        # ----------------------------------------------------

        target_pitch = clamp(
            target_pitch,
            -MAX_PITCH_DEG,
            MAX_PITCH_DEG
        )

        target_roll = clamp(
            target_roll,
            -MAX_ROLL_DEG,
            MAX_ROLL_DEG
        )

        # ----------------------------------------------------
        # Сглаживание
        # ----------------------------------------------------

        filtered_pitch = self.pitch_filter.update(
            target_pitch
        )

        filtered_roll = self.roll_filter.update(
            target_roll
        )

        # ----------------------------------------------------
        # Возвращаем только то,
        # что понадобится физической платформе
        # ----------------------------------------------------

        return {
            "pitch": filtered_pitch,
            "roll": filtered_roll,
        }


# ============================================================
# MAIN
# ============================================================

async def main():

    capture = TelemetryCapture(hz=60)

    controller = MotionController()

    print("=" * 60)
    print("              EVO MOTION CONTROLLER")
    print("=" * 60)
    print()
    print("Ожидание Assetto Corsa EVO...")
    print()

    await capture.start_capture()

    try:

        while True:

            await asyncio.sleep(1 / 60)

            frames = capture.get_frames()

            if not frames:
                continue

            frame = frames[-1]

            physics = frame.physics

            if not physics:
                continue

            # Получаем обработанное движение
            motion = controller.update(physics)

            pitch = motion["pitch"]
            roll = motion["roll"]

            # ------------------------------------------------
            # Вывод
            # ------------------------------------------------

            print(
                "\033[2J\033[H",
                end=""
            )

            print("=" * 60)
            print("              EVO MOTION CONTROLLER")
            print("=" * 60)

            print()

            print("TARGET PLATFORM")
            print("-" * 60)

            print(
                f"Pitch:       {pitch:+8.2f}°"
            )

            print(
                f"Roll:        {roll:+8.2f}°"
            )

            print()

            print("Эти два значения будут передаваться")
            print("на контроллер физической платформы.")

            print()

            print("Ctrl+C — остановить")

    finally:

        await capture.stop_capture()


if __name__ == "__main__":

    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        print()
        print("Motion controller stopped.")