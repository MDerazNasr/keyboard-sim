#!/usr/bin/env python3
"""Type text into whatever has focus, as if you were typing it yourself.

Usage:
    python3 keyboard_sim.py -f sample.txt
    python3 keyboard_sim.py -t "hello world" --delay 5 --wpm 70
    pbpaste | python3 keyboard_sim.py

Workflow: run it, then click where you want the text to go. After the
countdown it starts typing. Press Ctrl+C in the terminal or Esc to abort.
"""
import argparse
import random
import sys
import time

from code_typing import LANGUAGES, FormatError, format_source, plan
from timing import Profile, expand
from Quartz import (
    CGEventCreateKeyboardEvent, CGEventKeyboardSetUnicodeString, CGEventPost,
    CGEventSetFlags, CGEventSourceCreate, CGEventSourceKeyState, kCGEventFlagMaskCommand,
    kCGEventFlagMaskShift,
    kCGEventSourceStatePrivate, kCGHIDEventTap, kCGEventSourceStateCombinedSessionState,
)

KEY_RETURN, KEY_TAB, KEY_DELETE, KEY_ESC, KEY_FWD_DELETE = 36, 48, 51, 53, 117


def esc_pressed():
    return CGEventSourceKeyState(kCGEventSourceStateCombinedSessionState, KEY_ESC)


KEY_CMD, KEY_SHIFT, KEY_LEFT = 55, 56, 123


class Keys:
    """Posts synthetic keystrokes. Every event gets its modifier flags set
    explicitly (0 unless asked), so a modifier can never leak into later keys."""

    def __init__(self):
        self.src = CGEventSourceCreate(kCGEventSourceStatePrivate)

    def _post(self, code, down, text=None, flags=0):
        ev = CGEventCreateKeyboardEvent(self.src, code, down)
        if text is not None:
            CGEventKeyboardSetUnicodeString(ev, len(text), text)
        CGEventSetFlags(ev, flags)
        CGEventPost(kCGHIDEventTap, ev)
        time.sleep(0.002)

    def _tap(self, code, text=None, flags=0):
        self._post(code, True, text, flags)
        self._post(code, False, text, flags)

    def type(self, text):
        for c in text:
            self._tap(0, c)

    def key(self, code, cmd=False):
        if not cmd:
            self._tap(code)
            return
        # Press the Command key itself, tap the key, then release Command.
        flags = kCGEventFlagMaskCommand
        try:
            self._post(KEY_CMD, True, flags=flags)
            self._tap(code, flags=flags)
        finally:
            self.release_all()

    def clear_line(self):
        """Remove everything left of the cursor on this line (auto-inserted indent).

        Types a sentinel space first, so there is always something to the left;
        then Cmd+Shift+Left selects back to the line start and Backspace deletes
        the selection. Backspace over a non-empty selection can never join lines,
        so this is safe whatever the editor inserted (nothing, or any indent).
        Avoids Cmd+Delete, which means "delete line" in JetBrains editors.
        """
        self.type(" ")
        cmd = kCGEventFlagMaskCommand
        both = cmd | kCGEventFlagMaskShift
        try:
            self._post(KEY_CMD, True, flags=cmd)
            self._post(KEY_SHIFT, True, flags=both)
            self._tap(KEY_LEFT, flags=both)
        finally:
            self.release_all()
        self._tap(KEY_DELETE)

    def release_all(self):
        self._post(KEY_SHIFT, False, flags=0)
        self._post(KEY_CMD, False, flags=0)


def text_actions(text):
    """Turn plain text into an action list for run_actions."""
    out = []
    for ch in text:
        out.append(("enter", None) if ch == "\n" else ("tab", None) if ch == "\t" else ("char", ch))
    return out


def _sleep(d, stop):
    """Sleep d seconds in small slices so Esc/Stop interrupts long pauses."""
    end = time.monotonic() + d
    while (left := end - time.monotonic()) > 0:
        if stop["flag"] or esc_pressed():
            return
        time.sleep(min(left, 0.05))


