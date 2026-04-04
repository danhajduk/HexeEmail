# Email Processing Pipeline (ORDER Flow)

## Overview

This document defines the full pipeline for processing emails classified as `ORDER`.
The goal is to convert raw email data (HTML/text) into structured, reliable, and cost-efficient data.

---

## Pipeline Flow

### Phase 0 — Entry (Classification)

1. Run initial classifier on incoming email.
2. If `label != ORDER` → STOP.
3. If `label == ORDER` → continue.

---

### Phase 1 — Fetch & Normalize

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

   * `cleaned_text`
   * `links` (optional)
   * `metadata` (optional)

---

### Phase 3 — Profile Detection

8. Detect email profile using:

   * sender domain
   * subject
   * cleaned_text markers

9. Example profiles:

   * `amazon_order_confirmation`
   * `amazon_shipping_update`
   * `fedex_tracking_update`
   * `generic_order`

---

### Phase 4 — Pattern Engine

#### Known Profile

10. Load JSON pattern.
11. Run extraction rules.
12. Normalize extracted values.
13. Compute confidence score.

#### Unknown Profile

14. Send cleaned_text + metadata to AI.
15. Request:

* profile classification
* candidate JSON pattern

16. Validate JSON schema.

17. Run pattern on same email.

18. Compute confidence score.

19. Store pattern as:

* `patterns/draft/`
* or `patterns/probation/`

---

### Phase 5 — Validation

20. Validate extracted data:

* required fields present
* values properly formatted
* data consistency

21. Compute confidence score:

* range: `0.0 → 1.0`

---

### Phase 6 — Decision

22. If confidence HIGH:

* persist structured data
* trigger downstream actions

23. If confidence MEDIUM:

* optional AI fallback extraction
* mark as probation

24. If confidence LOW:

* reject
* log for review

---

### Phase 7 — Output & Actions

25. Store structured result:

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

26. Trigger:

* database updates
* tracking monitoring
* notifications
* automation workflows

---

## Key Design Principles

### 1. Scrubber is Mandatory

* Reduces token cost
* Improves accuracy
* Enables deterministic parsing

---

### 2. Profile-Based Parsing (Not Sender-Based)

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

AI responsibilities:

* classify email
* generate JSON pattern
* fallback extraction

AI must NOT:

* execute logic
* write code
* control system flow

---

### 4. Confidence-Driven Decisions

Every parse must:

* produce structured data
* include a confidence score
* meet minimum thresholds

---

### 5. Pattern Versioning

Treat patterns as versioned assets:

```
amazon_order_v1
amazon_order_v2
```

Never mutate blindly.

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

* Vendor-specific optimizations (Amazon, FedEx, UPS)
* Multi-email pattern validation
* Pattern auto-promotion from probation → active
* Cost-aware AI fallback thresholds
* Event-driven notifications

---

## Summary

This pipeline ensures:

* deterministic parsing when possible
* AI-assisted flexibility when needed
* cost-efficient processing
* maintainable and scalable architecture

---
