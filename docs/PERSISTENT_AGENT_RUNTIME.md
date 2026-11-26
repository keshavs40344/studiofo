# Persistent Agent Runtime

This module adds a real SQLite-backed task queue and deterministic DAG runner.

## Capabilities
- Persistent task rows and append-only event history.
- Idempotent enqueue keyed by workflow, task, handler, payload and caller input fingerprint.
- Dependency validation, cycle detection and downstream blocking.
- Explicit task state transitions and bounded retries for `TimeoutError` / `ConnectionError` only.
- Workflow checkpoints for resumable stage metadata.
- Import diagnostics for registry targets, including duplicate module targets.
- Sequential execution by default to avoid overloading CPU-only machines.

## Integration contract
The application must explicitly provide handler callables to `DependencyScheduler`. This module does not dynamically execute arbitrary registry entries, downloaded code, shell commands or user-provided strings. Handlers receive a dictionary payload and return JSON-serializable output.

## Important limits
This is a reusable runtime component, not yet wired into the existing ChapterPipeline or dashboard. The registry diagnostic reports importability and duplicate targets; it does not certify semantic correctness of an agent. A workflow is only operational when the app registers tested handlers and invokes the scheduler.
