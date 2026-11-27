# Evidence integrity and human review boundary

## Rules enforced in the agent workflow

- A source record is a candidate bibliography entry, not proof that its contents support a claim.
- The source collector no longer manufactures example bibliography records from a topic keyword.
- The independent fact checker audits claims already present in the project ledger; it does not invent claims.
- The claim-to-source verifier does not promote claims based only on a source ID and a page/paragraph label.
- A claim can enter the `VERIFIED` state only after a reviewer explicitly submits a source excerpt, pinpoint reference, and reviewer label through the attestation workflow.
- Claims without that record remain `HUMAN_REVIEW_REQUIRED` or `UNSUPPORTED` and are excluded from the multi-pass safe factual narration list.
- Future-dated sources and conflict annotations continue to exclude claims.

## Attestation endpoint

`POST /api/projects/{project_id}/claims/{claim_id}/attest`

Required JSON fields:
- `source_id`
- `page_or_section`
- `evidence_excerpt`
- `reviewer_id` (audit label, not an authenticated identity)
- optional `ref_period`

The reviewer must inspect the original source and affirm that the excerpt supports the claim. The endpoint records the supplied attestation; it does not use an AI semantic entailment model to prove the excerpt supports the claim.

## Security and limitations

- The current local FastAPI endpoint does not authenticate reviewer identity. `reviewer_id` is an audit label supplied by the caller and can be spoofed by anyone who can reach the local API. Do not treat it as a cryptographic signature or account-level approval.
- The system stores the submitted excerpt and reviewer label in the claim ledger. Do not submit copyrighted source passages beyond what is necessary for review.
- Source discovery, original-document retrieval, semantic entailment checks, independent second-reviewer workflows, and cryptographically authenticated approvals remain separate work.
- This change intentionally fails closed. Empty source discovery or missing evidence can stop an agent run; that is preferable to fabricated research or unsupported claims being narrated as fact.
