from ignis.services.recorder import RecorderService


recorder = RecorderService.get_default()
if recorder.active:
    if recorder.is_paused:
        recorder.continue_recording()
    else:
        recorder.stop_recording()
else:
    recorder.start_recording()
