## Task 077
Original task details:
- Ganil actions: Fetch Email for first learing.
- fetch yesterday day emails
- fetch last hour email
- Just btns for now

## Task 078
Original task details:
- create a DB that will store the fetched emails
- keep a limit of the last 6 months

## Task 079
Original task details:
- Fetch email for first teach: last 3 months
- fetch yesterday/today/last hour email
- use the local timezone for the time windows

## Task 080
Original task details:
- create a new page called training
- put a button under Spamhaus in dashboard
- make it look like the setup flow with the side bar and one card in the main content
- in the side bar have back button and manual classify button
- create a process to make the mail flat with sender, domain, recipient flags, subject, flags, body preview, and Gmail labels
- create enum labels for important, receipt, alert, bulk, and unknown variants
- set threshold to 0.6 first and make it configurable
- add local label, confidence, and manual classification fields to stored emails
- manual classify should pick random 40 unclassified or unknown mails and show them for labeling

## Task 081
Original task details:
- add TF-IDF and LogisticRegression models to the training flow
- use flow: flat email text -> TF-IDF -> LogisticRegression
- create Train Model button under manual classification
- train from existing manual classifications
- show training status in the main content while training
- add Semi Auto Classification button for the 20 oldest unclassified mails
- show semi-auto results for manual reclassification
- if classification changes, mark it as manual
- all manual classifications should use confidence 1.0

## Task 082
Original task details:
- normalize every email into a clean, stable flat text format for TF-IDF -> Logistic Regression
- use the same normalization for training, inference, retraining, and evaluation
- bump and persist a normalization_version in model metadata when normalization changes
- output format should include sender, domain, recipient flags, normalized subject, normalized flags, and cleaned body
- lowercase all normalized text fields and boolean tokens
- normalize sender email and sender domain
- replace raw recipient text with recipient flags and bucketed recipient count
- aggressively normalize subject prefixes and punctuation
- clean body by decoding entities, removing tags, replacing URLs with `url`, normalizing numbers to `number`, removing noise, truncating to a fixed preview length, and collapsing whitespace

## Task 083
Original task details:
- redesign the email classifier training pipeline around all-mail ingestion from `gmail_messages`
- exclude SENT, DRAFT, TRASH, and SPAM from training
- use manual labels as highest-trust samples, weighted local auto labels as secondary samples, and Gmail/rule bootstrap labels as weak supervision
- keep `unknown` out of training by default
- keep raw Gmail labels out of TF-IDF input text
- add Gmail weak-supervision mapping and bootstrap scoring with precedence rules
- build normalized weighted dataset rows and a dataset summary report
- train TF-IDF + LogisticRegression with sample weights
- save richer model metadata including mapping config, excluded labels, and dataset stats

## Task 084
Original task details:
- Implement user notifications for the new emails with the `action_required` classification
- include sender and subject
- for now we can include the confidence level during the debug stage
- Make the email notifications a separate re-usable function

## Task 085
Original task details:
- repeat Task 084 for the `order` classification

## Task 086
Original task details:
- add sender reputation storage based on the ratings/signals already persisted in the local db
- store sender email and sender domain level reputation data
- persist rating inputs, derived score, reputation bucket, and timestamps

## Task 087
Original task details:
- build a reusable sender reputation aggregation/update flow
- compute reputation from existing db ratings and checks when new mail arrives or ratings change
- keep the aggregation reusable by runtime, training, and ui code

## Task 088
Original task details:
- expose sender reputation through backend apis
- add sender reputation summary/detail responses with counts, reputation state, last seen, and contributing ratings
- align the api shape with current gmail status/dashboard patterns

## Task 089
Original task details:
- show sender reputation in the ui
- surface reputation state, rating/score, and supporting counts in gmail or training views
- make the reputation explanation inspectable by the operator

## Task 090
Original task details:
- use sender reputation in classification and notifications
- include sender reputation in local/runtime classification helper flows where helpful
- surface risky or low-reputation senders in notifications/debug outputs
- document operator-visible behavior for sender reputation

## Task 091
Original task details:
- change the initial Gmail learning fetch window from 3 months to 6 months
- align the initial fetch range with the existing 6 month local retention window
- update tests and docs that still reference the old 3 month range

