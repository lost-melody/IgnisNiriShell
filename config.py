import os
import modules.adw as _
import modules.overrides as _
from ignis.app import IgnisApp
from ignis.services.niri import NiriService
from ignis.utils import get_n_monitors
from modules.modules import *
from modules.appdock import AppDock
from modules.applauncher import AppLauncher
from modules.backdrop import OverlayBackdrop
from modules.controlcenter import ControlCenter, NotificationPopups
from modules.osd import OnscreenDisplay
from modules.preferences import Preferences
from modules.topbar import Topbar
from modules.wallpaper import WallpaperWindow


app = IgnisApp.get_default()
niri = NiriService.get_default()

if app._config_path is not None:
    config_dir = os.path.dirname(app._config_path)
    app.apply_css(os.path.join(config_dir, "style.scss"))

AppLauncher()
ControlCenter()
NotificationPopups()
OnscreenDisplay()
Preferences()

for idx in range(get_n_monitors()):
    Topbar(idx)
    AppDock(idx)
    OverlayBackdrop(idx)

    WallpaperWindow(idx)
    if niri.is_available:
        WallpaperWindow(idx, is_backdrop=True)
