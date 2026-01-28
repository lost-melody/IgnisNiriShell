from ignis.base_service import BaseService
from ignis.utils import Poll

from ..utils import GProperty


class CpuLoadService(BaseService):
    def __init__(self):
        super().__init__()

        self._user_time: int = 0
        self._system_time: int = 0
        self._idle_time: int = 0
        self._iowait_time: int = 0
        self._total_time: int = 0

        self.__cpu_times = self.__read_cpu_times()
        self.__poll = Poll(timeout=1000, callback=self.__update_times)

    @classmethod
    def __read_cpu_times(cls) -> tuple[int, int, int, int, int]:
        """
        Returns the ``(user, system, idle, iowait, total)`` cpu times since system up
        """
        with open("/proc/stat") as stat:
            line = stat.readline().split()[1:]
            times = list(map(int, line[: min(7, len(line))]))
            return times[0] + times[1], times[2], times[3], times[4], sum(times)

    @GProperty
    def user_time(self) -> int:
        """
        user (and nice user) cpu time during last polling interval
        """
        return self._user_time

    @GProperty
    def system_time(self) -> int:
        """
        system cpu time during last polling interval
        """
        return self._system_time

    @GProperty
    def idle_time(self) -> int:
        """
        idle cpu time during last polling interval
        """
        return self._idle_time

    @GProperty
    def iowait_time(self) -> int:
        """
        iowait cpu time during last polling interval
        """
        return self._iowait_time

    @GProperty
    def total_time(self) -> int:
        """
        total cpu time during last polling interval
        """
        return self._total_time

    @GProperty
    def interval(self) -> int:
        """
        sample interval in milliseconds
        """
        return self.__poll.timeout

    @interval.setter
    def interval(self, ms: int):
        self.__poll.timeout = ms

    def __update_times(self, *_):
        """
        updates (user, system, idle, total) since last called
        """
        times = self.__read_cpu_times()
        deltas = [times[i] - self.__cpu_times[i] for i in range(len(times))]
        self.__cpu_times = times

        self._user_time = deltas[0]
        self._system_time = deltas[1]
        self._idle_time = deltas[2]
        self._iowait_time = deltas[3]
        self._total_time = deltas[4]

        self.notify("user-time")
        self.notify("system-time")
        self.notify("idle-time")
        self.notify("iowait-time")
        self.notify("total-time")
