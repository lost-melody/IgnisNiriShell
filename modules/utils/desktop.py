import shlex

from gi.repository import Gio
from ignis.services.applications import Application
from ignis.utils import get_app_icon_name as ignis_get_app_icon_name

app_icon_overrides: dict[str, str] = {}
app_id_overrides: dict[str, str] = {}


def get_app_id(app_id: str) -> str:
    if not app_id:
        app_id = "unknown"
    if app_id.lower().endswith(".desktop"):
        app_id = app_id[:-8]
    override = app_id_overrides.get(app_id)
    if override:
        app_id = override
    return app_id


def get_app_icon_name(app_id: str | None = None, app_info: Application | None = None) -> str:
    app_id = app_id or app_info and app_info.id or ""
    app_id = get_app_id(app_id)
    icon = app_info and app_info.icon
    if not icon:
        icon = ignis_get_app_icon_name(app_id)
    if not icon:
        icon = app_icon_overrides.get(app_id)
    if not icon:
        icon = "application-default-icon"
    return icon


def launch_application(
    app: Application,
    files: list[str] | None = None,
    command_format: str | None = None,
    terminal_format: str | None = None,
):
    if not app.exec_string:
        return

    command: str = app.exec_string

    # pass file paths as arguments
    files = [shlex.quote(file) for file in files or []]
    file = files[0] if files else ""
    for k, v in {"%f": file, "%F": " ".join(files), "%u": file, "%U": " ".join(files)}.items():
        # nautilus --new-window file1 file2
        command = command.replace(k, v)

    # set key "Path" as cwd
    app_info: Gio.DesktopAppInfo = app.app
    cwd = app_info.get_string("Path")
    if cwd:
        # cd xxx; nautilus --new-window file1 file2
        command = f"cd {shlex.quote(cwd)}; {command}"

    # sh -c "cd xxx; nautilus --new-window file1 file2"
    command = f"sh -c {shlex.quote(command)}"

    # apply customized launch command
    format = terminal_format if app.is_terminal else command_format
    if format:
        # niri msg action spawn -- foot sh -c "cd xxx; yazi file"
        command = format.replace("%command%", command)

    app.launch(command_format=command, terminal_format=command)
