"""Simple offline desktop calendar.
Click any date -> add one or more events, each with its own color.
A day shows the colors of all its events. Hover a day -> see its events.
Drag the month title bar to move it. Right-click -> transparency, size, theme, exit.
Data is saved in your home folder: desktop_calendar_data.json
Errors (if any) go to: desktop_calendar_error.log  (the app keeps running)
"""
import calendar
import datetime
import json
import os
import socket
import sys
import tkinter as tk
import tkinter.font as tkfont
import traceback

HOME = os.path.expanduser("~")
DATA = os.path.join(HOME, "desktop_calendar_data.json")
LOG = os.path.join(HOME, "desktop_calendar_error.log")
APP = "DesktopCalendar"
IS_WIN = os.name == "nt"
FONT = "Segoe UI" if IS_WIN else "Arial"
COLORS = {
    "Red": "#ff8a80",
    "Orange": "#ffcc80",
    "Yellow": "#fff59d",
    "Green": "#a5d6a7",
    "Blue": "#90caf9",
    "Purple": "#ce93d8",
}
THEMES = {
    "dark": dict(bg="#1e1e1e", head="#2d2d2d", fg="#e6e6e6", dim="#707070", grid="#2a2a2a", today="#ffffff"),
    "light": dict(bg="#ffffff", head="#dddddd", fg="#000000", dim="#b0b0b0", grid="#eeeeee", today="#000000"),
}
DEFAULT_SETTINGS = {"theme": "dark", "alpha": 0.8, "size": 9}
TIP_BG = "#ffffe0"


def log_error(text):
    try:
        if os.path.exists(LOG) and os.path.getsize(LOG) > 200000:
            os.remove(LOG)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(datetime.datetime.now().isoformat() + "\n" + text + "\n")
    except Exception:
        pass


# ---- only one calendar at a time ----
try:
    _lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _lock.bind(("127.0.0.1", 47391))
except OSError:
    sys.exit(0)


# ---- auto-start with Windows ----
def startup_command():
    exe = sys.executable
    folder, name = os.path.split(exe)
    if name.lower() == "python.exe" and os.path.exists(os.path.join(folder, "pythonw.exe")):
        exe = os.path.join(folder, "pythonw.exe")
    return '"%s" "%s"' % (exe, os.path.abspath(__file__))


def set_autostart(on):
    if not IS_WIN:
        return
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                           r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        if on:
            winreg.SetValueEx(k, APP, 0, winreg.REG_SZ, startup_command())
        else:
            try:
                winreg.DeleteValue(k, APP)
            except FileNotFoundError:
                pass
        winreg.CloseKey(k)
    except Exception:
        log_error(traceback.format_exc())
    try:  # launcher from the very first version
        os.remove(os.path.join(os.environ.get("APPDATA", ""),
                               r"Microsoft\Windows\Start Menu\Programs\Startup\DesktopCalendar.vbs"))
    except Exception:
        pass


# ---- saving ----
def normalize(v):
    """Any old or new format -> list of {"text", "color"}."""
    if isinstance(v, str):  # very first version: just a color
        v = {"color": v, "text": ""}
    if not isinstance(v, dict):
        return []
    items = v["events"] if isinstance(v.get("events"), list) else [v]
    out = []
    for e in items:
        if not isinstance(e, dict):
            continue
        text = str(e.get("text") or "").strip()
        color = e.get("color") if e.get("color") in COLORS else None
        if text or color:
            out.append({"text": text, "color": color})
    return out


def load():
    marks, settings = {}, dict(DEFAULT_SETTINGS)
    if not os.path.exists(DATA):
        return marks, settings
    try:
        with open(DATA, "r", encoding="utf-8") as f:
            raw = json.load(f)
        src = {}
        if isinstance(raw, dict) and isinstance(raw.get("marks"), dict):
            src = raw["marks"]
            if isinstance(raw.get("settings"), dict):
                settings.update(raw["settings"])
        elif isinstance(raw, dict):
            src = raw
        for k, v in src.items():
            evs = normalize(v)
            if evs:
                marks[k] = {"events": evs}
    except Exception:
        log_error(traceback.format_exc())
        try:
            os.replace(DATA, DATA + ".broken")
        except Exception:
            pass
    if settings.get("theme") not in THEMES:
        settings["theme"] = "dark"
    return marks, settings