## Task 092
Original task details:
- every hour at `00` minutes classify 100 newest unclassified emails
- run it in batch
- use the same flow as the existing button-triggered batch classification

## Task 093
Original task details:
- add an additional reputation per domain
- ignore mailbox-provider domains like gmail, hotmail, outlook, yahoo, icloud, and similar
- keep the extra domain reputation aligned with the existing sender reputation storage and aggregation flow

## Task 094
Original task details:
- make the reputation list grouped by domain
- make domain groups collapsible
- keep sender and domain summary data visible even when a domain group is collapsed

## Task 095
Original task details:
- add an option to manually rate senders and domains
- persist the manual rating in the reputation data model
- include manual ratings in the explanation and effective reputation calculation

## Task 096
Original task details:
- add an option to filter the reputation list by risk level
- support filtering by trusted, neutral, risky, and blocked
- keep the filtering compatible with the grouped and collapsible reputation list

## Task 097
Original task details:
- redesign the runtime prompt registration flow
- read the existing prompts on the AI node before registering local prompts
- send register requests only for prompts that are not present remotely
- if a remote prompt is outdated, retire it and register the new one based on the version in the local JSON
- keep prompt JSON files in a dedicated folder and have the registration flow scan that folder
- support the registration flow from the Runtime page button and from a once-per-week scheduled sync

## Task 098
Original task details:
- extract the current hardcoded prompt definition(s) into JSON
- keep the JSON file(s) in the dedicated prompt-registration folder used by Task 097

## Task 099
Original task details:
- on every new mail classified as `action_required` or `order`, use the `prompt.email.action_decision` prompt on ai
- possible actions:
  - `none` -> no action required
  - `notify` -> surface email to user (UI / HA / notification)
  - `summarize` -> generate summary via AI node
  - `track_shipment` -> extract and track delivery / shipment info
  - `flag_follow_up_needed` -> user likely needs to respond or take action
  - `flag_time_sensitive` -> deadlines, expiring links, delivery windows
  - `mark_priority` -> elevate importance / highlight
  - `human_review_required` -> uncertain, risky, or sensitive -> do not automate

## Task 100
Original task details:
- replace the previous user message for new `action_required` and `order` emails
- use the reply from the `prompt.email.action_decision` ai request
- make the notification/output more readable

## Task 101
Original task details:
- create a new dashboard screen for scheduled tasks
- use only one full-width card in it
- show the tasks in a table
- include the schedule and the last/next execution
- include any other runtime/scheduler data already available

## Task 102
Original task details:
- create a real backend schedule template system
- keep the schedule legend and scheduled task rows driven by the same backend definitions
- support the declared schedule names:
  - `daily`
  - `weekly`
  - `4_times_a_day`
  - `every_5_minutes`
  - `hourly`
  - `bi_weekly`
  - `monthly`
  - `every_other_day`
  - `twice_a_week`
  - `on_start`
- make next-run calculation part of the template system instead of scattered hardcoded helpers
- fix any mismatches between displayed schedule wording and actual backend next-run timestamps

## Task 103
Original task details:
- add SQLite-backed runtime settings storage instead of relying on scattered runtime JSON files for mutable runtime metadata
- create a reusable table for current runtime values/settings, suitable for timestamps, counters, feature flags, and structured JSON values
- keep the design compatible with the existing Gmail SQLite store unless a separate runtime SQLite file is clearly better

## Task 104
Original task details:
- move Gmail local model metadata from `training_model_meta.json` into SQLite
- include at least:
  - `trained_at`
  - `sample_count`
  - `train_count`
  - `test_count`
  - `test_accuracy`
  - normalization/version and any current metadata already returned by `training_model_status`
- add a migration/read-fallback so existing nodes with only the JSON metadata file still work

