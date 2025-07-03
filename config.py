import os
import modules.adw as _
import modules.modules as _
import modules.overrides as _
from ignis.app import IgnisApp
from ignis.css_manager import CssInfoPath, CssManager
from ignis.services.niri import NiriService
from ignis.utils import get_n_monitors, sass_compile
from modules.dbus import DBusServeur
from modules.appdock import AppDock
from modules.applauncher import AppLauncher
from modules.backdrop import OverlayBackdrop
from modules.controlcenter import ControlCenter, NotificationPopups
from modules.fcitxkimpopup import FcitxKimPopup
from modules.osd import OnscreenDisplay
from modules.preferences import Preferences
from modules.topbar import Topbar
from modules.wallpaper import WallpaperWindow


app = IgnisApp.get_default()
css_manager = CssManager.get_default()
niri = NiriService.get_default()
DBusServeur.get_default()

config_dir = os.path.dirname(os.path.abspath(__file__))
css_manager.apply_css(
    CssInfoPath(
        name="main", path=os.path.join(config_dir, "style.scss"), compiler_function=lambda path: sass_compile(path=path)
    )
)

AppLauncher()
ControlCenter()
FcitxKimPopup()
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
