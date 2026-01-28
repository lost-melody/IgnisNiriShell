import os
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
        cpu_count = os.cpu_count() or 1
        user, system, idle, iowait, total = (
            self.__cpu.user_time,
            self.__cpu.system_time,
            self.__cpu.idle_time,
            self.__cpu.iowait_time,
            self.__cpu.total_time,
        )

        if not total:
            return

        usage = (total - idle - iowait) / total
        self.set_tooltip_text(
            "\n".join(
                [
                    f"CPU Usage: {round(usage * cpu_count, 2)} / {cpu_count}",
                    f"User: {round(user / total * cpu_count, 2)}",
                    f"System: {round(system / total * cpu_count, 2)}",
                    f"IO Wait: {round(iowait / total * cpu_count, 2)}",
                ]
            )
        )

        label = f"{round(usage * 100)}%"
        if self.labeler:
            self.labeler.set_label(label)
        else:
            self.set_label(label)
