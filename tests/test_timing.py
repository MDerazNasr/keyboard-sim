"""Offline checks for the timing model and IAT features (no keys pressed).
Run: python3 tests/test_timing.py"""
import math, os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from analyze_timing import l_scale, preprocess, iats, session_features, simulated_times
from code_typing import plan
from timing import Profile, expand

# L-scale known values: pairwise 0.5*mean|xi-xj|
assert abs(l_scale([1, 2, 3]) - 2 / 3) < 1e-12
assert abs(l_scale([5, 5, 5, 5])) < 1e-12
assert abs(l_scale([0, 10]) - 5) < 1e-12
# preprocessing: drops zero gaps and >5 min gaps, then logs
assert preprocess(iats([0, 0.1, 0.1, 0.5, 400])) == [math.log(0.1), math.log(0.4)]

SRC = open(os.path.join(os.path.dirname(__file__), "..", "code_typing.py")).read()
acts = plan(SRC, auto_indent=False, auto_close=False)

def feats(profile, jitter=0.5, seed=1):
    return session_features(simulated_times(expand(acts, 80, jitter, 0, profile, random.Random(seed))))

flat, dev = feats(None), feats(Profile(), 0)
assert dev["l_scale"] > flat["l_scale"], (flat, dev)

# knobs do what they say
assert feats(Profile(burstiness=0.1), 0)["l_scale"] < feats(Profile(burstiness=0.9), 0)["l_scale"]
no_think = expand(acts, 80, 0, 0, Profile(think_chance=0), random.Random(1))
always = expand(acts, 80, 0, 0, Profile(think_chance=1, think_median=3, think_max=10), random.Random(1))
waits = lambda st: [d for k, _, d in st if k == "wait"]
assert len(waits(always)) > len(waits(no_think))
assert max(waits(always)) <= 10 + 1e-9                       # think_max respected
# revisions only retype what they delete: net characters typed are unchanged
def net(steps):
    out = []
    for k, a, _ in steps:
        if k == "char": out.append(a)
        elif k == "bs": out.pop()
    return "".join(out)
revised = expand(acts, 80, 0, 0, Profile(revise_rate=0.2), random.Random(3))
assert any(k == "bs" for k, _, _ in revised)
assert net(revised) == net(expand(acts, 80, 0, 0, None, random.Random(3)))
# flat timing is unchanged by the 'pause' hints
assert all(k != "wait" for k, _, _ in expand(acts, 80, 0.5, 0, None, random.Random(1)))
print("timing checks passed", {"flat_L": round(flat["l_scale"], 3), "dev_L": round(dev["l_scale"], 3)})