def run_actions(actions, wpm, jitter, typo_rate, stop, profile=None, log=None, rng=None):
    """Perform (kind, arg) actions with human-like timing (see timing.py).

    kinds: char, enter, tab, indent (space), indent_tab, clear (wipe left of cursor on the line), fdel (forward delete), pause (planner hint, timing only)
    profile: timing.Profile for developer-style timing, or None for flat jittered timing.
    log: optional list; receives (seconds_since_start, kind) for every keystroke.
    """
    steps = expand(actions, wpm, jitter, typo_rate, profile, rng)
    kb = Keys()
    keys = {"enter": lambda a: kb.key(KEY_RETURN), "tab": lambda a: kb.key(KEY_TAB),
            "indent": lambda a: kb.type(" "), "indent_tab": lambda a: kb.key(KEY_TAB),
            "clear": lambda a: kb.clear_line(), "fdel": lambda a: kb.key(KEY_FWD_DELETE),
            "bs": lambda a: kb.key(KEY_DELETE), "char": lambda a: kb.type(a)}
    t0 = time.monotonic()
    try:
        for kind, arg, delay in steps:
            if stop["flag"] or esc_pressed():
                stop["flag"] = True
                print("\nStopped.")
                return
            if kind in keys:
                keys[kind](arg)
                if log is not None:
                    log.append((time.monotonic() - t0, kind))
            _sleep(delay, stop)
    finally:
        kb.release_all()


def type_text(text, wpm, jitter, typo_rate, stop):
    run_actions(text_actions(text), wpm, jitter, typo_rate, stop)


def write_log(log, path):
    """Write a keystroke timing log as CSV (t_seconds,kind)."""
    import csv
    import os
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t_seconds", "kind"])
        w.writerows((f"{t:.4f}", k) for t, k in log)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    src = p.add_mutually_exclusive_group()
    src.add_argument("-f", "--file", help="read text from file")
    src.add_argument("-t", "--text", help="text to type")
    p.add_argument("--code", choices=list(LANGUAGES), help="type as source code in this language (handles indentation/auto-close)")
    p.add_argument("--no-auto-indent", action="store_true", help="code mode: editor does NOT auto-indent")
    p.add_argument("--no-auto-close", action="store_true", help="code mode: editor does NOT auto-close brackets/quotes")
    p.add_argument("--format", action="store_true", help="code mode: format the code (black for Python) before typing")
    p.add_argument("--dev-timing", action="store_true", help="code mode: developer-style timing (bursts, thinking pauses, revisions)")
    p.add_argument("--burstiness", type=float, default=Profile.burstiness, help="dev timing: 0-1.5 keystroke-speed variation")
    p.add_argument("--think-chance", type=float, default=Profile.think_chance, help="dev timing: chance of a pause at a line end (0-1)")
    p.add_argument("--think-median", type=float, default=Profile.think_median, help="dev timing: median thinking pause, seconds")
    p.add_argument("--think-max", type=float, default=Profile.think_max, help="dev timing: longest pause, seconds")
    p.add_argument("--revise-rate", type=float, default=Profile.revise_rate, help="dev timing: chance per identifier of backspace-and-retype")
    p.add_argument("--log", metavar="CSV", help="write a keystroke timing log to this CSV file")
    p.add_argument("--tabs", action="store_true", help="code mode: indent with tabs instead of spaces")
    p.add_argument("-d", "--delay", type=float, default=5, help="seconds to wait before typing (default 5)")
    p.add_argument("--wpm", type=float, default=80, help="typing speed in words/min (default 80)")
    p.add_argument("--jitter", type=float, default=0.5, help="0-1 random timing variation (default 0.5)")
    p.add_argument("--typos", type=float, default=0.0, help="chance per letter of a typo that gets corrected, e.g. 0.02")
    a = p.parse_args()

    if a.file:
        text = open(a.file, encoding="utf-8").read()
    elif a.text is not None:
        text = a.text
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        p.error("provide text with -t, -f, or stdin")

    stop = {"flag": False}

    for i in range(int(a.delay), 0, -1):
        print(f"Typing in {i}... (click where the text should go; Esc aborts)", end="\r", flush=True)
        time.sleep(1)
    print(" " * 70, end="\r")
    profile = None
    if a.dev_timing:
        if not a.code:
            p.error("--dev-timing requires --code")
        profile = Profile(a.burstiness, a.think_chance, a.think_median, a.think_max, a.revise_rate)
    if a.code:
        if a.format:
            try:
                text = format_source(text, LANGUAGES[a.code])
            except FormatError as e:
                sys.exit(str(e))
        actions = plan(text, LANGUAGES[a.code], not a.no_auto_indent, not a.no_auto_close, a.tabs)
    else:
        actions = text_actions(text)
    log = [] if a.log else None
    run_actions(actions, a.wpm, a.jitter, a.typos, stop, profile, log)
    if a.log:
        write_log(log, a.log)
        print(f"Timing log: {a.log}")
    print("Done.")


if __name__ == "__main__":
    main()
