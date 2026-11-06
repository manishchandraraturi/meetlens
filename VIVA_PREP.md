# Viva preparation (10 marks): MeetLens

Read this once. Every answer below is true of the code you are submitting.

## 30-second pitch
"Meetings end with tasks that have no owner or no date, and nobody notices. MeetLens reads a transcript, pulls out summary, decisions, tasks, deadlines and follow-ups, and for every task that is incomplete or ambiguous it asks a specific question and re-checks after you answer."

## Questions you will probably get

**Is this actually AI? You did not use an LLM.**
It is a rule-based NLP pipeline, a classical AI approach. I chose it because it is explainable, deterministic, testable and needs no API. The ambiguity logic is separate from the extraction, so an LLM can replace extraction later. The weakness is coverage of unusual phrasing, and I measured that (Section 7 of the report).

**How does it decide something is an action item?**
By how the sentence assigns responsibility: request ("Rahul, can you..."), first-person commitment ("I'll..."), named subject ("Ananya will..."), group obligation ("we should..."), passive ("needs to be sent") or an explicit "Action item:" line. Questions, past tense and negations are rejected. Code: `MeetLens._action` in engine.py.

**How does it find deadlines?**
`dates.py` has ordered regex patterns that resolve phrases against the meeting date: weekdays, "in 2 weeks", "25th October", "by the 18th", end of month. Words like "soon" and "ASAP" are classed as vague, because they have no date.

**How does it know an item is ambiguous?**
Ten flags (table in Section 4.5): no owner, group owner, pronoun, no deadline, vague deadline, approximate deadline, past deadline, vague task, tentative, revised. Each flag creates a question and subtracts from a confidence score that starts at 1.0.

**What happens when the user answers a question?**
`MeetLens.resolve` applies the answer, parses the date or matches the name to a participant, clears the flag and re-runs the assessment. A date it cannot read is rejected. In the demo, 30% of tasks fully specified became 100% after 11 answers.

**What if two people talk about the same task?**
Replies are merged into the request they answer ("Yes, I'll do it by Friday"). A later change of owner or date overrides the earlier one and is logged as a revision. Two statements count as the same task only if the words overlap and the verb is the same.

**How do you evaluate it?**
I hand-labelled owner, date and a keyword for each task in 6 transcripts (34 tasks) and measured recall, precision and strict owner+date accuracy. First-run numbers on transcripts the system had not seen: recall 90 to 100%, precision 64 to 71%. After fixing general bugs: 83 to 100%. The development set scores 100% because I tuned on it, so I do not quote that as accuracy.

**What are the limitations?**
Related tasks with no shared words are not linked; one owner per task; limited pronoun resolution; English with speaker labels only; "next Friday" is ambiguous. All listed in Section 8.

**Why is the summary extractive?**
No model to generate text, and extractive output cannot invent facts. Tasks and decisions are removed first so the summary shows what was discussed, not what was assigned.

**What would you do with more time?**
Swap extraction for an LLM and compare on the same labelled sets, add speech-to-text, link tasks by sentence similarity, export to a calendar.

## Commands to demo live
```
python -m meetlens serve                      # then open http://127.0.0.1:8000, load "Sprint Planning", Analyse, answer questions, Apply
python -m meetlens analyze samples/club_event.txt --ask
python -m unittest discover -s tests
python eval/gold.py
```
Demo order: load Sprint Planning, point at A6 (pronoun) and A3 (group owner), answer a few questions, show completeness rising, export HTML.
