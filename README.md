# keyboard-sim

Types text you give it into whatever window/cursor has focus, like real keystrokes (macOS).

```
pip3 install -r requirements.txt
python3 keyboard_sim.py -f sample.txt          # or -t "text", or pipe via stdin
python3 keyboard_sim.py -f sample.txt --delay 5 --wpm 70 --typos 0.02
```

GUI: `.venv/bin/python gui.py` — paste text, press Start, click the target spot.

Run it, then click where you want the text. After the countdown it types. Press Esc to abort.

**macOS permissions:** grant your terminal app Accessibility *and* Input Monitoring
(System Settings → Privacy & Security), then restart the terminal.

## Code mode (Python)

The GUI has a **Code** tab. Code editors auto-indent new lines and auto-close brackets/quotes, so
typing code verbatim produces doubled indentation and stray `)`. Code mode compensates:

- **Editor auto-indents** — after each Enter it clears the indentation the editor inserted
  (Cmd+Delete) and types the exact indentation from your source.
- **Editor auto-closes brackets/quotes** — if a line ends with brackets (or a `"""`) still open,
  it forward-deletes the editor's auto-inserted closers before pressing Enter.
- **Format code before typing** — runs the code through `black` (Python) first. Fixes messy style
  (spacing, line wrapping, odd indent widths), but the code must be valid Python; if it isn't, you get
  an error and nothing is typed. It can't restore indentation that was lost entirely.
- **Indent with tabs** — types Tab for each 4 spaces of indentation.

Tips: click into an empty line at column 0 first; turn off autocomplete suggestions in your editor
(Enter would accept a suggestion); uncheck the boxes for plain editors that don't auto-indent/close.
Source indented with tabs is typed as 4-space indents. Trailing whitespace is dropped.

CLI: `python3 keyboard_sim.py --code Python -f script.py` (`--no-auto-indent`, `--no-auto-close`, `--tabs`, `--format`).

More languages: add a `Language` entry to `LANGUAGES` in `code_typing.py`.

Tests: `python3 tests/test_code_typing.py` (replays the plan against a *simulated* editor).

## Developer timing (Code tab) — for generating/evaluating test sessions

Tick **Emulate developer timing** on the Code tab. Settings (editable like speed/countdown):

| Setting | Meaning |
|---|---|
| Burstiness (0–1.5) | spread of keystroke speed; typing also runs in fast/slow bursts |
| Think chance (0–1) | chance of a thinking pause at a line end (more likely after `:` blocks and blank lines) |
| Preset | starting points (Typical is the default); not fitted to data |
| Think median (s) / max (s) | typical / longest pause (lognormal) |
| Revise rate (0–0.2) | chance per identifier of backspace-and-retype |

**Record timing log** saves a keystroke CSV to `logs/`. CLI: `--code Python --dev-timing --log out.csv`
(plus `--burstiness`, `--think-chance`, `--think-median`, `--think-max`, `--revise-rate`).

`analyze_timing.py` computes log-IAT features (drops >5 min and zero gaps, log transform, L-scale λ₂):
`python3 analyze_timing.py out.csv`, or `--simulate code.py` to compare flat vs developer timing offline.
The timing model is my own heuristic; it has not been validated against any particular detector.
Tests: `python3 tests/test_timing.py`.

### How indentation is handled
With **Editor auto-indents** on, every line starts by wiping whatever the editor inserted (types a
sentinel space, Cmd+Shift+Left to select back to the line start, Backspace to delete the selection),
then types the exact indentation from the source. It doesn't guess what the editor did, so it works
whether the editor indents, dedents (after `return`/`pass`), keeps indent on blank lines, or uses a
different indent width. It never uses Cmd+Delete (that deletes the whole line in JetBrains IDEs).
