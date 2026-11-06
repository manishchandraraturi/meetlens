import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from meetlens.dates import find_deadline
from meetlens.engine import MeetLens, parse_transcript, split_sentences
from meetlens import report

REF = dt.date(2026, 10, 20)  # a Tuesday
HEAD = "Date: 2026-10-20\n"


def run(text):
    return MeetLens().analyze(HEAD + text)


def one(text):
    r = run(text)
    assert r["actions"], "no action extracted"
    return r["actions"][0]


class DateTests(unittest.TestCase):
    def d(self, t):
        x = find_deadline(t, REF)
        return x and (x["date"].isoformat() if x["date"] else x["kind"])

    def test_weekday(self):
        self.assertEqual(self.d("by Friday"), "2026-10-23")

    def test_next_weekday(self):
        self.assertEqual(self.d("by next Monday"), "2026-10-26")

    def test_explicit(self):
        self.assertEqual(self.d("on 25th October"), "2026-10-25")
        self.assertEqual(self.d("before 28/10"), "2026-10-28")

    def test_relative(self):
        self.assertEqual(self.d("in 2 weeks"), "2026-11-03")
        self.assertEqual(self.d("tomorrow"), "2026-10-21")
        self.assertEqual(self.d("end of the month"), "2026-10-31")

    def test_vague(self):
        self.assertEqual(self.d("soon"), "vague")
        self.assertEqual(self.d("ASAP"), "vague")

    def test_none(self):
        self.assertIsNone(self.d("send the report"))


class ParsingTests(unittest.TestCase):
    def test_headers_and_continuation(self):
        meta, turns = parse_transcript("Title: X\nA: hello\nthere\n[10:01] B: hi")
        self.assertEqual(meta["title"], "X")
        self.assertEqual(turns[0]["text"], "hello there")
        self.assertEqual(turns[1]["time"], "10:01")

    def test_compound_split(self):
        self.assertEqual(len(split_sentences("I'll draft the deck and Rahul will review it by Monday.")), 2)


class ActionTests(unittest.TestCase):
    def test_first_person_commitment(self):
        a = one("Priya: I'll send the budget to finance by Friday.")
        self.assertEqual((a["owner"], a["task"]), ("Priya", "Send the budget to finance"))
        self.assertEqual(a["deadline"]["date"], "2026-10-23")
        self.assertEqual(a["status"], "ready")

    def test_request_to_named_person(self):
        r = run("Priya: Rahul, can you fix the login bug by Monday?\nRahul: Sure.")
        a = r["actions"][0]
        self.assertEqual(a["owner"], "Rahul")
        self.assertEqual(a["deadline"]["date"], "2026-10-26")

    def test_acceptance_is_merged_not_duplicated(self):
        r = run("Priya: Rahul, can you fix the parser by Friday?\nRahul: Yes, I'll fix it by Friday and push the patch.")
        self.assertEqual(len(r["actions"]), 1)
        self.assertIn("push the patch", r["actions"][0]["task"])

    def test_group_owner_flagged(self):
        a = one("Priya: We should update the documentation.\nRahul: Right.")
        self.assertIn("GROUP_OWNER", a["flags"])
        self.assertTrue(any("Who will own" in q["question"] for q in a["questions"]))

    def test_no_deadline_and_vague_deadline(self):
        a = one("Priya: I'll update the README.\nRahul: ok")
        self.assertIn("NO_DEADLINE", a["flags"])
        b = one("Priya: I'll update the README soon.\nRahul: ok")
        self.assertIn("VAGUE_DEADLINE", b["flags"])

    def test_ambiguous_pronoun(self):
        a = one("Priya: She should collect the feedback.\nRahul: ok")
        self.assertIn("AMBIGUOUS_PRONOUN", a["flags"])

    def test_tentative(self):
        a = one("Karthik: Maybe I can write the tests by Monday.\nPriya: ok")
        self.assertIn("TENTATIVE", a["flags"])

    def test_vague_task(self):
        a = one("Rahul: I'll look into it by Friday.\nPriya: ok")
        self.assertIn("VAGUE_TASK", a["flags"])

    def test_revision_detected(self):
        r = run("Priya: I'll write the report by Friday.\nRahul: ok\nPriya: Actually I'll write the report by Monday.")
        self.assertEqual(len(r["actions"]), 1)
        self.assertEqual(r["actions"][0]["deadline"]["date"], "2026-10-26")
        self.assertIn("REVISED", r["actions"][0]["flags"])

    def test_dependency_and_priority(self):
        r = run("Priya: This is urgent. Rahul, deploy the build once the tests pass.\nRahul: ok")
        a = r["actions"][0]
        self.assertEqual(a["priority"], "High")
        self.assertIn("once the tests pass", a["dependency"])

    def test_assignment_of_earlier_unowned_task(self):
        r = run("Arjun: Someone needs to book the lab GPU.\nDr: Tanvi, can you take that?\nTanvi: Sure, I'll do it tomorrow.")
        self.assertEqual(len(r["actions"]), 1)
        a = r["actions"][0]
        self.assertEqual((a["owner"], a["deadline"]["date"]), ("Tanvi", "2026-10-21"))

    def test_take_care_of_it_volunteer(self):
        r = run("Pooja: The report has to be submitted before 25th October.\nImran: I'll take care of it.")
        self.assertEqual(len(r["actions"]), 1)
        self.assertEqual(r["actions"][0]["owner"], "Imran")

    def test_abbreviation_not_sentence_end(self):
        r = run("Tanvi: I will send the draft to Dr. Menon on Thursday.\nArjun: ok")
        self.assertEqual(r["actions"][0]["deadline"]["date"], "2026-10-22")

    def test_questions_are_not_actions(self):
        r = run("Priya: Should we deploy on Friday?\nRahul: Not sure.")
        self.assertEqual(r["actions"], [])

    def test_past_tense_is_not_action(self):
        r = run("Priya: I sent the report yesterday.\nRahul: Thanks.")
        self.assertEqual(r["actions"], [])


