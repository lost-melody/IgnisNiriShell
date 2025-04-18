from enum import Enum


class WindowName(Enum):
    top_bar = "ignis-topbar"
    app_launcher = "ignis-applauncher"
    app_dock = "ignis-appdock"
    control_center = "ignis-controlcenter"
    notification_popups = "ignis-notificationpopups"
    preferences = "ignis-preferences"
    backdrop = "ignis-backdrop"
    osd = "ignis-osd"


class AudioStreamType(Enum):
    speaker = "speaker"
    microphone = "microphone"
