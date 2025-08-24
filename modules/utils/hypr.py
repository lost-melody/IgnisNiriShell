from ignis.services.hyprland import HyprlandService


def hypr_command(command: str):
    hypr = HyprlandService.get_default()
    if hypr.is_available:
        return hypr.send_command(command)
