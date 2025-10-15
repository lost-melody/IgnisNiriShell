import base64
import os
from asyncio import Task, create_subprocess_shell, create_task
from typing import Any, Callable

from ignis.utils import AsyncCompletedProcess, exec_sh_async

from ..constants import CONFIG_DIR


def b64enc(input: str) -> str:
    return base64.b64encode(input.encode()).decode().rstrip("=")


def clear_dir(dirpath: str):
    if not os.path.isdir(dirpath):
        return

    for filename in os.listdir(dirpath):
        filepath = os.path.join(dirpath, filename)
        if os.path.isfile(filepath):
            os.remove(filepath)


def dbus_info_file(filename: str) -> str:
    return os.path.join(CONFIG_DIR, "modules/dbus", filename)


def format_time_duration(seconds: int, minutes: int = 0, hours: int = 0) -> str:
    minutes += seconds // 60
    seconds %= 60
    hours += minutes // 60
    minutes %= 60
    if hours != 0:
        return "%d:%02d:%02d" % (hours, minutes, seconds)
    else:
        return "%d:%02d" % (minutes, seconds)


def is_instance_method(callback: Callable) -> bool:
    """
    Checks whether callback is an instance method.
    """
    return hasattr(callback, "__self__")


def unpack_instance_method(callback: Callable):
    """
    Unpacks object and function from an instance method.
    """
    obj: Any = getattr(callback, "__self__")
    func: Callable = getattr(callback, "__func__")
    return obj, func


async def exec_sh_async_nopipe(cmd: str):
    """
    Similar to ``ignis.utils.exec_sh_async``, but without piping stdout/stderr.
    """
    process = await create_subprocess_shell(cmd)
    returncode = await process.wait()
    return AsyncCompletedProcess("", "", returncode)


def run_cmd_async(cmd: str, pipe: bool = False, on_done: Callable[[Task[AsyncCompletedProcess]], object] | None = None):
    if pipe:
        coro = exec_sh_async(cmd)
    else:
        coro = exec_sh_async_nopipe(cmd)
    task = create_task(coro)

    if on_done:
        task.add_done_callback(on_done)

    return task
