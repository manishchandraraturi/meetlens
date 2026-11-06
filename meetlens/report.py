"""Exporters: Markdown minutes, self-contained HTML report, CSV task list."""
import csv
import io
import json
import datetime as dt
from html import escape

from .dates import fmt


def _d(a):
    d = a.get("deadline")
    if not d:
        return "-"
    if d.get("date"):
        return fmt(dt.date.fromisoformat(d["date"]))
    return f"{d['raw']} (vague)"


def _who(a):
    return a.get("owner") or (f"? ({a['pronoun']})" if a.get("pronoun") else "? Unassigned")


def live(result):
    return [a for a in result["actions"] if a["status"] != "dropped"]


def to_json(result):
    return json.dumps(result, indent=2, ensure_ascii=False)


def to_csv(result):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["ID", "Task", "Owner", "Deadline", "Priority", "Status", "Confidence", "Depends on", "Open questions"])
    for a in live(result):
        w.writerow([a["id"], a["task"], a.get("owner") or "", _d(a) if a.get("deadline") else "", a["priority"],
                    a["status"], a["confidence"], a.get("dependency") or "", " | ".join(q["question"] for q in a["questions"])])
    return buf.getvalue()


def to_markdown(result):
    m, h = result["meta"], result["health"]
    L = [f"# Meeting Minutes: {m['title']}", "",
         f"**Date:** {m['date']}  ", f"**Participants:** {', '.join(m['participants'])}  ",
         f"**Length:** {m['turns']} turns, {m['words']} words" + (f", about {m['duration_min']} min" if m.get("duration_min") else ""), "",
         "## Summary", ""]
    L += [f"- {x}" for x in result["summary"]["overview"]] or ["- (no summary)"]
    if result["summary"]["topics"]:
        L += ["", "**Topics:** " + ", ".join(result["summary"]["topics"])]
    L += ["", "## Decisions", ""]
    if result["decisions"]:
        for d in result["decisions"]:
            extra = f" (because {d['rationale']})" if d.get("rationale") else ""
            conf = f" - confirmed by {d['confirmed_by']}" if d.get("confirmed_by") else ""
            L.append(f"{d['id']}. {d['text']}{extra}{conf}")
    else:
        L.append("None recorded.")
    L += ["", "## Action items", "", "| ID | Task | Owner | Deadline | Priority | Status |", "|---|---|---|---|---|---|"]
    for a in live(result):
        st = "Ready" if a["status"] == "ready" else "Needs clarification"
        L.append(f"| {a['id']} | {a['task']} | {_who(a)} | {_d(a)} | {a['priority']} | {st} |")
    L += ["", f"**Completeness:** {h['completeness']}% of action items are fully specified "
              f"({h['ready']}/{h['total']}); average confidence {h['avg_confidence']}.", ""]
    notes = [(a, n) for a in live(result) for n in a.get("revision_notes", [])]
    if notes:
        L += ["## Revisions during the meeting", ""] + [f"- {a['id']} ({a['task']}): {n}" for a, n in notes] + [""]
    L += ["## Clarifications needed", ""]
    L += [f"- [{q['action_id']}] {q['question']}" for q in result["clarifications"]] or ["None. All items are complete."]
    L += ["", "## Follow-ups", ""]
    fu = result["follow_ups"]
    labels = dict(next_meeting="Next meeting", open_issue="Open issue", unanswered_question="Unanswered question", dependency="Dependency")
    L += [f"- **{labels.get(f['type'], f['type'])}:** {f['text']}" + (f" ({f['date']})" if f.get("date") else "") for f in fu] or ["None."]
    return "\n".join(L) + "\n"


