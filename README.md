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
- **Indent with tabs** — types Tab for each 4 spaces of indentation.

Tips: click into an empty line at column 0 first; turn off autocomplete suggestions in your editor
(Enter would accept a suggestion); uncheck the boxes for plain editors that don't auto-indent/close.
Source indented with tabs is typed as 4-space indents. Trailing whitespace is dropped.

CLI: `python3 keyboard_sim.py --code Python -f script.py` (`--no-auto-indent`, `--no-auto-close`, `--tabs`).

More languages: add a `Language` entry to `LANGUAGES` in `code_typing.py`.

Tests: `python3 tests/test_code_typing.py` (replays the plan against a *simulated* editor).
