# Training And Sender Reputation Future Features

This document captures future-feature planning for the Gmail training flow and sender-reputation system. It is intentionally documentation-only work. No behavior in this document is implemented by this task.

The goal is to preserve the current design detail, record the current status clearly, and define future feature directions before code changes begin.

## Status Report

Status as of April 6, 2026:

- Gmail training already supports:
  - manual training batch loading from stored Gmail messages
  - manual per-message label assignment
  - semi-auto review batches driven by the local classifier
  - TF-IDF plus LogisticRegression local model training
  - normalized flat-text rendering for training and inference
  - sender-reputation visibility from the training experience
- Sender reputation already supports:
  - persisted sender reputation records derived from local Gmail data
  - sender email, sender domain, and business-domain reputation entities
  - grouped sender-reputation UI by domain
  - summary/detail reputation APIs
  - manual numeric reputation overrides for sender and domain entities
  - reputation-aware notification context
- Current manual operator controls include:
  - per-message training labels such as `financial`
  - sender/domain/business-domain manual reputation actions:
    - `Mark Trusted`
    - `Mark Neutral`
    - `Mark Risky`
    - `Block`
- Current gap relevant to this planning request:
  - there is no dedicated semantic sender/domain tag such as `probably_financial`
  - there is no domain heuristic that explicitly boosts future classification toward `financial`
  - reputation overrides are numeric trust/risk adjustments, not label priors or family hints

Current behavior references:

- [task-details.md](/home/dan/Projects/HexeEmail/docs/task-details.md)
- [sender-reputation-behavior.md](/home/dan/Projects/HexeEmail/docs/sender-reputation-behavior.md)
- [operations.md](/home/dan/Projects/HexeEmail/docs/operations.md)
- [api-map.md](/home/dan/Projects/HexeEmail/docs/api-map.md)

## Current State To Preserve

Any future implementation should preserve these current behaviors and design assumptions unless a later task explicitly changes them:

- training remains grounded in stored Gmail messages rather than an external training-only dataset
- manual labels remain the highest-trust operator signal
- `financial` continues to exist as a message-level training label
- sender reputation remains reusable across runtime, training, and operator UI flows
- sender/domain/business-domain reputation records remain inspectable and grouped by domain
- manual reputation remains explainable to the operator
- future heuristics must not silently erase or override the operator’s explicit per-message manual classifications

## Future Feature A: Manual Domain Tag In Sender Reputation

### Goal

Add a semantic manual domain tag in Sender Reputation so an operator can mark a sender domain or business domain as likely associated with financial mail without needing to manually label many individual messages first.

### Proposed Operator-Facing Tag

Primary candidate:

- `probably_financial`

Possible future expansion set:

- `probably_financial`
- `probably_order`
- `probably_shipment`
- `probably_security`
- `probably_newsletter`

This document only proposes `probably_financial` as the first future feature.

### Why The Existing Manual Rating Is Not Enough

The current manual rating actions are trust/risk controls:

- `Mark Trusted`
- `Mark Neutral`
- `Mark Risky`
- `Block`

Those controls help with sender quality and notification posture, but they do not express a semantic classification prior. A trusted sender can still send non-financial mail, and a risky sender can still send financial mail. The future tag should therefore be modeled separately from reputation state.

### Proposed Data Model Direction

Add a sender/domain semantic tagging layer that lives alongside sender reputation, not inside the current numeric reputation field.

Candidate shape:

- entity scope:
  - `email`
  - `domain`
  - `business_domain`
- semantic tag:
  - `probably_financial`
- source:
  - `manual_operator`
- confidence:
  - fixed operator confidence such as `1.0`, or omitted if semantic tags are boolean
- note:
  - optional operator note
- timestamps:
  - created_at
  - updated_at
- actor metadata:
  - optional future field if operator identity is later added

Recommended storage rule:

- keep semantic tags in a separate persisted structure from reputation score inputs
- do not overload `manual_rating`
- do not treat semantic tags as Spamhaus-like reputation evidence

### Proposed UI Direction

Add this in Sender Reputation detail view for `domain` and `business_domain` entities:

