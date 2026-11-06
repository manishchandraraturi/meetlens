# MeetLens

**Meeting transcript in. Summary, decisions, tasks, deadlines and follow-ups out. And it asks you about anything that's missing.**

Most meetings don't fail in the discussion. They fail in the gaps: a task nobody owns, a deadline nobody wrote down, a "we should look into that" that goes nowhere. MeetLens reads a transcript, pulls out what was decided and assigned, and for every item that is incomplete or ambiguous it asks a specific question, then re-checks once you answer.

Pure Python standard library. No API key, no internet, nothing to install.

> Project 01, problem statement **M1-P2: AI-Powered Meeting-to-Action Assistant**

---

## Try it in 60 seconds

```bash
git clone https://github.com/manishchandraraturi/meetlens.git
cd meetlens
python -m meetlens serve
```

Open http://127.0.0.1:8000, pick **Sprint Planning** from the dropdown, press **Analyse**, answer the questions, press **Apply answers**.

Other ways to run it:

```bash
python -m meetlens demo                                   # analyse all sample transcripts into output/
python -m meetlens analyze samples/club_event.txt --ask   # answer clarification questions in the terminal
python -m unittest discover -s tests                      # 33 unit tests
python eval/gold.py -v                                    # accuracy on hand-labelled transcripts
```

Needs Python 3.8 or newer.

## What it looks like

Input (a sprint meeting):

```
[10:04] Priya: That is a blocker for the demo. Rahul, can you fix the two-column issue by Friday?
[10:05] Rahul: Yes, I'll fix it by Friday and push the patch to the main branch.
[10:08] Priya: Someone should write the test cases for the login flow.
[10:09] Karthik: Maybe I can look at it if I get time.
[10:19] Rahul: Sure. She should also collect feedback from last sprint's users.
```

Output:

| ID | Task | Owner | Deadline | Priority | Status |
|---|---|---|---|---|---|
| A1 | Fix the two-column issue and push the patch to the main branch | Rahul Verma | Fri, 23 Oct 2026 | High | Ready |
| A2 | Write the login test cases | Karthik Iyer | Mon, 26 Oct 2026 | Medium | Ready |
| A3 | Figure out the database hosting | ? Unassigned | - | Medium | Needs clarification |
| A6 | Collect feedback from last sprint's users | ? (she) | - | Medium | Needs clarification |

Questions it asks:

- `"the team" is not a single person. Who will own "Figure out the database hosting"?`
- `Who does "she" refer to for the task "Collect feedback from last sprint's users"?`

After answering all 11 questions on this sample, fully specified tasks go from **30% to 100%**.

Full generated reports for every sample are in [`output/`](output/) as Markdown, HTML, CSV and JSON.

## What it understands

| | |
|---|---|
| **Action items** | "I'll send it", "Rahul, can you fix it", "Ananya will prepare slides", "we should book the hall", "the report needs to be sent", `Action item: ...` |
| **Replies** | "Yes, I'll do it by Friday" is merged into the request it answers, not counted twice |
| **Revisions** | "Actually, make it Monday" updates the earlier task and records what changed |
| **Deadlines** | "by Friday", "next Monday", "in 2 weeks", "25th October", "by the 18th", "EOD", and flags "soon" / "ASAP" as not a real date |
| **Decisions** | "we've decided...", or a proposal someone else confirmed ("Agreed"), with the reason |
| **Ambiguity** | no owner, group owner, "she will...", no deadline, vague deadline, vague task, tentative ("maybe"), past deadline |
| **Follow-ups** | next meeting, open issues, unanswered questions, dependencies ("once the patch is merged") |

Every task gets a confidence score and a status: `ready` or `needs_clarification`. It never invents an owner or a date. If the transcript doesn't say it, the item is flagged.

## How it works

```
transcript -> turns -> sentences -> classify -> normalise -> merge replies/revisions -> assess ambiguity -> questions -> output
```

It is a deterministic rule-based NLP pipeline, not an LLM. That is deliberate: every result can be traced to a sentence and a rule, the same input always gives the same output, and it runs offline. Extraction and ambiguity checking are separate, so a language model could replace extraction later without touching the clarification logic.

```
meetlens/engine.py   parsing, extraction, ambiguity assessment, clarification loop
meetlens/dates.py    deadline and date understanding
meetlens/report.py   Markdown / HTML / CSV / JSON export
meetlens/server.py   web server (stdlib)      meetlens/ui.html   the interface
meetlens/cli.py      command line
samples/             demo transcripts         eval/    evaluation transcripts + gold labels
tests/               unit tests
```

## Transcript format

```
Title: Sprint Planning
Date: 2026-10-20
Attendees: Priya Nair, Rahul Verma

[10:02] Priya: Rahul, can you fix the parser by Friday?
Rahul: Yes, I'll fix it by Friday.
```

`Title`, `Date`, `Attendees` and timestamps are optional. The date is what relative deadlines are measured from.

## Evaluation

Hand-labelled owner, date and task for 34 tasks across 6 transcripts.

| Set | Recall | Precision | Owner + date correct |
|---|---|---|---|
| Second set, first run | 90% | 64% | 20% |
| Unseen transcript, first run | 100% | 71% | 80% |
| After fixing the bugs those runs exposed | 100% | 83-100% | 90-100% |

The development transcripts score 100% because the rules were written against them, so that number isn't quoted as accuracy. The sets are small and written by the author. See the report for details.

## Limitations

- Related tasks with no shared words ("inform the students" / "put up a notice") are not linked.
- One owner per task.
- Pronoun resolution is limited to nearby sentences.
- English only, and the transcript needs speaker labels.
- "Next Friday" is read as the Friday of next week.

## Author

Manish, B.E. AI & ML, CMR Institute of Technology, Bengaluru.

## License

MIT
