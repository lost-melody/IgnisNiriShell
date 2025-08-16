import os

from ignis.app import IgnisApp
from ignis.css_manager import CssInfoPath, CssManager
from ignis.services.niri import NiriService
from ignis.utils import get_n_monitors, sass_compile

from modules.prelude import post_initialized
from modules.windows import (
    AppDock,
    AppLauncher,
    ControlCenter,
    FcitxKimPopup,
    NotificationPopups,
    OnscreenDisplay,
    OverlayBackdrop,
    Preferences,
    Topbar,
    WallpaperWindow,
)

app = IgnisApp.get_initialized()
css_manager = CssManager.get_default()
niri = NiriService.get_default()

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

post_initialized()
