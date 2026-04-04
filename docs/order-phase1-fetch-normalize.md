# ORDER Phase 1 Fetch And Normalize

The ORDER-only Phase 1 flow now lives in [src/providers/gmail/order_flow.py](/home/dan/Projects/HexeEmail/src/providers/gmail/order_flow.py).

It is triggered from the existing classified-email path only when the new label is `order`.

Current Phase 1 responsibilities:

- fetch the full Gmail message payload
- parse MIME structure, boundaries, and part inventory
- package raw `text/plain` and `text/html` bodies plus message headers into a typed fetch object
- normalize sender identity into canonical top-level fields while keeping raw headers for reference
- decode transfer-encoded body content with charset-aware byte decoding
- score decoded body quality and choose the preferred downstream body source
- attach selected body provenance and stage diagnostics for fetch, MIME parse, sender normalization, decode, selection, and validation
- compute deterministic hashes before any later scrubbing
- preserve explicit Gmail provider ids separately from the RFC `Message-ID` header
- attach normalization metadata and a `handoff_ready` indicator for Phase 2
- return one versioned normalized payload for later phases

Current non-goals:

- no scrubbing
- no deterministic extraction
- no profile matching
- no Phase 2 handoff side effects yet beyond producing the normalized object

Regression fixtures for this flow live in `tests/fixtures/gmail_phase1/`.
