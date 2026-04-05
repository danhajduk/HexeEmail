# Email Processing Pipeline (ORDER Flow)

## Overview

This document defines the full pipeline for processing emails classified as `ORDER`.
The goal is to convert raw email data (HTML/text) into structured, reliable, and cost-efficient data.

Implementation status in this repo is marked inline:

- `[DONE]` implemented and exercised in code/tests
- `[PARTIAL]` partially implemented or implemented with a narrower scope than described here
- `[TODO]` still planned / not implemented yet

---

## Pipeline Flow

### Phase 0 — Entry (Classification)

Status: `[DONE]`

1. Run initial classifier on incoming email.
2. If `label != ORDER` → STOP.
3. If `label == ORDER` → continue.

---

### Phase 1 — Fetch & Normalize

Status: `[DONE]`

4. Fetch full email:

   * HTML body
   * text/plain (if available)
   * headers (from, subject, message-id)

5. Decode content:

   * Handle quoted-printable encoding
   * Normalize UTF-8
   * Fix artifacts:

     * `=3D` → `=`
     * `=C2=A9` → ©
     * broken line wrapping

---

### Phase 2 — Scrubber (Critical)

Status: `[DONE]`

6. Run scrubber on HTML or text:

   * Remove:

     * `<style>`, `<script>`, `<head>`
     * images and tracking pixels
     * navigation links (Your Orders / Account)
     * buttons (View order)
     * footer/legal sections
     * MIME artifacts (`------=_Part_...`)
   * Stop parsing at:

     * `Deals related to your purchases`
   * Normalize:

     * whitespace
     * line breaks

7. Output:

   * `cleaned_text` `[DONE]`
   * `links` (optional) `[DONE]`
   * `metadata` (optional) `[DONE]`

---

### Phase 3 — Profile Detection

Status: `[DONE]`

8. Detect email profile using:

   * sender domain
   * subject
   * cleaned_text markers

9. Example profiles:

   * `amazon_order_confirmation` `[DONE]`
   * `amazon_shipping_update` `[TODO]`
   * `fedex_tracking_update` `[TODO]`
   * `generic_order` `[PARTIAL]`

---

### Phase 4 — Pattern Engine

Status: `[PARTIAL]`

#### Known Profile

Status: `[DONE]`

10. Load JSON pattern.
11. Run extraction rules.
12. Normalize extracted values.
13. Compute confidence score.

#### Unknown Profile

Status: `[PARTIAL]`

14. Send cleaned_text + metadata to AI. `[TODO]`
15. Request: `[TODO]`

* profile classification
* candidate JSON pattern

16. Validate JSON schema. `[DONE]`

17. Run pattern on same email. `[TODO]`

18. Compute confidence score. `[TODO]`

19. Store pattern as: `[TODO]`

* `patterns/draft/`
* or `patterns/probation/`

---

### Phase 5 — Validation

Status: `[PARTIAL]`

20. Validate extracted data: `[PARTIAL]`

* required fields present
* values properly formatted
* data consistency

21. Compute confidence score: `[DONE]`

* range: `0.0 → 1.0`

---

### Phase 6 — Decision

Status: `[TODO]`

22. If confidence HIGH: `[TODO]`

* persist structured data
* trigger downstream actions

23. If confidence MEDIUM: `[TODO]`

* optional AI fallback extraction
* mark as probation

24. If confidence LOW: `[TODO]`

* reject
* log for review

---

### Phase 7 — Output & Actions

Status: `[PARTIAL]`

25. Store structured result: `[DONE]`

```json
{
  "profile": "amazon_order_confirmation",
  "order_number": "...",
  "status": "...",
  "items": [...],
  "total": "...",
  "confidence": 0.87
}
```

26. Trigger: `[TODO]`

* database updates
* tracking monitoring
* notifications
* automation workflows

---

## Key Design Principles

### 1. Scrubber is Mandatory

Status: `[DONE]`

* Reduces token cost
* Improves accuracy
* Enables deterministic parsing

---

### 2. Profile-Based Parsing (Not Sender-Based)

Status: `[DONE]`

Use:

```
sender + subject + content → profile
```

Not:

```
sender → parser
```

---

### 3. AI Generates Patterns, Not Code

Status: `[PARTIAL]`

AI responsibilities:

* classify email `[TODO]`
* generate JSON pattern `[PARTIAL]`
* fallback extraction `[TODO]`

AI must NOT:

* execute logic
* write code
* control system flow

---

### 4. Confidence-Driven Decisions

Status: `[PARTIAL]`

Every parse must:

* produce structured data `[DONE]`
* include a confidence score `[DONE]`
* meet minimum thresholds `[TODO]`

---

### 5. Pattern Versioning

Status: `[PARTIAL]`

Treat patterns as versioned assets:

```
amazon_order_v1
amazon_order_v2
```

Never mutate blindly. `[DONE]`

---

## System Mental Model

```
Email (raw)
→ Scrubber (clean signal)
→ Pattern Engine (deterministic extraction)
→ AI (fallback only)
→ Structured Data (usable)
```

---

## Recommended Directory Structure

```
email_node/
  patterns/
    active/
    draft/
    probation/
    archive/
  schemas/
    email_pattern.schema.json
  cleaners/
    scrubber.py
  parsers/
    pattern_engine.py
    router.py
    confidence.py
```

---

## Future Enhancements

* Vendor-specific optimizations (Amazon, FedEx, UPS) `[PARTIAL]`
* Multi-email pattern validation `[TODO]`
* Pattern auto-promotion from probation → active `[TODO]`
* Cost-aware AI fallback thresholds `[TODO]`
* Event-driven notifications `[TODO]`

---

## Summary

This pipeline ensures:

* deterministic parsing when possible
* AI-assisted flexibility when needed
* cost-efficient processing
* maintainable and scalable architecture

---
