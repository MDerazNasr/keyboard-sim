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
