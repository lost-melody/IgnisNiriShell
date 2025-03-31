from modules.useroptions import user_options


if user_options and user_options.appdock:
    user_options.appdock.auto_conceal = not user_options.appdock.auto_conceal
