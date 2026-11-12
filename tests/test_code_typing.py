"""Replays plan() output against a *simulated* auto-indenting, auto-closing
editor and checks the buffer equals the source. This verifies the planner's
logic against my model of editor behavior, not any real editor.
Run: python3 tests/test_code_typing.py
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from code_typing import plan

PAIRS = {"(": ")", "[": "]", "{": "}"}
CLOSERS = set(PAIRS.values())


class SimEditor:
    def __init__(self, auto_indent, auto_close, width=4, dedent=False, sticky=False):
        self.t, self.c = "", 0
        self.ai, self.ac, self.w, self.dedent, self.sticky = auto_indent, auto_close, width, dedent, sticky

    def line_start(self):
        return self.t.rfind("\n", 0, self.c) + 1

    def ins(self, s):
        self.t = self.t[:self.c] + s + self.t[self.c:]
        self.c += len(s)

    def in_comment_or_string(self):
        """Crude: real editors don't auto-close inside comments/strings."""
        prefix = self.t[self.line_start():self.c]
        q = None
        for i, c in enumerate(prefix):
            if q:
                if c == q and prefix[i - 1] != "\\":
                    q = None
            elif c == "#":
                return True
            elif c in "'\"":
                q = c
        return q is not None

    def char(self, ch):
        nxt = self.t[self.c:self.c + 1]
        if self.ac and ch in PAIRS and self.in_comment_or_string():
            self.ins(ch)
            return
        if self.ac and ch in "'\"" and self.in_comment_or_string() and nxt != ch:
            self.ins(ch)
            return
        if self.ac and ch in CLOSERS | {"'", '"'} and nxt == ch:
            self.c += 1
        elif self.ac and ch in PAIRS and not (nxt and nxt not in CLOSERS | {" ", "\n"}):
            self.ins(ch + PAIRS[ch]); self.c -= 1
        elif self.ac and ch in "'\"" and not (self.t[self.c - 1:self.c].isalnum()) and not nxt.strip():
            self.ins(ch + ch); self.c -= 1
        else:
            self.ins(ch)

    def enter(self):
        ls = self.line_start()
        before = self.t[ls:self.c]
        indent = len(before) - len(before.lstrip(" "))
        if self.sticky and before.strip() == "":   # blank line: keep the last code line's indent
            prev = [l for l in self.t[:ls].split("\n") if l.strip()]
            indent = len(prev[-1]) - len(prev[-1].lstrip(" ")) if prev else 0
        b = before.rstrip()
        opener = b != "" and b[-1] in "([{"
        extra = self.w if (b.endswith(":") or opener) else 0
        if self.dedent and b.strip().split(" ")[0] in ("return", "pass", "break", "continue", "raise"):
            indent = max(indent - self.w, 0)
        if not self.ai:
            indent, extra = 0, 0
        nxt = self.t[self.c:self.c + 1]
        if self.ai and nxt in CLOSERS and opener:
            self.ins("\n" + " " * (indent + extra) + "\n" + " " * indent)
            self.c -= 1 + indent
        else:
            self.ins("\n" + " " * (indent + extra))

    def clear(self):
        """Sentinel space, select to line start, Backspace (never joins lines)."""
        self.ins(" ")
        ls = self.line_start()
        self.t = self.t[:ls] + self.t[self.c:]
        self.c = ls

    def fdel(self):
        self.t = self.t[:self.c] + self.t[self.c + 1:]

    def run(self, actions):
        for kind, arg in actions:
            if kind == "char": self.char(arg)
            elif kind == "enter": self.enter()
            elif kind == "indent": self.char(" ")
            elif kind == "indent_tab": self.ins("\t")
            elif kind == "clear": self.clear()
            elif kind == "fdel": self.fdel()
        return self.t


SAMPLE = '''import os


def greet(name, times=2):
    """Say hi."""
    for i in range(times):
        if i % 2 == 0:
            print(f"Hello, {name}! ({i})")
        else:
            print('odd', end="")

    result = compute(
        name,
        [1, 2,
         3],
        {"a": (1, 2), "b": [x for x in range(3)]},
    )
    return result


class A:
    def m(self):
        # it's a comment with ( bracket
        s = "string with ( paren"
        return (
            1 + 2
        )
'''


def normalized(src):
    return "\n".join(l.rstrip() for l in src.split("\n"))


def check(src, want=None, width=4, dedent=False, sticky=False, **opts):
    ed = SimEditor(opts["auto_indent"], opts["auto_close"], width, dedent, sticky)
    got = ed.run(plan(src, **opts))
    want = normalized(src) if want is None else want
    assert got == want, f"{opts} width={width} dedent={dedent} sticky={sticky}\n--- got ---\n{got!r}\n--- want ---\n{want!r}"


def to_tabs(src):
    out = []
    for l in normalized(src).split("\n"):
        n = len(l) - len(l.lstrip(" "))
        out.append("\t" * (n // 4) + " " * (n % 4) + l.lstrip(" "))
    return "\n".join(out)


for ai in (True, False):
    for ac in (True, False):
        for width in (2, 4, 8):
            for dedent, sticky in ((False, False), (True, False), (False, True), (True, True)):
                if not ai and (dedent or sticky):
                    continue
                check(SAMPLE, auto_indent=ai, auto_close=ac, width=width, dedent=dedent, sticky=sticky)
                check(SAMPLE.replace("    ", "\t"), want=normalized(SAMPLE), auto_indent=ai,
                      auto_close=ac, width=width, dedent=dedent, sticky=sticky)
        if not ai:  # (the simulated editor's auto-indent only knows spaces)
            check(SAMPLE, want=to_tabs(SAMPLE), auto_indent=ai, auto_close=ac, use_tabs=True)
print("all simulated-editor checks passed")
