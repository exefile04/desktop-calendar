# Desktop Calendar

A tiny, offline calendar that lives on your Windows desktop.

It sits behind your open programs, so it never covers your work. When you go to the desktop, it shows on top. It starts automatically when you log in.

![Desktop Calendar screenshot](screenshot.png)

## Features

- **Fully offline:** no internet and no account. Everything is saved locally.
- **Stays on the desktop:** it hides behind your programs, can't be minimised, has no taskbar button, and Alt+F4 doesn't close it.
- **Starts with Windows** automatically.
- **Several events per day,** each with its own colour. A day with several colours shows them as stripes.
- **Hover a day** to see all its events.
- **Shows the previous and next month's days** in grey, and you can click them too.
- **Drag to move it.** It remembers where you put it.
- **Adjustable:** transparency (100% to 35%), size (Tiny to Large) and theme (Dark or Light).
- **Lightweight:** one Python file using only the standard library.

## Requirements

- Windows 10 or 11
- [Python 3](https://www.python.org/downloads/). During install, tick **"Add Python to PATH"**.

## Install

1. Download this repository: **Code → Download ZIP**, then unzip it.
2. Put the folder somewhere permanent, for example `Documents\DesktopCalendar`.
3. Double-click **`install_windows.bat`**.

The calendar appears in the top-right corner and will start every time you log in.

> If you move the folder later, double-click `calendar_desktop.pyw` once from its new place to update auto-start.

## How to use

| Action | How |
|---|---|
| Add or edit events | Click a date. Type a name, pick a colour, and use **+ Add event** for more. Press **Enter** to save. |
| See events | Hover over a date. Dates with named events have an underlined number. |
| Change month | Click `<` or `>` |
| Move the calendar | Drag the month title bar |
| Settings | Right-click anywhere on the calendar to change Transparency, Size, Theme, or use Move back to top-right |
| Close | Right-click → **Exit**. It starts again at next login. |
| Stop auto-start | Right-click → **Exit and turn off auto-start** |

## Where your data is stored

Data is kept in your user folder (`C:\Users\<you>\`):

- `desktop_calendar_data.json` holds your events and settings.
- `desktop_calendar_error.log` holds error messages, only if something goes wrong. It's capped at 200 KB.

To back up your events, copy `desktop_calendar_data.json`.

## Uninstall

Double-click **`uninstall_windows.bat`**. It closes the calendar, removes auto-start and deletes the program files. It asks before deleting your saved events.

## macOS

`install_mac.command` makes it start at login. On macOS it's a normal small window, without the stay-behind-programs behaviour that Windows has.

## License

[MIT](LICENSE)
