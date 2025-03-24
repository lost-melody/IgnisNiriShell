import os, subprocess
from typing import Any, Callable
from gi.repository import Gtk
from ignis.app import IgnisApp


TMPDIR = os.getenv("TMPDIR") or "/tmp"
app = IgnisApp.get_default()

if app._config_path is None:
    raise Exception("app._config_path is None")

config_dir = os.path.dirname(app._config_path)
ui_path = os.path.join(config_dir, "ui")
tmp_path = os.path.join(TMPDIR, "ignis/ui")


def build_blueprint(blp_filename: str, ui_filename: str):
    os.makedirs(os.path.dirname(ui_filename), exist_ok=True)

    result = subprocess.run(args=["blueprint-compiler", "compile", "--out", ui_filename, blp_filename])

    if result.returncode != 0:
        raise Exception(f"blueprint-compiler exits with return code {result.returncode}")


def ensure_ui_file(filename: str) -> str:
    blp_filename = os.path.join(ui_path, filename + ".blp")
    ui_filename = os.path.join(tmp_path, filename + ".ui")

    blp_exist = os.path.exists(blp_filename)
    ui_exist = os.path.exists(ui_filename)

    if blp_exist:
        if ui_exist:
            blp_mtime = os.path.getmtime(blp_filename)
            ui_mtime = os.path.getmtime(ui_filename)

            if ui_mtime < blp_mtime:
                build_blueprint(blp_filename, ui_filename)
        else:
            build_blueprint(blp_filename, ui_filename)
    else:
        if ui_exist:
            pass
        else:
            raise Exception(f"blueprint file `{blp_filename}` does not exist")

    return ui_filename


def gtk_template[Widget: type[Gtk.Widget]](filename: str) -> Callable[[Widget], Widget]:
    template = Gtk.Template(filename=ensure_ui_file(filename))

    def decorator(cls: Widget) -> Widget:
        return template(cls)  # type: ignore

    return decorator


def gtk_template_child() -> Any:
    return Gtk.Template.Child()  # type: ignore


def gtk_template_callback[Callback: Callable](method: Callback) -> Callback:
    make_callback = Gtk.Template.Callback()
    return make_callback(method)
