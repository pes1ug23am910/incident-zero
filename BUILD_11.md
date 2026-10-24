# Build 11: live reviewer and cache diagnosis

24 October 2026, IST. Local branch `demo-stable`, starting HEAD `fd28dfebb`.
Docker endpoint: `tcp://localhost:2375`. Diagnosis only; no approval or repair
execution. `INCIDENT_ZERO_TEST` unset; knowledge OFF; model IDs loaded from
ignored `.env`. Local commit only, never push.

## Session and deadline

BUILD_10 and the README reviewer paragraph were read before stack access.
Initial clock: **09:02:42 IST**. Setup encountered a sandbox Python-launch
denial and then an unavailable optional `dotenv` import; neither started the
checkpoint. The check was corrected to use the repository's `load_env`.
The operator reports the prior process ended at **09:04:55 IST**, after model
configuration passed and before checkpoint2 started. No live run is counted.

The operator resumed the session at **09:19 IST**, replacing the deadline with
**09:50 IST** and reporting a reset, ready stack. First resumed clock:
**09:20:22 IST**; branch, HEAD and clean working tree confirmed.

At approximately **09:20:40 IST**, automatic approval review rejected the live
command because it required explicit authorization to send demo telemetry and
diagnosis data through OpenRouter to the configured external models. Specific
approval was requested; no checkpoint had started. The configured primary is
`openai/gpt-5`; reviewer and primary fallback are `google/gemini-2.5-pro`.
Reviewer isolation must also be checked against the primary models actually
used: a primary fallback to Google would preclude a Google reviewer.

At **09:24 IST**, the operator relaunched with network enabled and explicitly
directed continuation with OpenRouter/Docker traffic. The direct sandbox attempt
at **09:25:03 IST** still failed in the uv Python launcher (`permission denied`,
OS error 5), before checkpoint code started. An execution exception for the
existing interpreter succeeded. No environment, dependencies or source behavior
were changed; the approval-review rejection was not treated as a provider error.

## 1. Payment failure, reviewer ON, knowledge OFF

The single launched wrapper attempt began **09:25:33.666 IST**:

```powershell
$env:DOCKER_HOST = 'tcp://localhost:2375'
$env:DOCKER_CONFIG = "$PWD/.build/docker"
$env:INCIDENT_ZERO_KNOWLEDGE = '0'
$env:INCIDENT_ZERO_REVIEWER = '1'
Remove-Item Env:INCIDENT_ZERO_TEST -ErrorAction SilentlyContinue
foreach ($name in 'OPENROUTER_MODEL','OPENROUTER_FALLBACK_MODEL','GEMINI_MODEL','REVIEWER_MODEL') {
    Remove-Item "Env:$name" -ErrorAction SilentlyContinue
}
scripts/checkpoint2.ps1 payment-failure -ReportId stable11-payment-review-off-r1
```

**REFUSED by preflight, 23/26; wrapper exit 1.** Preflight capture began at
**09:25:34.967 IST**; the saved record was written at approximately **09:25:48**
(about 14 seconds after wrapper launch); exit was observed by **09:25:54**.
Failed gates:

- Clean detector: `checkout:p95_ms`, `frontend:p95_ms`, `frontend-proxy:p95_ms`.
- Traffic health/baseline: high p95 for those same three services.
- Fresh real Control Room: neither process-start/source-time nor matching API
  revision verification confirmed freshness; the gate calls for operator restart.

All other checks passed, including 21 containers, pristine overlay, no STOP,
test mode absent, healthy Action API, no stuck/cooling attempts, and authenticated
primary inference **HTTP 200**. No injection, agent diagnosis or reviewer call
occurred. No report bundle exists for the requested report ID.

| Requested reviewer check | Observed result |
|---|---|
| Different vendor | `.env` config: OpenAI primary, Google reviewer; no actual diagnosis model usage to assess |
| At most three additional reads | 0 because review never started; not a live budget verification |
| Resolvable extra evidence | Not exercised; no reviewer evidence |
| Schema-valid report with `review` | Not produced; not verified |
| Unchanged confidence when unopposed | Not exercised; no diagnosis or verdict |
| Reviewer latency | N/A; no reviewer request |
| Reviewer provider failure | None observed because no call occurred; availability not verified |

Evidence: [payment preflight](reports/stable11-handoff/payment-preflight.json).
README retains **built, not live-verified** and now states the attempted run's
actual outcome. No retry or readiness bypass was performed.

## 2. Cache unavailable, knowledge OFF

The single wrapper attempt began **09:26:15.765 IST**, leaving **23 minutes
44 seconds** before the deadline, satisfying the nine-minute start condition.
The same environment preparation was used, with knowledge OFF and reviewer OFF
(`INCIDENT_ZERO_REVIEWER=0`); model IDs still came from `.env`.

```powershell
scripts/checkpoint2.ps1 cache-unavailable -ReportId stable11-cache-off-r1
```

**REFUSED by preflight, 25/26; wrapper exit 1.** Capture began at
**09:26:16.880 IST**; the saved record was written at approximately **09:26:30**
(about 14 seconds after launch); exit was observed by **09:26:34**.
The earlier latency crossings had cleared: clean detector and traffic/baseline
both passed. **Fresh real Control Room remained unverified**, blocking the run.
Primary authenticated inference again returned **HTTP 200**.

No cache injection or diagnosis occurred; no report was produced, so cache
confidence, diagnosis latency and reliability are unmeasured in this session.
Evidence: [cache preflight](reports/stable11-handoff/cache-preflight.json).
The failed freshness check was not bypassed, and the Control Room was not restarted.

## 3. Reset and handoff

Explicit `faultctl reset --timeout 90` started **09:26:49.640 IST** and passed in
**3.677 s**. Verification finished **09:26:53.969 IST**, **4.335 s** total:

- **21/21 expected containers running**.
- Active, saved pristine and official-source flags have identical SHA-256 hashes.
- **Zero active incidents**, no flag override.
- **STOP absent** on disk and false through the real Control Room API.
- Load remained running with **5 users**; `INCIDENT_ZERO_TEST` was unset.

Evidence: [reset](reports/stable11-handoff/final-reset.json) and
[handoff verification](reports/stable11-handoff/verification.json).
**Stack access ended at 09:26:53.969 IST**, over 23 minutes before 09:50.
Both checkpoint wrapper processes exited; no rehearsal worker remains.
All subsequent work is local documentation, retained-file checks and Git only.

The required stack-state handoff passed; this does **not** clear the separate
Control Room freshness failure or establish full Checkpoint 3 readiness. The
operator owns that check and the human rehearsal after the deadline.

No incident was injected, no action approved or repair executed, and no source
code changed. No unrelated unit suite was run. At **09:28:14 IST**, local-only
verification confirmed the retained handoff record passed. `git diff --check`
passed; all **6** session documentation/evidence files were scanned against
configured credentials and key patterns with **zero hits**. README, this ledger
and the four retained preflight/reset/handoff JSON files form the local commit,
using Yash Verma's author and committer identity. No push is authorized or made.