## Task 105
Original task details:
- define modular gateway architecture for outbound integrations
- introduce an `AiNodeGateway` as the single boundary for all outbound AI-node communication
- introduce an `EmailProviderGateway` as the single boundary for all outbound email-provider communication
- document the intended ownership split between orchestration code and gateway transport code before large refactors begin
- inventory every existing outbound AI-node and email-provider call path
- trace all current AI-node calls in `src/service.py`, `src/node_backend/providers.py`, and `src/node_backend/scheduler.py`
- trace all current Gmail or provider API calls under `src/providers/gmail/` and any related orchestration code
- produce a concrete migration map so no direct remote call path is left behind after the refactor
- implement `AiNodeGateway`
- move all AI-node HTTP concerns into the gateway, including target URL normalization, prompt sync, prompt review, review-due migration, and direct execution calls
- remove duplicated low-level AI-node HTTP logic from service orchestration code
- centralize AI kill-switch enforcement in `AiNodeGateway`
- the runtime AI switch must be checked inside the gateway before any outbound AI-node request is made
- if disabled, the gateway must exit early and guarantee that no AI-node request is sent
- update current callers to rely on gateway-enforced behavior rather than scattered direct checks where appropriate
- implement `EmailProviderGateway`
- move outbound provider-facing operations into the gateway, including fetches, full-message reads, OAuth/provider API calls, and related transport behavior
- keep provider orchestration outside the gateway, but make the gateway the only place where remote provider requests are executed
- add provider gateway disable support
- define and implement a provider-call gating mechanism in `EmailProviderGateway`
- ensure disabled provider calls exit cleanly before any network request is made
- keep the design extensible for future provider-specific switches or policy rules
- refactor orchestration layers to use gateways only
- update runtime handlers, background tasks, schedulers, and provider workflows to call `AiNodeGateway` and `EmailProviderGateway` instead of making direct remote calls
- remove or isolate any remaining direct HTTP usage that bypasses the new gateways
- add dependency-injected gateway wiring
- instantiate gateways in a clear composition point and inject them into the service/managers that need them
- avoid hidden global coupling so future AI or email providers can be added without rewriting core orchestration
- design gateway interfaces for future providers
- make the AI gateway extensible for additional AI backends or nodes
- make the email-provider gateway extensible for additional providers beyond Gmail
- keep provider-specific details behind gateway or adapter boundaries instead of leaking them across the service layer
- add regression tests for zero-contact disabled behavior
- verify that disabling AI calls results in zero outbound AI-node requests across runtime actions, background tasks, and scheduled flows
- verify that disabling provider calls results in zero outbound provider requests across fetch, read, and scheduled flows
- add tests that prove helper paths cannot bypass the gateways
- add gateway contract and integration-focused tests
- cover request construction, URL normalization, error mapping, and successful response handling for each gateway
- confirm orchestration code still behaves correctly when gateways return disabled/skip responses or remote failures
- update operator-facing UI and wording
- ensure runtime and provider controls reflect the gateway-based architecture clearly
- use labels and notices that make it obvious when AI-node calls or provider calls are disabled and being skipped
- update runtime and architecture documentation
- document `AiNodeGateway` and `EmailProviderGateway` as the canonical outbound integration boundaries
- update runtime docs to explain switch enforcement, extension patterns, and future-provider expectations
- remove old bypass paths and cleanup dead code
- delete obsolete direct-call helpers and duplicated guard logic once gateway migration is complete
- confirm there is a single supported outbound path for AI-node calls and a single supported outbound path for email-provider calls

Implementation sub-phases:
- Phase 1: integration inventory and boundary definition
  - inventory every current outbound AI-node call path in `src/service.py`, `src/node_backend/providers.py`, and `src/node_backend/scheduler.py`
  - inventory every current outbound provider/Gmail call path under `src/providers/gmail/` and related orchestration code
  - define which methods belong in `AiNodeGateway` and which belong in `EmailProviderGateway`
  - identify all existing bypass paths that must be removed or redirected
- Phase 2: prompt JSON location migration
  - move prompt JSON files out of `src/runtime_prompts/` into a runtime-owned prompt folder under the runtime area
  - update prompt-loading code so runtime prompt definitions are read from the new runtime folder location
  - add migration or bootstrap behavior so existing repos/nodes still get the prompt files in the new location without manual breakage
  - update any tests, docs, and configuration that still assume `src/runtime_prompts/`
  - keep prompt JSON handling consistent with the new gateway-based AI runtime ownership
