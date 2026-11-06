"""MeetLens core engine.

Pipeline:  transcript -> turns -> sentences -> classify (decision / action / open issue /
follow-up) -> normalise (owner, task, deadline, priority, dependency) -> merge revisions ->
ambiguity assessment -> clarification questions -> structured result.

Pure Python standard library. Deterministic, so every output can be explained and tested.
"""
import re
import datetime as dt
from collections import Counter

from .dates import find_deadline, parse_answer, fmt

# --------------------------------------------------------------------------- lexicons
STOP = set("""a an the and or but if of to in on at for with from by as is are was were be been being it its this that these
those i you he she they we me him her them us my your his their our so then than too very just also not no do does did
have has had will would can could should may might must shall about into over after before there here what which who
whom how when where why all any some each more most other such only own same up out off again further once ok okay yeah
yes right well like going get got let lets one need want sure three two four today tomorrow week next still""".split())

VERBS = set("""send prepare draft write review update fix build create make set organise organize schedule book arrange
contact email mail call ping message follow share upload submit finish complete finalise finalize check test run deploy
design implement develop research investigate collect gather compile analyse analyze compare evaluate present present
demo document record publish post print order buy purchase pay arrange confirm approve negotiate discuss plan list
prioritise prioritize estimate assign reassign add remove delete clean migrate refactor merge release launch announce
invite register reserve coordinate handle own lead take talk speak reach ask find look sort setup configure integrate
train label tag monitor track audit verify validate benchmark rewrite revise edit polish proofread translate summarise
summarize outline brainstorm sync meet ensure make look decide choose figure resolve raise escalate loop reschedule
postpone cancel kick draw sketch mock hold host conduct distribute circulate archive backup back push pull
open close file log report notify remind inform tell show walk install provision upgrade patch""".split())

NONVERB_START = set("""be not never you it that this there a an the some any no to really just still yes ok okay sure fine
good great know think see say mention honest clear sorry afraid hope guess wait""".split())
LETME_BAD = set("know think see explain finish say just go wait".split())
LETS_BAD = re.compile(r"^(?:start|begin|get started|go (?:through|over|ahead)|move on|hear|see|talk|wrap|kick off|dive|jump)\b", re.I)

FILLER_RE = re.compile(r"^(?:ok(?:ay)?|yes|yeah|yep|no|nope|sure|right|alright|thanks?(?: you)?|thank you|got it|cool|great|fine|"
                       r"hi|hello|hey|good (?:morning|afternoon|evening)|bye|goodbye|see you|noted|hmm+|uh+|um+|exactly|correct|"
                       r"agreed|perfect|sounds good|makes sense|understood|nice)[\s,.!]*(?:everyone|all|folks|team|guys)?[\s,.!]*$", re.I)

TENTATIVE_RE = re.compile(r"\b(?:maybe|might|perhaps|probably|possibly|if possible|if i can|if time permits|if we have time|hopefully|"
                          r"i guess|try to|try and|see if|not sure|i could|we could|ideally|if needed)\b", re.I)
PRIORITY_HI = re.compile(r"\b(?:urgent(?:ly)?|asap|critical|top priority|high priority|blocker|immediately|right away|at the earliest|p0|p1)\b", re.I)
PRIORITY_LO = re.compile(r"\b(?:low priority|nice to have|no rush|when you get a chance|when you have time|whenever you can|not urgent|p3)\b", re.I)
DEPEND_RE = re.compile(r"\b(?:once|as soon as|assuming|depending on|depends on|blocked by|waiting (?:for|on)|until)\s+([^,.;?!]+)", re.I)
IF_RE = re.compile(r"^\s*(?:only\s+)?if\s+([^,]+),", re.I)

DECISION_RE = re.compile(
    r"\b(?:we(?:'ve| have)?\s+decided|(?:the\s+)?decision\s+(?:is|was)|let'?s\s+go\s+with|we'?ll\s+go\s+with|we(?:'re| are)\s+going\s+(?:with|to\s+go\s+with)|"
    r"we(?:'ll| will)\s+(?:use|adopt|stick\s+with|keep|switch\s+to|move\s+to|postpone|push|extend|cancel|skip|drop)|"
    r"we\s+agree[d]?|it'?s\s+(?:been\s+)?(?:decided|settled|approved)|that'?s\s+settled|final\s+(?:decision|call)|consensus\s+is|"
    r"(?:is|was|been)\s+approved|let'?s\s+(?:stick\s+with|keep|drop|skip|postpone|cancel|switch\s+to|move\s+to|push)|"
    r"we(?:'re| are)\s+(?:dropping|skipping|postponing|cancelling|canceling|switching|moving|keeping))\b", re.I)
DECISION_MARK = re.compile(r"^\s*(?:decision|decided|resolved|agreed)\s*[:\-]\s*(.+)$", re.I)
PROPOSAL_RE = re.compile(r"\b(?:let'?s|we should|how about|what if we|i suggest|i propose|we could|why don'?t we|shall we|should we|i'd suggest|my suggestion)\b", re.I)
DECISION_VERBS = re.compile(r"\b(?:go with|move|switch|use|adopt|postpone|push|extend|cancel|launch|choose|pick|change|drop|skip|keep|stick|shift|reduce|increase|"
                            r"freeze|approve|replace|prioriti[sz]e|limit|cap|split|merge|rename|reschedule)\b", re.I)
