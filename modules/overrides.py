from .utils import app_icon_overrides, app_id_overrides


app_icons_mapper: dict[str, str] = {
    # map windows by app_id/class to icon names
    "com.github.linkfrg.ignis": "window-symbolic",
}

app_id_mapper: dict[str, str] = {
    # map windows by app_id/class to desktop files
    "Chromium": "chromium",
    "wechat": "com.tencent.WeChat",
    "wemeetapp": "com.tencent.wemeet",
    "QQ": "com.qq.QQ",
}

for app_id, icon_name in app_icons_mapper.items():
    app_icon_overrides[app_id] = icon_name

for from_id, to_id in app_id_mapper.items():
    app_id_overrides[from_id] = to_id