- a semantic tag section next to or below Manual Rating
- action button:
  - `Mark Probably Financial`
- clear action:
  - `Clear Financial Tag`
- optional note:
  - reuse the current operator note pattern if useful

Suggested operator copy:

- "Use semantic tags to hint likely mail type. This does not replace manual per-message labels."

### Proposed API Direction

Possible future API additions:

- `POST /api/gmail/reputation/manual-tag`
- `DELETE /api/gmail/reputation/manual-tag`
- include semantic tags in:
  - reputation detail response
  - reputation summary row when relevant
  - training status payload if training/classification needs the hints

### Behavioral Rules

- the tag should only apply to `domain` and `business_domain` by default
- `email`-level tagging can be deferred unless a later need appears
- the tag should not rewrite historical classifications
- the tag should not silently mark messages as `financial`
- the tag should only provide a future hint to classification/review flows
- the tag must be visible and reversible in the UI
- the tag must be included in explanation/diagnostic payloads whenever it affects a future classification decision

### Risks

- over-biasing a broad domain that sends mixed-content mail
- confusing trust/risk reputation with semantic label priors
- hiding true classification uncertainty from the operator

### Safeguards

- keep the feature inspectable and reversible
- prefer `business_domain` over raw sender subdomain when that better reflects the real entity
- preserve manual per-message labels as stronger than domain tags
- log when a domain semantic tag contributed to a predicted result

## Future Feature B: Domain Heuristic That Boosts Future Classification Toward Financial

### Goal

Use domain-level evidence to increase the likelihood that future unclassified messages from certain domains are reviewed or predicted as `financial`, without turning the domain into a hard rule.

### Intent

This is a boost heuristic, not an automatic hard classification rule.

The system should behave like:

- "messages from this domain may be financial"

not like:

- "all messages from this domain are financial"

### Recommended Signal Sources

Potential future financial-prior signals:

- manual `probably_financial` domain tag
- repeated manual message labels of `financial` for the same domain
- repeated `invoice` or `financial` labels for the same business domain
- stable sender naming patterns associated with financial institutions
- future family-extraction evidence from the financial flow

### Recommended Heuristic Layers

Layer 1: explicit operator semantic tag

- strongest domain-level semantic prior
- should outweigh purely derived heuristics

Layer 2: observed manual-message label history

- if a business domain has enough manual `financial` examples, it can earn a derived financial prior

Layer 3: weaker observational evidence

- repeated non-manual local predictions may contribute, but should be weighted below manual operator evidence

### Proposed Classification Use Cases

The future heuristic could influence:

- ranking of messages selected for manual review
- tie-breaking or prior weighting in local classification
- semi-auto review suggestions
- operator diagnostics explaining why a message was proposed as `financial`

It should not immediately change:

- historical stored labels
- sender reputation state
- notification severity on its own

### Recommended Implementation Direction

Candidate approach:

1. compute a domain-level financial prior score
2. inject that prior into the local classification helper before final label choice
3. expose the contribution in diagnostics
4. keep the final decision overrideable by per-message manual review

Possible strategies:

- adjust class scores after model prediction
- add heuristic post-processing before final label selection
- use the domain prior to prioritize messages into a review queue rather than changing the predicted label directly

The safest starting version is:

- affect review prioritization and explanation first
- only later consider score-level prediction adjustments

### Precedence Rules

Recommended future precedence:

1. per-message manual label
2. explicit domain semantic tag
3. strong manual-history-derived domain prior
4. model prediction
5. weak heuristic evidence

### Explainability Requirements

If the heuristic contributes to a result, the operator should be able to inspect:

- which domain/business-domain signal fired
- whether the signal was manual or derived
- how many supporting examples exist
- whether the heuristic boosted review priority only or changed the suggested label

### Risks

- false positives for mixed-purpose domains
- overfitting to broad business domains
- hidden drift where the model starts depending too much on one domain clue
- classification loops if auto-generated labels later reinforce the same heuristic

### Safeguards

