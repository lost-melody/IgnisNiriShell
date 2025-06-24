---This script is only useful when you're using fcitx5
---
---Install `fcitx5-lua`:
---
---```sh
---pacman -S fcitx5-lua
---```
---
---Install this extension:
---
---```sh
---mkdir -p ~/.local/share/fcitx5/lua/imeapi/extensions/
---ln -s /path/to/this/script.lua ~/.local/share/fcitx5/lua/imeapi/extensions/
---```
---
---Then restart fcitx5.
local _

---Module [`fcitx`](https://fcitx.github.io/fcitx5-lua/modules/fcitx.html)
local fcitx = require("fcitx")
---Module [`ime`](https://fcitx.github.io/fcitx5-lua/modules/ime.html)
local ime = ime

local function sync_state()
	local dest = "io.github.lost_melody.IgnisNiriShell"
	local cmd = {
		"dbus-send",
		"--session",
		"--type=method_call",
		"--dest=" .. dest,
		"/" .. string.gsub(dest, "[.]", "/"),
		dest .. ".SyncFcitxState",
	}
	os.execute(ime.join_string(cmd, " "))
end

function INS_on_key_event(key_code, key_state, is_release)
	local current_input_method = fcitx.currentInputMethod()
	if is_release and key_state ~= 0 and not string.match(current_input_method, "^keyboard%-") then
		sync_state()
	end
end

function INS_on_input_method_changed()
	sync_state()
end

fcitx.watchEvent(fcitx.EventType.KeyEvent, "INS_on_key_event")
fcitx.watchEvent(fcitx.EventType.SwitchInputMethod, "INS_on_input_method_changed")
