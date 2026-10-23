# Knowledge layer: integration-owner acceptance

The knowledge worktree performed offline work only. The commands below are **for the integration owner in `D:\incident-zero`, after merging `knowledge`, with exclusive use of the demo stack**. They are instructions, not a record of execution. The checkpoint wrappers manage injection, baseline checks and cleanup; do not run these while another session owns an incident. Human approval remains required for Checkpoint 3. Keep model identifiers from the existing `.env`; do not print credentials.

## Offline checks and inspection

Completed on branch `knowledge`: 15 runbooks, 23 sanitized Compose service entries,
143 indexed chunks, and a 0.193-second local build. The complete offline suite
passed **694 tests with 3 skips**. Knowledge/memory source and content scanning
found no prohibited disclosures. Tests cover both flag settings, the wrong
payment-memory hint, cited-remedy policy disagreements, terminal memory writes,
report rendering and mock Control Room passthrough. UI checks exercised the
JavaScript and API offline; an interactive browser rendering was not verified.

Recorded-observation graph tests use payment-failure-r6, container-stopped-r2 and
cache-unavailable-r2. They reconstruct the compact tool observations retained in
model requests and validate the original evidence snapshots. Existing decisions
are replayed, not regenerated. Older recommendation recordings r3 and loop-r1
do not exactly follow the current graph's stopping rules and are left unchanged.
The retrieval-only ablation below can still inspect the validated r3 report.

The suite also corrects two pre-existing test issues: numeric port matching no
longer treats digits embedded in SHA-256 checksums as disclosures, and the report
repair fixture explicitly selects the offline graph. No historical evidence was
rewritten and no production guard was removed.

```powershell
Set-Location D:\incident-zero
& .\.venv\Scripts\python.exe -m knowledge build
& .\.venv\Scripts\python.exe -m knowledge search 'cart errors connection refused'
& .\.venv\Scripts\python.exe -m pytest -q -m 'not live'
& .\.venv\Scripts\python.exe -m eval.knowledge_ablation --output .build/knowledge-ablation.json
```

The build must index at least 12 runbooks plus the catalogue in under 10 seconds; the search must rank the cache runbook first. The offline ablation validates `payment-failure-r6`, `container-stopped-r3` and `cache-unavailable-r2` using retained evidence and freezes their decisions. Its measured quantity is retrieval milliseconds. It is not a fresh investigation or a measurement of improvement. Use `--reports-dir <directory>` if the retained bundles are in another reports directory under this repository.

## Live acceptance: payment failure, then memory reuse

Prepare a fresh reference-only index so unrelated memories cannot influence this check. These commands create a new directory and leave existing stores intact.

```powershell
Set-Location D:\incident-zero
$env:DOCKER_HOST = 'tcp://localhost:2375'
$env:INCIDENT_ZERO_KNOWLEDGE = '1'
$knowledgeRoot = Join-Path (Get-Location) ('.build\knowledge-acceptance-' + (Get-Date -Format 'yyyyMMddTHHmmss'))
$knowledgeSeed = Join-Path $knowledgeRoot 'seed'
New-Item -ItemType Directory -Path (Join-Path $knowledgeSeed 'knowledge') -Force | Out-Null
Copy-Item -LiteralPath knowledge\runbooks -Destination (Join-Path $knowledgeSeed 'knowledge\runbooks') -Recurse
Copy-Item -LiteralPath knowledge\services.yaml -Destination (Join-Path $knowledgeSeed 'knowledge\services.yaml')
$env:INCIDENT_ZERO_KNOWLEDGE_INDEX = Join-Path $knowledgeRoot 'index.sqlite'
$env:INCIDENT_ZERO_MEMORY_DIR = Join-Path $knowledgeRoot 'memory'
New-Item -ItemType Directory -Path $env:INCIDENT_ZERO_MEMORY_DIR | Out-Null
& .\.venv\Scripts\python.exe -m knowledge --root $knowledgeSeed --index $env:INCIDENT_ZERO_KNOWLEDGE_INDEX build
if ($LASTEXITCODE -ne 0) { throw 'Knowledge index build failed' }
$beforeCount = @(Get-ChildItem -LiteralPath $env:INCIDENT_ZERO_MEMORY_DIR -Filter '*.json').Count
& .\scripts\checkpoint3.ps1 -Incident payment-failure -ReportId knowledge-payment-first
```

