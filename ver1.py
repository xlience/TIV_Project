import asyncio
from acevo import TelemetryCapture


async def main():
    print("=" * 50)
    print("       ASSETTO CORSA EVO TELEMETRY")
    print("=" * 50)

    print()
    print("Ожидаю данные от Assetto Corsa EVO...")
    print("Запусти игру и выйди на трассу.")
    print("Для остановки программы нажми Ctrl+C.")
    print()

    capture = TelemetryCapture(hz=20)

    try:
        await capture.start_capture()

        while True:
            await asyncio.sleep(1)

            print("Telemetry capture работает...")

    except KeyboardInterrupt:
        print()
        print("Остановка...")

    finally:
        frames = await capture.stop_capture()
        print(f"Получено кадров: {len(frames)}")


if __name__ == "__main__":
    asyncio.run(main())