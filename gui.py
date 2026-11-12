#!/usr/bin/env python3
"""GUI for keyboard_sim: paste text or code, hit Start, click where it should go."""
import threading
import time
import tkinter as tk
from tkinter import ttk

from code_typing import LANGUAGES, plan
from keyboard_sim import esc_pressed, run_actions, text_actions

CODE_HINT = (
    "Click into an empty line at column 0 first. Turn off your editor's autocomplete "
    "suggestions (Enter would accept a suggestion instead of adding a new line)."
)


class App:
    def __init__(self, root):
        self.root = root
        root.title("Keyboard Sim")
        root.geometry("600x600")
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
        checks = ttk.Frame(code_tab)
        checks.pack(fill="x", padx=6)
        ttk.Checkbutton(checks, text="Editor auto-indents", variable=self.auto_indent).pack(side="left")
        ttk.Checkbutton(checks, text="Editor auto-closes brackets/quotes",
                        variable=self.auto_close).pack(side="left", padx=10)
        ttk.Checkbutton(checks, text="Indent with tabs", variable=self.use_tabs).pack(side="left")
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
            actions = plan(source, LANGUAGES[self.lang.get()], self.auto_indent.get(),
                           self.auto_close.get(), self.use_tabs.get())
        else:
            actions = text_actions(source)
        self.running = True
        self.stop["flag"] = False
        self.start_btn.state(["disabled"])
        threading.Thread(target=self.run, args=(actions, delay, wpm, typos), daemon=True).start()

    def run(self, actions, delay, wpm, typos):
        for i in range(int(delay), 0, -1):
            if self.stop["flag"]:
                break
            self.set_status(f"Typing in {i}… click where it should go (Esc aborts)")
            time.sleep(1)
        if not self.stop["flag"]:
            self.set_status("Typing…")
            run_actions(actions, max(wpm, 1), 0.5, typos, self.stop)
        self.set_status("Stopped." if self.stop["flag"] else "Done.")
        self.running = False
        self.root.after(0, lambda: self.start_btn.state(["!disabled"]))


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