AFFIRM_RE = re.compile(r"^\s*(?:yes|yeah|yep|sure|agreed?|okay|ok|fine|sounds good|works for me|that works|perfect|approved|"
                       r"let'?s do (?:that|it)|go for it|makes sense|i'?m fine with (?:that|it)|fine by me|i second that|done deal)\b[^?]*$", re.I)
OPEN_RE = re.compile(r"\b(?:open question|still (?:need to )?(?:figure|decide|work) out|to be decided|tbd|tbc|yet to be (?:decided|finalised|finalized|confirmed)|"
                     r"haven'?t (?:yet )?(?:decided|finali[sz]ed|confirmed)|parking lot|park (?:this|that|it)|table (?:this|that)|revisit|circle back|come back to|not (?:yet )?(?:decided|finali[sz]ed|clear)|"
                     r"unclear|we don'?t know|no idea (?:who|when|how|what|why)|undecided|pending (?:approval|decision|confirmation))\b", re.I)
UNSURE_RE = re.compile(r"\b(?:not sure|don'?t know|no idea|unsure|let me check|we'll see|haven'?t (?:decided|checked)|can'?t say|dunno|not certain|good question)\b", re.I)
NEXT_MEET_RE = re.compile(r"\b(?:next (?:meeting|sync|call|standup|review|catch[- ]?up)|(?:meet|sync|catch up|reconvene|regroup|touch base|talk) (?:again|next|on|by|at)|"
                          r"let'?s (?:meet|sync|regroup|reconvene))\b", re.I)

MARKER_RE = re.compile(r"^\s*(?:action(?:\s*items?)?|todo|to-do|task|a\.?i\.?)\s*[:\-]\s*(.+)$", re.I)
HEADER_KEYS = ("title", "meeting", "date", "agenda", "attendees", "participants", "project", "venue", "location", "time", "subject")
NONSPEAKER = ("action", "todo", "to-do", "task", "decision", "decided", "resolved", "agreed", "note", "notes", "summary", "next steps", "agenda", "ai")

VAGUE_TASK_RE = re.compile(r"^(?:(?:look|have a look|take a look)\s+(?:into|at)|handle|take care of|deal with|sort(?: out)?|check|do|work on|think about|"
                           r"see to|figure out|follow up|follow-up|explore|investigate|discuss|talk about)\s*(?:it|that|this|them|things?|stuff|the thing|everything|the same|"
                           r"the rest|more|something)?$", re.I)
GROUP_NOUNS = ("someone", "somebody", "anyone", "anybody", "everyone", "everybody", "the team", "team", "we all", "all of us")


def recs_turn(a):
    return a.get("turn")


def _norm(s):
    return (s.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
             .replace("\u2013", "-").replace("\u2014", "-"))


def _cap(s):
    s = s.strip(" ,;:-")
    return s[:1].upper() + s[1:] if s else s


def _tokens(s):
    out = []
    for w in re.findall(r"[a-z0-9']+", s.lower()):
        if w in STOP or len(w) < 3 or "'" in w:
            continue
        for suf in ("ing", "ed", "es", "s"):
            if w.endswith(suf) and len(w) - len(suf) >= 3:
                w = w[: -len(suf)]
                break
        out.append(w)
    return out


def _jaccard(a, b):
    a, b = set(a), set(b)
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return max(inter / len(a | b), inter / min(len(a), len(b)) if min(len(a), len(b)) >= 3 else 0)


# --------------------------------------------------------------------------- parsing
TURN_RE = re.compile(r"^\s*(?:[\[(]?(\d{1,2}:\d{2}(?::\d{2})?)[\])]?\s+)?([A-Za-z][\w.'-]*(?:\s[A-Za-z][\w.'-]*){0,2})\s*(?:[\[(](\d{1,2}:\d{2}(?::\d{2})?)[\])])?\s*:\s+(.*\S)\s*$")


def parse_transcript(text):
    """Return (meta, turns). Understands 'Name: text', optional [hh:mm] stamps, header lines, continuations."""
    meta, turns = {}, []
    for raw in _norm(text).splitlines():
        line = raw.strip()
        if not line:
            continue
        m = TURN_RE.match(line)
        if m:
            spk = m.group(2).strip()
            low = spk.lower()
            if not turns and low in HEADER_KEYS:
                meta[low] = m.group(4).strip()
                continue
            if low in NONSPEAKER and turns:
                turns[-1]["text"] += " " + line
                continue
            turns.append(dict(idx=len(turns), speaker=spk, time=m.group(1) or m.group(3), text=m.group(4).strip()))
        elif turns:
            turns[-1]["text"] += " " + line
        else:
            meta.setdefault("preamble", "")
            meta["preamble"] += line + " "
    return meta, turns


