"""Simple offline desktop calendar with a notes panel.
Click any date -> add one or more events, each with its own color.
A day shows the colors of all its events. Hover a day -> see its events.
Click the month title -> pick a month; click again -> pick a year.
Drag the title bar to move it. Right-click -> blur, transparency, size, theme, notes, exit.
Data is saved in your home folder: desktop_calendar_data.json and desktop_calendar_notes.txt
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
NOTES = os.path.join(HOME, "desktop_calendar_notes.txt")
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
    "dark": dict(bg="#16181c", fg="#e9eaee", dim="#70747d", hover="#262a31", line="#2b2f36",
                 today="#ffffff", sel="#30353f", tint=0x781C1816,
                 wkend="#ff6b6b", wkend_dim="#7d4545"),
    "light": dict(bg="#f4f5f7", fg="#1b1d22", dim="#80848c", hover="#e2e5ea", line="#c9cdd3",
                  today="#1b1d22", sel="#d3d8e0", tint=0x90F7F5F4,
                  wkend="#d43c3c", wkend_dim="#e6a8a8"),
}
DEFAULT_SETTINGS = {"theme": "dark", "alpha": 0.85, "size": 9, "blur": False, "notes": True,
                    "week_start": 0}  # 0 = Monday, 6 = Sunday
DAY_ABBR = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
MONTHS = [calendar.month_abbr[i] for i in range(1, 13)]

if IS_WIN:
    import ctypes
    from ctypes import wintypes


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
    low = name.lower()
    if low.startswith("python") and not low.startswith("pythonw"):
        w = os.path.join(folder, "pythonw" + name[len("python"):])
        if os.path.exists(w):
            exe = w
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


def write_atomic(path, text):
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        log_error(traceback.format_exc())


def save():
    write_atomic(DATA, json.dumps({"marks": marks, "settings": settings}, ensure_ascii=False))


def load_notes():
    try:
        with open(NOTES, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""
    except Exception:
        log_error(traceback.format_exc())
        return ""


def events_for(d):
    return (marks.get(d.isoformat()) or {}).get("events", [])


marks, settings = load()
for _k, _v in DEFAULT_SETTINGS.items():
    settings.setdefault(_k, _v)
today = datetime.date.today()
# mode: "days" (normal), "months" (pick a month), "years" (pick a year)
view = {"y": today.year, "m": today.month, "mode": "days", "ystart": today.year - today.year % 12}

root = tk.Tk()
root.title("Calendar")
root.resizable(False, False)
root.report_callback_exception = lambda *a: log_error("".join(traceback.format_exception(*a)))
root.protocol("WM_DELETE_WINDOW", lambda: None)
if IS_WIN:
    root.overrideredirect(True)

# layout: [notes | divider | calendar]
cal = tk.Frame(root)
cal.pack(side="right", fill="y")
divider = tk.Frame(root, width=1)
notes = tk.Frame(root)

header = tk.Frame(cal)
header.pack(fill="x", pady=(4, 0))
btn_prev = tk.Label(header, text="‹", cursor="hand2", padx=8)
btn_prev.pack(side="left")
btn_next = tk.Label(header, text="›", cursor="hand2", padx=8)
btn_next.pack(side="right")
title = tk.Label(header, text="", cursor="hand2")
title.pack(side="left", expand=True, fill="x")

grid = tk.Frame(cal)
grid.pack(padx=6, pady=(2, 6))

day_names = []
for i in range(7):
    lb = tk.Label(grid)
    lb.grid(row=0, column=i, pady=(0, 2))
    day_names.append(lb)

cells = []
for i in range(42):
    cv = tk.Canvas(grid, highlightthickness=0, bd=0, cursor="hand2")
    cv.grid(row=i // 7 + 1, column=i % 7, padx=1, pady=1)
    cv._date = None
    cv._plain = True
    cells.append(cv)

# month / year picker, laid over the day grid so the window keeps its size
picker = tk.Frame(cal)
pick_cells = []
for i in range(12):
    lb = tk.Label(picker, cursor="hand2")
    lb.grid(row=i // 3, column=i % 3, sticky="nsew", padx=2, pady=2)
    lb._value = None
    lb._base = None
    pick_cells.append(lb)
for c in range(3):
    picker.columnconfigure(c, weight=1, uniform="pc")
for r in range(4):
    picker.rowconfigure(r, weight=1, uniform="pr")

# notes panel
notes_head = tk.Label(notes, text="Notes", anchor="w", padx=10)
notes_head.pack(fill="x", pady=(6, 0))
notes_text = tk.Text(notes, width=24, height=1, wrap="word", relief="flat", bd=0,
                     padx=10, pady=6, undo=True, highlightthickness=0)
notes_text.pack(fill="both", expand=True, pady=(2, 6))
notes_text.insert("1.0", load_notes())
notes_text.edit_reset()
notes_text.edit_modified(False)

cell = {"w": 30, "h": 22}


def theme():
    return THEMES[settings["theme"]]


def render_days():
    t = theme()
    s = int(settings["size"])
    ws = int(settings.get("week_start", 0))
    for i, lb in enumerate(day_names):
        wd = (ws + i) % 7
        lb.config(text=DAY_ABBR[wd], fg=t["wkend"] if wd >= 5 else t["fg"])
    first = calendar.Calendar(ws).monthdatescalendar(view["y"], view["m"])[0][0]
    W, H = cell["w"], cell["h"]
    for i, cv in enumerate(cells):
        d = first + datetime.timedelta(days=i)
        cv._date = d
        evs = events_for(d)
        colors = [COLORS[e["color"]] for e in evs if e.get("color") in COLORS]
        in_month = d.month == view["m"]
        is_today = d == today
        cv.delete("all")
        cv._plain = not colors
        cv.config(bg=t["bg"])
        # one stripe per colored event
        n = len(colors)
        for j, c in enumerate(colors):
            x0 = round(j * W / n)
            x1 = round((j + 1) * W / n)
            cv.create_rectangle(x0, 0, x1, H, fill=c, outline="")
        if is_today:
            cv.create_rectangle(0, 0, W - 1, H - 1, outline=t["today"], width=1)
        style = []
        if is_today:
            style.append("bold")
        if any(e.get("text") for e in evs):
            style.append("underline")  # underlined number = has named event(s)
        if colors:
            fg = "#000000" if in_month else "#555555"
        else:
            if d.weekday() >= 5:  # Saturday / Sunday in red
                fg = t["wkend"] if in_month else t["wkend_dim"]
            else:
                fg = t["fg"] if in_month else t["dim"]
        cv.create_text(W / 2, H / 2, text=str(d.day), fill=fg,
                       font=(FONT, s, " ".join(style) or "normal"))


def render_picker():
    t = theme()
    s = int(settings["size"])
    if view["mode"] == "months":
        values = list(range(1, 13))
        labels = MONTHS
        current = view["m"]
        now = today.month if view["y"] == today.year else None
    else:
        values = list(range(view["ystart"], view["ystart"] + 12))
        labels = [str(v) for v in values]
        current = view["y"]
        now = today.year
    for lb, v, text in zip(pick_cells, values, labels):
        lb._value = v
        sel = v == current
        bg = t["sel"] if sel else t["bg"]
        ring = t["today"] if v == now else bg
        lb.config(text=text, bg=bg, fg=t["fg"],
                  font=(FONT, s + 1, "bold" if v == now else "normal"),
                  highlightthickness=1, highlightbackground=ring, highlightcolor=ring)
        lb._base = bg


def render():
    mode = view["mode"]
    if mode == "days":
        title.config(text=calendar.month_name[view["m"]] + " " + str(view["y"]))
        picker.place_forget()
        render_days()
    else:
        if mode == "months":
            title.config(text=str(view["y"]))
        else:
            title.config(text="%d – %d" % (view["ystart"], view["ystart"] + 11))
        render_picker()
        picker.place(in_=grid, x=0, y=0, relwidth=1, relheight=1)
        picker.lift()


def apply_look():
    t = theme()
    s = int(settings["size"])
    f = tkfont.Font(root=root, family=FONT, size=s, weight="bold")
    cell["w"] = f.measure("00") + 14
    cell["h"] = f.metrics("linespace") + 8
    for cv in cells:
        cv.config(width=cell["w"], height=cell["h"])
    for w in (root, cal, grid, header, notes, picker):
        w.config(bg=t["bg"])
    divider.config(bg=t["line"])
    title.config(bg=t["bg"], fg=t["fg"], font=(FONT, s + 1, "bold"))
    for w in (btn_prev, btn_next):
        w.config(bg=t["bg"], fg=t["dim"], font=(FONT, s + 4))
    for lb in day_names:
        lb.config(bg=t["bg"], font=(FONT, s, "bold"))
    notes_head.config(bg=t["bg"], fg=t["dim"], font=(FONT, s - 1, "bold"))
    notes_text.config(bg=t["bg"], fg=t["fg"], insertbackground=t["fg"],
                      selectbackground=t["sel"], selectforeground=t["fg"],
                      font=(FONT, s + 1))
    show_notes(settings.get("notes", True), keep_right=False)
    try:
        root.attributes("-alpha", float(settings["alpha"]))
    except Exception:
        pass
    render()
    place_top_right()
    apply_glass()


# ---- glass (Windows blur behind the window) ----
if IS_WIN:
    class _ACCENT(ctypes.Structure):
        _fields_ = [("AccentState", ctypes.c_int), ("AccentFlags", ctypes.c_int),
                    ("GradientColor", ctypes.c_uint), ("AnimationId", ctypes.c_int)]

    class _WCAD(ctypes.Structure):
        _fields_ = [("Attribute", ctypes.c_int), ("Data", ctypes.c_void_p),
                    ("SizeOfData", ctypes.c_size_t)]


_hwnd = {}


def frame_hwnd():
    if "root" not in _hwnd:
        _hwnd["root"] = int(root.wm_frame(), 16)
    return _hwnd["root"]


def glass_on():
    return IS_WIN and bool(settings.get("blur", True))


def apply_glass():
    """Blur what is behind the window. Windows only blurs the pixels that are
    'see-through', so the background colour is made transparent (colour key)
    and an almost invisible 'catcher' window behind it takes the clicks that
    would otherwise fall through those pixels."""
    if not IS_WIN:
        return
    try:
        root.update_idletasks()
        hwnd = frame_hwnd()
        on = glass_on()
        root.attributes("-transparentcolor", theme()["bg"] if on else "")
        acc = _ACCENT(3 if on else 0, 2, theme()["tint"], 0)  # 3 = blur behind, 2 = use tint
        data = _WCAD(19, ctypes.cast(ctypes.pointer(acc), ctypes.c_void_p), ctypes.sizeof(acc))
        ctypes.windll.user32.SetWindowCompositionAttribute(wintypes.HWND(hwnd), ctypes.byref(data))
        pref = ctypes.c_int(2)  # Windows 11: rounded corners
        ctypes.windll.dwmapi.DwmSetWindowAttribute(wintypes.HWND(hwnd), 33,
                                                   ctypes.byref(pref), ctypes.sizeof(pref))
        if on:
            if catcher is None:
                make_catcher()
            catcher.deiconify()
        elif catcher is not None:
            catcher.withdraw()
        sync_catcher()
    except Exception:
        log_error(traceback.format_exc())


# ---- click catcher (only used with blur on Windows) ----
catcher = None
fwd = {"press": None, "hover": None}


def make_catcher():
    global catcher
    catcher = tk.Toplevel(root)
    catcher.withdraw()
    catcher.overrideredirect(True)
    catcher.config(bg="#000000")
    catcher.attributes("-alpha", 0.01)
    catcher.bind("<Motion>", c_hover)
    catcher.bind("<Leave>", c_leave)
    catcher.bind("<Button-1>", lambda e: c_press(e, "<Button-1>"))
    catcher.bind("<Double-Button-1>", lambda e: c_press(e, "<Double-Button-1>"))
    catcher.bind("<Button-3>", lambda e: c_press(e, "<Button-3>"))
    catcher.bind("<B1-Motion>", c_drag)
    catcher.bind("<ButtonRelease-1>", c_release)
    catcher.bind("<MouseWheel>", c_wheel)


def widget_at(xr, yr):
    """Deepest calendar widget under a screen point (ignores the pop-up windows)."""
    def walk(w):
        for ch in reversed(w.winfo_children()):
            if isinstance(ch, (tk.Toplevel, tk.Menu)) or not ch.winfo_ismapped():
                continue
            x, y = ch.winfo_rootx(), ch.winfo_rooty()
            if x <= xr < x + ch.winfo_width() and y <= yr < y + ch.winfo_height():
                return walk(ch) or ch
        return None
    return walk(root) or root


def fwd_event(target, seq, e, **kw):
    try:
        target.event_generate(seq, x=e.x_root - target.winfo_rootx(), y=e.y_root - target.winfo_rooty(),
                              rootx=e.x_root, rooty=e.y_root, **kw)
    except tk.TclError:
        pass


def c_hover(e):
    t = widget_at(e.x_root, e.y_root)
    if t is not fwd["hover"]:
        if fwd["hover"] is not None:
            fwd_event(fwd["hover"], "<Leave>", e)
        fwd["hover"] = t
        fwd_event(t, "<Enter>", e)
        try:
            catcher.config(cursor=t.cget("cursor"))
        except tk.TclError:
            catcher.config(cursor="")


def c_leave(e):
    if fwd["hover"] is not None:
        fwd_event(fwd["hover"], "<Leave>", e)
        fwd["hover"] = None


def c_press(e, seq):
    t = widget_at(e.x_root, e.y_root)
    fwd["press"] = t
    fwd_event(t, seq, e)


def c_drag(e):
    if fwd["press"] is not None:
        fwd_event(fwd["press"], "<B1-Motion>", e)


def c_release(e):
    if fwd["press"] is not None:
        fwd_event(fwd["press"], "<ButtonRelease-1>", e)
        fwd["press"] = None


def c_wheel(e):
    fwd_event(widget_at(e.x_root, e.y_root), "<MouseWheel>", e, delta=e.delta)


def sync_catcher():
    """Keep the catcher exactly under the calendar: same place, size and layer."""
    if catcher is None or not glass_on():
        return
    root.update_idletasks()
    g = "%dx%d+%d+%d" % (root.winfo_width(), root.winfo_height(), root.winfo_x(), root.winfo_y())
    if catcher.geometry() != g:
        catcher.geometry(g)
    try:
        u = ctypes.windll.user32
        ch = wintypes.HWND(int(catcher.wm_frame(), 16))
        ex = u.GetWindowLongW(ch, -20)
        if not ex & 0x08000000:  # never take focus or jump in front when clicked
            u.SetWindowLongW(ch, -20, ex | 0x08000000)
        # right below the calendar (this also copies its "always on top" state)
        u.SetWindowPos(ch, wintypes.HWND(frame_hwnd()), 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)
    except Exception:
        log_error(traceback.format_exc())


# ---- notes ----
notes_job = {"id": None}


def save_notes_now():
    if notes_job["id"]:
        root.after_cancel(notes_job["id"])
        notes_job["id"] = None
    write_atomic(NOTES, notes_text.get("1.0", "end-1c"))


def on_notes_change(event=None):
    if notes_text.edit_modified():
        notes_text.edit_modified(False)
        if notes_job["id"]:
            root.after_cancel(notes_job["id"])
        notes_job["id"] = root.after(700, save_notes_now)


def notes_focus(event=None):
    hide_tip()
    try:
        root.focus_force()
    except Exception:
        pass
    notes_text.focus_set()


def select_all(event=None):
    notes_text.tag_add("sel", "1.0", "end-1c")
    return "break"


notes_text.bind("<<Modified>>", on_notes_change)
notes_text.bind("<Button-1>", notes_focus, add="+")
notes_text.bind("<Control-a>", select_all)
notes_text.bind("<Control-A>", select_all)


def show_notes(on, keep_right=True):
    visible = bool(notes.winfo_manager())
    if on == visible:
        return
    root.update_idletasks()
    old_w = root.winfo_reqwidth()
    if on:
        notes.pack(side="left", fill="both", expand=True)
        divider.pack(side="left", fill="y", pady=10)
    else:
        save_notes_now()
        notes.pack_forget()
        divider.pack_forget()
    root.update_idletasks()
    # keep the calendar's right edge where it was: the notes grow to the left
    if keep_right and "x" in settings:
        settings["x"] = int(settings["x"]) - (root.winfo_reqwidth() - old_w)


def toggle_notes():
    settings["notes"] = notes_var.get()
    show_notes(settings["notes"])
    save()
    place_top_right()


# ---- hover tooltip (one window, reused) ----
tip = tk.Toplevel(root)
tip.overrideredirect(True)
tip.withdraw()
tip.attributes("-topmost", True)
tip_box = tk.Frame(tip, bd=0, highlightthickness=1)
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
    t = theme()
    tip_box.config(bg=t["bg"], highlightbackground=t["line"])
    for ch in tip_box.winfo_children():
        ch.destroy()
    tk.Label(tip_box, text=d.strftime("%A, %d %B"), bg=t["bg"], fg=t["fg"],
             font=(FONT, 9, "bold")).pack(anchor="w", padx=8, pady=(5, 2))
    for e in evs:
        row = tk.Frame(tip_box, bg=t["bg"])
        row.pack(anchor="w", padx=8, pady=1)
        tk.Label(row, text="", width=1, bg=COLORS.get(e.get("color"), t["dim"])).pack(side="left")
        tk.Label(row, text=e.get("text") or "(no name)", bg=t["bg"], fg=t["fg"],
                 font=(FONT, 9), justify="left", wraplength=240).pack(side="left", padx=(6, 0))
    tk.Frame(tip_box, bg=t["bg"], height=5).pack()
    tip.update_idletasks()
    tw = tip.winfo_reqwidth()
    x = min(w.winfo_rootx(), root.winfo_screenwidth() - tw - 5)
    y = w.winfo_rooty() + w.winfo_height() + 2
    tip.geometry("+%d+%d" % (x, y))
    tip.deiconify()
    tip.lift()


hov = {"w": None}


def pointer_inside(w):
    px, py = root.winfo_pointerxy()
    x, y = w.winfo_rootx(), w.winfo_rooty()
    return x <= px < x + w.winfo_width() and y <= py < y + w.winfo_height()


def on_enter(event):
    w = event.widget
    if hov["w"] is w:
        return  # still the same day (moving between its text and its glass)
    hov["w"] = w
    if w._plain:
        w.config(bg=theme()["hover"])
    hide_tip()
    tip_job["id"] = root.after(250, lambda w=w: show_tip(w))


def on_leave(event):
    w = event.widget
    if pointer_inside(w):
        return
    if hov["w"] is w:
        hov["w"] = None
    if w._plain:
        w.config(bg=theme()["bg"])
    hide_tip()


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


# ---- navigation ----
def shift(delta):
    mode = view["mode"]
    if mode == "days":
        m = view["m"] + delta
        y = view["y"]
        if m < 1:
            m, y = 12, y - 1
        elif m > 12:
            m, y = 1, y + 1
        view["m"], view["y"] = m, y
    elif mode == "months":
        view["y"] += delta
    else:
        view["ystart"] += 12 * delta
    hide_tip()
    render()


def title_clicked():
    hide_tip()
    if view["mode"] == "days":
        view["mode"] = "months"
    elif view["mode"] == "months":
        view["ystart"] = view["y"] - view["y"] % 12
        view["mode"] = "years"
    else:
        view["mode"] = "days"
    render()


def on_pick(event):
    v = event.widget._value
    if v is None:
        return
    if view["mode"] == "months":
        view["m"] = v
        view["mode"] = "days"
    else:
        view["y"] = v
        view["mode"] = "months"
    render()


def pick_hover(event, on):
    w = event.widget
    if w._base:
        w.config(bg=theme()["hover"] if on else w._base)


def go_today():
    view.update(y=today.year, m=today.month, mode="days")
    render()


def quit_app():
    try:
        save_notes_now()
    except Exception:
        pass
    root.destroy()


def exit_and_disable():
    set_autostart(False)
    quit_app()


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
press = {"x": 0, "y": 0, "down": False}


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


def drag_begin(x_root, y_root):
    hide_tip()
    drag["on"] = True
    drag["dx"] = x_root - root.winfo_x()
    drag["dy"] = y_root - root.winfo_y()


def drag_start(event):
    drag_begin(event.x_root, event.y_root)


def drag_move(event):
    if drag["on"]:
        root.geometry("+%d+%d" % (event.x_root - drag["dx"], event.y_root - drag["dy"]))
        sync_catcher()


def drag_end(event):
    if drag["on"]:
        drag["on"] = False
        settings["x"], settings["y"] = root.winfo_x(), root.winfo_y()
        save()
        place_top_right()


# the title is both a button (click) and a drag handle (press and move)
def title_press(event):
    press.update(x=event.x_root, y=event.y_root, down=True)


def title_motion(event):
    if not press["down"]:
        return
    if not drag["on"] and (abs(event.x_root - press["x"]) > 4 or abs(event.y_root - press["y"]) > 4):
        drag_begin(press["x"], press["y"])
    drag_move(event)


def title_release(event):
    was_down = press["down"]
    press["down"] = False
    if drag["on"]:
        drag_end(event)
    elif was_down:
        title_clicked()


def reset_position():
    settings.pop("x", None)
    settings.pop("y", None)
    save()
    place_top_right()


# ---- right-click menu ----
theme_var = tk.StringVar(value=settings["theme"])
week_var = tk.IntVar(value=int(settings.get("week_start", 0)))
alpha_var = tk.DoubleVar(value=float(settings["alpha"]))
size_var = tk.IntVar(value=int(settings["size"]))
blur_var = tk.BooleanVar(value=bool(settings.get("blur", True)))
notes_var = tk.BooleanVar(value=bool(settings.get("notes", True)))


def set_setting(name, value):
    settings[name] = value
    save()
    apply_look()


menu = tk.Menu(root, tearoff=0)
menu.add_command(label="Go to this month", command=go_today)
menu.add_checkbutton(label="Show notes", variable=notes_var, command=toggle_notes)
menu.add_separator()
menu.add_checkbutton(label="Blur background", variable=blur_var,
                     command=lambda: set_setting("blur", blur_var.get()))
m_alpha = tk.Menu(menu, tearoff=0)
for label, v in [("100% (solid)", 1.0), ("92%", 0.92), ("85%", 0.85), ("75%", 0.75),
                 ("65%", 0.65), ("50%", 0.5)]:
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
m_week = tk.Menu(menu, tearoff=0)
for label, v in [("Monday", 0), ("Sunday", 6)]:
    m_week.add_radiobutton(label=label, variable=week_var, value=v,
                           command=lambda v=v: set_setting("week_start", v))
menu.add_cascade(label="Week starts on", menu=m_week)
menu.add_command(label="Move back to top-right", command=reset_position)
menu.add_separator()
menu.add_command(label="Exit (starts again next login)", command=quit_app)
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
    cv.bind("<Leave>", on_leave)
for lb in pick_cells:
    lb.bind("<Button-1>", on_pick)
    lb.bind("<Enter>", lambda e: pick_hover(e, True))
    lb.bind("<Leave>", lambda e: pick_hover(e, False))
btn_prev.bind("<Button-1>", lambda e: shift(-1))
btn_next.bind("<Button-1>", lambda e: shift(1))
for b in (btn_prev, btn_next):
    b.bind("<Enter>", lambda e: e.widget.config(fg=theme()["fg"]))
    b.bind("<Leave>", lambda e: e.widget.config(fg=theme()["dim"]))
title.bind("<Button-1>", title_press)
title.bind("<B1-Motion>", title_motion)
title.bind("<ButtonRelease-1>", title_release)
for w in (header, notes_head):
    w.config(cursor="fleur")
    w.bind("<Button-1>", drag_start)
    w.bind("<B1-Motion>", drag_move)
    w.bind("<ButtonRelease-1>", drag_end)
for w in [header, title, grid, btn_prev, btn_next, picker, notes_head] + day_names + cells + pick_cells:
    w.bind("<Button-3>", show_menu)
    w.bind("<Button-2>", show_menu)  # macOS right-click
root.bind("<Escape>", lambda e: go_today() if view["mode"] != "days" else None)


# ---- Windows: sit on the desktop, behind every program ----
if IS_WIN:
    user32 = ctypes.windll.user32
    dwmapi = ctypes.windll.dwmapi
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetTopWindow.restype = wintypes.HWND
    user32.GetTopWindow.argtypes = [wintypes.HWND]
    user32.GetWindow.restype = wintypes.HWND
    user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    dwmapi.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    HWND_TOPMOST, HWND_NOTOPMOST, HWND_BOTTOM = -1, -2, 1
    FLAGS = 0x0001 | 0x0002 | 0x0010  # NOSIZE | NOMOVE | NOACTIVATE
    GW_HWNDNEXT = 2
    GWL_EXSTYLE = -20
    WS_EX_TOPMOST = 0x8
    WS_EX_TOOLWINDOW = 0x80
    DESKTOP_CLASSES = ("WorkerW", "Progman")
    MY_PID = os.getpid()
    _cls = ctypes.create_unicode_buffer(64)
    _pid = wintypes.DWORD()
    z = {"mode": None}

    def class_of(h):
        user32.GetClassNameW(h, _cls, 64)
        return _cls.value

    def pid_of(h):
        user32.GetWindowThreadProcessId(h, ctypes.byref(_pid))
        return _pid.value

    def cloaked(h):
        # windows on another virtual desktop (or hidden store apps) are "cloaked"
        val = ctypes.c_int(0)
        try:
            dwmapi.DwmGetWindowAttribute(h, 14, ctypes.byref(val), ctypes.sizeof(val))
        except Exception:
            return False
        return val.value != 0

    def covered_by_program(my_hwnd):
        """True if a real program window on this virtual desktop overlaps the calendar."""
        me = wintypes.RECT()
        user32.GetWindowRect(my_hwnd, ctypes.byref(me))
        r = wintypes.RECT()
        h = user32.GetTopWindow(None)
        guard = 0
        while h and guard < 3000:
            guard += 1
            if class_of(h) in DESKTOP_CLASSES:
                break  # everything below this is behind the desktop
            if (h != my_hwnd and user32.IsWindowVisible(h) and not user32.IsIconic(h)
                    and pid_of(h) != MY_PID):
                ex = user32.GetWindowLongW(h, GWL_EXSTYLE)
                if not (ex & (WS_EX_TOPMOST | WS_EX_TOOLWINDOW)) and not cloaked(h):
                    user32.GetWindowRect(h, ctypes.byref(r))
                    if (r.right - r.left > 0 and r.bottom - r.top > 0 and
                            r.left < me.right and r.right > me.left and
                            r.top < me.bottom and r.bottom > me.top):
                        return True
            h = user32.GetWindow(h, GW_HWNDNEXT)
        return False

    def go_front(hwnd):
        if z["mode"] != "front":
            user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, FLAGS)
            if editor["win"] is not None:
                editor["win"].attributes("-topmost", True)
            z["mode"] = "front"

    def go_back(hwnd, fg):
        if z["mode"] != "back":
            user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, FLAGS)
            hide_tip()
            if editor["win"] is not None:
                editor["win"].attributes("-topmost", False)
            z["mode"] = "back"
            z["fg"] = None
        if fg != z.get("fg"):  # sink again only when the user switches window
            user32.SetWindowPos(hwnd, HWND_BOTTOM, 0, 0, 0, 0, FLAGS)
            z["fg"] = fg

    def keep_on_desktop():
        hwnd = frame_hwnd()
        fg = user32.GetForegroundWindow()
        if fg and pid_of(fg) == MY_PID:
            return  # user is using the calendar / notes / editor / menu
        # Show on top only when the desktop itself is what the user sees.
        # Clicking the desktop (or switching virtual desktops) while program
        # windows are still open must NOT pull the calendar over them.
        if fg and class_of(fg) in DESKTOP_CLASSES and not covered_by_program(hwnd):
            go_front(hwnd)
        else:
            go_back(hwnd, fg)
else:
    def keep_on_desktop():
        pass


def fast_loop():
    try:
        keep_on_desktop()
        if root.state() != "normal":
            root.deiconify()
        sync_catcher()
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
