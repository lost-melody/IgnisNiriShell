import asyncio

from ignis.services.recorder import RecorderConfig, RecorderService
from ignis.widgets import Box, Icon

from ..utils import set_on_click


class RecorderIndicator(Box):
    __gtype_name__ = "IgnisRecorderIndicator"

    def __init__(self):
        self.__service = RecorderService.get_default()
        self.__icon = Icon()
        super().__init__(css_classes=["hover", "px-1", "rounded", "warning"], child=[self.__icon])

        set_on_click(self, left=self.__class__.__on_clicked, right=self.__class__.__on_right_clicked)
        self.__on_status_changed()

    def __on_status_changed(self, *_):
        if self.__service.active:
            self.set_visible(True)
            if self.__service.is_paused:
                self.set_tooltip_text("Screen Recorder Paused")
                self.__icon.image = "media-playback-pause-symbolic"
            else:
                self.set_tooltip_text("Screen Recording")
                self.__icon.image = "camera-video-symbolic"
        else:
            self.set_visible(False)

    def __on_clicked(self, *_):
        if self.__service.active:
            if self.__service.is_paused:
                self.__service.continue_recording()
            else:
                self.__service.stop_recording()
        else:
            asyncio.create_task(self.__service.start_recording(RecorderConfig.new_from_options()))

    def __on_right_clicked(self, *_):
        if self.__service.active:
            if self.__service.is_paused:
                self.__service.continue_recording()
            else:
                self.__service.pause_recording()
