#!/usr/bin/env python3
"""Type text into whatever has focus, as if you were typing it yourself.

Usage:
    python3 keyboard_sim.py -f sample.txt
    python3 keyboard_sim.py -t "hello world" --delay 5 --wpm 70
    pbpaste | python3 keyboard_sim.py

Workflow: run it, then click where you want the text to go. After the
countdown it starts typing. Press
Ctrl+C in the terminal to abort or press Esc.
"""
import argparse
import random
import sys
import time

from Quartz import (
    CGEventCreateKeyboardEvent, CGEventKeyboardSetUnicodeString, CGEventPost,
    CGEventSourceKeyState, kCGHIDEventTap, kCGEventSourceStateCombinedSessionState,
)

KEY_RETURN, KEY_TAB, KEY_DELETE, KEY_ESC = 36, 48, 51, 53


def esc_pressed():
    return CGEventSourceKeyState(kCGEventSourceStateCombinedSessionState, KEY_ESC)


class Keys:
    def _tap(self, code, text=None):
        for down in (True, False):
            ev = CGEventCreateKeyboardEvent(None, code, down)
            if text is not None:
                CGEventKeyboardSetUnicodeString(ev, len(text), text)
            CGEventPost(kCGHIDEventTap, ev)
            time.sleep(0.002)

    def type(self, text):
        for c in text:
            self._tap(0, c)

    def key(self, code):
        self._tap(code)


def type_text(text, wpm, jitter, typo_rate, stop):
    kb = Keys()
    base = 60.0 / (wpm * 5)  # seconds per character
    for ch in text:
        if stop["flag"] or esc_pressed():
            stop["flag"] = True
            print("\nStopped.")
            return
        if typo_rate and ch.isalpha() and random.random() < typo_rate:
            kb.type(random.choice("abcdefghijklmnopqrstuvwxyz"))
            time.sleep(base * random.uniform(1.5, 3))
            kb.key(KEY_DELETE)
            time.sleep(base * random.uniform(0.5, 1.5))
        if ch == "\n":
            kb.key(KEY_RETURN)
        elif ch == "\t":
            kb.key(KEY_TAB)
        else:
            kb.type(ch)
        d = base * random.uniform(1 - jitter, 1 + jitter)
        if ch in ".!?\n":
            d *= 3
        elif ch in ",;: ":
            d *= 1.4
        time.sleep(max(d, 0.005))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    src = p.add_mutually_exclusive_group()
    src.add_argument("-f", "--file", help="read text from file")
    src.add_argument("-t", "--text", help="text to type")
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
    type_text(text, a.wpm, a.jitter, a.typos, stop)
    print("Done.")


if __name__ == "__main__":
    main()
