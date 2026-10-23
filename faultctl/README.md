# Operator incident controls

Run `python -m faultctl list`, `inject <id>`, `reset`, or `status` from the
repository root. `inject --combo payment-failure,cpu-starve --svc recommendation`
applies both incidents, recording each operation separately. `--rate 50%`
changes the payment failure variant. Infrastructure incidents require an
allowlisted official service name through `--svc`; the cache incident selects
its own dependency. A root `STOP` file refuses injections and stops loop workers.
Reset remains available with STOP present.

`config.yaml` is JSON, which is also valid YAML; this avoids an extra runtime
dependency. Set `INCIDENT_ZERO_DEMO_DIR` to override the sibling demo directory.
Every Compose invocation explicitly selects demo image version `2.0.2`.

The official demo directory is read-only to this implementation. The first
mutation copies the original incident settings into `.pristine/`; all active
settings live in `.state/flags/`. An injection-only Compose overlay mounts that
directory read-only in the incident service. No original source or Compose file
is changed. Reset restores the active copy byte-for-byte and recreates that
service with the original official Compose configuration. These directories
and `runs/` are ignored by Git and must never be consumed by diagnostic tools.

Each injection journals its intent before the external operation, preserves
read-back and failure details, and retains enough information for retrying
reset. Reset cancels loop workers before restoring containers, verifies resource
limits and queueing discipline, and checks all services and telemetry endpoints.
`fault_state_clean` reports whether injected changes were removed;
`stack_ready` reports the separate readiness result. Exit zero requires both.
`reset --timeout 0` performs one readiness check without retrying. This is useful
for recording an unrelated stack failure without hiding it. `status` observes
new frontend trace IDs over 60 seconds; `status --traffic-seconds 0` skips that
observation for a quick readiness check. The service count is discovered from
the official Compose file (this tag's minimal file contains 21 services).

Restart loops run every 20 seconds and record their PID and a cumulative manual
restart count under their run directory. Docker's `RestartCount` counts automatic
policy restarts, not `docker restart`; evidence for this injector is changed
`StartedAt` plus the worker counter. Cancellation and a cross-process mutation
lock prevent an old worker restarting a service after reset.

Build the network helper with `python -m faultctl build-netem`. Its Dockerfile
contains Alpine and `iproute2`; the helper receives only `NET_ADMIN` in the
selected local service's network namespace. `up` and `down` provide the stack
lifecycle entrypoints for the repository scripts. `down` cancels workers and
clears injection state after Compose successfully stops and removes the stack.

The acceptance evidence in `BUILD_01.md` distinguishes observed behavior from
anything that could not be verified against the live stack.
