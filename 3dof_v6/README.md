# 3DOF Motion Software — current software-only stage

## Run

Use the same Python environment where `acevo-sdk` is installed:

```bash
python main.py
```

Offline Motion Engine tests (no EVO or hardware required):

```bash
python -m unittest -v
```

## Current data flow

`Assetto Corsa EVO / acevo-sdk` → `telemetry.py` (`VehicleMotion`) → `motion.py` (`MotionController`) → virtual Pitch/Roll/Heave monitor.

- EVO capture polling remains configured for 333 Hz.
- The Motion Engine loop targets 100 Hz.
- `get_latest()` returns only a newly observed newest frame; repeated reads of the same frame do not generate duplicate commands.
- `motion.py` is independent of the game adapter and only consumes `VehicleMotion`.
- The acceleration cue uses a configurable washout (high-pass component) so sustained G gradually returns toward neutral.
- Output limits and slew rates are software-preview values only. They are not physical actuator safety limits.
- No ESP32/network output is implemented yet.

## Important limitations

The adapter uses the currently known public `get_frames()` interface and selects the last item. If the SDK retains a very large history or copies that history on each call, this may remain a performance bottleneck. The monitor reports average `get_latest()` cost to help identify that. Do not assume the 100 Hz target is achieved until the live measurement confirms it.

Wheel suspension travel is exposed in the normalized model but is not currently used to drive heave because its sign/reference convention needs validation. The heave cue currently uses transient vertical acceleration only.


## Game selection

`python main.py` — **auto mode (default)**: waits until a game is actually sending telemetry
(you must be in the car, on track), then connects. If two games are live it asks which one.
Manual: `python main.py --game acevo|ac|acc|lmu`. `--swap-yz` swaps vertical/longitudinal axes.

Detection: LMU = `LMU_Data` shared memory with a player car; AC/ACC = `acpmf_physics` with live
packets (ACC does not fill wheel load, AC does, which tells them apart); EVO = a short capture attempt.
Detection never creates shared memory, so starting the program before the game is safe.

## Simple cue method (default)

Pitch/Roll come only from G forces (braking/acceleration -> pitch, cornering -> roll) with washout.
Body attitude gains are 0. If the virtual platform leans the wrong way, set `pitch_sign` / `roll_sign` to -1.0 in `MotionConfig`.

## Checks per game (same for all)

Braking: `long` must go strongly negative, Pitch command negative.
Right turn: `lat` must go negative, Roll command negative.
