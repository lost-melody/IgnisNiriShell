from enum import Enum
from os import path

current_dir = path.dirname(path.realpath(__file__))
CONFIG_DIR = path.dirname(current_dir)
del current_dir


class WindowName(Enum):
    top_bar = "ignis-topbar"
    app_launcher = "ignis-applauncher"
    app_dock = "ignis-appdock"
    control_center = "ignis-controlcenter"
    kim_popup = "ignis-kimpopup"
    notification_popups = "ignis-notificationpopups"
    preferences = "ignis-preferences"
    backdrop = "ignis-backdrop"
    osd = "ignis-osd"


class AudioStreamType(Enum):
    speaker = "speaker"
    microphone = "micrphone"
