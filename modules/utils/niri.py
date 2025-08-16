from typing import Any

from ignis.services.niri import NiriService


def niri_action(action: str, args: Any = {}):
    niri = NiriService.get_default()
    if niri.is_available:
        return niri.send_command({"Action": {action: args}})
