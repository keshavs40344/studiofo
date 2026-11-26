# Persistent Agent Runtime

This module provides a SQLite-backed task queue and deterministic dependency-graph scheduler.

## Implemented
- Persistent task rows and append-only event history.
- Idempotency keys include workflow/task identity, agent and handler, input fingerprint, payload, dependency list, required flag, retry limit and retry-safety declaration.
- Dependency validation, cycle detection and downstream blocking.
- Worker-level FAILED, BLOCKED, REVIEW_REQUIRED and SKIPPED results propagate to scheduler task states.
- Crash-interrupted RUNNING tasks are quarantined as REVIEW_REQUIRED; the runtime does not replay possible side effects automatically.
- Transient retries are allowed only when a TaskSpec explicitly declares retry_safe=true.
- A persisted RETRY_WAIT task is not resumed after restart unless the current TaskSpec declares retry_safe=true.
- Workflow checkpoints and import diagnostics for registry targets.
- Sequential execution by default for CPU-limited local machines.
- create_default_scheduler(conn) wires the deterministic audit workers into the runtime.

## Integration contract
The application must explicitly provide handler callables to DependencyScheduler or use create_default_scheduler. Handlers receive a dictionary payload and should return JSON-serializable output. Handlers with external side effects must not be marked retry_safe unless they implement idempotency or reconciliation.

## Safety and limitations
This runtime is not yet integrated into the existing ChapterPipeline or dashboard. It does not automatically fetch research, generate scripts, render media or upload content. Registry importability is not proof of agent quality. A workflow is operational only when the application invokes it with tested handlers and real project data.

## Recovery
A task found RUNNING after a process restart is moved to REVIEW_REQUIRED. An operator must inspect logs and external side effects before deciding how to resume it. The runtime intentionally does not offer blind automatic replay.
