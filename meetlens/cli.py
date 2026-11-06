"""Command line interface:  python -m meetlens <analyze|demo|serve> ..."""
import argparse
import datetime as dt
import json
import os
import sys

from .engine import MeetLens
from . import report

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _write(outdir, name, text):
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def interactive_clarify(engine, result):
    """Ask the user each open question in the terminal, then re-assess."""
    answers = {}
    for a in [x for x in result["actions"] if x["status"] == "needs_clarification"]:
        print(f"\n[{a['id']}] {a['task']}   (confidence {a['confidence']})")
        ans = {}
        for q in a["questions"]:
            if q["code"] == "REVISED":
                continue
            hint = f"  options: {', '.join(q['options'])}" if q.get("options") else ""
            sug = f"  suggestion: {q['suggested']}" if q.get("suggested") else ""
            val = input(f"  ? {q['question']}{hint}{sug}\n    > ").strip()
            if val:
                ans[q["fields"][0]] = val
        if ans:
            answers[a["id"]] = ans
    return engine.resolve(result, answers)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="meetlens", description="Meeting transcript -> summary, decisions, tasks, deadlines, follow-ups")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze", help="analyse a transcript file")
    a.add_argument("file")
    a.add_argument("--date", help="meeting date YYYY-MM-DD (default: Date: header, else today)")
    a.add_argument("--out", default="output", help="output folder")
    a.add_argument("--ask", action="store_true", help="answer clarification questions in the terminal")
    sub.add_parser("demo", help="run all bundled sample transcripts")
    s = sub.add_parser("serve", help="start the web interface")
    s.add_argument("--port", type=int, default=8000)
    args = ap.parse_args(argv)

    if args.cmd == "serve":
        from .server import serve
        return serve(args.port)

    files = [args.file] if args.cmd == "analyze" else sorted(os.path.join(ROOT, "samples", f) for f in os.listdir(os.path.join(ROOT, "samples")) if f.endswith(".txt"))
    out = getattr(args, "out", os.path.join(ROOT, "output"))
    for fp in files:
        eng = MeetLens()
        date = dt.date.fromisoformat(args.date) if getattr(args, "date", None) else None
        res = eng.analyze(open(fp, encoding="utf-8").read(), meeting_date=date)
        if getattr(args, "ask", False):
            res = interactive_clarify(eng, res)
        base = os.path.splitext(os.path.basename(fp))[0]
        md = report.to_markdown(res)
        for name, text in ((f"{base}.md", md), (f"{base}.html", report.to_html(res)), (f"{base}.csv", report.to_csv(res)), (f"{base}.json", report.to_json(res))):
            _write(out, name, text)
        h = res["health"]
        print(f"{base}: {h['total']} actions, {len(res['decisions'])} decisions, {h['completeness']}% complete, {len(res['clarifications'])} open questions -> {out}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