Review and approve the proposed payment action **in this terminal** when the wrapper asks; wait for its verification and cleanup to finish. Terminal approval keeps the resume/remember step in the shell's isolated-store environment. An already-running Control Room process may have different environment settings; the integration owner must align them before testing browser approval with these stores. If these report IDs already exist, choose new matching IDs throughout the remaining commands rather than replacing prior evidence. Inspect and assert the recorded result:

```powershell
$first = Get-Content -LiteralPath reports\knowledge-payment-first\report.json -Raw | ConvertFrom-Json
if (-not $first.knowledge_consulted.enabled) { throw 'Knowledge was not enabled' }
if (@($first.runbook_refs.id) -notcontains 'kb:application-fault#remediation') { throw 'Required application runbook citation missing' }
$paymentAction = @($first.proposed_actions | Where-Object { $_.type -eq 'toggle_flag' -and $_.target -eq 'payment' })
if ($paymentAction.Count -eq 0) { throw 'Proposal does not match the allowed application remediation' }
$afterCount = @(Get-ChildItem -LiteralPath $env:INCIDENT_ZERO_MEMORY_DIR -Filter '*.json').Count
if ($afterCount -ne ($beforeCount + 1)) { throw 'Expected one new incident memory record' }
$firstMemoryPath = Join-Path $env:INCIDENT_ZERO_MEMORY_DIR 'knowledge-payment-first.json'
$firstMemory = Get-Content -LiteralPath $firstMemoryPath -Raw | ConvertFrom-Json
if ($firstMemory.report_status -ne $first.status) { throw 'Memory did not retain the final report outcome' }
if ($first.status -eq 'fixed' -and $firstMemory.outcome -ne 'recovered') { throw 'Memory recovery outcome is inconsistent' }
& .\.venv\Scripts\python.exe -m knowledge --index $env:INCIDENT_ZERO_KNOWLEDGE_INDEX explain reports\knowledge-payment-first\report.json
$found = & .\.venv\Scripts\python.exe -m knowledge --index $env:INCIDENT_ZERO_KNOWLEDGE_INDEX search 'payment error_rate application_fault' | ConvertFrom-Json
if (@($found.memory_refs.id) -notcontains 'mem:knowledge-payment-first') { throw 'First incident was not indexed' }

# Keep this same index and memory for the second run; do not rebuild the seed index.
& .\scripts\checkpoint3.ps1 -Incident payment-failure -ReportId knowledge-payment-second
$second = Get-Content -LiteralPath reports\knowledge-payment-second\report.json -Raw | ConvertFrom-Json
if (@($second.memory_refs.id) -notcontains 'mem:knowledge-payment-first') { throw 'Second report did not retrieve the first incident' }
$comparison = [PSCustomObject]@{
    first_component = $first.root_cause.component
    second_component = $second.root_cause.component
    first_confidence = $first.root_cause.confidence
    second_confidence = $second.root_cause.confidence
    first_tool_calls = $first.agent.tool_calls
    second_tool_calls = $second.agent.tool_calls
    first_seconds = $first.agent.elapsed_s
    second_seconds = $second.agent.elapsed_s
    same_or_fewer_tool_calls = ($second.agent.tool_calls -le $first.agent.tool_calls)
}
$comparison | ConvertTo-Json | Tee-Object -FilePath (Join-Path $knowledgeRoot 'payment-repeat-comparison.json')
if (-not $comparison.same_or_fewer_tool_calls) { Write-Warning 'Acceptance item 3 did not improve or tie tool calls; retain and report this result.' }
```

Do not treat cleanup recovery as the action's verified recovery. Retain each report's status and verification, including escalation or rollback. A missing citation, memory write failure or increased tool count is an acceptance finding to investigate, not a value to edit out.

## Live on/off ablation: three Checkpoint 2 cases

Run after the repeated-payment check has finished and cleanup is confirmed. This creates another reference-only seed and an independent index/empty memory for **every** case and mode. Thus the general ablation measures retrieval with the same corpus, while the preceding experiment measures memory reuse. Both modes use the same model configuration, traffic settings and checkpoint baseline/cleanup procedure. The real measurements are collected by fresh model investigations; no result is assumed.

