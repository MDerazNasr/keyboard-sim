#!/usr/bin/env python3
"""GUI for keyboard_sim: paste text, hit Start, click where it should go."""
import threading
import time
import tkinter as tk
from tkinter import ttk

from keyboard_sim import esc_pressed, type_text


class App:
    def __init__(self, root):
        self.root = root
        root.title("Keyboard Sim")
        root.geometry("560x520")
        root.attributes("-topmost", True)
        self.stop = {"flag": False}
        self.running = False

        ttk.Label(root, text="Text to type:").pack(anchor="w", padx=10, pady=(10, 0))
        self.text = tk.Text(root, wrap="word", height=14)
        self.text.pack(fill="both", expand=True, padx=10, pady=5)

        opts = ttk.Frame(root)
        opts.pack(fill="x", padx=10)
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
        self.status = tk.StringVar(value="Paste text, press Start, then click where it should go.")
        ttk.Label(root, textvariable=self.status, wraplength=530).pack(anchor="w", padx=10, pady=(0, 10))

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
        text = self.text.get("1.0", "end-1c")
        if not text:
            self.status.set("Nothing to type.")
            return
        try:
            delay, wpm, typos = self.delay.get(), self.wpm.get(), self.typos.get()
        except tk.TclError:
            self.status.set("Check the number fields.")
            return
        self.running = True
        self.stop["flag"] = False
        self.start_btn.state(["disabled"])
        threading.Thread(target=self.run, args=(text, delay, wpm, typos), daemon=True).start()

    def run(self, text, delay, wpm, typos):
        for i in range(int(delay), 0, -1):
            if self.stop["flag"]:
                break
            self.set_status(f"Typing in {i}… click where the text should go (Esc aborts)")
            time.sleep(1)
        if not self.stop["flag"]:
            self.set_status("Typing…")
            type_text(text, max(wpm, 1), 0.5, typos, self.stop)
        self.set_status("Stopped." if self.stop["flag"] else "Done.")
        self.running = False
        self.root.after(0, lambda: self.start_btn.state(["!disabled"]))


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
