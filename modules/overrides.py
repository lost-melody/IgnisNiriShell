from .utils import app_icon_overrides


app_icons_mapper: dict[str, str] = {
    "com.github.linkfrg.ignis": "window-symbolic",
    "wechat": "com.tencent.WeChat",
    "wemeetapp": "com.tencent.wemeet",
    "QQ": "com.qq.QQ",
}

for app_id, icon_name in app_icons_mapper.items():
    app_icon_overrides[app_id] = icon_name