```powershell
Set-Location D:\incident-zero
$ablationRoot = Join-Path (Get-Location) ('.build\knowledge-live-ablation-' + (Get-Date -Format 'yyyyMMddTHHmmss'))
$ablationSeed = Join-Path $ablationRoot 'seed'
New-Item -ItemType Directory -Path (Join-Path $ablationSeed 'knowledge') -Force | Out-Null
Copy-Item -LiteralPath knowledge\runbooks -Destination (Join-Path $ablationSeed 'knowledge\runbooks') -Recurse
Copy-Item -LiteralPath knowledge\services.yaml -Destination (Join-Path $ablationSeed 'knowledge\services.yaml')
$ablationBase = Join-Path $ablationRoot 'base.sqlite'
& .\.venv\Scripts\python.exe -m knowledge --root $ablationSeed --index $ablationBase build
if ($LASTEXITCODE -ne 0) { throw 'Ablation index build failed' }
$ablationCases = @(
    @{ Incident = 'payment-failure' },
    @{ Incident = 'container-stopped'; Service = 'recommendation' },
    @{ Incident = 'cache-unavailable' }
)
$ablationRows = @()
foreach ($case in $ablationCases) {
    foreach ($enabled in @('0', '1')) {
        $env:INCIDENT_ZERO_KNOWLEDGE = $enabled
        $caseId = 'knowledge-ablation-' + $case.Incident + '-' + $enabled + '-' + (Get-Date -Format 'yyyyMMddTHHmmss')
        $caseRoot = Join-Path $ablationRoot $caseId
        New-Item -ItemType Directory -Path $caseRoot | Out-Null
        $env:INCIDENT_ZERO_KNOWLEDGE_INDEX = Join-Path $caseRoot 'index.sqlite'
        $env:INCIDENT_ZERO_MEMORY_DIR = Join-Path $caseRoot 'memory'
        New-Item -ItemType Directory -Path $env:INCIDENT_ZERO_MEMORY_DIR | Out-Null
        Copy-Item -LiteralPath $ablationBase -Destination $env:INCIDENT_ZERO_KNOWLEDGE_INDEX
        $checkpointArguments = @{ Incident = $case.Incident; ReportId = $caseId }
        if ($case.ContainsKey('Service')) { $checkpointArguments.Service = $case.Service }
        & .\scripts\checkpoint2.ps1 @checkpointArguments
        $caseReport = Get-Content -LiteralPath (Join-Path 'reports' "$caseId\report.json") -Raw | ConvertFrom-Json
        $ablationRows += [PSCustomObject]@{
            incident = $case.Incident; knowledge_enabled = ($enabled -eq '1')
            component = $caseReport.root_cause.component; confidence = $caseReport.root_cause.confidence
            tool_calls = $caseReport.agent.tool_calls; seconds = $caseReport.agent.elapsed_s
            status = $caseReport.status; model = $caseReport.agent.model
            prompt_sha256 = $caseReport.agent.prompt_sha256; report = "reports/$caseId/report.json"
        }
        $ablationRows | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath .build\knowledge-live-ablation.json -Encoding utf8
    }
}
$ablationRows | Format-Table incident,knowledge_enabled,component,confidence,tool_calls,seconds,status
Remove-Item Env:\INCIDENT_ZERO_KNOWLEDGE_INDEX,Env:\INCIDENT_ZERO_MEMORY_DIR -ErrorAction SilentlyContinue
$env:INCIDENT_ZERO_KNOWLEDGE = '0'
```

Checkpoint 2 diagnoses and proposes; it does not establish executed recovery. Copy the six measured rows into the mentor's ablation table, retain the output JSON and reports, and describe ties/regressions alongside any gains. One pair per case is a small observational comparison; repeat with reversed order before claiming a stable benefit. The integration owner owns any necessary stack reset or further live investigation.

## Merge surface

Bring in `knowledge/`, `memory/`, the offline evaluation utility and tests, `docs/KNOWLEDGE.md`, this acceptance guide, package metadata and ignored local-store paths. Shared edits are the two optional graph nodes and their state/helper wiring, untrusted investigator/planner context, policy disagreement logging, additive report schema fields, report rendering and Control Room static files. Preserve the integration owner's response/approval graph changes when resolving shared files. No execution endpoints, detector behavior, fault-injection tools or live stack configuration are changed by this guide.

In particular, merge `agent/graph.py` and `agent/respond.py` together: both call the
same helper to add only `retrieve_context` and `remember` when enabled. Preserve
the current response tail and approval logic. Other agent edits are in
`knowledge_context.py`, `prompts.py`, `policy.py`, `reporting.py`, `state.py`,
`run.py` (report destination in state), and `replay.py` (honest fallback when an
old recording has no planner response). The schema changes add consultation
fields and their validation only. `tools/`, `faultctl/`, `action_api/` and
`detect/` are untouched. Generated SQLite indexes and memory JSON stay ignored;
build the index after installing the added `rank-bm25` dependency. No embedding
model or torch dependency is required.
