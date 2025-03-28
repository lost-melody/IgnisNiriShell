from ignis import CACHE_DIR
from ignis.options_manager import OptionsGroup, OptionsManager


class UserOptions(OptionsManager):
    def __init__(self):
        try:
            super().__init__(file=f"{CACHE_DIR}/ignis_user_options.json")
        except FileNotFoundError:
            pass

    class AppLauncher(OptionsGroup):
        command_format: str = "niri msg action spawn -- %command%"
        terminal_format: str = "niri msg action spawn -- foot %command%"

    class ActiveWindow(OptionsGroup):
        on_click: str = "niri msg action center-column"
        on_right_click: str = "niri msg action switch-preset-window-width"
        on_middle_click: str = "niri msg action toggle-column-tabbed-display"
        on_scroll_up: str = "niri msg action focus-window-up-or-column-left"
        on_scroll_down: str = "niri msg action focus-window-down-or-column-right"
        on_scroll_left: str = "niri msg action focus-window-up-or-column-left"
        on_scroll_right: str = "niri msg action focus-window-down-or-column-right"

    applauncher = AppLauncher()
    activewindow = ActiveWindow()


user_options = UserOptions()
