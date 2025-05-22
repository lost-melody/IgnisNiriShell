from ignis import DATA_DIR
from ignis.options_manager import OptionsGroup, OptionsManager


class UserOptions(OptionsManager):
    def __init__(self):
        try:
            super().__init__(file=f"{DATA_DIR}/user_options.json")
        except FileNotFoundError:
            pass

    class AppLauncher(OptionsGroup):
        command_format: str = "%command%"
        terminal_format: str = "foot %command%"

    class ActiveWindow(OptionsGroup):
        on_click: str = "niri msg action center-column"
        on_right_click: str = "niri msg action switch-preset-window-width"
        on_middle_click: str = "niri msg action toggle-column-tabbed-display"
        on_scroll_up: str = "niri msg action focus-window-up-or-column-left"
        on_scroll_down: str = "niri msg action focus-window-down-or-column-right"
        on_scroll_left: str = "niri msg action focus-window-up-or-column-left"
        on_scroll_right: str = "niri msg action focus-window-down-or-column-right"

    class AppDock(OptionsGroup):
        exclusive: bool = False
        focusable: bool = False
        auto_conceal: bool = True
        conceal_delay: int = 1000
        monitor_only: bool = True
        workspace_only: bool = True

    class Osd(OptionsGroup):
        timeout: int = 3000

    class Topbar(OptionsGroup):
        exclusive: bool = True
        focusable: bool = False

    class Wallpaper(OptionsGroup):
        blur_radius: float = 0
        bottom_margin: int = 0
        backdrop_blur_radius: float = 5
        backdrop_bottom_margin: int = 0

    applauncher = AppLauncher()
    activewindow = ActiveWindow()
    appdock = AppDock()
    topbar = Topbar()
    osd = Osd()
    wallpaper = Wallpaper()


user_options = UserOptions()