_SPLIT_COMPOUND = re.compile(r"\s+(?:and|then|but)\s+(?=(?:I|we|he|she|they|[A-Z][a-z]+)(?:'ll|\s+(?:will|can|should|could|needs?\s+to|has\s+to|have\s+to|to)\b))")


_ABBR = re.compile(r"\b(Dr|Mr|Mrs|Ms|Prof|Sr|Jr|vs|etc|e\.g|i\.e)\.", re.I)


def split_sentences(text):
    text = _ABBR.sub(lambda m: m.group(1) + "\u2024", text)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"'\(\[])|;\s+", text)
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        out.extend(x.strip().replace("\u2024", ".") for x in _SPLIT_COMPOUND.split(p) if x.strip())
    return out


# --------------------------------------------------------------------------- engine
class MeetLens:
    def __init__(self, meeting_date=None):
        self.ref = meeting_date or dt.date.today()

    # ---------- public API
    def analyze(self, text, meeting_date=None, title=None):
        if meeting_date:
            self.ref = meeting_date
        meta, turns = parse_transcript(text)
        if "date" in meta and not meeting_date:
            d = find_deadline(meta["date"], self.ref)
            if d and d["date"]:
                self.ref = d["date"]
        participants = self._participants(meta, turns)
        self._build_name_re(participants)
        canon = {}
        for p in participants:
            for t in turns:
                if t["speaker"].split()[0].lower() == p.split()[0].lower():
                    canon[t["speaker"]] = p
        for t in turns:
            t["speaker"] = canon.get(t["speaker"], t["speaker"])
        recs = self._sentences(turns)
        decisions, actions, follow, opens = [], [], [], []
        used, last = set(), None
        confirmed = self._confirmed_proposals(recs)

        for i, r in enumerate(recs):
            s, spk = r["text"], r["speaker"]
            if FILLER_RE.match(s) or (len(s.split()) < 3 and not MARKER_RE.match(s)):
                continue
            dm = DECISION_MARK.match(s)
            if dm or DECISION_RE.search(s) or i in confirmed:
                decisions.append(self._decision(dm.group(1) if dm else s, r, confirmed.get(i)))
                used.add(i)
                continue
            act = self._action(s, spk, recs[i - 1] if i else None, r)
            if act and act["owner"] is None and (OPEN_RE.search(s) or NEXT_MEET_RE.search(s)):
                act = None
            if act:
                used.add(i)
                if self._absorb(act, last, i, recs):
                    last = (i, last[1])
                    continue
                self._coref(act, last, i, r)
                actions.append(act)
                last = (i, act)
                continue
            if NEXT_MEET_RE.search(s):
                d = find_deadline(s, self.ref)
                follow.append(dict(type="next_meeting", text=_cap(s.rstrip(".")), date=d["date"].isoformat() if d and d["date"] else None, turn=r["turn"]))
                used.add(i)
                continue
            if OPEN_RE.search(s):
                opens.append(dict(type="open_issue", text=_cap(s.rstrip(".")), turn=r["turn"], owner=None))
                used.add(i)
                continue
            if s.endswith("?") and i + 1 < len(recs) and recs[i + 1]["speaker"] != spk and UNSURE_RE.search(recs[i + 1]["text"]):
                opens.append(dict(type="unanswered_question", text=_cap(s), turn=r["turn"], owner=None))
                used.add(i)

        actions = self._merge_revisions(actions)
        decisions = self._merge_decisions(decisions)
        for n, a in enumerate(actions, 1):
            a["id"] = f"A{n}"
            self.assess(a, participants)
        for n, d in enumerate(decisions, 1):
            d["id"] = f"D{n}"
        follow = follow + opens + self._dependency_followups(actions)
        result = dict(
            meta=self._meta(meta, turns, participants, title),
            summary=self._summary(recs, used),
            decisions=decisions, actions=actions, follow_ups=follow,
        )
        result["stats"] = self._stats(turns, actions, participants)
        self._refresh(result)
        return result

    # ---------- replies that complete an earlier request / volunteer for an unowned task
    def _absorb(self, act, last, i, recs):
        if not last or last[0] != i - 1:
            return False
        prev, spk = last[1], recs[i]["speaker"]
        head = " ".join(act["task"].split()[:4])
        if (act["owner"] and act["said_by"] != act["owner"] and prev["owner"] is None
                and re.search(r"\b(?:it|that|this|them)\b", head, re.I)):
            # "Sana, can you take that?" right after an unowned task: assign the earlier task
            prev["owner"], prev["owner_label"], prev["pronoun"] = act["owner"], None, None
            prev["assigned_by"] = act["said_by"]
            if act.get("deadline"):
                prev["deadline"] = act["deadline"]
            prev["source"] += "  ->  " + act["source"]
            return True
        if act["said_by"] != spk or act["owner"] != spk or prev["said_by"] == spk:
            return False
        m = re.match(r"^\w+(?:\s+(?:at|into|on|after))?\s+(?:it|that|this|them|those|these)\b(?:\s+and\s+(.+))?", act["task"], re.I)
        related = _jaccard(_tokens(act["task"]), _tokens(prev["task"])) >= 0.5
        accepted = prev["owner"] == spk and (m or related)
        volunteer = prev["owner"] is None and (m or related)
        if not (accepted or volunteer):
            return False
        extra = m.group(1) if m and m.group(1) else None
        if extra:
            prev["task"] = prev["task"].rstrip(".") + " and " + extra
        if volunteer:
            prev["owner"], prev["owner_label"], prev["pronoun"] = spk, None, None
            prev["volunteered_by"] = spk
        else:
            prev["accepted_by"] = spk
        nd, od = act.get("deadline"), prev.get("deadline")
        if nd and nd.get("date") and od and od.get("date") and nd["date"] != od["date"]:
            prev.setdefault("revision_notes", []).append(
                f"Deadline changed from {fmt(dt.date.fromisoformat(od['date']))} to {fmt(dt.date.fromisoformat(nd['date']))}")
        if nd:
            prev["deadline"] = nd
        prev["tentative"] = bool(act["tentative"]) if volunteer else bool(prev["tentative"] or act["tentative"])
        prev["vague_task"] = False if m else prev["vague_task"]
        if act["priority"] == "High":
            prev["priority"] = "High"
        prev["source"] += "  ->  " + act["source"]
        return True

    def _coref(self, act, last, i, rec):
        """'Review them' right after 'Prepare the demo slides' -> 'Review the demo slides'."""
        if not last or last[0] != i - 1 or recs_turn(last[1]) != rec["turn"]:
            return
        m = re.match(r"^(\w+)\s+(?:it|them)\b(.*)$", act["task"], re.I)
        words = last[1]["task"].split()
        if m and len(words) > 2 and words[1].lower() not in ("out", "up", "to", "with", "on", "over", "through", "into", "for", "at", "in", "about"):
            act["task"] = _cap(m.group(1) + " " + " ".join(words[1:]) + m.group(2))
            act["vague_task"] = False

    def _merge_decisions(self, decs):
        out = []
        for d in decs:
            hit = None
            for e in out:
                if abs(e["turn"] - d["turn"]) <= 3:
                    shared = set(_tokens(e["text"])) & set(_tokens(d["text"]))
                    if any(re.search(r"\d", w) for w in shared) or len(shared) >= 2:
                        hit = e
                        break
            if not hit:
                out.append(d)
                continue
            if len(d["text"]) > len(hit["text"]) + 15:
                hit["text"] = d["text"]
            hit["rationale"] = hit["rationale"] or d["rationale"]
            hit["confirmed_by"] = hit["confirmed_by"] or d["confirmed_by"]
        return out

    def resolve(self, result, answers):
        """Apply user answers {action_id: {owner, deadline, task, confirm}} and re-assess."""
        parts = result["meta"]["participants"]
        ref = dt.date.fromisoformat(result["meta"]["date"])
        self.ref = ref
        for a in result["actions"]:
            ans = answers.get(a["id"])
            if not ans or a["status"] == "dropped":
                continue
            done = a.setdefault("resolved_fields", [])
            if ans.get("confirm", "").strip().lower() in ("no", "n", "drop", "false"):
                a["status"], a["flags"], a["questions"] = "dropped", [], []
                a["note"] = "Dropped after clarification (not a firm commitment)."
                continue
            if ans.get("confirm", "").strip().lower() in ("yes", "y", "true", "firm"):
                a["tentative"] = False
                done.append("confirm")
            if ans.get("owner", "").strip():
                a["owner"] = self._match_participant(ans["owner"].strip(), parts) or ans["owner"].strip().title()
                a["owner_label"], a["pronoun"] = None, None
                done.append("owner")
            if ans.get("task", "").strip():
                a["task"] = _cap(ans["task"].strip().rstrip("."))
                a["vague_task"] = False
                done.append("task")
            if ans.get("deadline", "").strip():
                d = parse_answer(ans["deadline"], ref)
                if d:
                    a["deadline"] = dict(raw=ans["deadline"].strip(), date=d["date"].isoformat(), kind="exact")
                    done.append("deadline")
                else:
                    a["answer_error"] = f"Could not read '{ans['deadline']}' as a date. Try '25 Oct' or 'next Friday'."
                    continue
            a.pop("answer_error", None)
            self.assess(a, parts)
        self._refresh(result)
        return result

    # ---------- participants / names
    def _participants(self, meta, turns):
        names = []
        for t in turns:
            if t["speaker"] not in names:
                names.append(t["speaker"])
        for key in ("attendees", "participants"):
            for n in re.split(r"[,;&]|\band\b", meta.get(key, "")):
                n = re.sub(r"\(.*?\)", "", n).strip()
                if not n or len(n.split()) > 3:
                    continue
                first = n.split()[0].lower()
                hit = next((x for x in names if x.split()[0].lower() == first), None)
                if hit and len(n.split()) > len(hit.split()):
                    names[names.index(hit)] = n
                elif not hit:
                    names.append(n)
        return names

    def _build_name_re(self, participants):
        alts = set()
        for p in participants:
            alts.add(p)
            alts.add(p.split()[0])
        self.participants = participants
        self.verb_alt = "|".join(sorted(VERBS, key=len, reverse=True))
        self.names = "|".join(re.escape(n) for n in sorted(alts, key=len, reverse=True)) or r"(?!)"

    @staticmethod
    def _match_participant(name, participants):
        n = name.lower().strip()
        for p in participants:
            if n == p.lower():
                return p
        for p in participants:
            if n == p.split()[0].lower():
                return p
        return None

    def _sentences(self, turns):
        recs = []
        for t in turns:
            for s in split_sentences(t["text"]):
                recs.append(dict(text=s, speaker=t["speaker"], turn=t["idx"], time=t["time"]))
        return recs

    # ---------- decisions
    def _confirmed_proposals(self, recs):
        out = {}
        for i, r in enumerate(recs):
            if not AFFIRM_RE.match(r["text"]) or len(r["text"].split()) > 9:
                continue
            for j in range(i - 1, max(i - 4, -1), -1):
                p = recs[j]
                if p["speaker"] != r["speaker"] and PROPOSAL_RE.search(p["text"]) and DECISION_VERBS.search(p["text"]) and j not in out:
                    out[j] = r["speaker"]
                    break
        return out

    def _decision(self, body, r, confirmed_by):
        txt = body.strip().rstrip(".?!")
        txt = re.sub(r"^(?:ok(?:ay)?|so|right|alright)[,\s]+", "", txt, flags=re.I)
        why = None
        m = re.search(r"\b(?:because|since|due to|as)\b\s+(.+)$", txt, re.I)
        if m and len(m.group(1).split()) >= 3:
            why, txt = m.group(1).strip(), txt[: m.start()].strip(" ,")
        txt = re.sub(r"^(?:how about|what if)\s+we\s+|^(?:i\s+(?:suggest|propose)|i'd suggest)\s+(?:that\s+)?(?:we\s+)?|^we\s+(?:should|could)\s+|^why don't we\s+|"
                     r"^(?:shall|should)\s+we\s+|^let's\s+|^we(?:'ve| have)?\s+decided\s+(?:to\s+)?|^the\s+decision\s+(?:is|was)\s+(?:to\s+)?|^we(?:'ll| will)\s+", "", txt, flags=re.I)
        return dict(text=_cap(txt), rationale=why, proposed_by=r["speaker"], confirmed_by=confirmed_by, turn=r["turn"])

    # ---------- actions
    def _action(self, s, speaker, prev_rec, rec):
        prev_speaker = prev_rec["speaker"] if prev_rec else None
        ctx = s + (" " + prev_rec["text"] if prev_rec and prev_rec["turn"] == rec["turn"] else "")
        owner = group = pronoun = suggested = None
        task = None
        strength = "explicit"
        m = MARKER_RE.match(s)
        body = m.group(1) if m else s
        marked = bool(m)
        body = re.sub(r"^(?:also|and|so|then|okay|ok|right|alright|well|actually)[,\s]+", "", body, flags=re.I)
        q = body.rstrip().endswith("?")
        names = self.names

        req = re.match(rf"^(?:(?:ok(?:ay)?|so|and|also|alright|right|then|well)[,\s]+)*(?:(?P<n>{names})[,\s]+)?"
                       r"(?:(?:can|could|would|will)\s+you(?:\s+please)?|please|you\s+(?:should|need\s+to|will|can)|you'll)\s+(?P<t>.+?)\??$", body, re.I)
        if req and req.group("t").split() and req.group("t").split()[0].lower() in NONVERB_START:
            req = None
        imper = re.match(rf"^(?:(?:ok(?:ay)?|so|and|also|alright|right|then|well|actually)[,\s]+)*(?P<n>{names}),?\s+(?P<t>(?:{self.verb_alt})\b.+?)\??$", body, re.I)
        first = re.search(r"\b(?:I'll\s+go\s+ahead\s+and|I'd\s+like\s+to\s+take|I'll|I\s+will|I'm\s+going\s+to|I\s+am\s+going\s+to|I\s+shall|let\s+me|I\s+can|I\s+could)\s+(?P<t>.+?)$", body, re.I)
        named = re.search(rf"\b(?P<o>{names})\s*(?:,\s*)?(?:will|'ll|to|should|needs?\s+to|has\s+to|must|can|could|is\s+going\s+to|is\s+to)\s+(?P<t>.+?)$", body)
        pron = re.search(r"\b(?P<o>he|she|they)\s+(?:will|'ll|should|needs?\s+to|has\s+to|must)\s+(?P<t>.+?)$", body, re.I)
        gnoun = re.search(r"\b(?P<g>" + "|".join(GROUP_NOUNS) + r")\s+(?:should|needs?\s+to|must|has\s+to|have\s+to|will|can|could|'ll)\s+(?P<t>.+?)$", body, re.I)
        we = re.search(r"\b(?:we)\s+(?:still\s+|also\s+|really\s+|all\s+)?(?:need\s+to|have\s+to|should|must|ought\s+to|gotta|will\s+need\s+to|'ll\s+need\s+to|want\s+to|will|'ll)\s+(?P<t>.+?)$", body, re.I)
        lets = re.search(r"\b(?:let's|let\s+us)\s+(?P<t>.+?)$", body, re.I)
        passive = re.match(r"^(?P<t>.+?\b(?:needs?\s+to|has\s+to|have\s+to|must|should)\s+be\s+\w+(?:ed|en|nt|one|ade|ent|ept)\b.*)$", body, re.I)

        if req:
            task = req.group("t")
            if req.group("n"):
                owner = self._match_participant(req.group("n"), self.participants)
            else:
                suggested = prev_speaker if prev_speaker and prev_speaker != speaker else None
                group = "Unassigned"
        elif imper and not q:
            task = imper.group("t")
            owner = self._match_participant(imper.group("n"), self.participants)
        elif first and not q:
            lead = first.group(0).lower()
            task = first.group("t")
            fw = task.split()[0].lower() if task.split() else ""
            if lead.startswith("let me") and fw in LETME_BAD:
                task = None
            elif fw in NONVERB_START and not re.match(r"be\s+(?:responsible|in charge)", task, re.I):
                task = None
            else:
                owner = speaker
                if lead.endswith("could") or lead.endswith("can"):
                    strength = "offer"
        if task is None and named and not q:
            t = named.group("t")
            fw = t.split()[0].lower() if t.split() else ""
            if fw not in NONVERB_START or re.match(r"be\s+(?:responsible|in charge)", t, re.I):
                task, owner = t, self._match_participant(named.group("o"), self.participants)
        if task is None and pron and not q:
            t = pron.group("t")
            if t.split() and t.split()[0].lower() not in NONVERB_START:
                task = t
                prior = re.findall(rf"\b({names})\b", body[: pron.start()])
                if prior:
                    owner = self._match_participant(prior[-1], self.participants)
                else:
                    pronoun = pron.group("o").lower()
        if task is None and gnoun and not q:
            t = gnoun.group("t")
            if t.split() and t.split()[0].lower() in VERBS:
                task, group = t, gnoun.group("g").lower()
        if task is None and we and not q:
            t = re.sub(r"^(?:also|still|really|just)\s+", "", we.group("t"), flags=re.I)
            if t.split() and t.split()[0].lower() in VERBS:
                task, group = t, "the team"
        if task is None and lets and not q:
            t = lets.group("t")
            if t.split() and t.split()[0].lower() in VERBS and not LETS_BAD.match(t):
                task, group = t, "the team"
        if task is None and passive and not q:
            task, group = passive.group("t"), "Unassigned"
            strength = "passive"
            pm = re.match(r"^(?:the\s+)?(?P<obj>.+?)\s+(?:needs?\s+to|has\s+to|have\s+to|must|should)\s+be\s+(?P<pp>\w+)\b(?P<rest>.*)$", task, re.I)
            if pm:
                pp = pm.group("pp").lower()
                irregular = dict(sent="send", done="do", made="make", written="write", taken="take", given="give", held="hold", built="build", kept="keep")
                cands = [irregular[pp]] if pp in irregular else [pp[:-2], pp[:-1], pp[:-3]]
                verb = next((c for c in cands if c in VERBS or c == "do"), None)
                if verb:
                    task = f"{verb} the {pm.group('obj')}{pm.group('rest')}"
        if task is None and marked:
            task = body
            sm = re.search(rf"\s*[-(@]\s*(?:owner:?\s*)?(?P<o>{names})\)?\s*$", body)
            if sm:
                owner, task = self._match_participant(sm.group("o"), self.participants), body[: sm.start()]
            else:
                group = "Unassigned"
        if not task:
            return None

        dl = find_deadline(task, self.ref) or find_deadline(body, self.ref)
        task_c = task
        if dl and dl.get("span") and task is not None and find_deadline(task, self.ref):
            sp = find_deadline(task, self.ref)["span"]
            task_c = task[: sp[0]] + " " + task[sp[1]:]
        task_c = self._clean_task(task_c)
        if len(task_c.split()) < 1:
            return None
        dep = None
        dm = DEPEND_RE.search(task_c)
        if dm:
            dep = dm.group(0).strip()
            task_c = self._clean_task(task_c[: dm.start()])
        else:
            im = IF_RE.match(body)
            dep = ("if " + im.group(1)) if im else None
        pr = "High" if PRIORITY_HI.search(ctx) else "Low" if PRIORITY_LO.search(ctx) else "Medium"
        vague = bool(re.fullmatch(r"\w+(?:\s+\w+)?\s+(?:it|that|this|them)", task_c.strip(" .").lower()) or VAGUE_TASK_RE.match(task_c.strip(" .")) or re.search(r"\b(?:the thing|that thing|stuff|things)\b", task_c, re.I) or len(task_c.split()) < 2 and task_c.lower() not in ("deploy", "rollback"))
        return dict(
            task=_cap(task_c), owner=owner, owner_label=group, pronoun=pronoun, suggested_owner=suggested,
            deadline=(dict(raw=dl["raw"], date=dl["date"].isoformat() if dl["date"] else None, kind=dl["kind"]) if dl else None),
            priority=pr, dependency=dep, tentative=bool(TENTATIVE_RE.search(s)) or strength == "offer" and "could" in s.lower(),
            vague_task=vague, strength=strength, source=s, said_by=speaker, turn=rec["turn"], time=rec["time"],
            status="open", flags=[], questions=[], confidence=1.0, resolved_fields=[],
        )

    def _clean_task(self, t):
        t = _norm(t).strip()
        t = re.sub(r"\b(?:eod|cob|end of day|asap|as soon as possible)\b", "", t, flags=re.I)
        t = re.sub(r"\b(?:please|kindly)\b", "", t, flags=re.I)
        t = re.sub(r",?\s*\bif (?:i|we|you) (?:get|have) (?:the )?(?:time|a chance)\b|,?\s*\bif (?:possible|time permits|i can|needed)\b", "", t, flags=re.I)
        t = re.sub(r",?\s*\b(?:probably|maybe|perhaps|hopefully|i guess)\b", "", t, flags=re.I)
        t = re.sub(r"^(?:also|then|first|just|really|actually|definitely|probably|maybe|go ahead and|try to|try and|still|quickly)\s+", "", t, flags=re.I)
        t = re.sub(r"^(?:also|then|first|just|really|actually|definitely|probably|maybe|go ahead and|try to|try and|still|quickly)\s+", "", t, flags=re.I)
        t = re.sub(r"^(?:be responsible for|be in charge of|take ownership of|take charge of)\s+", "Own ", t, flags=re.I)
        t = re.sub(r"^(?:take care of|be handling)\s+", "Handle ", t, flags=re.I)
        t = re.sub(r"\s+(?:from|by|on|before|until|in)\s*$", "", t, flags=re.I)
        t = re.sub(r"\s{2,}", " ", t).strip(" ,;:-.?!\"")
        return _cap(t)

    # ---------- merge repeated / revised actions
    def _merge_revisions(self, actions):
        out = []
        for a in actions:
            hit = None
            for b in out:
                sim = _jaccard(_tokens(a["task"]), _tokens(b["task"]))
                same_verb = a["task"].split()[0].lower() == b["task"].split()[0].lower()
                if sim >= 0.85 or (sim >= 0.6 and same_verb):
                    hit = b
                    break
            if not hit:
                out.append(a)
                continue
            notes = []
            ao, bo = a["owner"], hit["owner"]
            if ao and bo and ao != bo:
                notes.append(f"Owner changed from {bo} to {ao}")
            ad, bd = (a["deadline"] or {}).get("date"), (hit["deadline"] or {}).get("date")
            if ad and bd and ad != bd:
                notes.append(f"Deadline changed from {fmt(dt.date.fromisoformat(bd))} to {fmt(dt.date.fromisoformat(ad))}")
            # fill gaps from earlier mention, newer statement wins on conflicts
            for k in ("owner", "deadline", "dependency", "suggested_owner"):
                if not a.get(k) and hit.get(k):
                    a[k] = hit[k]
            if not a["owner"] and hit["owner"]:
                a["owner_label"] = None
            if hit["priority"] == "High":
                a["priority"] = "High"
            a["revision_notes"] = hit.get("revision_notes", []) + notes
            a["mentions"] = hit.get("mentions", 1) + 1
            a["source"] = hit["source"] + "  ->  " + a["source"]
            out[out.index(hit)] = a
        return out

    # ---------- ambiguity assessment
    def assess(self, a, participants):
        flags, qs = [], []
        t = a["task"]
        short = t if len(t) < 60 else t[:57] + "..."
        opts = list(participants)

        def add(code, q, fields, weight, **kw):
            flags.append(code)
            qs.append(dict(action_id=a.get("id"), code=code, question=q, fields=fields, options=kw.get("options", []), suggested=kw.get("suggested")))
            a["confidence"] = max(0.05, round(a["confidence"] - weight, 2))

        a["confidence"] = 1.0
        if a.get("pronoun"):
            add("AMBIGUOUS_PRONOUN", f"Who does \"{a['pronoun']}\" refer to for the task \"{short}\"?", ["owner"], 0.30, options=opts)
        elif not a.get("owner"):
            lab = a.get("owner_label")
            code = "GROUP_OWNER" if lab and lab != "Unassigned" else "NO_OWNER"
            who = f"\"{lab}\" is not a single person. " if code == "GROUP_OWNER" else ""
            add(code, f"{who}Who will own \"{short}\"?", ["owner"], 0.30 if code == "NO_OWNER" else 0.25, options=opts, suggested=a.get("suggested_owner"))
        dl = a.get("deadline")
        if not dl:
            add("NO_DEADLINE", f"By when should \"{short}\" be done?", ["deadline"], 0.15)
        elif dl["kind"] == "vague":
            add("VAGUE_DEADLINE", f"\"{dl['raw']}\" is not a concrete date. When exactly should \"{short}\" be done?", ["deadline"], 0.20)
        elif dl["kind"] == "approx":
            add("APPROX_DEADLINE", f"\"{dl['raw']}\" is approximate (assumed {fmt(dt.date.fromisoformat(dl['date']))}). Confirm the exact day for \"{short}\"?", ["deadline"], 0.08)
        elif dl["date"] and dt.date.fromisoformat(dl["date"]) < self.ref:
            add("PAST_DEADLINE", f"The deadline for \"{short}\" ({fmt(dt.date.fromisoformat(dl['date']))}) is before the meeting date. Which date was meant?", ["deadline"], 0.20)
        if a.get("vague_task"):
            add("VAGUE_TASK", f"\"{short}\" is too vague. What exactly is the deliverable?", ["task"], 0.25)
        if a.get("tentative"):
            add("TENTATIVE", f"\"{short}\" was said tentatively. Is it a firm commitment? (yes / no)", ["confirm"], 0.20)
        if a.get("revision_notes"):
            flags.append("REVISED")
            a["confidence"] = max(0.05, round(a["confidence"] - 0.05, 2))
        a["flags"], a["questions"] = flags, qs
        if a["status"] != "dropped":
            blocking = [f for f in flags if f != "REVISED"]
            a["status"] = "needs_clarification" if blocking else "ready"
        return a

    # ---------- summary / stats / meta
    def _summary(self, recs, used):
        pool = [(i, r) for i, r in enumerate(recs) if i not in used and len(r["text"].split()) >= 6
                and not FILLER_RE.match(r["text"]) and not r["text"].endswith("?") and not MARKER_RE.match(r["text"])]
        if not pool:
            pool = [(i, r) for i, r in enumerate(recs) if len(r["text"].split()) >= 6 and not r["text"].endswith("?")]
        freq = Counter(w for _, r in pool for w in _tokens(r["text"]))
        scored = []
        for i, r in pool:
            tok = _tokens(r["text"])
            if not tok:
                continue
            sc = sum(freq[w] for w in tok) / (len(tok) ** 0.7)
            if re.search(r"\b\d+\b|deadline|launch|budget|release|demo|risk|blocker|issue|fail|delay|complete|ready", r["text"], re.I):
                sc *= 1.2
            if re.match(r"^(?:let's|let us|good morning|welcome)", r["text"], re.I):
                sc *= 0.5
            scored.append((sc, i, r))
        top = sorted(scored, key=lambda x: -x[0])[:3]
        top.sort(key=lambda x: x[1])
        end = lambda x: x if x[-1:] in ".!?" else x + "."
        overview = [_cap(end(re.sub(r"^(?:ok(?:ay)?|so|actually|right|alright|well|good morning everyone)[,.\s]+", "", r["text"], flags=re.I))) for _, _, r in top]
        skip = {w.lower() for p in self.participants for w in p.split()}
        raw = Counter(w for _, r in pool for w in re.findall(r"[a-z]+", r["text"].lower())
                      if w not in STOP and w not in VERBS and w not in skip and len(w) > 3)
        bigr = Counter()
        for _, r in pool:
            tk = [w for w in re.findall(r"[a-z]+(?:'[a-z]+)?", r["text"].lower()) if "'" not in w]
            for a_, b_ in zip(tk, tk[1:]):
                if a_ not in STOP and b_ not in STOP and len(a_) > 3 and len(b_) > 3:
                    bigr[f"{a_} {b_}"] += 1
        topics = [k for k, v in bigr.most_common(8) if v >= 2][:5] or [w for w, _ in raw.most_common(5)]
        return dict(overview=overview, topics=topics)

    def _dependency_followups(self, actions):
        return [dict(type="dependency", text=f"\"{a['task']}\" depends on: {a['dependency']}", owner=a.get("owner"), turn=a["turn"])
                for a in actions if a.get("dependency")]

    def _stats(self, turns, actions, participants):
        words = Counter()
        tcount = Counter()
        for t in turns:
            words[t["speaker"]] += len(t["text"].split())
            tcount[t["speaker"]] += 1
        owned = Counter(a["owner"] for a in actions if a.get("owner") and a["status"] != "dropped")
        return dict(per_speaker=[dict(name=p, words=words[p], turns=tcount[p], actions=owned.get(p, 0)) for p in participants],
                    unassigned=sum(1 for a in actions if not a.get("owner")))

    def _meta(self, meta, turns, participants, title):
        times = [t["time"] for t in turns if t["time"]]
        dur = None
        if len(times) >= 2:
            def mins(x):
                p = x.split(":")
                return int(p[0]) * 60 + int(p[1])
            dur = max(mins(times[-1]) - mins(times[0]), 0)
        return dict(title=title or meta.get("title") or meta.get("meeting") or meta.get("project") or "Untitled meeting",
                    date=self.ref.isoformat(), participants=participants, turns=len(turns),
                    words=sum(len(t["text"].split()) for t in turns), duration_min=dur, agenda=meta.get("agenda"))

    def _refresh(self, result):
        live = [a for a in result["actions"] if a["status"] != "dropped"]
        result["clarifications"] = [q for a in live for q in a["questions"]]
        ready = sum(1 for a in live if a["status"] == "ready")
        result["health"] = dict(total=len(live), ready=ready, needs_clarification=len(live) - ready,
                                completeness=round(100 * ready / len(live)) if live else 100,
                                avg_confidence=round(sum(a["confidence"] for a in live) / len(live), 2) if live else 1.0)
        return result
