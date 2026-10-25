"""Save/load calibration profiles (JSON next to the program), one per game."""
from __future__ import annotations

import json
from dataclasses import asdict, fields
from pathlib import Path

from motion import MotionConfig

SETTINGS_PATH = Path(__file__).with_name("settings.json")

# Fields the GUI is allowed to change (everything else keeps its default).
TUNABLE = (
    "max_pitch_deg", "max_roll_deg", "max_heave_norm",
    "longitudinal_g_gain", "lateral_g_gain", "vertical_g_gain",
    "pitch_filter_tau_s", "roll_filter_tau_s", "heave_filter_tau_s",
    "longitudinal_washout_tau_s", "lateral_washout_tau_s",
    "max_pitch_rate_deg_s", "max_roll_rate_deg_s",
    "pitch_sign", "roll_sign",
)


def config_from_dict(data: dict) -> MotionConfig:
    allowed = {f.name for f in fields(MotionConfig)} & set(TUNABLE)
    clean = {}
    for key, value in data.items():
        if key in allowed:
            try:
                clean[key] = float(value)
            except (TypeError, ValueError):
                continue
    return MotionConfig(**clean)


def config_to_dict(config: MotionConfig) -> dict:
    full = asdict(config)
    return {k: full[k] for k in TUNABLE}


def load_profiles(path: Path = SETTINGS_PATH) -> dict[str, MotionConfig]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {name: config_from_dict(d) for name, d in raw.get("profiles", {}).items()
                if isinstance(d, dict)}
    except (OSError, ValueError, AttributeError):
        return {}


def save_profile(name: str, config: MotionConfig, path: Path = SETTINGS_PATH) -> None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        profiles = raw.get("profiles", {})
    except (OSError, ValueError, AttributeError):
        profiles = {}
    profiles[name] = config_to_dict(config)
    path.write_text(json.dumps({"profiles": profiles}, indent=2, ensure_ascii=False),
                    encoding="utf-8")
