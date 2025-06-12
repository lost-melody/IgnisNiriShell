import os
from ignis.app import IgnisApp
from ignis.dbus import DBusService
from ignis.base_service import BaseService
from ignis.services.recorder import RecorderService
from ignis.services.niri import NiriService
from ignis.utils import load_interface_xml
from .constants import WindowName
from .useroptions import user_options


app = IgnisApp.get_default()
niri = NiriService.get_default()
recorder = RecorderService.get_default()


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
        dbus.register_dbus_method("PauseRecording", self.__dbus_pause_recording)
        dbus.register_dbus_method("StopRecording", self.__dbus_stop_recording)
        dbus.register_dbus_method("OpenSettings", self.__dbus_open_settings)

    def __dbus_toggle_applauncher(self, _):
        app.toggle_window(WindowName.app_launcher.value)

    def __dbus_toggle_controlcenter(self, _):
        app.toggle_window(WindowName.control_center.value)

    def __dbus_toggle_dock(self, _):
        opts = user_options and user_options.appdock
        if opts:
            opts.auto_conceal = not opts.auto_conceal

    def __dbus_toggle_recording(self, _):
        if niri.is_available:
            return
        if recorder.active:
            if recorder.is_paused:
                recorder.continue_recording()
            else:
                recorder.stop_recording()
        else:
            recorder.start_recording()

    def __dbus_start_recording(self, _):
        if niri.is_available:
            return
        if not recorder.active:
            recorder.start_recording()
        elif recorder.is_paused:
            recorder.continue_recording()

    def __dbus_pause_recording(self, _):
        if niri.is_available:
            return
        if recorder.active and not recorder.is_paused:
            recorder.pause_recording()

    def __dbus_stop_recording(self, _):
        if niri.is_available:
            return
        if recorder.active:
            recorder.stop_recording()

    def __dbus_open_settings(self, _):
        app.open_window(WindowName.preferences.value)