- use manual labels as the main source of domain-prior promotion
- require minimum-support thresholds for derived domain priors
- do not let auto-only history create a strong domain prior by itself
- keep an operator-visible explanation trail
- allow a future neutralizing override if a domain sends mixed financial and non-financial mail

## Proposed Status Definitions For The Two Features

These future features should be tracked independently.

### Manual Domain Tag

- current status: not implemented
- documentation status: planned
- code status: no storage, no API, no UI semantic tag support
- nearest current substitute: manual reputation rating and manual per-message `financial` labels

### Financial Domain Heuristic

- current status: not implemented
- documentation status: planned
- code status: no explicit domain-level `financial` prior exists today
- nearest current substitute: repeated manual message labels can indirectly improve future training data, but there is no domain-prior heuristic layer

## Suggested Future Task Breakdown

Recommended future doc-first task sequence:

1. document the semantic tag model and operator behavior before implementation
2. add persistence and API support for manual sender/domain semantic tags
3. expose the manual domain tag UI in Sender Reputation
4. add diagnostics showing when a semantic domain tag influences future classification
5. add a derived domain-level `financial` prior model from manual-label history
6. apply the domain prior first to review prioritization
7. evaluate whether score-level classification boosting is safe enough to enable later

## Acceptance Criteria For Future Implementation Work

The future implementation should be considered complete only when:

- semantic domain tags are persisted separately from reputation ratings
- operators can set and clear `probably_financial` on supported domain entities
- the UI clearly distinguishes trust/risk reputation from semantic mail-type hints
- any domain-level financial heuristic is explainable and reversible
- manual per-message labels remain the strongest signal
- tests cover domain tagging, persistence, API exposure, UI behavior, and heuristic precedence

## Broader Future Backlog From `New_task.txt`

The current `docs/New_task.txt` backlog also contains broader future-feature planning beyond sender reputation. That file currently has duplicate task numbers and one partially interrupted entry, so this section normalizes the unique future-feature themes without changing implementation behavior.

These items are still future work only.

### Multi-Family Pipeline Evolution

This backlog theme comes from Task 347 and should remain part of the long-term roadmap for the multi-family email platform.

Planned areas:

- Family reassignment after initial flow resolution
  - support `initial_family` vs `resolved_family`
  - allow reassignment only when extraction evidence is strong enough
  - keep full diagnostics and traceability
  - use accept-only gating so unsafe relabeling does not occur silently
- Smart family tree evolution
  - learn relationships between families such as `order -> shipment`
  - detect subtypes automatically
  - promote generic templates into more specialized families
  - cluster similar patterns across vendors
- Probation intelligence improvements
  - auto-refine weak templates
  - identify recurring missing-required-field patterns
  - suggest template updates
  - track failure patterns across emails
- Cross-family linking
  - link `order -> shipment -> invoice -> action_required`
  - build a shared entity graph across order ids, account ids, and similar identifiers
  - update existing records instead of always creating duplicates
- Priority and urgency scoring
  - especially for `action_required` and `security`
  - model urgency levels and consequence severity
  - influence notification behavior in a controlled way
- Duplicate and event suppression
  - avoid duplicate notifications
  - detect repeated updates without meaningful changes
  - use stable event deduplication keys
- Sensitive flow handling
  - special handling for security mail
  - account verification flows
  - payment actions
  - stricter decision policies
- Tracking integration
  - optional external tracking providers
  - polling vs webhook models
  - cost control and rate limiting
- Heuristic pack evolution
  - improve early signal detection
  - learn which patterns matter over time
  - split heuristics by subtype
- Model feedback loop
  - use pipeline outputs to improve classification
  - identify misclassified cases
  - support human-in-the-loop correction

Current status:

- documentation status: planned
- implementation status: not implemented as a unified roadmap system
- nearest current substitute: family-specific pipeline docs and the existing planned-family references

### Adaptive Signal Learning And Suggestion System

This backlog theme comes from the remaining `New_task.txt` items and describes a future learning-assistance layer for profile detection and signal maintenance.

#### 1. Adaptive Signal Suggestion System

Future goal:

