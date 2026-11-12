#!/usr/bin/env python3
"""Inter-arrival-time (IAT) features for typing sessions.

  python3 analyze_timing.py session.csv            # CSV from `keyboard_sim.py --log` (first column = seconds)
  python3 analyze_timing.py --simulate code.py     # offline: compare flat vs developer timing, no keys pressed

Pipeline: IAT_i = t_i - t_{i-1}; drop gaps > 5 min and zero gaps; x_i = log(IAT_i);
feature = L-scale (lambda_2) of x.
"""
import argparse
import csv
import math
import random
import statistics

from code_typing import LANGUAGES, plan
from timing import Profile, expand

KEY_OVERHEAD = 0.004  # seconds of real time spent posting one keystroke


def iats(times):
    return [b - a for a, b in zip(times, times[1:])]


def preprocess(gaps, max_gap=300.0):
    return [math.log(g) for g in gaps if 0 < g <= max_gap]


def l_scale(x):
    """Sample L-scale lambda_2 = sum_i (2i - n - 1) x_(i) / (n (n-1)), i 1-based on sorted x."""
    n = len(x)
    if n < 2:
        raise ValueError("need at least 2 values")
    xs = sorted(x)
    return sum((2 * i - n - 1) * v for i, v in enumerate(xs, 1)) / (n * (n - 1))


def session_features(times):
    x = preprocess(iats(times))
    return {"events": len(times), "iats_used": len(x),
            "median_iat_s": math.exp(statistics.median(x)) if x else float("nan"),
            "log_iat_sd": statistics.pstdev(x) if len(x) > 1 else float("nan"),
            "l_scale": l_scale(x) if len(x) > 1 else float("nan")}


def simulated_times(steps):
    """Cumulative keystroke timestamps from expand() output (no keys pressed)."""
    t, times = 0.0, []
    for kind, _, d in steps:
        if kind not in ("wait", "pause"):
            times.append(t)
            t += KEY_OVERHEAD
        t += d
    return times


def _show(label, f):
    print(f"{label:<12} events={f['events']:<6} used={f['iats_used']:<6} "
          f"median_iat={f['median_iat_s']:.3f}s  sd(log)={f['log_iat_sd']:.3f}  L-scale={f['l_scale']:.3f}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("csv", nargs="?", help="timing log CSV")
    p.add_argument("--simulate", metavar="CODE_FILE", help="simulate flat vs developer timing for this source file")
    p.add_argument("--wpm", type=float, default=80)
    p.add_argument("--seed", type=int, default=0)
    a = p.parse_args()
    if a.simulate:
        src = open(a.simulate, encoding="utf-8").read()
        acts = plan(src, LANGUAGES["Python"], auto_indent=False, auto_close=False)
        _show("flat", session_features(simulated_times(expand(acts, a.wpm, 0.5, 0, None, random.Random(a.seed)))))
        _show("developer", session_features(simulated_times(expand(acts, a.wpm, 0, 0, Profile(), random.Random(a.seed)))))
    elif a.csv:
        with open(a.csv) as f:
            times = [float(r[0]) for r in list(csv.reader(f))[1:]]
        _show(a.csv, session_features(times))
    else:
        p.error("give a CSV or --simulate FILE")


if __name__ == "__main__":
    main()