class DecisionAndFollowUpTests(unittest.TestCase):
    def test_explicit_decision_with_rationale(self):
        r = run("Dev: We've decided to use PostgreSQL because the data is relational.\nIsha: ok")
        d = r["decisions"][0]
        self.assertEqual(d["text"], "Use PostgreSQL")
        self.assertIn("relational", d["rationale"])

    def test_confirmed_proposal_becomes_decision(self):
        r = run("Meera: We should move the launch to the 30th.\nSana: Agreed.")
        self.assertEqual(len(r["decisions"]), 1)
        self.assertEqual(r["decisions"][0]["confirmed_by"], "Sana")
        self.assertEqual(r["actions"], [])

    def test_open_issue_and_next_meeting(self):
        r = run("Meera: We haven't decided how many volunteers we need.\nSana: Let's revisit that at the next meeting on Friday.")
        types = {f["type"] for f in r["follow_ups"]}
        self.assertIn("open_issue", types)
        self.assertIn("next_meeting", types)


class ResolveTests(unittest.TestCase):
    def test_clarification_loop_completes_item(self):
        eng = MeetLens()
        r = eng.analyze(HEAD + "Priya: We should update the documentation.\nRahul: Right.")
        a = r["actions"][0]
        self.assertEqual(a["status"], "needs_clarification")
        r = eng.resolve(r, {a["id"]: {"owner": "rahul", "deadline": "28 Oct"}})
        a = r["actions"][0]
        self.assertEqual((a["owner"], a["status"]), ("Rahul", "ready"))
        self.assertEqual(r["health"]["completeness"], 100)
        self.assertEqual(a["confidence"], 1.0)

    def test_bad_date_answer_is_rejected(self):
        eng = MeetLens()
        r = eng.analyze(HEAD + "Priya: I'll update the README.\nRahul: ok")
        r = eng.resolve(r, {"A1": {"deadline": "banana"}})
        self.assertIn("answer_error", r["actions"][0])
        self.assertEqual(r["actions"][0]["status"], "needs_clarification")

    def test_tentative_dropped_on_no(self):
        eng = MeetLens()
        r = eng.analyze(HEAD + "Karthik: Maybe I can write the tests by Monday.\nPriya: ok")
        r = eng.resolve(r, {"A1": {"confirm": "no"}})
        self.assertEqual(r["actions"][0]["status"], "dropped")
        self.assertEqual(r["health"]["total"], 0)

    def test_pronoun_cleared_when_owner_given(self):
        eng = MeetLens()
        r = eng.analyze(HEAD + "Priya: She should collect the feedback by Friday.\nRahul: ok")
        r = eng.resolve(r, {"A1": {"owner": "Priya"}})
        self.assertEqual(r["actions"][0]["status"], "ready")


class SampleAndExportTests(unittest.TestCase):
    def test_clean_sample_is_fully_specified(self):
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "samples", "clean_standup.txt")
        with open(p) as fh:
            r = MeetLens().analyze(fh.read())
        self.assertEqual(r["health"]["completeness"], 100)
        self.assertEqual(len(r["actions"]), 3)

    def test_exports_render(self):
        r = run("Priya: Rahul, can you fix the bug by Friday?\nRahul: Sure, I'll fix it.")
        self.assertIn("Action items", report.to_markdown(r))
        self.assertIn("<table>", report.to_html(r))
        self.assertTrue(report.to_csv(r).startswith("ID,Task"))

    def test_html_escapes(self):
        r = run("Priya: I'll fix the <script>alert(1)</script> issue by Friday.\nRahul: ok")
        self.assertNotIn("<script>alert", report.to_html(r))


if __name__ == "__main__":
    unittest.main(verbosity=2)