CSS = """
:root{--bg:#fafaf7;--card:#fff;--ink:#1c1f24;--mut:#667;--line:#e4e4de;--acc:#1f5eff;--ok:#12805c;--warn:#b45309;--bad:#b42318}
@media(prefers-color-scheme:dark){:root{--bg:#14161a;--card:#1d2026;--ink:#ecedee;--mut:#9aa0a6;--line:#2c3038;--acc:#6b9bff;--ok:#4cc79a;--warn:#f0a548;--bad:#ff8a80}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
.w{max-width:980px;margin:0 auto;padding:28px 18px 60px}h1{font-size:24px;margin:0 0 4px}h2{font-size:15px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);margin:30px 0 10px}
.sub{color:var(--mut)}.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:8px 0}
.kpi{display:flex;gap:10px;flex-wrap:wrap;margin:16px 0}.kpi div{flex:1;min-width:130px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 14px}
.kpi b{display:block;font-size:22px}.tw{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px;background:var(--card);border:1px solid var(--line);border-radius:12px}
th,td{padding:9px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}th{color:var(--mut);font-weight:600;font-size:12px;text-transform:uppercase}
.pill{display:inline-block;padding:1px 9px;border-radius:99px;font-size:12px;border:1px solid var(--line)}.ready{color:var(--ok)}.needs_clarification{color:var(--warn)}
.High{color:var(--bad)}.bar{height:6px;background:var(--line);border-radius:9px;overflow:hidden;width:70px;display:inline-block;vertical-align:middle}.bar i{display:block;height:100%;background:var(--acc)}
ul{padding-left:20px}li{margin:3px 0}
"""


def to_html(result):
    m, h = result["meta"], result["health"]
    e = escape
    rows = ""
    for a in live(result):
        flags = " ".join(f'<span class="pill">{e(f.replace("_", " ").title())}</span>' for f in a["flags"])
        extra = f'<div class="sub">Depends on: {e(a["dependency"])}</div>' if a.get("dependency") else ""
        rows += (f'<tr><td>{e(a["id"])}</td><td>{e(a["task"])}{extra}<div>{flags}</div></td><td>{e(_who(a))}</td><td>{e(_d(a))}</td>'
                 f'<td class="{a["priority"]}">{a["priority"]}</td><td class="{a["status"]}">{"Ready" if a["status"] == "ready" else "Needs clarification"}</td>'
                 f'<td><span class="bar"><i style="width:{int(a["confidence"] * 100)}%"></i></span> {a["confidence"]}</td></tr>')
    dec = "".join(f'<div class="card"><b>{e(d["id"])}.</b> {e(d["text"])}'
                  + (f'<div class="sub">Because {e(d["rationale"])}</div>' if d.get("rationale") else "")
                  + (f'<div class="sub">Confirmed by {e(d["confirmed_by"])}</div>' if d.get("confirmed_by") else "") + "</div>"
                  for d in result["decisions"]) or '<div class="sub">None recorded.</div>'
    qs = "".join(f'<li><b>{e(q["action_id"])}</b> {e(q["question"])}</li>' for q in result["clarifications"]) or "<li>None. All items are complete.</li>"
    fu = "".join(f'<li><b>{e(f["type"].replace("_", " ").title())}:</b> {e(f["text"])}</li>' for f in result["follow_ups"]) or "<li>None.</li>"
    summ = "".join(f"<li>{e(x)}</li>" for x in result["summary"]["overview"])
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(m['title'])} - MeetLens report</title><style>{CSS}</style></head><body><div class="w">
<h1>{e(m['title'])}</h1><div class="sub">{e(m['date'])} &middot; {e(', '.join(m['participants']))}</div>
<div class="kpi"><div><b>{h['total']}</b>action items</div><div><b>{len(result['decisions'])}</b>decisions</div>
<div><b>{h['completeness']}%</b>fully specified</div><div><b>{len(result['clarifications'])}</b>open questions</div></div>
<h2>Summary</h2><ul>{summ}</ul>
<h2>Decisions</h2>{dec}
<h2>Action items</h2><div class="tw"><table><tr><th>ID</th><th>Task</th><th>Owner</th><th>Deadline</th><th>Priority</th><th>Status</th><th>Confidence</th></tr>{rows}</table></div>
<h2>Clarifications needed</h2><ul>{qs}</ul>
<h2>Follow-ups</h2><ul>{fu}</ul>
<p class="sub">Generated by MeetLens.</p></div></body></html>"""
