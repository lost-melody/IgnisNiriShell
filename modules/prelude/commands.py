import asyncio
from ignis.command_manager import CommandManager
from ignis.exceptions import WindowNotFoundError
from ignis.window_manager import WindowManager
from ignis.services.recorder import RecorderConfig, RecorderService
from ignis.options import options
from ..constants import WindowName
from ..useroptions import user_options


cm = CommandManager.get_default()
wm = WindowManager.get_default()
recorder = RecorderService.get_default()


def toggle_window(window_name: WindowName):
    try:
        wm.toggle_window(window_name.value)
    except WindowNotFoundError:
        pass


def open_window(window_name: WindowName):
    try:
        wm.open_window(window_name.value)
    except WindowNotFoundError:
        pass


@cm.command(name="toggle-applauncher")
def toggle_applauncher(*_):
    toggle_window(WindowName.app_launcher)


@cm.command(name="toggle-controlcenter")
def toggle_controlcenter(*_):
    toggle_window(WindowName.control_center)


@cm.command(name="toggle-dock")
def toggle_dock(*_):
    opts = user_options.appdock
    opts.auto_conceal = not opts.auto_conceal


@cm.command(name="toggle-do-not-disturb")
def toggle_do_not_disturb(*_):
    opts = options.notifications
    opts.dnd = not opts.dnd


@cm.command(name="open-settings")
def open_settings(*_):
    open_window(WindowName.preferences)


@cm.command(name="start-recording")
def start_recording(*_):
    asyncio.create_task(recorder.start_recording(RecorderConfig.new_from_options()))


@cm.command(name="stop-recording")
def stop_recording(*_):
    recorder.stop_recording()


@cm.command(name="pause-recording")
def pause_recording(*_):
    recorder.pause_recording()


@cm.command(name="continue-recording")
def continue_recording(*_):
    recorder.continue_recording()


@cm.command(name="toggle-recording")
def toggle_recording(*_):
    if recorder.active:
        if recorder.is_paused:
            recorder.continue_recording()
        else:
            stop_recording()
    else:
        start_recording()
