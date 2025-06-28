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

local function open_signal_file()
	local run_dir = os.getenv("XDG_RUNTIME_DIR")
	if not run_dir then
		return
	end
	local file = io.open(run_dir .. "/fcitx-ignis-signal", "w")
	return file
end

local signal_file = open_signal_file()
local signal_count = 0

local function notify_state()
	if not signal_file then
		signal_file = open_signal_file()
		if not signal_file then
			return
		end
	end

	signal_file:write("\n")
	signal_file:flush()

	signal_count = signal_count + 1
	if signal_count > 256 then
		signal_count = 0
		signal_file:close()
		signal_file = nil
	end
end

function INS_on_key_event(key_code, key_state, is_release)
	if is_release and key_state ~= 0 and not string.match(fcitx.currentInputMethod(), "^keyboard%-") then
		notify_state()
	end
end

function INS_on_input_method_changed()
	notify_state()
end

fcitx.watchEvent(fcitx.EventType.KeyEvent, "INS_on_key_event")
fcitx.watchEvent(fcitx.EventType.SwitchInputMethod, "INS_on_input_method_changed")
