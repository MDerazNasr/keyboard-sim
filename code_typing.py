"""Plan keystrokes for typing source code into a real code editor.

Editors fight raw typing: they auto-indent new lines and auto-close brackets
and quotes. Typing code verbatim therefore double-indents and leaves stray
closers. plan() turns source into an action list (see keyboard_sim.run_actions)
that compensates:

* auto_indent: after Enter the editor may have inserted indentation (copied from
  the previous line, +1 level after ':' or an opening bracket). We predict that,
  wipe it with Cmd+Delete, and type the exact indentation from the source.
* auto_close: when a line ends with brackets (or a triple quote) still open, the
  editor has already inserted their closers after the cursor. We forward-delete
  them before pressing Enter, so the closers we type later aren't duplicated.
  Closers typed on the same line as their opener are simply typed over.

Assumes you start on an empty line at column 0 of a new area (nothing to the
right of the cursor).

To add a language, define a Language and register it in LANGUAGES.
"""
from dataclasses import dataclass
from typing import Callable

OPEN, CLOSE = "([{", ")]}"


@dataclass(frozen=True)
class Language:
    name: str
    comment: str                              # line-comment marker
    quotes: str = "'\""
    triple_quotes: bool = False
    opens_block: Callable[[str], bool] = lambda code: False   # line (sans comment) starts an indented block
    formatter: Callable[[str], str] = None    # source -> formatted source; raises FormatError


class FormatError(Exception):
    pass


def _format_python(source):
    try:
        import black
    except ImportError:
        raise FormatError("black isn't installed (pip install black)")
    try:
        return black.format_str(source, mode=black.Mode())
    except Exception as e:  # black.InvalidInput, etc.
        raise FormatError(f"Can't format (is the code valid Python?): {e}")


PYTHON = Language("Python", "#", triple_quotes=True, opens_block=lambda code: code.endswith(":"),
                  formatter=_format_python)
LANGUAGES = {"Python": PYTHON}


def _scan(lang, line, line_no, triple, stack):
    """Scan one line. Mutates stack of (bracket, line_no); returns
    (code_without_comment, triple_state_at_eol, triple_opened_on_this_line)."""
    i, n = 0, len(line)
    quote = None
    opened_triple = False
    end = n
    while i < n:
        c = line[i]
        if triple:
            if line.startswith(triple, i):
                triple, opened_triple = None, False
                i += 3
            else:
                i += 2 if c == "\\" else 1
            continue
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if line.startswith(lang.comment, i):
            end = i
            break
        if c in lang.quotes:
            if lang.triple_quotes and line.startswith(c * 3, i):
                triple, opened_triple = c * 3, True
                i += 3
            else:
                quote = c
                i += 1
            continue
        if c in OPEN:
            stack.append((c, line_no))
        elif c in CLOSE and stack:
            stack.pop()
        i += 1
    return line[:end].rstrip(), triple, opened_triple


def format_source(source, lang=PYTHON):
    """Run the language's formatter; raises FormatError if it can't."""
    if lang.formatter is None:
        raise FormatError(f"No formatter available for {lang.name}")
    return lang.formatter(source)


def plan(source, lang=PYTHON, auto_indent=True, auto_close=True, use_tabs=False):
    source = source.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    lines = source.split("\n")
    actions = []
    stack, triple = [], None
    editor_has_ws = False  # does the editor currently have auto-inserted indent on this line?

    for i, raw in enumerate(lines):
        stripped = raw.lstrip(" \t")
        lead = raw[: len(raw) - len(stripped)].expandtabs(4)
        content = stripped.rstrip()
        indent = len(lead) if content else 0

        # --- start of line: fix up indentation ---
        if auto_indent and editor_has_ws:
            actions.append(("clear", None))
        if content:
            if use_tabs:
                actions += [("indent_tab", None)] * (indent // 4)
                actions += [("indent", None)] * (indent % 4)
            else:
                actions += [("indent", None)] * indent
            actions += [("char", c) for c in content]

        # --- end of line: bookkeeping + predict what the editor did ---
        code, new_triple, opened_triple = _scan(lang, lead + content, i, triple, stack)
        if auto_close:
            pending = sum(1 for _, ln in stack if ln == i) + (3 if opened_triple else 0)
            actions += [("fdel", None)] * pending
        in_string = bool(triple or new_triple)
        editor_has_ws = bool(content) and (
            indent > 0 or (not in_string and (lang.opens_block(code) or (code != "" and code[-1] in OPEN)))
        )
        triple = new_triple

        if i < len(lines) - 1:
            actions.append(("enter", None))
    return actions
