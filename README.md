# IgnisNiriShell

Requirements:

- One of the compositors:
  - [YaLTeR/niri](https://github.com/yalter/niri), a scrollable-tiling _Wayland_ compositor.
  - [hyprwm/Hyprland](https://hyprland.org), an independent, highly customizable, dynamic tiling _Wayland_ compositor.
- [ignis-sh/ignis](https://github.com/ignis-sh/ignis), a widget framework for building desktop shells.
  - Currently the latest main branch should be installed.
- [Blueprint](https://jwestman.pages.gitlab.gnome.org/blueprint-compiler/), a markup language for _GTK_ user interfaces.
- [libadwaita](https://gnome.pages.gitlab.gnome.org/libadwaita/), building blocks for modern _GNOME_ applications.
- [Tela icon theme](https://github.com/vinceliuice/Tela-icon-theme), a flat colorful design icon theme.
  - Without _tela_ installed, some icons might be missing.

## Screenshots

<details>
<summary>Screenshots (light theme)</summary>

![ignis-shell-appdock.png](https://i.postimg.cc/FH2n6QH4/ignis-shell-appdock.png)
![ignis-shell-applauncher.png](https://i.postimg.cc/15CHLKXr/ignis-shell-applauncher.png)
![ignis-shell-controlcenter.png](https://i.postimg.cc/TYL0vDb8/ignis-shell-controlcenter.png)
![ignis-shell-preferences.png](https://i.postimg.cc/mDpW55zW/ignis-shell-preferences.png)
![ignis-shell-overview.png](https://i.postimg.cc/GpKYr2xM/ignis-shell-overview.png)

</details>

## About the project

- _Adw_ is initialized in `config.py` and is required for ui styles, light/dark color schemes, and is used in some widgets.
- _Blueprint_ is used in most views and widgets, so can be tweaked as wish. They are built during class declarations.
  - An example is to use grid layout in _AppLauncher_ by replacing `ListView` by `GridView` in its `.blp` file. Some declarations in the `.py` file should also be replaced accordingly.
  - Don't forget to run `ignis reload` after editing blueprints.
- _AppLauncher_ is initialized in `config.py` and can be disabled by commenting it out.
  - Don't forget to also edit the launcher command in topbar buttons.
- _Notification_ service is required in `NotificationPopups` and `ControlCenter`.
  - `NotificationPopups` can be disabled by commenting it out in `config.py`.
  - `NotificationCenter` can be removed from `ControlCenter`'s blueprint file.
- `WallpaperWindow`s are initialized in `config.py`, and can be commented out if other wallpaper services are used.
  - For _niri_, an extra `WallpaperWindow` is initialized as the overview backdrop, which should also be configured in _niri_ (example below).
- _OSD_ displays changes of volumes, backlight, and optionally caps lock state.
  - _libevdev_ is required for caps lock state detection, installed via system package manager and pip.
    - Install _libevdev_: `pacman -S libevdev`.
    - Install _Python_ bindings: `pacman -S python-libevdev` or `pip install libevdev`.
  - User should also be a member of group `input` for _libevdev_ to work.

## Integrations

- As is stated, this project works under _niri_ and _Hyprland_, and synchronizes windows and workspaces in addition to their focus states. These functions are designed as three widgets: a workspaces pill, a focused window indicator, and a dock.
- Recommended keybindings (which should be configured in _niri_ or _Hyprland_):
  - Toggle _App Launcher_: `ignis toggle-window ignis-applauncher`.
    - It is recommended to also have a fallback launcher, since we are unstable now.
  - Toggle _Control Center_: `ignis toggle-window ignis-controlcenter`.
  - Run custom commands with `ignis run-command`:
    - Start/stop _Screen Recorder_: `ignis run-command toggle-recording`.
    - Toggle _Dock Auto Hide_: `ignis run-command toggle-dock`.
    - List all available commands: `ignis list-commands`.
  - Note: if the `ignis` _CLI_ is slow for you, try [`goignis`](https://github.com/ignis-sh/goignis).
- Layer window rules:
  - Under _niri_, `layer-rule` can match `namespace` with `ignis-applauncher`, `ignis-controlcenter`, `ignis-topbar` and `ignis-appdock`.
  - Under _Hyprland_, `layerrule` is used instead.
  - _Hyprland_ should disable window enter animations for _App Launcher_ and _Control Center_, as they already have a _Revealer_ transition inside.
  - Window shadow often cares the border radius, which is defined as `var(--window-border-radius)`, which is provided by _libadwaita_.

## Usage and Tweaks

- Shortcuts in _App Launcher_:
  - Toggle search bar: `Control-f`.
  - Close launcher window: `Esc`, or `Control-[`.
  - Select next: `Down`, `Control-j`, or `Control-n`.
  - Select previous: `Up`, `Control-k`, or `Control-p`.
  - Page Up/Down: `PageUp`, `PageDown`.
- Styles:
  - CSS variables and classes from _libadwaita_ can be used in `.blp` files.
  - Some css classes are also generated in _TailWindCSS_ style to be used in `.blp` designs, e.g. `px-2`, `m-1`.
  - If that's not enough, more style definitions can be added into `styles.scss`.
- Designs:
  - It should be easy to read and edit `.blp` files, but don't break widget names and callbacks that are needed in widgets' codes.
- Widgets:
  - Some widgets are designed to be used and customized in anywhere of `.blp` files.
  - `CommandPill`: a `Gtk.Button` that accepts an additional `click-command` property to be run upon clicked.
  - `ControlSwitchCmd`: a `ControlSwitch` that are used to toggle service up and down in `ControlCenter`, e.g. `wlsunset`.
- Configure `BackdropWallpaper` in _niri_:

  ```kdl
  layer-rule {
      match namespace="^ignis_wallpaper_backdrop_.*$"
      place-within-backdrop true
      opacity 0.5
  }
  layer-rule {
      match namespace="^ignis_wallpaper_service_.*$"
      baba-is-float true
  }
  ```

## Development

I personally use `neovim` for coding.
With `pyright`, `ruff`, `blueprint-compiler` installed, and with typing stubs, _LSP_, code formatter configured, it should be easy to work with.

An example `pyproject.toml`:

```toml
[tool.pyright]
# ignis is installed at venv "/path/to/venv/lib/ignis"
venvPath = "/path/to/venv/lib"
venv = "ignis"

[tool.ruff]
line-length = 120
target-version = "py313"

[tool.ruff.format]
skip-magic-trailing-comma = true
docstring-code-format = true
```
