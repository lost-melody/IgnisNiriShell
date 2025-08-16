from ignis.services.audio import AudioService, Stream
from ignis.widgets import Box, Icon
from ignis.window_manager import WindowManager

from ..constants import WindowName
from ..utils import set_on_click

wm = WindowManager.get_default()


class Audio(Box):
    __gtype_name__ = "IgnisAudio"

    class AudioItem(Box):
        __gtype_name__ = "IgnisAudioItem"

        def __init__(self, stream: Stream):
            super().__init__(
                css_classes=["px-1"],
                tooltip_text=stream.bind("description"),
                child=[Icon(image=stream.bind("icon_name"))],
            )
            set_on_click(
                self,
                left=lambda _: stream.set_is_muted(not stream.is_muted),
                right=lambda _: wm.toggle_window(WindowName.control_center.value),
            )

    def __init__(self):
        self.__service = AudioService.get_default()
        super().__init__(
            css_classes=["hover", "rounded"],
            child=[self.AudioItem(stream) for stream in [self.__service.speaker, self.__service.microphone] if stream],
        )
