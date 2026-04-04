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
- update backend status/training reads and writes to use the DB-backed local model metadata
- keep the UI behavior unchanged except that `trained_at` and related model status come from SQLite-backed state
- make sure the main header model pill and training page both read the same persisted source of truth

## Task 106
Original task details:
- retire the legacy `training_model_meta.json` path after the DB migration is stable
- remove unnecessary runtime JSON writes for local model metadata
- keep the local model binary file if still needed, but stop using JSON for the model metadata state
