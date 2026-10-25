"""3DOF Motion — графическое приложение (Windows, tkinter, без доп. библиотек).

Запуск: python app.py   (или run_gui.bat)
Программная часть: платформы пока нет, показывается ВИРТУАЛЬНАЯ платформа.
"""
from __future__ import annotations

import ctypes
import os
import sys
import tkinter as tk
from dataclasses import replace
from math import cos, radians, sin
from tkinter import messagebox, ttk

import ui_text as T
from engine import MotionRunner
from motion import MotionConfig
from settings_store import load_profiles, save_profile

STEAM_IDS = {"acevo": 3058630, "ac": 244210, "acc": 805550, "lmu": 2399420}
GAME_ORDER = ["auto", "acevo", "ac", "acc", "lmu"]
RATES = ["100 Гц", "200 Гц", "333 Гц"]
VISUAL_GAIN = 3.0  # drawn angles are exaggerated for visibility

BG, PANEL, FG, DIM = "#1b1d21", "#25282e", "#e8e8e8", "#7d8590"
ACCENT, WARN, OK = "#4da3ff", "#ffb347", "#5fd38d"

# slider key -> (label, lo, hi, number format)
SLIDERS = [
    ("long_gain", "Чувствительность: вперёд/назад (торможение, разгон)", 0.0, 8.0, "{:.1f}"),
    ("lat_gain", "Чувствительность: влево/вправо (повороты)", 0.0, 8.0, "{:.1f}"),
    ("vert_gain", "Чувствительность: подъём/опускание (неровности)", 0.0, 3.0, "{:.2f}"),
    ("max_pitch", "Макс. наклон вперёд/назад, °", 1.0, 30.0, "{:.0f}"),
    ("max_roll", "Макс. наклон влево/вправо, °", 1.0, 30.0, "{:.0f}"),
    ("smooth", "Плавность (сглаживание), с", 0.02, 0.5, "{:.2f}"),
    ("washout", "Возврат в центр при длительной перегрузке, с", 0.5, 5.0, "{:.1f}"),
    ("rate", "Макс. скорость наклона, °/с", 10.0, 200.0, "{:.0f}"),
]


def _timer_resolution(on: bool) -> None:
    if sys.platform == "win32":
        try:
            (ctypes.windll.winmm.timeBeginPeriod if on else ctypes.windll.winmm.timeEndPeriod)(1)
        except Exception:
            pass


