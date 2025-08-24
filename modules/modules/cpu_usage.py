from gi.repository import Gtk

from ..services import CpuLoadService
from ..utils import GProperty
from .command_pill import CommandPill


class CpuUsagePill(CommandPill):
    __gtype_name__ = "CpuUsagePill"

    def __init__(self):
        self._label: Gtk.Label | None = None
        super().__init__()

        self.__cpu = CpuLoadService.get_default()
        self.__processors = self.__cpu.cpu_count
        self.__cpu.connect("notify::total-time", self.__on_updated)

    @GProperty(type=int)
    def interval(self) -> int:
        return self.__cpu.interval

    @interval.setter
    def interval(self, interval: int):
        self.__cpu.interval = interval

    @GProperty(type=Gtk.Label)
    def labeler(self) -> Gtk.Label | None:
        return self._label

    @labeler.setter
    def labeler(self, label: Gtk.Label):
        self._label = label

    def __on_updated(self, *_):
        idle, total = self.__cpu.idle_time, self.__cpu.total_time
        # this means how many percent of computing resources of a single processor are used
        # e.g. 234% means 2.34 processors are used; 1600% (with 16 processors) means all processors are used
        percent = (total - idle) * 100 * self.__processors // total if total else 0
        label = f"{round(percent)}"
        self.set_tooltip_text(f"CPU Usage: {round(percent)}% / {self.__processors * 100}%")
        if self.labeler:
            self.labeler.set_label(label)
        else:
            self.set_label(label)
