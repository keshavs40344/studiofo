# Deterministic specialist workers

The following executable workers are available in `upsc_studio.agents.workers` and can be registered by name through `default_worker_handlers()`:

- `topic_profile`: requires an explicit category and a cutoff date for current affairs; enables syllabus mapping only for UPSC.
- `coverage_audit`: detects declared concepts missing from supplied script text using normalized literal matching.
- `evidence_completeness_audit`: flags claims without source references or source dates; does not prove source support.
- `rights_asset_audit`: requires asset references, provenance and an allowed rights status.
- `release_gate`: aggregates gate results and human approval, but never authorizes public upload.

These are deterministic validation workers, not autonomous research or generative agents. They do not fetch external sources, write scripts, create images, render video, or publish content. They are intentionally conservative and return explicit blocked/review states when required input is absent.