- Phase 3: `AiNodeGateway` extraction
  - implement a dedicated `AiNodeGateway` module as the only supported boundary for outbound AI-node requests
  - move target URL normalization, prompt sync, prompt review, review-due migration, and direct execution calls into the gateway
  - remove duplicated low-level AI-node HTTP logic from service orchestration code
- Phase 4: centralized AI disable behavior
  - move the runtime AI disable enforcement into `AiNodeGateway`
  - guarantee that when AI calls are disabled, no AI-node HTTP request is sent from runtime actions, background tasks, helper paths, or scheduled flows
  - update callers to depend on gateway-enforced skip/deny behavior instead of scattered direct guards where appropriate
- Phase 5: `EmailProviderGateway` extraction
  - implement a dedicated `EmailProviderGateway` module as the only supported boundary for outbound provider requests
  - move provider-facing fetches, full-message reads, OAuth/provider API calls, and related network behavior into the gateway
  - keep provider orchestration outside the gateway while making the gateway the only place that performs remote provider requests
- Phase 6: provider disable behavior
  - add a provider-call gating mechanism in `EmailProviderGateway`
  - guarantee that when provider calls are disabled, no remote provider request is sent from fetch flows, full-message reads, polling, or scheduled flows
  - keep the design extensible for future provider-specific switches or policy rules
- Phase 7: orchestration migration
  - refactor runtime handlers, background tasks, schedulers, and provider workflows to use the two gateways only
  - add dependency-injected gateway wiring at a clear composition point
  - remove or isolate any remaining direct HTTP usage that bypasses the new gateways
- Phase 8: future-provider extensibility
  - shape the AI gateway so additional AI backends or nodes can be added later without rewriting orchestration
  - shape the provider gateway so additional email providers beyond Gmail can be added later without leaking provider-specific transport logic into the service layer
- Phase 9: verification and regression coverage
  - add regression tests proving disabled AI mode results in zero outbound AI-node requests across runtime actions, background tasks, helper paths, and scheduled flows
  - add regression tests proving disabled provider mode results in zero outbound provider requests across fetch, read, and scheduled flows
  - add gateway-level tests for request construction, URL normalization, error mapping, and successful response handling
  - verify prompt JSON loading works from the new runtime-owned prompt folder
- Phase 10: UI, docs, and cleanup
  - update operator-facing UI wording so AI-node and provider disable states are explicit and consistent with gateway behavior
  - update runtime and architecture documentation so `AiNodeGateway` and `EmailProviderGateway` are the canonical outbound boundaries
  - delete obsolete direct-call helpers and duplicated guard logic
  - confirm there is a single supported outbound path for AI-node calls and a single supported outbound path for email-provider calls

Acceptance criteria:
- all outbound AI-node requests flow through `AiNodeGateway`
- all outbound provider requests flow through `EmailProviderGateway`
- disabling AI calls guarantees zero outbound AI-node requests
- disabling provider calls guarantees zero outbound provider requests
- runtime prompt JSON files no longer live under `src/runtime_prompts/`
- prompt JSON loading, sync, and review behavior works from the new runtime-owned prompt location
- no direct orchestration-layer bypass remains for AI-node or provider transport calls

## Task 105
Original task details:
- update backend status/training reads and writes to use the DB-backed local model metadata
- keep the UI behavior unchanged except that `trained_at` and related model status come from SQLite-backed state
- make sure the main header model pill and training page both read the same persisted source of truth

## Task 106
Original task details:
- retire the legacy `training_model_meta.json` path after the DB migration is stable
- remove unnecessary runtime JSON writes for local model metadata
- keep the local model binary file if still needed, but stop using JSON for the model metadata state

## Task 107
Original task details:
- before sending an email to the AI action-decision flow, fetch the full Gmail message by `message_id`
- do this for the action-decision path instead of relying only on the locally stored normalized message/snippet view
- keep the fetch scoped to the target message so it does not disturb the existing batch fetch windows
- use the fetched full message as the source for the action-decision input build

## Task 108
Original task details:
- build a text-only email extraction path for the full-message fetch used by AI action decision
- prefer Gmail `text/plain` content when available
- if the message is HTML-only, convert the HTML body to readable plain text before sending to AI
- use that extracted text for the AI action-decision request instead of the current normalized classifier body text
- keep attachments out of the AI body text for now

