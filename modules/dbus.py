import asyncio
import os
from ignis.dbus import DBusService
from ignis.window_manager import WindowManager
from ignis.base_service import BaseService
from ignis.services.recorder import RecorderConfig, RecorderService
from ignis.utils import load_interface_xml
from .constants import WindowName
from .services import FcitxStateService
from .useroptions import user_options


wm = WindowManager.get_default()
recorder = RecorderService.get_default()
fcitx = FcitxStateService.get_default()


class DBusServeur(BaseService):
    current_dir = os.path.dirname(os.path.abspath(__file__))

    def __init__(self):
        super().__init__()
        self.__bus = DBusService(
            name="io.github.lost_melody.IgnisNiriShell",
            object_path="/io/github/lost_melody/IgnisNiriShell",
            info=load_interface_xml(
                path=os.path.join(self.current_dir, "dbus", "io.github.lost-melody.IgnisNiriShell.xml")
            ),
        )
        self.__register_methods(self.__bus)

    def __register_methods(self, dbus: DBusService):
        dbus.register_dbus_method("ToggleAppLauncher", self.__dbus_toggle_applauncher)
        dbus.register_dbus_method("ToggleControlCenter", self.__dbus_toggle_controlcenter)
        dbus.register_dbus_method("ToggleDock", self.__dbus_toggle_dock)
        dbus.register_dbus_method("ToggleRecording", self.__dbus_toggle_recording)
        dbus.register_dbus_method("StartRecording", self.__dbus_start_recording)
        dbus.register_dbus_method("StopRecording", self.__dbus_stop_recording)
        dbus.register_dbus_method("TogglePauseRecording", self.__dbus_toggle_pause_recording)
        dbus.register_dbus_method("PauseRecording", self.__dbus_pause_recording)
        dbus.register_dbus_method("ContinueRecording", self.__dbus_continue_recording)
        dbus.register_dbus_method("OpenSettings", self.__dbus_open_settings)
        dbus.register_dbus_method("SyncFcitxState", self.__dbus_sync_fcitx_state)

    def __dbus_toggle_applauncher(self, _):
        wm.toggle_window(WindowName.app_launcher.value)

    def __dbus_toggle_controlcenter(self, _):
        wm.toggle_window(WindowName.control_center.value)

    def __dbus_toggle_dock(self, _):
        opts = user_options and user_options.appdock
        if opts:
            opts.auto_conceal = not opts.auto_conceal

    def __dbus_toggle_recording(self, _):
        if recorder.active:
            if recorder.is_paused:
                recorder.continue_recording()
            else:
                recorder.stop_recording()
        else:
            asyncio.create_task(recorder.start_recording(RecorderConfig.new_from_options()))

    def __dbus_start_recording(self, _):
        if not recorder.active:
            asyncio.create_task(recorder.start_recording(RecorderConfig.new_from_options()))

    def __dbus_stop_recording(self, _):
        if recorder.active:
            recorder.stop_recording()

    def __dbus_toggle_pause_recording(self, _):
        if recorder.active:
            if recorder.is_paused:
                recorder.continue_recording()
            else:
                recorder.pause_recording()

    def __dbus_pause_recording(self, _):
        if recorder.active and not recorder.is_paused:
            recorder.pause_recording()

    def __dbus_continue_recording(self, _):
        if recorder.active and recorder.is_paused:
            recorder.continue_recording()

    def __dbus_open_settings(self, _):
        wm.open_window(WindowName.preferences.value)

    def __dbus_sync_fcitx_state(self, _):
        asyncio.create_task(fcitx.sync_state_async())
