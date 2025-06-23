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

local state = {
	current_input_method = "",
}

local function sync_state()
	local attrs = {}
	for k, v in pairs(state) do
		table.insert(attrs, k .. ":" .. tostring(v))
	end
	local msg = ime.join_string(attrs, ";")
	local dest = "io.github.lost_melody.IgnisNiriShell"
	local cmd = {
		"dbus-send",
		"--session",
		"--type=method_call",
		"--dest=" .. dest,
		"/" .. string.gsub(dest, "[.]", "/"),
		dest .. ".SyncFcitxState",
		'string:"' .. string.gsub(msg, '"', '\\"') .. '"',
	}
	os.execute(ime.join_string(cmd, " "))
end

function INS_on_input_method_changed()
	local new_input_method = fcitx.currentInputMethod()
	if state.current_input_method ~= new_input_method then
		state.current_input_method = new_input_method
		sync_state()
	end
end

fcitx.watchEvent(fcitx.EventType.SwitchInputMethod, "INS_on_input_method_changed")
