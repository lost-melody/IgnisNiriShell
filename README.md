# IgnisNiriShell

Requirements:

- One of the compositors:
  - [YaLTeR/niri](https://github.com/yalter/niri), a scrollable-tiling _Wayland_ compositor.
  - [hyprwm/Hyprland](https://hyprland.org), an independent, highly customizable, dynamic tiling _Wayland_ compositor.
- [linkfrg/ignis](https://github.com/linkfrg/ignis), a widget framework for building desktop shells.
  - Currently the latest main branch should be installed.
- [Blueprint](https://jwestman.pages.gitlab.gnome.org/blueprint-compiler/), a markup language for _GTK_ user interfaces.
- [libadwaita](https://gnome.pages.gitlab.gnome.org/libadwaita/), Building blocks for modern _GNOME_ applications.

## About the project

- _Adw_ is initialized in `config.py` and is required for ui styles, light/dark color schemes, and is used in some widgets.
- _Blueprint_ is used in most views and widgets, so can be tweaked as wish. They are built during class declarations.
  - An example is to use use grid layout in _AppLauncher_ by replacing `ListView` by `GridView` in its `.blp` file.
  - Don't forget to run `ignis reload` after editing blueprints.
- _AppLauncher_ is initialized in `config.py` and can be disabled by commenting it out.
  - Don't forget to also edit the launcher command in topbar buttons.
- _Notification_ service is required in `NotificationPopups` and `ControlCenter`.
  - `NotificationPopups` can be disabled by commenting it out in `config.py`.
  - `NotificationCenter` can be removed from `ControlCenter`'s blueprint file.
- _Wallpaper_ service is also initialized there, and can be commented out if other wallpaper services are used.

## Tweak

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

## Development

I personally use `neovim` for coding.
With `pyright`, `python-black`, `blueprint-compiler` installed, and with typing stubs, _LSP_, code formatter configured, it should be easy to work with.

An example `pyproject.toml`:

```toml
[tool.black]
target-version = ["py313"]
line-length = 120
skip-magic-trailing-comma = true

[tool.pyright]
# ignis is installed at venv "/path/to/venv/lib/ignis"
venvPath = "/path/to/venv/lib"
venv = "ignis"
```

It might help to soft link stubs from `gi-stubs` and `ignis/stubs` to project's `typeings/` directory:

```
typeings/
  - gi-stubs/
    - __init__.pyi
    - repository/
      - __init__.pyi
      - Gtk.pyi
      - Adw.pyi
      - Gvc.pyi
      - ...
```
