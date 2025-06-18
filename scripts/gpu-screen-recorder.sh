#!/usr/bin/env bash

# This is a wrapper for gpu-screen-recorder installed via flatpak.
# We trap the INT signal and forward it to the right process,
# so that ignis stops the recording by sending the signal.

target_pid=0

# among all those "gpu-screen-recorder" processes,
# find the one that is a descendant of the current instance
function find_target() {
    if [ "${target_pid}" -ne 0 ]; then
        return
    fi
    for pid in $(pidof gpu-screen-recorder); do
        local p="${pid}"
        while [ "${p}" -gt 1 ]; do
            # find the parent process
            p="$(cat "/proc/${p}/stat" | cut -d " " -f 4)"
            if [ "${p}" -eq "$$" ]; then
                target_pid="${pid}"
                return
            fi
        done
    done
    # target not found
    target_pid=1
    return 1
}

function on_signal() {
    local signal="$1"
    find_target
    if [ "${target_pid}" -gt 1 ]; then
        kill -s "${signal}" "${target_pid}"
    fi
    if [ "${signal}" = "INT" ]; then
        exit
    fi
}

function main() {
    # run gpu-screen-recorder in background and wait
    flatpak run --command=gpu-screen-recorder -- com.dec05eba.gpu_screen_recorder "$@" &
    trap "on_signal INT" INT
    trap "on_signal USR2" USR2
    # child process can exit on USR2, so keep waiting for a sleep process
    while true; do
        wait
        find_target
        if [ "${target_pid}" -le 1 ]; then
            break
        fi
        sleep 1m &
    done
}

main "$@"