def _rot(points, angle_deg, cx, cy):
    a = radians(angle_deg)
    out = []
    for x, y in points:
        out += [cx + x * cos(a) - y * sin(a), cy + x * sin(a) + y * cos(a)]
    return out


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("3DOF Motion — виртуальная платформа")
        self.geometry("1180x760")
        self.minsize(980, 640)
        self.configure(bg=BG)

        self.runner = MotionRunner()
        self.profiles = load_profiles()
        self.profile_name = "default"
        self.loaded_game = ""
        self.vars: dict[str, tk.DoubleVar] = {}
        self.value_labels: dict[str, ttk.Label] = {}
        self.inv_pitch = tk.BooleanVar(value=False)
        self.inv_roll = tk.BooleanVar(value=False)
        self.topmost = tk.BooleanVar(value=False)

        self._style()
        self._build_top()
        self._build_body()
        self._apply_config_to_widgets(self.profiles.get("default", MotionConfig()))
        self._push_config()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(33, self._refresh)

    # ------------------------------------------------------------ layout
    def _style(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure(".", background=BG, foreground=FG, fieldbackground=PANEL, font=("Segoe UI", 10))
        s.configure("Panel.TFrame", background=PANEL)
        s.configure("TLabelframe", background=PANEL, foreground=FG)
        s.configure("TLabelframe.Label", background=PANEL, foreground=ACCENT, font=("Segoe UI", 10, "bold"))
        s.configure("P.TLabel", background=PANEL, foreground=FG)
        s.configure("Dim.TLabel", background=PANEL, foreground=DIM)
        s.configure("Big.TLabel", background=PANEL, foreground=FG, font=("Segoe UI", 12, "bold"))
        s.configure("TCheckbutton", background=PANEL, foreground=FG)
        s.configure("TButton", padding=6)

    def _build_top(self):
        bar = ttk.Frame(self, style="Panel.TFrame", padding=8)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Игра:", style="P.TLabel").pack(side="left")
        self.game_box = ttk.Combobox(bar, state="readonly", width=30,
                                     values=[T.GAME_NAMES[k] for k in GAME_ORDER])
        self.game_box.current(0)
        self.game_box.pack(side="left", padx=(4, 8))
        ttk.Button(bar, text="Запустить в Steam", command=self._launch_steam).pack(side="left", padx=2)
        ttk.Label(bar, text="  Частота:", style="P.TLabel").pack(side="left")
        self.rate_box = ttk.Combobox(bar, state="readonly", width=8, values=RATES)
        self.rate_box.current(0)
        self.rate_box.pack(side="left", padx=4)
        self.start_btn = ttk.Button(bar, text="▶ Старт", command=self._toggle)
        self.start_btn.pack(side="left", padx=(10, 2))
        ttk.Button(bar, text="Тест движения", command=self._test).pack(side="left", padx=2)
        ttk.Checkbutton(bar, text="Поверх всех окон", variable=self.topmost,
                        command=lambda: self.attributes("-topmost", self.topmost.get())
                        ).pack(side="right")

        self.status = ttk.Label(self, text="", style="Big.TLabel", padding=(12, 4))
        self.status.pack(fill="x", padx=8)

    def _build_body(self):
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=8, pady=4)
        left = ttk.Frame(body, style="Panel.TFrame", padding=8)
        left.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(body, style="Panel.TFrame", padding=8, width=380)
        right.pack(side="right", fill="y", padx=(8, 0))
        right.pack_propagate(False)

        views = ttk.Frame(left, style="Panel.TFrame")
        views.pack(fill="both", expand=True)
        self.side = self._view(views, "Вид сбоку — наклон вперёд/назад", 0, 300, 260)
        self.rear = self._view(views, "Вид сзади — наклон влево/вправо", 1, 300, 260)
        self.lift = self._view(views, "Подъём / опускание", 2, 140, 260)
        self.pitch_lbl = self._text(views, 0)
        self.roll_lbl = self._text(views, 1)
        self.heave_lbl = self._text(views, 2)
        for c in range(3):
            views.columnconfigure(c, weight=1 if c < 2 else 0)

        info = ttk.LabelFrame(left, text="Что сейчас делает автомобиль", padding=8)
        info.pack(fill="x", pady=(8, 0))
        self.long_lbl = ttk.Label(info, style="P.TLabel", text="")
        self.lat_lbl = ttk.Label(info, style="P.TLabel", text="")
        self.vert_lbl = ttk.Label(info, style="P.TLabel", text="")
        for w in (self.long_lbl, self.lat_lbl, self.vert_lbl):
            w.pack(anchor="w")
        self.stats_lbl = ttk.Label(left, style="Dim.TLabel", text="")
        self.stats_lbl.pack(anchor="w", pady=(6, 0))
        ttk.Label(left, style="Dim.TLabel", wraplength=640,
                  text=f"Углы на рисунке увеличены в {VISUAL_GAIN:.0f} раза; цифры показывают реальные "
                       "значения команды. Это виртуальная платформа: физические пределы хода пока неизвестны."
                  ).pack(anchor="w")

        # --- tuning panel
        tune = ttk.LabelFrame(right, text="Настройка (калибровка виртуальной платформы)", padding=8)
        tune.pack(fill="x")
        for key, label, lo, hi, fmt in SLIDERS:
            self._slider(tune, key, label, lo, hi, fmt)
        ttk.Checkbutton(tune, text="Инвертировать наклон вперёд/назад", variable=self.inv_pitch,
                        command=self._push_config).pack(anchor="w", pady=(6, 0))
        ttk.Checkbutton(tune, text="Инвертировать наклон влево/вправо", variable=self.inv_roll,
                        command=self._push_config).pack(anchor="w")
        row = ttk.Frame(tune, style="Panel.TFrame")
        row.pack(fill="x", pady=(8, 0))
        self.profile_lbl = ttk.Label(tune, style="Dim.TLabel", text="Профиль: общий")
        self.profile_lbl.pack(anchor="w")
        ttk.Button(row, text="Сохранить профиль", command=self._save).pack(side="left")
        ttk.Button(row, text="Сбросить", command=self._reset).pack(side="left", padx=6)

        hw = ttk.LabelFrame(right, text="Калибровка реальной платформы", padding=8)
        hw.pack(fill="x", pady=(10, 0))
        ttk.Label(hw, style="Dim.TLabel", wraplength=340,
                  text="Нулевое положение, пределы хода и скорость приводов будут "
                       "доступны после подключения контроллера (ESP32). Сейчас контроллера нет."
                  ).pack(anchor="w")
        ttk.Button(hw, text="Найти центр платформы", state="disabled").pack(anchor="w", pady=(6, 0))

    def _view(self, parent, title, col, w, h):
        frame = ttk.LabelFrame(parent, text=title, padding=4)
        frame.grid(row=0, column=col, sticky="nsew", padx=4, pady=4)
        canvas = tk.Canvas(frame, width=w, height=h, bg="#14161a", highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        return canvas

    def _text(self, parent, col):
        lbl = ttk.Label(parent, style="Big.TLabel", text="", wraplength=290)
        lbl.grid(row=1, column=col, sticky="w", padx=6, pady=(0, 4))
        return lbl

    def _slider(self, parent, key, label, lo, hi, fmt):
        ttk.Label(parent, text=label, style="P.TLabel", wraplength=340).pack(anchor="w", pady=(4, 0))
        row = ttk.Frame(parent, style="Panel.TFrame")
        row.pack(fill="x")
        var = tk.DoubleVar(value=lo)
        self.vars[key] = var
        val = ttk.Label(row, width=6, style="P.TLabel", text=fmt.format(lo))
        self.value_labels[key] = val

        def changed(_=None, k=key, f=fmt, v=var, l=val):
            l.config(text=f.format(v.get()))
            self._push_config()
        ttk.Scale(row, from_=lo, to=hi, variable=var, command=changed).pack(
            side="left", fill="x", expand=True)
        val.pack(side="right")
        var._fmt = fmt  # type: ignore[attr-defined]

    # ------------------------------------------------------------ config
    def _config_from_widgets(self) -> MotionConfig:
        v = {k: var.get() for k, var in self.vars.items()}
        return MotionConfig(
            longitudinal_g_gain=v["long_gain"], lateral_g_gain=v["lat_gain"],
            vertical_g_gain=v["vert_gain"],
            max_pitch_deg=v["max_pitch"], max_roll_deg=v["max_roll"],
            pitch_filter_tau_s=v["smooth"], roll_filter_tau_s=v["smooth"],
            heave_filter_tau_s=v["smooth"] * 1.2,
            longitudinal_washout_tau_s=v["washout"], lateral_washout_tau_s=v["washout"],
            max_pitch_rate_deg_s=v["rate"], max_roll_rate_deg_s=v["rate"],
            pitch_sign=-1.0 if self.inv_pitch.get() else 1.0,
            roll_sign=-1.0 if self.inv_roll.get() else 1.0,
        )

    def _apply_config_to_widgets(self, c: MotionConfig):
        values = {"long_gain": c.longitudinal_g_gain, "lat_gain": c.lateral_g_gain,
                  "vert_gain": c.vertical_g_gain, "max_pitch": c.max_pitch_deg,
                  "max_roll": c.max_roll_deg, "smooth": c.pitch_filter_tau_s,
                  "washout": c.longitudinal_washout_tau_s, "rate": c.max_pitch_rate_deg_s}
        for key, value in values.items():
            self.vars[key].set(value)
            self.value_labels[key].config(text=self.vars[key]._fmt.format(value))  # type: ignore[attr-defined]
        self.inv_pitch.set(c.pitch_sign < 0)
        self.inv_roll.set(c.roll_sign < 0)

    def _push_config(self):
        self.runner.set_config(self._config_from_widgets())

    def _save(self):
        save_profile(self.profile_name, self._config_from_widgets())
        self.profiles[self.profile_name] = self._config_from_widgets()
        messagebox.showinfo("Сохранено", f"Профиль «{self._profile_title()}» сохранён (settings.json).")

    def _reset(self):
        self._apply_config_to_widgets(MotionConfig())
        self._push_config()

    def _profile_title(self):
        return T.GAME_NAMES.get(self.profile_name, "общий")

    # ------------------------------------------------------------ actions
    def _selected_game(self) -> str:
        return GAME_ORDER[self.game_box.current()]

    def _rate(self) -> int:
        return int(RATES[self.rate_box.current()].split()[0])

    def _toggle(self):
        if self.runner.is_running():
            self.runner.stop()
        else:
            self.runner.start(self._selected_game(), self._rate())

    def _test(self):
        if self.runner.is_running():
            self.runner.stop()
        self.runner.start_test(100)

    def _launch_steam(self):
        game = self._selected_game()
        if game not in STEAM_IDS:
            messagebox.showinfo("Выберите игру", "В списке выберите конкретную игру, "
                                "затем нажмите «Запустить в Steam».")
            return
        try:
            os.startfile(f"steam://rungameid/{STEAM_IDS[game]}")  # type: ignore[attr-defined]
        except Exception as exc:
            messagebox.showerror("Не удалось запустить Steam", str(exc))
            return
        if not self.runner.is_running():
            self.runner.start(game, self._rate())

    def _close(self):
        self.runner.stop()
        self.destroy()

    # ------------------------------------------------------------ drawing
    def _refresh(self):
        snap = self.runner.snapshot()
        running = self.runner.is_running()
        self.start_btn.config(text="■ Стоп" if running else "▶ Старт")

        game_name = T.GAME_NAMES.get(snap.game, snap.game)
        state = T.STATE_NAMES.get(snap.state, snap.state)
        text = f"Состояние: {state}"
        if snap.game and snap.game not in ("auto", "test"):
            text += f"  |  Игра: {game_name}"
        if snap.message:
            text += f"  |  {snap.message}"
        self.status.config(text=text, foreground=WARN if snap.state in ("stale", "error") else
                           OK if snap.state in ("connected", "test") else FG)

        if snap.game in STEAM_IDS and snap.game != self.loaded_game:
            self.loaded_game = snap.game
            self.profile_name = snap.game
            if snap.game in self.profiles:
                self._apply_config_to_widgets(self.profiles[snap.game])
                self._push_config()
            self.profile_lbl.config(text=f"Профиль: {self._profile_title()}")

        cmd = snap.command
        pitch = cmd.pitch_deg if cmd else 0.0
        roll = cmd.roll_deg if cmd else 0.0
        heave = cmd.heave_norm if cmd else 0.0
        cfg = self._config_from_widgets()
        self._draw_side(pitch, cfg.max_pitch_deg)
        self._draw_rear(roll, cfg.max_roll_deg)
        self._draw_lift(heave)
        self.pitch_lbl.config(text=T.pitch_text(pitch))
        self.roll_lbl.config(text=T.roll_text(roll))
        self.heave_lbl.config(text=T.heave_text(heave))

        v = snap.vehicle
        if v is not None and snap.state in ("connected", "stale"):
            self.long_lbl.config(text=T.long_g_text(v.longitudinal_g))
            self.lat_lbl.config(text=T.lat_g_text(v.lateral_g))
            self.vert_lbl.config(text=T.vert_g_text(v.vertical_g))
        else:
            for w in (self.long_lbl, self.lat_lbl, self.vert_lbl):
                w.config(text="—")
        self.stats_lbl.config(text=T.stats_text(snap.loop_hz, snap.max_ms, snap.samples, snap.missed))
        self.after(33, self._refresh)

    def _seat_side(self):
        base = [(-70, -8), (70, -8), (70, 8), (-70, 8)]
        back = [(-70, -8), (-54, -8), (-54, -84), (-70, -84)]
        head = [(-72, -84), (-50, -84), (-50, -108), (-72, -108)]
        return [("#4da3ff", base), ("#6bb6ff", back), ("#9ccbff", head)]

    def _seat_rear(self):
        base = [(-70, -8), (70, -8), (70, 8), (-70, 8)]
        back = [(-34, -8), (34, -8), (34, -84), (-34, -84)]
        head = [(-20, -84), (20, -84), (20, -108), (-20, -108)]
        return [("#4da3ff", base), ("#6bb6ff", back), ("#9ccbff", head)]

    def _draw_tilt(self, canvas, angle_deg, limit_deg, parts, left_text, right_text):
        canvas.delete("all")
        w, h = int(canvas["width"]), int(canvas["height"])
        cx, cy = w / 2, h * 0.62
        canvas.create_line(10, cy, w - 10, cy, fill="#3a3f47", dash=(4, 4))
        for sign in (-1, 1):  # limit markers
            a = radians(sign * limit_deg * VISUAL_GAIN)
            canvas.create_line(cx, cy, cx + 110 * cos(a), cy + 110 * sin(a), fill="#4a3f2a")
        for color, pts in parts:
            canvas.create_polygon(_rot(pts, angle_deg * VISUAL_GAIN, cx, cy),
                                  fill=color, outline="")
        canvas.create_text(14, 14, text=left_text, fill=DIM, anchor="w")
        canvas.create_text(w - 14, 14, text=right_text, fill=DIM, anchor="e")

    def _draw_side(self, pitch_deg, limit):
        # pitch < 0 = forward = front (right side of the drawing) goes down = clockwise
        self._draw_tilt(self.side, -pitch_deg, limit, self._seat_side(), "назад", "вперёд →")

    def _draw_rear(self, roll_deg, limit):
        # roll < 0 = left side down = counter-clockwise (negative screen angle)
        self._draw_tilt(self.rear, roll_deg, limit, self._seat_rear(), "← влево", "вправо →")

    def _draw_lift(self, heave):
        c = self.lift
        c.delete("all")
        w, h = int(c["width"]), int(c["height"])
        cx, top, bottom = w / 2, 34, h - 34
        mid = (top + bottom) / 2
        c.create_rectangle(cx - 6, top, cx + 6, bottom, fill="#2a2e35", outline="")
        c.create_line(cx - 30, mid, cx + 30, mid, fill="#3a3f47")
        y = mid - max(-1.0, min(1.0, heave)) * (bottom - top) / 2
        c.create_rectangle(cx - 28, y - 7, cx + 28, y + 7, fill=ACCENT, outline="")
        c.create_text(cx, 14, text="вверх", fill=DIM)
        c.create_text(cx, h - 14, text="вниз", fill=DIM)


def main():
    _timer_resolution(True)
    try:
        App().mainloop()
    finally:
        _timer_resolution(False)


if __name__ == "__main__":
    main()