## Task 109
Original task details:
- investigate this prompt-sync/read issue:
  - `Client error '400 Bad Request' for url 'http://127.0.0.1:9002/api/prompts/services/prompt.email.summarization'`
  - detail: `prompt_id is not registered`
- verify whether the sync flow should treat that response as "not configured" instead of a hard failure
- verify whether `prompt.email.summarization.json` is being scanned and registered correctly
- fix the sync behavior so missing prompt ids can still be registered cleanly
- if this exact `400` happens, treat it as "no prompt available" and register the prompt

## Task 110
Original task details:
- add a monthly scheduled runtime task
- this task should run task resolve and authorize with Core
- keep it visible in the scheduled tasks table with the proper schedule template/legend entry
- persist last/next execution state like the other scheduled runtime tasks

## Task 111
Original task details:
- update the action-decision shipment structure so `tracking_signals` is more detailed
- replace the current loose shipment payload with fields that explicitly cover:
  - current status
  - seller
  - carrier
  - order number
  - tracking number
- update the prompt JSON, node schema validation, and any persistence/notification formatting that reads these fields
- keep the action-decision output structured and schema-validated

## Task 112
Original task details:
- change the AI email prompt input shape so the mail is sent like:
  - `subject: <subject>`
  - `mail body:`
  - `<text only body>`
- use text-only body content for the AI request
- keep subject separated from body instead of blending everything into one generic normalized block
- apply this where AI email prompts are built, especially the action-decision path

## Task 113
Original task details:
- create a lightweight local-only shipment email scrubber for the Email Node
- this scrubber must NOT use AI
- this scrubber must only process emails when there is already an existing order in the local database
- keep it deterministic and cost-saving by skipping unnecessary parsing/model calls
- use existing local order/shipment records plus sender-domain matching
- do not build a generic email classifier or a broad scraper for all emails
- do not call OpenAI or any other provider in this flow

Existing local DB data model assumption:
- seller
- carrier
- order_number
- tracking_number
- domain
- last_known_status

Behavior requirements:
- only run for known shipment/order domains that are explicitly supported
- only run if there is already an existing matching order in the DB
- if there is no existing order match, skip processing entirely
- stay lightweight and deterministic
- do not infer unrelated orders across unrelated sellers/domains
- no AI fallback in this task

Core matching rule:
- only process an email if it can be associated with an existing order or shipment record

Important domain rule:
- if there is an order from Amazon and the email is from FedEx, do NOT check it by default
- if that Amazon order already has a FedEx tracking number or `carrier=FedEx`, then FedEx emails for that tracking number MAY be checked
- seller/source domain alone must not authorize unrelated carrier mail
- carrier mail is allowed only when that carrier is already linked to an existing order
- seller mail is allowed only for that seller/domain's existing orders

Examples:
- existing order: seller=amazon, domain=amazon.com, no carrier yet, no tracking yet
  - incoming email from `fedex.com` -> skip
- existing order: seller=amazon, domain=amazon.com, carrier=fedex, tracking_number=449044304137821
  - incoming email from `fedex.com` mentioning that tracking number -> process
- existing order: seller=amazon, domain=amazon.com, order_number=111-1234567-1234567
  - incoming email from `amazon.com` mentioning that order -> process
- no existing order at all
  - incoming email from `fedex.com` -> skip

Deliverables:
- add a lightweight local shipment email scrubber/reconciler service
- add deterministic domain and identifier matching rules
- add DB lookup/update flow for existing orders only
- add tests covering allowed and denied processing cases
- add docs for the local scrubber behavior and boundaries

Implementation requirements:
- create a service/module such as `local_shipment_email_scrubber.py` or `shipment_email_reconciler.py`
- inspect incoming email metadata and parsed text
- resolve sender domain
- extract candidate order/tracking references using lightweight local regex rules
- determine whether the email is eligible for local processing
- find an existing matching order/shipment record
- update status fields only when allowed

Keep it lightweight:
- allowed: simple regex, string normalization, exact or near-exact DB matching, deterministic domain allowlists/mappings
- not allowed: LLM calls, embeddings, fuzzy AI extraction, heavy NLP libraries, broad classification logic

