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

    applauncher = AppLauncher()


user_options = UserOptions()
