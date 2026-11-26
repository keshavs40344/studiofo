# Deterministic specialist workers

Executable workers are available in `upsc_studio.agents.workers` and can be registered by name through `default_worker_handlers()`.

- `topic_profile`: requires an explicit category and a cutoff date for current affairs; enables syllabus mapping only for UPSC.
- `coverage_audit`: detects declared concepts missing from supplied script text using normalized literal matching; semantic coverage still requires independent review.
- `evidence_completeness_audit`: flags claims without source references or source dates; metadata completeness does not prove that a source supports a claim.
- `rights_asset_audit`: requires asset references, provenance and an allowed rights status; it does not independently validate a licence.
- `release_gate`: aggregates supplied gate results and human approval, but never authorizes public upload.
- `build_quality_review_tasks`: builds a DAG that runs topic profiling, coverage, evidence metadata, rights metadata and release checks in dependency order.

## Execution

Use `create_default_scheduler(sqlite_connection)` from `upsc_studio.agents.runtime`, then pass the task list from `build_quality_review_tasks(...)` to `scheduler.run(workflow_id, tasks)`. A failed or review-required worker result blocks dependent tasks. The release gate remains blocked without human approval.

## Boundaries

These are deterministic validation workers, not autonomous research or generative agents. They do not fetch external sources, independently judge semantic claim support, write scripts, create images, render video, or publish content. Rights metadata is not a substitute for checking the actual licence terms.
