# faultctl: mentor command card

`python -m faultctl` is the operator's injector/resetter. The agent cannot use its
ground-truth journal to diagnose. Run with exclusive ownership of the local demo.
`python -m faultctl list` lists shipped aliases; `status` checks readiness and
`reset` prints read-backs. Reset completion is not agent remediation credit.

| Ten practice families | Existing command after `python -m faultctl` |
|---|---|
| Payment charge failure | `inject payment-failure` |
| Intermittent cart | `inject cart-intermittent` |
| One product catalog failure | `inject catalog-one-product` |
| Recommendation memory leak | `inject recommendation-leak` |
| Ad high CPU / garbage collection | `inject ad-high-cpu` (optional `ad-gc`) |
| Homepage flood | `inject homepage-flood` |
| Container stopped / restarting | `inject container-stopped --svc recommendation` (optional `restart-loop`) |
| Cache unavailable | `inject cache-unavailable` |
| Network delay / loss | `inject network-latency --svc product-catalog --delay 800ms --loss 10` |
| CPU / memory starvation | `inject cpu-starve --svc recommendation` (optional `memory-starve`) |

These are command availability, not ten successfully diagnosed cases. Historical
live injection/read-back evidence is in [BUILD_01B](../BUILD_01B.md); diagnosis
coverage and failures are in [EVALUATION_NOTE.md](EVALUATION_NOTE.md). The existing
memory-starve preset can raise small service limits; measure actual pressure.

**Generic grammar lands in the fold; not yet implemented/verified here:**

```text
python -m faultctl inject flag --name <demo-flag-name> --variant <variant>
python -m faultctl inject stop|pause|restart-loop --svc <compose-service>
python -m faultctl inject cpu-starve --svc <compose-service> --cpus <quota>
python -m faultctl inject memory-starve --svc <compose-service> --mb <MiB>
python -m faultctl inject network-latency --svc <compose-service> --delay <duration> --loss <percent>
python -m faultctl inject network-loss --svc <compose-service> --loss <percent>
python -m faultctl inject combo <two individually targeted generic members>
python -m faultctl reset
```

The combo member serialization is not specified/verified in this snapshot; use
the folded `inject combo --help`, not an invented syntax. For a mentor request
to stop currency and add 300ms to product-catalog, after the fold these two
operator steps express the request without the old shared-target ambiguity:

```text
python -m faultctl inject stop --svc currency
python -m faultctl inject network-latency --svc product-catalog --delay 300ms --loss 0
python -m faultctl reset
```

Default existing netem includes loss, so `--loss 0` matters for pure delay. Generic
flags use any valid flag/variant from the demo at the operator boundary only;
never show control settings to the investigator. The fold must cover all Compose
services, read back every change, print the grammar in `list`, and make reset
detect/undo external faults as well as journalled ones. External-reset regression
is currently xfail. STOP blocks injection; explicit operator reset remains available.