Domain/source rules:
- implement explicit supported-domain handling for the first batch only
- examples may include:
  - `amazon.com`
  - `fedex.com`
  - `ups.com`
  - `usps.com`
  - `dhl.com`
  - `doordash.com`
- use a simple mapping layer:
  - sender domain -> source type
  - source type -> supported identifier types
- example source types:
  - seller
  - carrier

Eligibility gate:
- normalize sender domain
- determine source type
- search for an existing relevant order/shipment record
- if no relevant existing record exists, stop immediately and return `skipped`
- this gate is critical; the scrubber must be existing-order-only

Matching strategy priority:
- `tracking_number` exact normalized match
- `order_number + domain` exact normalized match
- `order_number + seller` exact normalized match

Safety rules:
- seller-origin email may match seller/domain-linked existing orders
- carrier-origin email may match only when the existing order already has the same carrier or the same tracking number
- do not attach a FedEx email to an Amazon order just because both mention shipping language
- do not create a new order from a carrier email in this task
- do not create a new order from a seller email in this task

Normalization helpers:
- domain: lowercase, trim
- seller/carrier names: lowercase canonical mapping
- order numbers: trim, uppercase if needed, comparison-safe normalized value
- tracking numbers: trim, uppercase, remove spaces/dashes when appropriate for comparison
- avoid a large DB redesign unless clearly needed

Candidate extraction:
- lightweight extraction only for:
  - tracking numbers
  - order numbers
  - status phrases
- suggested initial patterns:
  - Amazon order numbers like `111-1234567-1234567`
  - UPS tracking numbers beginning with `1Z`
  - common FedEx numeric tracking lengths
  - USPS common numeric patterns
  - DHL common numeric patterns

Status update behavior:
- when a valid existing match is found, allow updating:
  - `last_known_status`
  - `last_seen_at` if present
  - `status_updated_at` if present
  - `carrier` if missing and now confidently known
  - `tracking_number` if missing and confidently matched from a seller-origin email tied to the same existing order
- do not overwrite good data with weak guesses
- if there is ambiguity, skip

Return/result contract:
- `action`: `skipped | matched | updated | ignored`
- `reason_code`
- `matched_record_id`
- `matched_by`: `tracking_number | order_number_domain | order_number_seller`
- `sender_domain`
- `source_type`
- `extracted_order_number`
- `extracted_tracking_number`
- `status_update_applied`

Suggested reason codes:
- `unsupported_domain`
- `no_existing_order`
- `carrier_not_linked_to_existing_order`
- `tracking_mismatch`
- `order_mismatch`
- `ambiguous_match`
- `matched_existing_order`
- `updated_existing_order`

No creation behavior:
- do not create new order/shipment rows in this task
- update-only for already-existing records
- if no existing record matches, skip cleanly

Logging:
- log sender domain
- log source type
- log eligibility decision
- log match method
- log update applied or skipped reason
- avoid logging secrets or full sensitive payloads unnecessarily

Tests:
- existing Amazon order, Amazon email, matching order number -> allowed
- existing Amazon order, FedEx email, no linked FedEx carrier/tracking -> skipped
- existing Amazon order with linked FedEx tracking, FedEx email with same tracking -> allowed
- existing Amazon order with linked UPS tracking, FedEx email -> skipped
- no existing order, seller email -> skipped
- no existing order, carrier email -> skipped
- ambiguous match -> skipped
- unsupported domain -> skipped
- existing record matched by tracking number -> updates status
- existing seller email fills missing tracking number only when the order match is already established

Docs:
- describe that this is a local deterministic scrubber
- it is existing-order-only
- it does not use AI
- it does not create new orders
- carrier mail is only processed when the carrier is already linked to the order or tracking number

Constraints:
- keep code small and maintainable
- avoid refactoring unrelated systems
- do not redesign the entire email pipeline
- integrate cleanly with the current email node flow
- preserve current contracts unless a tiny extension is necessary

Definition of done:
- local scrubber exists and is wired into the email processing path
- it only processes emails for existing orders
- it respects seller/carrier domain safety rules
- it updates existing records deterministically
- it never calls AI
- it never creates new records in this task
- tests pass
- docs updated
