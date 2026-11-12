"""Timing model for keystroke actions.

expand() turns an action list (see code_typing.plan / keyboard_sim.text_actions)
into concrete steps (kind, arg, delay_after_seconds). It is pure (no key presses),
so the same model drives real typing, offline simulation and tests.

With profile=None you get the original flat model (uniform jitter). With a
Profile you get developer-style timing: bursty keystroke speed, thinking pauses
at line/block/section boundaries, brief hesitations, and backspace-and-retype
revisions inside identifiers.
"""
import math
import random
from dataclasses import dataclass


@dataclass
class Profile:
    burstiness: float = 0.45      # sigma of log keystroke interval (0 = metronome)
    think_chance: float = 0.30    # chance of a thinking pause at a line end (blocks/sections get more)
    think_median: float = 1.5     # median thinking pause, seconds (lognormal)
    think_max: float = 30.0       # cap on any thinking pause, seconds
    revise_rate: float = 0.03     # chance per identifier of backspace-and-retype


# multipliers on the per-character base interval
_WORD = lambda c: c.isalnum() or c == "_"


def _legacy_mult(kind, arg):
    if kind == "char":
        return 3 if arg in ".!?" else 1.4 if arg in ",;: " else 1
    return {"enter": 3, "tab": 1, "indent": 0.25, "indent_tab": 0.25,
            "clear": 1.5, "fdel": 0.5, "bs": 1}.get(kind, 0)


def expand(actions, wpm, jitter=0.5, typo_rate=0.0, profile=None, rng=None):
    rng = rng or random
    base = 60.0 / (max(wpm, 1) * 5)  # seconds per character
    steps = []
    burst = {"left": 0, "f": 1.0}

    def add(kind, arg, d):
        steps.append((kind, arg, max(d, 0.005)))

    def interval(mult):
        if profile is None:
            return base * mult * rng.uniform(1 - jitter, 1 + jitter)
        if burst["left"] <= 0:
            burst["f"] = rng.choices((0.55, 1.0, 1.7), (0.3, 0.5, 0.2))[0]
            burst["left"] = rng.randint(5, 25)
        burst["left"] -= 1
        return base * mult * burst["f"] * rng.lognormvariate(0, profile.burstiness)

    def char_mult(prev, ch):
        if profile is None:
            return _legacy_mult("char", ch)
        if _WORD(ch):
            return 0.85 if _WORD(prev) else 1.25
        if ch == " ":
            return 1.2
        if ch in ",;:":
            return 1.4
        return 1.3 if ch in "([{=+-*/<>" else 1.1

    def mult_for(kind, arg, prev):
        if kind == "char":
            return char_mult(prev, arg)
        if profile is not None and kind == "enter":
            return 2
        return _legacy_mult(kind, arg)

    def lognormal_wait(median, sigma, lo, hi):
        return min(hi, max(lo, rng.lognormvariate(math.log(median), sigma)))

    prev = ""
    run = 0  # length of the identifier just typed (only counts consecutive char actions)
    for idx, (kind, arg) in enumerate(actions):
        if kind == "pause":
            if profile is not None:
                c = profile.think_chance
                p, scale = {"line": (c, 1.0), "block": (min(1, 2 * c), 1.5),
                            "section": (min(1, 2.5 * c), 2.5)}.get(arg, (0, 1))
                if rng.random() < p:
                    add("wait", None, lognormal_wait(profile.think_median * scale, 0.8, 0.3, profile.think_max))
            continue

        if kind == "char":
            # backspace-and-retype inside an identifier, right as it ends
            if (profile is not None and run >= 4 and not _WORD(arg)
                    and rng.random() < profile.revise_rate):
                k = rng.randint(1, min(3, run - 1))
                word = [a for kd, a in actions[idx - k:idx]]
                add("wait", None, lognormal_wait(0.5, 0.5, 0.2, 2.0))
                for _ in range(k):
                    add("bs", None, interval(1.3))
                add("wait", None, lognormal_wait(0.35, 0.5, 0.15, 1.5))
                for j, ch in enumerate(word):
                    add("char", ch, interval(char_mult(word[j - 1] if j else "", ch)))
            if typo_rate and arg.isalpha() and rng.random() < typo_rate:
                add("char", rng.choice("abcdefghijklmnopqrstuvwxyz"), base * rng.uniform(1.5, 3))
                add("bs", None, base * rng.uniform(0.5, 1.5))
            add("char", arg, interval(char_mult(prev, arg)))
            if profile is not None and arg == " " and rng.random() < min(0.1, 0.02 * profile.think_chance / 0.3):
                add("wait", None, lognormal_wait(0.5, 0.5, 0.2, 3.0))   # brief hesitation
            run = run + 1 if _WORD(arg) else 0
            prev = arg
        else:
            add(kind, arg, interval(mult_for(kind, arg, prev)))
            run, prev = 0, ""
    return steps
