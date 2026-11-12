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
from Quartz import (
    CGEventCreateKeyboardEvent, CGEventKeyboardSetUnicodeString, CGEventPost,
    CGEventSetFlags, CGEventSourceCreate, CGEventSourceKeyState, kCGEventFlagMaskCommand,
    kCGEventSourceStatePrivate, kCGHIDEventTap, kCGEventSourceStateCombinedSessionState,
)

KEY_RETURN, KEY_TAB, KEY_DELETE, KEY_ESC, KEY_FWD_DELETE = 36, 48, 51, 53, 117


def esc_pressed():
    return CGEventSourceKeyState(kCGEventSourceStateCombinedSessionState, KEY_ESC)


KEY_CMD = 55


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

    def release_all(self):
        self._post(KEY_CMD, False, flags=0)


def text_actions(text):
    """Turn plain text into an action list for run_actions."""
    out = []
    for ch in text:
        out.append(("enter", None) if ch == "\n" else ("tab", None) if ch == "\t" else ("char", ch))
    return out


def run_actions(actions, wpm, jitter, typo_rate, stop):
    """Perform (kind, arg) actions with human-like timing.

    kinds: char, enter, tab, indent (space), indent_tab (fast),
           clear (Cmd+Delete: delete to line start), fdel (forward delete)
    """
    kb = Keys()
    base = 60.0 / (wpm * 5)  # seconds per character

    def pause(mult):
        time.sleep(max(base * mult * random.uniform(1 - jitter, 1 + jitter), 0.005))

    try:
        _run(kb, actions, base, pause, typo_rate, stop)
    finally:
        kb.release_all()


def _run(kb, actions, base, pause, typo_rate, stop):
    for kind, arg in actions:
        if stop["flag"] or esc_pressed():
            stop["flag"] = True
            print("\nStopped.")
            return
        if kind == "char":
            if typo_rate and arg.isalpha() and random.random() < typo_rate:
                kb.type(random.choice("abcdefghijklmnopqrstuvwxyz"))
                time.sleep(base * random.uniform(1.5, 3))
                kb.key(KEY_DELETE)
                time.sleep(base * random.uniform(0.5, 1.5))
            kb.type(arg)
            pause(3 if arg in ".!?" else 1.4 if arg in ",;: " else 1)
        elif kind == "enter":
            kb.key(KEY_RETURN)
            pause(3)
        elif kind == "tab":
            kb.key(KEY_TAB)
            pause(1)
        elif kind == "indent":
            kb.type(" ")
            pause(0.25)
        elif kind == "indent_tab":
            kb.key(KEY_TAB)
            pause(0.25)
        elif kind == "clear":
            kb.key(KEY_DELETE, cmd=True)
            pause(1.5)
        elif kind == "fdel":
            kb.key(KEY_FWD_DELETE)
            pause(0.5)


def type_text(text, wpm, jitter, typo_rate, stop):
    run_actions(text_actions(text), wpm, jitter, typo_rate, stop)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    src = p.add_mutually_exclusive_group()
    src.add_argument("-f", "--file", help="read text from file")
    src.add_argument("-t", "--text", help="text to type")
    p.add_argument("--code", choices=list(LANGUAGES), help="type as source code in this language (handles indentation/auto-close)")
    p.add_argument("--no-auto-indent", action="store_true", help="code mode: editor does NOT auto-indent")
    p.add_argument("--no-auto-close", action="store_true", help="code mode: editor does NOT auto-close brackets/quotes")
    p.add_argument("--format", action="store_true", help="code mode: format the code (black for Python) before typing")
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
    if a.code:
        if a.format:
            try:
                text = format_source(text, LANGUAGES[a.code])
            except FormatError as e:
                sys.exit(str(e))
        actions = plan(text, LANGUAGES[a.code], not a.no_auto_indent, not a.no_auto_close, a.tabs)
    else:
        actions = text_actions(text)
    run_actions(actions, a.wpm, a.jitter, a.typos, stop)
    print("Done.")


if __name__ == "__main__":
    main()
