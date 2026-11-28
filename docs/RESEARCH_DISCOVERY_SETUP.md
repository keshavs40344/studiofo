# Research discovery setup

UPSC Studio supports free-first candidate discovery through Crossref and Wikipedia. An optional Brave Search provider can be enabled with an API key.

## Default providers

- **Crossref:** bibliographic metadata for indexed works. Discovery results are recorded with source tier `OTHER` until a reviewer checks the actual publisher and publication.
- **Wikipedia:** tertiary background material only. It must not be the sole support for legal, statistical, constitutional or current-affairs claims.
- **Brave Search (optional):** set `BRAVE_SEARCH_API_KEY` in the environment. Search snippets and dates remain unverified metadata.

Set `UPSC_STUDIO_CONTACT_EMAIL` to a contact email when using Crossref's polite API access.

## Dashboard workflow

1. Open a project.
2. In **Research & Evidence Ledger**, enter a topic or specific research question.
3. Select **Find Source Candidates**.
4. Open each source in its original publisher site and check its date, authority, methodology and relevance.
5. Create atomic claims and use the exact page/section and excerpt verification form only after human review.

For Current Affairs, the discovery endpoint uses the project's cutoff date and excludes results that are undated or later than the cutoff. For other categories, candidates are returned without a date filter unless one is supplied to the service.

## Important limitations

Discovery does not download complete documents, prove that a source supports a claim, or mark claims VERIFIED. Crossref metadata is not proof of peer review. The Brave provider is optional and requires a key. URL reachability and search snippets are not factual verification.
