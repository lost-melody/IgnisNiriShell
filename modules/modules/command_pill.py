from gi.repository import Gtk

from ..utils import GProperty, run_cmd_async


class CommandPill(Gtk.Button):
    __gtype_name__ = "CommandPill"

    def __init__(self):
        self._click_cmd: str = ""
        super().__init__()

        self.connect("clicked", self.__class__.__on_clicked)

    def __on_clicked(self, *_):
        if self._click_cmd != "":
            run_cmd_async(self._click_cmd)

    @GProperty(type=str)
    def click_command(self) -> str:
        return self._click_cmd

    @click_command.setter
    def click_command(self, cmd: str):
        self._click_cmd = cmd
