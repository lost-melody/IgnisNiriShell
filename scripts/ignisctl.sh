#!/usr/bin/env bash

function logf() {
    local fmt="$1"
    shift
    printf "${fmt}\n" "$@" >&2
}

function dbus_call() {
    local dest
    local object
    local method="$1"
    shift

    case "${method}" in
    CloseWindow | Inspector | ListWindows | OpenWindow | Reload | RunFile | RunPython | ToggleWindow | Quit)
        dest="com.github.linkfrg.ignis"
        object="/com/github/linkfrg/ignis"
        method="com.github.linkfrg.ignis.${method}"
        ;;
    *)
        dest="io.github.lost_melody.IgnisNiriShell"
        object="/io/github/lost_melody/IgnisNiriShell"
        method="io.github.lost_melody.IgnisNiriShell.${method}"
        ;;
    esac

    dbus-send --session --dest="${dest}" --type=method_call --print-reply "${object}" "${method}" "$@"
}

function usage() {
    logf "Usage:"
    logf "\t%s <method> [arguments]" "$0"
    logf "Example:"
    logf "\t%s ListWindows" "$0"
    logf "\t%s ToggleWindow string:ignis-applauncher" "$0"
    logf "For a list of available methods, please refer to:"
    logf "\t%s" "{ignis}/dbus/com.github.linkfrg.ignis.xml"
    logf "\t%s" "{IgnisNiriShell}/modules/dbus/io.github.lost-melody.IgnisNiriShell.xml"
}

function main() {
    if [ -z "$1" ]; then
        usage
        return 1
    fi

    dbus_call "$@"
}

main "$@"
