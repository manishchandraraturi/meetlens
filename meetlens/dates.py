"""Deadline / date understanding for meeting transcripts.

Resolves phrases such as "by Friday", "next Tuesday", "in 2 weeks",
"25th October", "EOD" into concrete dates relative to the meeting date,
and recognises vague phrases ("soon", "ASAP") that need clarification.
"""
import re
import datetime as dt
from calendar import monthrange

WEEKDAYS = {
    "monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "tues": 1, "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3, "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5, "sunday": 6, "sun": 6,
}
MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3, "april": 4, "apr": 4,
    "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7, "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9, "october": 10, "oct": 10, "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}
NUMWORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}

_PRE = r"(?:(?:by|before|on|until|till|due|from|no\s+later\s+than|within|in)\s+)?(?:the\s+)?"
_WD = "|".join(sorted(WEEKDAYS, key=len, reverse=True))
_MO = "|".join(sorted(MONTHS, key=len, reverse=True))

VAGUE_RE = re.compile(
    r"\b(?:as\s+soon\s+as\s+possible|asap|soon|shortly|at\s+some\s+point|sometime|some\s+time|"
    r"eventually|later|whenever|in\s+due\s+course|down\s+the\s+line|"
    r"when\s+(?:you|we|i)\s+(?:get|have)\s+(?:a\s+)?(?:chance|time)|"
    r"in\s+the\s+near\s+future|at\s+the\s+earliest)\b", re.I)

PATTERNS = [
    ("iso", re.compile(_PRE + r"(\d{4})-(\d{2})-(\d{2})\b", re.I)),
    ("dmy", re.compile(_PRE + r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4}|\d{2})\b", re.I)),
    ("dm", re.compile(_PRE + r"\b(\d{1,2})[/.](\d{1,2})\b(?![/.\d])", re.I)),
    ("d_month", re.compile(_PRE + r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(" + _MO + r")\b(?:,?\s+(\d{4}))?", re.I)),
    ("month_d", re.compile(_PRE + r"\b(" + _MO + r")\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b(?:,?\s+(\d{4}))?", re.I)),
    ("ord", re.compile(r"\b(?:by|before|on|until|till|due)\s+(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)\b(?!\s+(?:of\s+)?(?:" + _MO + r"))", re.I)),
    ("in_n", re.compile(r"\b(?:within|in)\s+(\d+|a|an|one|two|three|four|five|six)\s+(day|week|month)s?\b", re.I)),
    ("eo", re.compile(_PRE + r"\b(?:the\s+)?(?:end\s+of\s+(?:the\s+)?(week|month)|eo(w|m))\b", re.I)),
    ("weekday", re.compile(_PRE + r"\b(?:(this|next|coming|upcoming)\s+)?(" + _WD + r")\b", re.I)),
    ("day_rel", re.compile(_PRE + r"\b(day\s+after\s+tomorrow|tomorrow|tonight|today|eod|end\s+of\s+(?:the\s+)?day|cob|close\s+of\s+business)\b", re.I)),
    ("week_rel", re.compile(_PRE + r"\b(next\s+week|this\s+week|next\s+month|this\s+month)\b", re.I)),
]


def _safe(y, m, d):
    try:
        return dt.date(y, m, d)
    except ValueError:
        return None


def _resolve(kind, m, ref):
    g = m.groups()
    if kind == "iso":
        return _safe(int(g[0]), int(g[1]), int(g[2])), "exact"
    if kind == "dmy":
        y = int(g[2])
        y += 2000 if y < 100 else 0
        return _safe(y, int(g[1]), int(g[0])), "exact"
    if kind == "dm":
        return _safe(ref.year, int(g[1]), int(g[0])), "exact"
    if kind in ("d_month", "month_d"):
        if kind == "d_month":
            day, mon, yr = int(g[0]), MONTHS[g[1].lower()], g[2]
        else:
            day, mon, yr = int(g[1]), MONTHS[g[0].lower()], g[2]
        y = int(yr) if yr else ref.year
        d = _safe(y, mon, day)
        if d and not yr and d < ref - dt.timedelta(days=180):
            d = _safe(y + 1, mon, day)
        return d, "exact"
    if kind == "ord":
        day = int(g[0])
        d = _safe(ref.year, ref.month, day)
        if d is None or d < ref:
            y, mo = ref.year + (ref.month == 12), ref.month % 12 + 1
            d = _safe(y, mo, day)
        return d, "exact"
    if kind == "in_n":
        n = NUMWORDS.get(g[0].lower()) or int(g[0])
        days = n * {"day": 1, "week": 7, "month": 30}[g[1].lower()]
        return ref + dt.timedelta(days=days), "relative"
    if kind == "eo":
        unit = (g[0] or ("week" if g[1] == "w" else "month")).lower()
        if unit == "week":
            return ref + dt.timedelta(days=(4 - ref.weekday()) % 7), "relative"
        return dt.date(ref.year, ref.month, monthrange(ref.year, ref.month)[1]), "relative"
    if kind == "weekday":
        mod, wd = (g[0] or "").lower(), WEEKDAYS[g[1].lower()]
        if mod == "next":
            monday_next = ref + dt.timedelta(days=7 - ref.weekday())
            return monday_next + dt.timedelta(days=wd), "relative"
        delta = (wd - ref.weekday()) % 7 or 7
        return ref + dt.timedelta(days=delta), "relative"
    if kind == "day_rel":
        w = re.sub(r"\s+", " ", g[0].lower())
        if w == "day after tomorrow":
            return ref + dt.timedelta(days=2), "relative"
        if w == "tomorrow":
            return ref + dt.timedelta(days=1), "relative"
        return ref, "relative"
    if kind == "week_rel":
        w = re.sub(r"\s+", " ", g[0].lower())
        if w == "next week":
            return ref + dt.timedelta(days=7 - ref.weekday() + 4), "approx"
        if w == "this week":
            return ref + dt.timedelta(days=max(4 - ref.weekday(), 0)), "approx"
        if w == "next month":
            y, mo = ref.year + (ref.month == 12), ref.month % 12 + 1
            return dt.date(y, mo, monthrange(y, mo)[1]), "approx"
        return dt.date(ref.year, ref.month, monthrange(ref.year, ref.month)[1]), "approx"
    return None, "none"


def find_deadline(text, ref):
    """Return dict(raw, date, kind, span) for the earliest deadline phrase in text, or None.
    kind: exact | relative | approx | vague"""
    best = None
    for kind, rx in PATTERNS:
        for m in rx.finditer(text):
            d, prec = _resolve(kind, m, ref)
            if d is None:
                continue
            cand = (m.start(), -(m.end() - m.start()),
                    dict(raw=m.group(0).strip(), date=d, kind=prec, span=(m.start(), m.end())))
            if best is None or cand[:2] < best[:2]:
                best = cand
            break
    v = VAGUE_RE.search(text)
    if v and (best is None or v.start() < best[0]):
        return dict(raw=v.group(0).strip(), date=None, kind="vague", span=(v.start(), v.end()))
    return best[2] if best else None


def parse_answer(text, ref):
    """Parse a user's typed answer to a deadline question; None if it is still not a real date."""
    d = find_deadline(text, ref)
    return d if d and d["date"] else None


def fmt(d):
    return d.strftime("%a, %d %b %Y") if d else ""
