# Build 10: stopped-container knowledge comparison

24 October 2026, IST. Local branch `demo-stable`, starting HEAD `a92ab6f27`.
Stack endpoint: `tcp://localhost:2375`. Stack access ends at **08:57 IST**;
the human operator owns Checkpoint 3 at 09:00. No push is authorized.

## 1. Stopped recommendation, knowledge OFF

First clock observation: **08:44:54 IST**, leaving about 12 minutes before the
hard deadline, rather than a full 25-minute execution window. BUILD_09 was read
before any stack operation. The working tree was clean on the expected branch
and revision.

The literal `--svc recommendation` form was rejected by PowerShell parameter
binding before Python ran. The documented `-Service recommendation` equivalent
then encountered a sandbox Python-launch denial, also before stack access.
The same single rehearsal was launched with elevated execution at approximately
**08:45:40 IST**:

```powershell
$env:DOCKER_HOST = 'tcp://localhost:2375'
$env:DOCKER_CONFIG = "$PWD/.build/docker"
$env:INCIDENT_ZERO_KNOWLEDGE = '0'
Remove-Item Env:INCIDENT_ZERO_TEST -ErrorAction SilentlyContinue
foreach ($name in 'OPENROUTER_MODEL','OPENROUTER_FALLBACK_MODEL','GEMINI_MODEL') {
    Remove-Item "Env:$name" -ErrorAction SilentlyContinue
}
scripts/checkpoint2.ps1 container-stopped -Service recommendation -ReportId stable10-recommendation-off-r1
```

Model IDs resolve from ignored `.env`; keys are not printed. Read-only preflight
`20261024T031541.667135Z` passed **26/26**, including 21 running containers,
pristine overlay, no STOP, real Control Room, healthy traffic, 1.39 GiB free RAM,
and authenticated model inference HTTP 200. Initial reset took **2.536 s**.
Both telemetry-clearance windows retain the normal minimum 180 seconds.

**Diagnosis PASS:** [stable10-recommendation-off-r1](reports/stable10-recommendation-off-r1/report.json)
reported `recommendation / container_down`, `diagnosed`, **0.90 confidence**,
**59.673 s agent time**, three tool calls, and a tier-2 `restart_service`
proposal targeting recommendation. No approval or execution occurred.
Diagnosis timestamp: **08:50:10.919 IST**. Report validation passed.

| Mode / run | Confidence | Agent seconds | Diagnosis gate |
|---|---|---|---|
| ON, stable09-recommendation-on-r1 | 0.80 | 56.537 | PASS |
| ON, stable09-recommendation-on-r2 | 0.90 | 172.794 | FAIL: >=120 s |
| OFF, stable10-recommendation-off-r1 | 0.90 | 59.673 | PASS |

The requested rounded ON comparison is **0.80 / 57 s**, **0.90 / 173 s**.
README and CHECKPOINT2_BRIEF select **OFF** for the stopped-container demo.
OFF was 3.136 s slower than the faster ON run and 113.121 s faster than the
slower ON run, with confidence matching the latter. This single OFF rehearsal
supports an operational demo choice, not general retrieval superiority or
statistical reliability. No source behavior or other case's mode was changed.
The Control Room already runs OFF according to BUILD_09 and was not restarted.

The wrapper exited **0**, observed complete at **08:53:28 IST**. Measured stage
total: **451.084 s**, excluding preflight and process-launch overhead (the full
command ran approximately 08:45:40–08:53:25). The report's **59.673 s** agent
time differs from the **70.544 s** wrapper agent stage, which includes launch
and report-generation overhead.

| Stage | Seconds |
|---|---:|
| reset_before | 2.536 |
| clear_before | 182.443 |
| baseline | 2.089 |
| inject | 4.291 |
| wait_for_alert | 1.556 |
| agent subprocess | 70.544 |
| validate | 1.662 |
| print_report | 0.007 |
| reset_after | 3.417 |
| clear_after | 182.539 |

Both clearance windows verified. After reset, historical frontend error-rate
samples declined and the final samples at +152.5 s and +182.5 s were clean.
See [checkpoint2.json](reports/stable10-recommendation-off-r1/checkpoint2.json)
for retained timings and recovery samples. The report also passed an independent
offline schema/evidence check against its retained bundle, with no live reads.

## 2. Cache unavailable, knowledge ON

**Not run.** At **08:48:11 IST**, step 1 was still in its clean-baseline window;
only **8 minutes 49 seconds** remained before 08:57. The required nine-minute
start allowance was no longer available. No cache injection or knowledge-ON
diagnosis was made in this session; cache reliability remains unmeasured today.

## 3. Reset, handoff and local commit

Final explicit `faultctl reset --timeout 90` started **08:53:36.938 IST**, took
**2.190 s**, and passed. Verification finished **08:53:39.702 IST**, total
**2.767 s**: **21/21 containers running**, active/source/saved flags byte-hash
identical, zero active incidents, no flag override, **STOP absent** on disk and
false through the real Control Room API. Load remained running with **5 users**;
test mode was unset. This is **3 minutes 20 seconds before the 08:57 deadline**.

Evidence: [preflight](reports/stable10-handoff/preflight.json),
[final reset](reports/stable10-handoff/final-reset.json), and
[handoff verification](reports/stable10-handoff/verification.json).
**Stack access ended at 08:53:39.702 IST.** Subsequent work is local documentation,
artifact hygiene and Git only. The checkpoint process exited; no rehearsal or
cleanup worker remains. The existing Control Room is left for the operator.

Local checks: `git diff --check` passed; all **300** new/updated artifact files
were scanned against configured credential values and key patterns with **zero
hits**. No source code changed, so no unrelated unit suite was rerun.

README, CHECKPOINT2_BRIEF, this ledger and the new report/handoff evidence are
committed locally with Yash Verma's authorship. No push, Checkpoint 3 approval,
or repair execution is performed in this session. The 09:00 human run remains
outside this session's acceptance claims.
