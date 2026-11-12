#!/usr/bin/env python3
"""GUI for keyboard_sim: paste text or code, hit Start, click where it should go."""
import os
import threading
import time
import tkinter as tk
from tkinter import ttk

from code_typing import LANGUAGES, FormatError, format_source, plan
from keyboard_sim import esc_pressed, run_actions, text_actions, write_log
from timing import Profile

CODE_HINT = (
    "Click into an empty line at column 0 first. Turn off your editor's autocomplete "
    "suggestions (Enter would accept a suggestion instead of adding a new line)."
)


class App:
    def __init__(self, root):
        self.root = root
        root.title("Keyboard Sim")
        root.geometry("640x700")
        root.attributes("-topmost", True)
        self.stop = {"flag": False}
        self.running = False

        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=(10, 0))

        # --- Text tab ---
        text_tab = ttk.Frame(self.tabs)
        self.tabs.add(text_tab, text="Text")
        ttk.Label(text_tab, text="Text to type:").pack(anchor="w", padx=6, pady=(6, 0))
        self.text = tk.Text(text_tab, wrap="word", height=14)
        self.text.pack(fill="both", expand=True, padx=6, pady=6)

        # --- Code tab ---
        code_tab = ttk.Frame(self.tabs)
        self.tabs.add(code_tab, text="Code")
        top = ttk.Frame(code_tab)
        top.pack(fill="x", padx=6, pady=(6, 0))
        ttk.Label(top, text="Language:").pack(side="left")
        self.lang = tk.StringVar(value="Python")
        ttk.Combobox(top, textvariable=self.lang, values=list(LANGUAGES), state="readonly",
                     width=12).pack(side="left", padx=6)
        self.auto_indent = tk.BooleanVar(value=True)
        self.auto_close = tk.BooleanVar(value=True)
        self.use_tabs = tk.BooleanVar(value=False)
        self.format = tk.BooleanVar(value=False)
        checks = ttk.Frame(code_tab)
        checks.pack(fill="x", padx=6)
        ttk.Checkbutton(checks, text="Editor auto-indents", variable=self.auto_indent).pack(side="left")
        ttk.Checkbutton(checks, text="Editor auto-closes brackets/quotes",
                        variable=self.auto_close).pack(side="left", padx=10)
        ttk.Checkbutton(checks, text="Indent with tabs", variable=self.use_tabs).pack(side="left")
        ttk.Checkbutton(code_tab, text="Format code before typing (black for Python)",
                        variable=self.format).pack(anchor="w", padx=6)
        # developer-style timing (Code tab only)
        dev = ttk.LabelFrame(code_tab, text="Developer timing")
        dev.pack(fill="x", padx=6, pady=(4, 0))
        self.dev_on = tk.BooleanVar(value=False)
        self.record = tk.BooleanVar(value=False)
        ttk.Checkbutton(dev, text="Emulate developer timing", variable=self.dev_on).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=4)
        ttk.Checkbutton(dev, text="Record timing log (CSV)", variable=self.record).grid(
            row=0, column=3, columnspan=2, sticky="w", padx=4)
        self.dev_vars = {}
        for i, (key, label, default, lo, hi, inc) in enumerate([
            ("burstiness", "Burstiness (0-1.5)", Profile.burstiness, 0, 1.5, 0.05),
            ("think_chance", "Think chance (0-1)", Profile.think_chance, 0, 1, 0.05),
            ("think_median", "Think median (s)", Profile.think_median, 0.2, 20, 0.5),
            ("think_max", "Think max (s)", Profile.think_max, 1, 120, 5),
            ("revise_rate", "Revise rate (0-0.2)", Profile.revise_rate, 0, 0.2, 0.01),
        ]):
            var = tk.DoubleVar(value=default)
            self.dev_vars[key] = var
            ttk.Label(dev, text=label).grid(row=1, column=i, sticky="w", padx=4)
            ttk.Spinbox(dev, from_=lo, to=hi, increment=inc, textvariable=var, width=7).grid(
                row=2, column=i, padx=4, pady=(0, 4))
        ttk.Label(code_tab, text=CODE_HINT, wraplength=560, foreground="gray").pack(anchor="w", padx=6, pady=2)
        self.code = tk.Text(code_tab, wrap="none", height=14, font=("Menlo", 12), undo=True)
        self.code.pack(fill="both", expand=True, padx=6, pady=6)

        # --- shared options ---
        opts = ttk.Frame(root)
        opts.pack(fill="x", padx=10, pady=(6, 0))
        self.delay = tk.DoubleVar(value=5)
        self.wpm = tk.DoubleVar(value=80)
        self.typos = tk.DoubleVar(value=0)
        for i, (label, var, lo, hi, inc) in enumerate([
            ("Countdown (s)", self.delay, 0, 60, 1),
            ("Speed (WPM)", self.wpm, 10, 600, 5),
            ("Typo rate (0-0.1)", self.typos, 0, 0.1, 0.01),
        ]):
            ttk.Label(opts, text=label).grid(row=0, column=i, sticky="w", padx=4)
            ttk.Spinbox(opts, from_=lo, to=hi, increment=inc, textvariable=var, width=8).grid(
                row=1, column=i, padx=4, pady=(0, 6))

        btns = ttk.Frame(root)
        btns.pack(fill="x", padx=10, pady=5)
        self.start_btn = ttk.Button(btns, text="Start", command=self.start)
        self.start_btn.pack(side="left")
        ttk.Button(btns, text="Stop (Esc)", command=self.abort).pack(side="left", padx=6)
        self.status = tk.StringVar(value="Paste text or code, press Start, then click where it should go.")
        ttk.Label(root, textvariable=self.status, wraplength=570).pack(anchor="w", padx=10, pady=(0, 10))

        self.poll_esc()
        root.protocol("WM_DELETE_WINDOW", self.close)

    def poll_esc(self):
        if self.running and esc_pressed():
            self.abort()
        self.root.after(50, self.poll_esc)

    def abort(self):
        self.stop["flag"] = True

    def close(self):
        self.stop["flag"] = True
        self.root.destroy()

    def set_status(self, msg):
        self.root.after(0, self.status.set, msg)

    def start(self):
        if self.running:
            return
        in_code = self.tabs.index(self.tabs.select()) == 1
        profile, record = None, False
        source = (self.code if in_code else self.text).get("1.0", "end-1c")
        if not source.strip():
            self.status.set("Nothing to type.")
            return
        try:
            delay, wpm, typos = self.delay.get(), self.wpm.get(), self.typos.get()
        except tk.TclError:
            self.status.set("Check the number fields.")
            return
        if in_code:
            lang = LANGUAGES[self.lang.get()]
            if self.format.get():
                try:
                    source = format_source(source, lang)
                except FormatError as e:
                    self.status.set(str(e))
                    return
            actions = plan(source, lang, self.auto_indent.get(),
                           self.auto_close.get(), self.use_tabs.get())
            if self.dev_on.get():
                try:
                    profile = Profile(**{k: v.get() for k, v in self.dev_vars.items()})
                except tk.TclError:
                    self.status.set("Check the developer timing fields.")
                    return
            record = self.record.get()
        else:
            actions = text_actions(source)
        self.running = True
        self.stop["flag"] = False
        self.start_btn.state(["disabled"])
        threading.Thread(target=self.run, args=(actions, delay, wpm, typos, profile, record), daemon=True).start()

    def run(self, actions, delay, wpm, typos, profile, record):
        for i in range(int(delay), 0, -1):
            if self.stop["flag"]:
                break
            self.set_status(f"Typing in {i}… click where it should go (Esc aborts)")
            time.sleep(1)
        if not self.stop["flag"]:
            self.set_status("Typing…")
            log = [] if record else None
            run_actions(actions, max(wpm, 1), 0.5, typos, self.stop, profile, log)
        msg = "Stopped." if self.stop["flag"] else "Done."
        if record and log:
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs",
                                time.strftime("session-%Y%m%d-%H%M%S.csv"))
            write_log(log, path)
            msg += f" Timing log: {path}"
        self.set_status(msg)
        self.running = False
        self.root.after(0, lambda: self.start_btn.state(["!disabled"]))


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
