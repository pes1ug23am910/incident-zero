# Prior work declaration

Rule 1 says all code is written on the day. On Oct 23 the mentors told us that earlier code may be reused if it was never uploaded anywhere before, provided we declare it. This file is that declaration.

## Modules that predate today

Unpublished personal rehearsal code by Yash Verma, reused with the mentors' permission. Its local repository has no git remote, and it was never uploaded anywhere before Oct 23, 2026.

<!-- Builder: one row per file in this repo that contains ported code. The "origin" column names the file it came from in the
     unpublished rehearsal project (hack-template). Candidate origins are pre-listed; delete any row that was not ported,
     and add a row for anything else that was. -->

| File in this repo | Origin (unpublished rehearsal project) | What changed today |
|---|---|---|
| `<file>` | `hack-template/core/safety.py` (candidate) | `<fill>` |
| `<file>` | `hack-template/core/approval.py` (candidate) | `<fill>` |
| `<file>` | `hack-template/core/recovery_lock.py` (candidate) | `<fill>` |
| `<file>` | `hack-template/core/evidence_check.py` (candidate) | `<fill>` |
| `<file>` | `hack-template/core/hypotheses.py` (candidate) | `<fill>` |
| `<file>` | `hack-template/core/llm_router.py` (candidate) | `<fill>` |

What "what changed today" should say, in one line per file: what was renamed or adapted to our interfaces, what was removed, what was added. Example form: "ported the approval record; world-state hash now covers container ids and the flag file; CLI prompt added."

## Everything else was written today

Every file not listed above was written on Oct 23-24, 2026, from 09:15 on Oct 23. This repository was created on Oct 23 with no imported git history; `git log --reverse --format="%ad %an %s" | Select-Object -First 1` shows the first commit at `<time>`.

## What was not reused

No documents, prompts, reports, recorded runs or test fixtures from the rehearsal project were copied. Fixtures under `tests/fixtures/` were recorded from our own runs on this laptop today.

## Available on request

The original rehearsal project is on Yash's laptop and can be shown to a mentor or judge on request, so any row above can be compared with its origin.
