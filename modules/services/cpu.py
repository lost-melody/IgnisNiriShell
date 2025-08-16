from ignis.base_service import BaseService
from ignis.gobject import IgnisProperty
from ignis.utils import Poll

class CpuLoadService(BaseService):
    def __init__(self):
        super().__init__()
        self._cpu_count = self.__read_cpu_count()
        self._idle_time: int = 0
        self._total_time: int = 0
        self.__cpu_times = self.__read_cpu_times()
        self.__poll = Poll(timeout=1000, callback=self.__update_times)

    @classmethod
    def __read_cpu_count(cls) -> int:
        with open("/proc/cpuinfo") as cpuinfo:
            count = 0
            for line in cpuinfo.readlines():
                if line.startswith("processor"):
                    count += 1
            return count

    @classmethod
    def __read_cpu_times(cls) -> list[int]:
        with open("/proc/stat") as stat:
            line = stat.readline().split()[1:]
            return list(map(int, line[: min(7, len(line))]))

    @IgnisProperty
    def cpu_count(self) -> int:
        return self._cpu_count

    @IgnisProperty
    def idle_time(self) -> int:
        """
        idle cpu time during last polling interval
        """
        return self._idle_time

    @IgnisProperty
    def total_time(self) -> int:
        """
        total cpu time during last polling interval
        """
        return self._total_time

    @IgnisProperty
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
        updates (idle, total) since last called
        """
        times = self.__read_cpu_times()
        deltas = [times[i] - self.__cpu_times[i] for i in range(len(times))]
        self._total_time = sum(deltas)
        self.notify("total_time")
        self._idle_time = deltas[3]
        self.notify("idle_time")
        self.__cpu_times = times
