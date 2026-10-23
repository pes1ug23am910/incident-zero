# Evaluation note

Which practice incidents our agent got right and wrong in our own testing, and why. Every number here comes from a report in `reports/`; nothing is estimated. Rows still showing `<...>` were not run.

## How we tested

- One run per incident, from a clean stack: `faultctl reset` (exit 0), `faultctl inject <id>`, `detect/` raises the alert, `agent.run` writes the report.
- The agent never saw the incident id. Correctness was scored after the run by comparing the report with `runs/<ts>/injected.json`.
- **Correct**: right component and right cause category. **Partial**: right component, wrong category. **Escalated**: `needs_human` with findings (the brief counts this above a confident wrong fix). **Wrong**: a confident diagnosis of the wrong component.
- **Seconds**: `diagnosed_at` minus `detected_at`. Alert delay (inject to alert) goes in notes.
- Model: `<model id>`. Tool budget: 12 calls. Laptop: `<RAM, CPU>`. Runs done on `<date, time range>`.

## Practice incidents

| # | Incident (`faultctl` id) | Expected component | Diagnosed component | Category | Correct? | Confidence | Seconds | Status | Report | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `payment-failure` | payment | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<file>` | `<...>` |
| 2 | `cart-intermittent` | cart | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<file>` | `<...>` |
| 3 | `catalog-one-product` | product-catalog | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<file>` | `<...>` |
| 4 | `recommendation-leak` | recommendation | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<file>` | `<...>` |
| 5 | `ad-high-cpu` | ad | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<file>` | `<...>` |
| 6 | `homepage-flood` | load-generator or frontend, category `load` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<file>` | `<...>` |
| 7 | `container-stopped --svc recommendation` | recommendation | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<file>` | `<...>` |
| 8 | `cache-unavailable` | valkey-cart | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<file>` | `<...>` |
| 9 | `network-latency --svc product-catalog` | product-catalog | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<file>` | `<...>` |
| 10 | `cpu-starve --svc recommendation` | recommendation | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<file>` | `<...>` |

Variants of the same slide incidents (run if time allows):

| Incident | Expected component | Diagnosed | Correct? | Confidence | Seconds | Notes |
|---|---|---|---|---|---|---|
| `payment-unreachable` | payment | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` |
| `ad-gc` | ad | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` |
| `restart-loop --svc <svc>` | `<svc>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` |
| `memory-starve --svc <svc>` | `<svc>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` |

**Totals:** `<n>`/10 correct, `<p>` partial, `<e>` escalated, `<w>` wrong. Median seconds to diagnosis: `<s>`.

## Unseen-style rehearsal (combinations we invented, and no fault)

| # | Injected | Expected | Primary cause found | Alternative listed | Correct? | Status | Notes |
|---|---|---|---|---|---|---|---|
| C1 | `<a>,<b>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` |
| C2 | `<a>,<b>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` |
| C3 | `<a>,<b>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` |
| C4 | `<a>,<b>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` |
| C5 | `<a>,<b>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` |
| C6 | `<a>,<b>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` |
| N0 | nothing | no alert, or `needs_human` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` |

## Full loop runs (approve, act, verify)

The hands session ran **mock integration acceptance only** while another session
owned the sole live stack. The six bundles below exercise the real SQLite
checkpoint/approval/response path with fake executors and telemetry. No row
counts toward live diagnosis accuracy or confidence calibration. Confidence
0.90 is an input fixture; model = none; the 180-second windows use virtual time.

| Bundle | Action | Approval fixture | Before | After | Recovered in mock? | Final status | Action log |
|---|---|---|---|---|---|---|---|
| [payment approved](../reports/mock-payment-approved/report.md) | toggle_flag payment | Mock operator: yes | 0.9 | 0 | yes, 40 requests | fixed | [excerpt](../reports/mock-payment-approved/action-log.jsonl) |
| [payment rejected](../reports/mock-payment-rejected/report.md) | none executed | Mock operator: no | 0.9 | n/a | not checked | needs_human | [excerpt](../reports/mock-payment-rejected/action-log.jsonl) |
| [recommendation restart](../reports/mock-recommendation-restart/report.md) | restart_service recommendation | Mock operator: yes | 0.9 | 0 | yes, 40 requests | fixed | [excerpt](../reports/mock-recommendation-restart/action-log.jsonl) |
| [homepage throttle](../reports/mock-homepage-throttle/report.md) | throttle_load load-generator | Mock operator: y | 0.9 | 0 | yes, 40 requests | fixed | [excerpt](../reports/mock-homepage-throttle/action-log.jsonl) |
| [STOP mid-run](../reports/mock-stop-mid-run/report.md) | toggle_flag payment, then STOP | Mock operator: yes | 0.9 | unavailable | no | aborted | [excerpt](../reports/mock-stop-mid-run/action-log.jsonl) |
| [forced non-recovery](../reports/mock-non-recovery/report.md) | toggle_flag payment, then rollback | Mock operator: yes | 0.9 | 0.8 | no; original settings restored | rolled_back | [excerpt](../reports/mock-non-recovery/action-log.jsonl) |

The mock signals intentionally use one scalar error-rate fixture across action
types; they do not reproduce the actual stopped-container or flood signatures.
All live rows remain unverified. Exact follow-up commands are in
[BUILD_05.md](../BUILD_05.md#live-acceptance-deferred).

## Confidence calibration

Stated confidence against how often it was right, over every run above (practice, variants, combinations).

| Stated confidence | Runs | Correct | Hit rate | Mean stated |
|---|---|---|---|---|
| below 0.60 (escalated) | `<...>` | `<...>` | `<...>` | `<...>` |
| 0.60 to 0.74 | `<...>` | `<...>` | `<...>` | `<...>` |
| 0.75 to 0.89 | `<...>` | `<...>` | `<...>` | `<...>` |
| 0.90 to 1.00 | `<...>` | `<...>` | `<...>` | `<...>` |

Reading: `<one honest sentence, e.g. "stated 0.8, right 7 of 8"; say plainly if the sample is too small to mean much>`.

## What does not work

Known by design:
- No `scale_service` on Docker Compose; the API answers `not_available_on_compose`.
- Network and resource-starvation faults have no allowlisted fix. We diagnose and escalate.
- `restart_service` cannot be undone. If verification fails after a restart, we escalate.
- Independent multi-service causes escalate at tier 3. Eligible proposal queues
  are approved individually, and rejection does not cancel later proposals.
- Live evidence can age out. Tools retain sanitized snapshots per run, and resolution reports when it used a snapshot; retained historical evidence does not establish current recovery.

Found in testing (one line each: what failed, why we think it failed, which report shows it):
- A concurrent caller initially attempted to read a Windows byte-locked file;
  the lock now inspects file size without reading the locked byte. The threaded
  exclusion regression test passes.
- No live hands failure or success has been measured. Missing or insufficient
  traffic, unavailable telemetry and concurrent world changes all block a
  recovery claim in mocked tests.

## What we would do next

- `<the miss we would fix first, and how>`
- `<...>`
- `<...>`
