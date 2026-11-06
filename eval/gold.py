"""Hand-labelled evaluation. gold = list of (owner_first_name | None, deadline ISO | None, keyword).
dev set  = transcripts used while building the rules.
held-out = transcripts written afterwards and never used to tune the rules."""
import datetime as dt
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from meetlens.engine import MeetLens

SETS = {
 "dev": {
  os.path.join(ROOT, "samples", "sprint_planning.txt"): [
    ("Rahul", "2026-10-23", "two-column"), ("Karthik", "2026-10-26", "test cases"), (None, None, "database hosting"),
    ("Ananya", None, "demo slides"), ("Rahul", None, "review"), (None, None, "feedback"), ("Ananya", "2026-10-21", "wireframes"),
    (None, None, "staging"), ("Rahul", None, "api keys"), ("Karthik", None, "readme")],
  os.path.join(ROOT, "samples", "club_event.txt"): [
    ("Aditya", "2026-10-15", "projector"), ("Vikram", "2026-10-15", "posters"), (None, None, "sponsors"),
    ("Sana", "2026-10-20", "three companies"), ("Vikram", "2026-10-14", "registration"), ("Aditya", None, "last year")],
  os.path.join(ROOT, "samples", "clean_standup.txt"): [
    ("Isha", "2026-10-23", "deployment guide"), ("Neel", "2026-10-28", "user table"), ("Dev", "2026-10-29", "migration scripts")],
 },
 "unseen": {
  os.path.join(HERE, "unseen_3.txt"): [
    ("Lakshmi", "2026-10-15", "feedback forms"), ("Gaurav", None, "help"), ("Gaurav", "2026-10-09", "pick up"),
    ("Imran", "2026-10-12", "hygiene"), ("Imran", "2026-10-12", "notice")],
 },
 "held-out": {
  os.path.join(HERE, "heldout_1.txt"): [
    ("Arjun", "2026-10-20", "labelling"), ("Divya", "2026-10-18", "label"), ("Tanvi", "2026-10-15", "literature review"),
    ("Tanvi", "2026-10-13", "gpu"), ("Tanvi", None, "metrics")],
  os.path.join(HERE, "heldout_2.txt"): [
    ("Kavya", "2026-10-21", "integrate"), ("Rohit", "2026-10-19", "copy"), ("Rohit", "2026-10-16", "analytics"),
    ("Sameer", "2026-10-16", "teaser"), ("Kavya", None, "payment gateway")],
 },
}


def first(n):
    return n.split()[0] if n else None


def match(a, g):
    own, dl, kw = g
    d = (a.get("deadline") or {}).get("date")
    return kw in a["task"].lower() and first(a.get("owner")) == own and (d == dl or (dl is None and d is None))


def score(path, gold):
    with open(path, encoding="utf-8") as f:
        r = MeetLens().analyze(f.read())
    acts = r["actions"]
    kw_hit = sum(1 for g in gold if any(g[2] in a["task"].lower() for a in acts))
    full_hit = sum(1 for g in gold if any(match(a, g) for a in acts))
    prec_hit = sum(1 for a in acts if any(g[2] in a["task"].lower() for g in gold))
    return len(gold), len(acts), kw_hit, full_hit, prec_hit, r


if __name__ == "__main__":
    verbose = "-v" in sys.argv
    for name, files in SETS.items():
        G = E = K = F = P = 0
        for path, gold in files.items():
            g, e, k, f, p, r = score(path, gold)
            G += g; E += e; K += k; F += f; P += p
            if verbose:
                print(f"\n[{name}] {os.path.basename(path)}: gold={g} extracted={e} found={k} fully-correct={f}")
                for a in r["actions"]:
                    print("   ", a["id"], a["task"], "|", a.get("owner") or a.get("owner_label") or a.get("pronoun"), "|", (a.get("deadline") or {}).get("date") or (a.get("deadline") or {}).get("raw"))
        print(f"{name:9s} gold={G:2d} extracted={E:2d} | detection recall={K/G:.0%} precision={P/E:.0%} | owner+deadline correct={F/G:.0%}")