- observe successful and failed processing results
- generate structured improvement suggestions for profile signals
- keep suggestions separate from live production configs

Planned signal sources:

- subject text
- scrubbed body text
- sender domain
- sender display name
- extracted fields
- link text and URLs

Current status:

- documentation status: planned
- implementation status: not implemented

#### 2. Signal Observation Logging

Future goal:

- record structured signal evidence during Phase 3 to Phase 5 execution

Planned captured data:

- profile id
- classification confidence
- subject tokens
- high-weight body tokens
- sender domain
- extracted-field presence
- decision outcome such as accept, probation, or reject

Requirements to preserve:

- avoid excessive raw text logging
- log meaningful tokens only
- support both successful and failed/missed matches

Current status:

- documentation status: planned
- implementation status: not implemented

#### 3. Signal Aggregation Engine

Future goal:

- aggregate observed signals across messages per profile and rank recurring patterns

Planned outputs:

- candidate subject terms
- candidate body anchor terms
- candidate sender domains
- candidate field-presence patterns

Planned metrics:

- supporting sample count
- success correlation
- failure correlation
- signal frequency

Current status:

- documentation status: planned
- implementation status: not implemented

#### 4. Structured Signal Suggestions

Future goal:

- convert aggregated evidence into structured suggestion objects

Planned suggestion shape:

- `profile_id`
- `signal_type`
- `candidate_signal`
- `supporting_samples`
- `success_correlation`
- `failure_correlation`
- `suggested_weight_adjustment`

Suggestion rules to preserve:

- require thresholds such as minimum support and minimum success correlation
- avoid generic/common phrases
- rank suggestions in a reviewable way

Current status:

- documentation status: planned
- implementation status: not implemented

#### 5. Negative Signal And Conflict Detection

Future goal:

- detect signals that correlate with incorrect or conflicting classifications

Examples:

- `cancelled` conflicting with confirmation profiles
- `verify account` conflicting with order profiles

Planned outputs:

- candidate negative signals
- candidate conflict pairs
- confidence penalty suggestions

Current status:

- documentation status: planned
- implementation status: not implemented

#### 6. Manual Review Workflow For Signal Suggestions

Future goal:

- provide an operator workflow to inspect, approve, reject, and optionally edit learned signal suggestions before production use

Rules to preserve:

- only approved signals can be promoted
- rejected signals should not be re-suggested repeatedly without new evidence

Current status:

- documentation status: planned
- implementation status: not implemented

#### 7. Signal Quality Filters And Noise Suppression

Future goal:

- prevent low-quality suggestions from polluting the review queue

Planned filter rules:

- exclude common greetings
- exclude footer/legal phrases
- exclude high-frequency generic tokens
- require contextual relevance through co-occurrence with stronger signals

Current status:

- documentation status: planned
- implementation status: not implemented

#### 8. Reporting For Signal Learning Effectiveness

Future goal:

- measure whether approved signal changes actually improve profile detection quality

Planned metrics:

- profile detection accuracy change
- reduction in misclassification
- confidence distribution change
- false-positive and false-negative trends

Current status:

- documentation status: planned
- implementation status: not implemented

#### 9. Configuration For Adaptive Learning Behavior

Future goal:

- expose deployment-level controls for learning behavior

Example config controls:

- `enable_signal_learning`
- `min_supporting_samples`
- `min_success_correlation`
- `max_suggestions_per_cycle`
- `require_manual_approval`

Current status:

- documentation status: planned
- implementation status: not implemented

## GitHub Backlog Mapping

Recommended GitHub tracking should mirror these unique roadmap items rather than the raw duplicate numbering in `docs/New_task.txt`.

Normalized future-feature groups:

1. manual domain semantic tag in Sender Reputation
2. domain heuristic to boost future classification toward `financial`
3. multi-family future-features roadmap
4. adaptive signal suggestion system
5. signal observation logging
6. signal aggregation engine
7. structured signal suggestions
8. negative signal and conflict detection
9. manual review workflow for signal suggestions
10. signal quality filters and noise suppression
11. reporting for signal learning effectiveness
12. configuration for adaptive learning behavior
