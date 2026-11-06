# Meeting Minutes: Sprint 7 Planning - Campus Placement Portal

**Date:** 2026-10-20  
**Participants:** Priya Nair, Rahul Verma, Ananya Rao, Karthik Iyer  
**Length:** 21 turns, 251 words, about 28 min

## Summary

- Accuracy on the test set is around 91 percent, but it still fails on two-column resumes.
- That is a blocker for the demo.
- On the frontend side, the dashboard is ready but the login page still needs work.

**Topics:** start, status, resume, parser, module

## Decisions

D1. Move the demo to the 30th of October instead of the 27th (because the placement cell is unavailable on the 27th) - confirmed by Ananya Rao

## Action items

| ID | Task | Owner | Deadline | Priority | Status |
|---|---|---|---|---|---|
| A1 | Fix the two-column issue and push the patch to the main branch | Rahul Verma | Fri, 23 Oct 2026 | High | Ready |
| A2 | Write the login test cases | Karthik Iyer | Mon, 26 Oct 2026 | Medium | Ready |
| A3 | Figure out the database hosting | ? Unassigned | - | Medium | Needs clarification |
| A4 | Prepare the demo slides | Ananya Rao | - | Medium | Needs clarification |
| A5 | Review the demo slides before the demo | Rahul Verma | - | Medium | Needs clarification |
| A6 | Collect feedback from last sprint's users | ? (she) | - | Medium | Needs clarification |
| A7 | Send the updated wireframes to the design team | Ananya Rao | Wed, 21 Oct 2026 | Medium | Ready |
| A8 | Deploy the staging build | ? Unassigned | - | Medium | Needs clarification |
| A9 | Handle the thing with the API keys | Rahul Verma | soon (vague) | Medium | Needs clarification |
| A10 | Update the project README | Karthik Iyer | - | Medium | Needs clarification |

**Completeness:** 30% of action items are fully specified (3/10); average confidence 0.78.

## Clarifications needed

- [A3] "the team" is not a single person. Who will own "Figure out the database hosting"?
- [A3] By when should "Figure out the database hosting" be done?
- [A4] By when should "Prepare the demo slides" be done?
- [A5] By when should "Review the demo slides before the demo" be done?
- [A6] Who does "she" refer to for the task "Collect feedback from last sprint's users"?
- [A6] By when should "Collect feedback from last sprint's users" be done?
- [A8] "the team" is not a single person. Who will own "Deploy the staging build"?
- [A8] By when should "Deploy the staging build" be done?
- [A9] "soon" is not a concrete date. When exactly should "Handle the thing with the API keys" be done?
- [A9] "Handle the thing with the API keys" is too vague. What exactly is the deliverable?
- [A10] By when should "Update the project README" be done?

## Follow-ups

- **Next meeting:** Next meeting is next Tuesday to review progress (2026-10-27)
- **Open issue:** We still need to figure out who approves the hosting cost
- **Dependency:** "Deploy the staging build" depends on: once the parser patch is merged