def save():
    tmp = DATA + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"marks": marks, "settings": settings}, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, DATA)
    except Exception:
        log_error(traceback.format_exc())


def events_for(d):
    return (marks.get(d.isoformat()) or {}).get("events", [])


marks, settings = load()
today = datetime.date.today()
view = {"y": today.year, "m": today.month}

root = tk.Tk()
root.title("Calendar")
root.resizable(False, False)
root.report_callback_exception = lambda *a: log_error("".join(traceback.format_exception(*a)))
root.protocol("WM_DELETE_WINDOW", lambda: None)
if IS_WIN:
    root.overrideredirect(True)

header = tk.Frame(root)
header.pack(fill="x")
btn_prev = tk.Label(header, text=" < ", cursor="hand2")
btn_prev.pack(side="left")
btn_next = tk.Label(header, text=" > ", cursor="hand2")
btn_next.pack(side="right")
title = tk.Label(header, text="")
title.pack(side="left", expand=True, fill="x")

grid = tk.Frame(root)
grid.pack(padx=3, pady=3)

day_names = []
for i, d in enumerate(["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]):
    lb = tk.Label(grid, text=d)
    lb.grid(row=0, column=i)
    day_names.append(lb)

cells = []
for i in range(42):
    cv = tk.Canvas(grid, highlightthickness=1, bd=0, cursor="hand2")
    cv.grid(row=i // 7 + 1, column=i % 7, padx=1, pady=1)
    cv._date = None
    cells.append(cv)

cell = {"w": 30, "h": 22}


def render():
    t = THEMES[settings["theme"]]
    s = int(settings["size"])
    title.config(text=calendar.month_name[view["m"]] + " " + str(view["y"]))
    first = calendar.Calendar(0).monthdatescalendar(view["y"], view["m"])[0][0]
    W, H = cell["w"] + 2, cell["h"] + 2
    for i, cv in enumerate(cells):
        d = first + datetime.timedelta(days=i)
        cv._date = d
        evs = events_for(d)
        colors = [COLORS[e["color"]] for e in evs if e.get("color") in COLORS]
        in_month = d.month == view["m"]
        is_today = d == today
        cv.delete("all")
        cv.config(bg=t["bg"], highlightbackground=t["today"] if is_today else t["grid"])
        # one stripe per colored event
        n = len(colors)
        for j, c in enumerate(colors):
            x0 = round(j * W / n)
            x1 = round((j + 1) * W / n)
            cv.create_rectangle(x0, 0, x1, H, fill=c, outline="")
        style = []
        if is_today:
            style.append("bold")
        if any(e.get("text") for e in evs):
            style.append("underline")  # underlined number = has named event(s)
        if colors:
            fg = "#000000" if in_month else "#666666"
        else:
            fg = t["fg"] if in_month else t["dim"]
        cv.create_text(W / 2, H / 2, text=str(d.day), fill=fg,
                       font=(FONT, s, " ".join(style) or "normal"))


def apply_look():
    t = THEMES[settings["theme"]]
    s = int(settings["size"])
    f = tkfont.Font(root=root, family=FONT, size=s, weight="bold")
    cell["w"] = f.measure("00") + 12
    cell["h"] = f.metrics("linespace") + 6
    for cv in cells:
        cv.config(width=cell["w"], height=cell["h"])
    root.config(bg=t["bg"])
    grid.config(bg=t["bg"])
    header.config(bg=t["head"])
    for w in (btn_prev, btn_next, title):
        w.config(bg=t["head"], fg=t["fg"], font=(FONT, s + 1, "bold"))
    for lb in day_names:
        lb.config(bg=t["bg"], fg=t["dim"], font=(FONT, s - 1, "bold"))
    try:
        root.attributes("-alpha", float(settings["alpha"]))
    except Exception:
        pass
    render()
    place_top_right()


# ---- hover tooltip (one window, reused) ----
tip = tk.Toplevel(root)
tip.overrideredirect(True)
tip.withdraw()
tip.attributes("-topmost", True)
tip_box = tk.Frame(tip, bg=TIP_BG, relief="solid", bd=1)
tip_box.pack()
tip_job = {"id": None}


def hide_tip(event=None):
    if tip_job["id"]:
        root.after_cancel(tip_job["id"])
        tip_job["id"] = None
    tip.withdraw()


def show_tip(w):
    tip_job["id"] = None
    d = w._date
    evs = events_for(d)
    if not evs:
        return
    for ch in tip_box.winfo_children():
        ch.destroy()
    tk.Label(tip_box, text=d.strftime("%A, %d %B"), bg=TIP_BG, fg="#000000",
             font=(FONT, 9, "bold")).pack(anchor="w", padx=6, pady=(3, 1))
    for e in evs:
        row = tk.Frame(tip_box, bg=TIP_BG)
        row.pack(anchor="w", padx=6, pady=1)
        tk.Label(row, text="", width=2, bg=COLORS.get(e.get("color"), TIP_BG),
                 relief="solid" if e.get("color") else "flat", bd=1).pack(side="left")
        tk.Label(row, text=e.get("text") or "(no name)", bg=TIP_BG, fg="#000000",
                 font=(FONT, 9), justify="left", wraplength=240).pack(side="left", padx=(4, 0))
    tk.Frame(tip_box, bg=TIP_BG, height=3).pack()
    tip.update_idletasks()
    tw = tip.winfo_reqwidth()
    x = min(w.winfo_rootx(), root.winfo_screenwidth() - tw - 5)
    y = w.winfo_rooty() + w.winfo_height() + 2
    tip.geometry("+%d+%d" % (x, y))
    tip.deiconify()
    tip.lift()


def on_enter(event):
    hide_tip()
    tip_job["id"] = root.after(250, lambda w=event.widget: show_tip(w))


# ---- editor window (click a date) ----
editor = {"win": None}


def close_editor():
    if editor["win"] is not None:
        try:
            editor["win"].destroy()
        except Exception:
            pass
        editor["win"] = None


def open_editor(d, x, y):
    hide_tip()
    close_editor()
    k = d.isoformat()
    win = tk.Toplevel(root)
    editor["win"] = win
    win.title(d.strftime("%d %B %Y"))
    win.resizable(False, False)
    win.attributes("-topmost", True)
    win.protocol("WM_DELETE_WINDOW", close_editor)

    tk.Label(win, text=d.strftime("%A, %d %B %Y"), font=(FONT, 10, "bold")).pack(padx=8, pady=(8, 4), anchor="w")
    lst = tk.Frame(win)
    lst.pack(padx=8, fill="x")
    rows = []

    def pick(r, name):
        r["color"] = name
        for n, sw in r["sw"].items():
            sw.config(relief="solid" if n == name else "flat", bd=2 if n == name else 1)

    def remove_row(r):
        r["frame"].destroy()
        rows.remove(r)

    def next_color():
        used = {r["color"] for r in rows}
        for name in COLORS:
            if name not in used:
                return name
        return list(COLORS)[len(rows) % len(COLORS)]

    def add_row(text="", color="auto"):
        if color == "auto":
            color = next_color()
        fr = tk.Frame(lst)
        fr.pack(fill="x", pady=2)
        var = tk.StringVar(value=text)
        ent = tk.Entry(fr, textvariable=var, width=24, font=(FONT, 10))
        ent.pack(side="left", padx=(0, 6))
        ent.bind("<Return>", do_save)
        r = {"frame": fr, "var": var, "color": color, "sw": {}}
        for name in [None] + list(COLORS):
            sw = tk.Label(fr, text="x" if name is None else "", width=2,
                          bg=COLORS.get(name, "#f0f0f0"), cursor="hand2")
            sw.pack(side="left", padx=1)
            sw.bind("<Button-1>", lambda e, n=name, r=r: pick(r, n))
            r["sw"][name] = sw
        tk.Button(fr, text="Remove", command=lambda r=r: remove_row(r)).pack(side="left", padx=(6, 0))
        rows.append(r)
        pick(r, color)
        ent.focus_set()
        return ent

    def do_save(event=None):
        evs = []
        for r in rows:
            text = r["var"].get().strip()
            if text or r["color"]:
                evs.append({"text": text, "color": r["color"]})
        if evs:
            marks[k] = {"events": evs}
        else:
            marks.pop(k, None)
        save()
        render()
        close_editor()

    def do_delete_all():
        marks.pop(k, None)
        save()
        render()
        close_editor()

    existing = events_for(d)
    for e in existing:
        add_row(e.get("text", ""), e.get("color"))
    if not existing:
        add_row()

    tk.Button(win, text="+ Add event", command=lambda: add_row()).pack(padx=8, pady=6, anchor="w")

    btns = tk.Frame(win)
    btns.pack(padx=8, pady=(0, 8), fill="x")
    tk.Button(btns, text="Save", width=8, command=do_save).pack(side="left")
    tk.Button(btns, text="Delete all", width=9, command=do_delete_all).pack(side="left", padx=4)
    tk.Button(btns, text="Cancel", width=8, command=close_editor).pack(side="right")

    win.bind("<Escape>", lambda e: close_editor())

    win.update_idletasks()
    ww, wh = win.winfo_reqwidth(), win.winfo_reqheight()
    x = max(5, min(x - ww // 2, root.winfo_screenwidth() - ww - 10))
    y = max(5, min(y + 10, root.winfo_screenheight() - wh - 60))
    win.geometry("+%d+%d" % (x, y))
    win.focus_force()
    if rows:
        rows[-1]["frame"].winfo_children()[0].focus_set()


def on_click(event):
    d = getattr(event.widget, "_date", None)
    if d:
        open_editor(d, event.x_root, event.y_root)


def shift(delta):
    m = view["m"] + delta
    y = view["y"]
    if m < 1:
        m, y = 12, y - 1
    elif m > 12:
        m, y = 1, y + 1
    view["m"], view["y"] = m, y
    hide_tip()
    render()


def go_today():
    view["y"], view["m"] = today.year, today.month
    render()


def exit_and_disable():
    set_autostart(False)
    root.destroy()


# ---- position & dragging ----
def screen_area():
    """Whole desktop area (all monitors on Windows)."""
    if IS_WIN:
        try:
            gm = ctypes.windll.user32.GetSystemMetrics
            left, top, w, h = gm(76), gm(77), gm(78), gm(79)
            if w > 0 and h > 0:
                return left, top, left + w, top + h
        except Exception:
            pass
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()


drag = {"on": False, "dx": 0, "dy": 0}


def place_top_right():
    if drag["on"]:
        return
    root.update_idletasks()
    w, h = root.winfo_reqwidth(), root.winfo_reqheight()
    left, top, right, bottom = screen_area()
    if "x" in settings and "y" in settings:
        x = min(max(left, int(settings["x"])), right - w)
        y = min(max(top, int(settings["y"])), bottom - h)
    else:
        x = root.winfo_screenwidth() - w - 30
        y = 50
    if root.winfo_x() != x or root.winfo_y() != y:
        root.geometry("+%d+%d" % (x, y))


def drag_start(event):
    hide_tip()
    drag["on"] = True
    drag["dx"] = event.x_root - root.winfo_x()
    drag["dy"] = event.y_root - root.winfo_y()


def drag_move(event):
    if drag["on"]:
        root.geometry("+%d+%d" % (event.x_root - drag["dx"], event.y_root - drag["dy"]))


def drag_end(event):
    if drag["on"]:
        drag["on"] = False
        settings["x"], settings["y"] = root.winfo_x(), root.winfo_y()
        save()
        place_top_right()


def reset_position():
    settings.pop("x", None)
    settings.pop("y", None)
    save()
    place_top_right()


# ---- right-click menu ----
theme_var = tk.StringVar(value=settings["theme"])
alpha_var = tk.DoubleVar(value=float(settings["alpha"]))
size_var = tk.IntVar(value=int(settings["size"]))


def set_setting(name, value):
    settings[name] = value
    save()
    apply_look()


menu = tk.Menu(root, tearoff=0)
menu.add_command(label="Go to this month", command=go_today)
menu.add_separator()
m_alpha = tk.Menu(menu, tearoff=0)
for label, v in [("100% (solid)", 1.0), ("90%", 0.9), ("80%", 0.8), ("65%", 0.65), ("50%", 0.5), ("35%", 0.35)]:
    m_alpha.add_radiobutton(label=label, variable=alpha_var, value=v,
                            command=lambda v=v: set_setting("alpha", v))
menu.add_cascade(label="Transparency", menu=m_alpha)
m_size = tk.Menu(menu, tearoff=0)
for label, v in [("Tiny", 7), ("Small", 9), ("Medium", 11), ("Large", 13)]:
    m_size.add_radiobutton(label=label, variable=size_var, value=v,
                           command=lambda v=v: set_setting("size", v))
menu.add_cascade(label="Size", menu=m_size)
m_theme = tk.Menu(menu, tearoff=0)
for label, v in [("Dark", "dark"), ("Light", "light")]:
    m_theme.add_radiobutton(label=label, variable=theme_var, value=v,
                            command=lambda v=v: set_setting("theme", v))
menu.add_cascade(label="Theme", menu=m_theme)
menu.add_command(label="Move back to top-right", command=reset_position)
menu.add_separator()
menu.add_command(label="Exit (starts again next login)", command=root.destroy)
menu.add_command(label="Exit and turn off auto-start", command=exit_and_disable)


def show_menu(event):
    hide_tip()
    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()


for cv in cells:
    cv.bind("<Button-1>", on_click)
    cv.bind("<Enter>", on_enter)
    cv.bind("<Leave>", hide_tip)
btn_prev.bind("<Button-1>", lambda e: shift(-1))
btn_next.bind("<Button-1>", lambda e: shift(1))
for w in (title, header):
    w.config(cursor="fleur")
    w.bind("<Button-1>", drag_start)
    w.bind("<B1-Motion>", drag_move)
    w.bind("<ButtonRelease-1>", drag_end)
for w in [header, title, grid, btn_prev, btn_next] + day_names + cells:
    w.bind("<Button-3>", show_menu)
    w.bind("<Button-2>", show_menu)  # macOS right-click


# ---- Windows: sit on the desktop, behind every program ----
if IS_WIN:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    HWND_TOPMOST, HWND_NOTOPMOST, HWND_BOTTOM = -1, -2, 1
    FLAGS = 0x0001 | 0x0002 | 0x0010  # NOSIZE | NOMOVE | NOACTIVATE
    MY_PID = os.getpid()
    _cls = ctypes.create_unicode_buffer(64)
    _pid = wintypes.DWORD()
    z = {"mode": None}

    def keep_on_desktop():
        hwnd = int(root.wm_frame(), 16)
        fg = user32.GetForegroundWindow()
        if not fg:
            return
        user32.GetWindowThreadProcessId(fg, ctypes.byref(_pid))
        if _pid.value == MY_PID:
            return  # user is using the calendar / editor / menu
        user32.GetClassNameW(fg, _cls, 64)
        if _cls.value in ("WorkerW", "Progman"):
            if z["mode"] != "front":
                user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, FLAGS)
                if editor["win"] is not None:
                    editor["win"].attributes("-topmost", True)
                z["mode"] = "front"
        else:
            if z["mode"] != "back":
                user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, FLAGS)
                hide_tip()
                if editor["win"] is not None:
                    editor["win"].attributes("-topmost", False)
            user32.SetWindowPos(hwnd, HWND_BOTTOM, 0, 0, 0, 0, FLAGS)
            z["mode"] = "back"
else:
    def keep_on_desktop():
        pass


def fast_loop():
    try:
        keep_on_desktop()
        if root.state() != "normal":
            root.deiconify()
    except Exception:
        log_error(traceback.format_exc())
    root.after(300, fast_loop)


def slow_loop():
    global today
    try:
        now = datetime.date.today()
        if now != today:
            today = now
            render()
        place_top_right()
    except Exception:
        log_error(traceback.format_exc())
    root.after(30000, slow_loop)


set_autostart(True)
apply_look()
fast_loop()
slow_loop()
root.mainloop()
