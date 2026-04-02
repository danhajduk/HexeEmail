# Gmail Fetch, Status, And Storage

## Purpose

This document describes the current Gmail mailbox-status, manual fetch, and local storage behavior in the Email Node.

It covers:

- unread-count semantics
- manual fetch actions
- local SQLite storage
- retention behavior
- runtime API endpoints

## Mailbox Status

The node exposes Gmail mailbox status at:

- `GET /api/gmail/status`

Each account entry can include:

- account identity/state
- mailbox unread counters
- local message-store summary

Current unread counters:

- `Unread Inbox`
- `Unread Today`
- `Unread Yesterday`
- `Unread Last Hour`

## Unread Count Semantics

The counters intentionally do not all use the same Gmail search.

`Unread Inbox`:

- query: `is:unread in:inbox`
- purpose: unread messages still sitting in the inbox

`Unread Today`:

- query shape: `is:unread after:<today_start> before:<tomorrow_start>`
- purpose: unread mail received in the current local-day window

`Unread Yesterday`:

- query shape: `is:unread after:<yesterday_start> before:<today_start>`
- purpose: unread mail received in the prior local-day window

`Unread Last Hour`:

- query shape: `is:unread after:<one_hour_ago> before:<now>`
- purpose: unread mail received in the last rolling hour

Important behavior:

- the time-window counters are not restricted to `in:inbox`
- they count exact matched Gmail message IDs
- they do not rely on Gmail `resultSizeEstimate`

This means:

- `Unread Inbox` can be lower than `Unread Today`
- the time-window counters may include unread mail that has been moved out of the inbox

## Manual Fetch Actions

The dashboard Gmail section exposes these operator actions:

- `Fetch Initial Learning`
- `Fetch Today Email`
- `Fetch Yesterday Email`
- `Fetch Last Hour Email`

These call:

- `POST /api/gmail/fetch/initial_learning`
- `POST /api/gmail/fetch/today`
- `POST /api/gmail/fetch/yesterday`
- `POST /api/gmail/fetch/last_hour`

Current fetch query behavior:

`initial_learning`:

- fetches inbox mail for the last three months
- intended as the first population pass for local learning/classification workflows

`today`:

- fetches inbox mail from local midnight to now

`yesterday`:

- fetches inbox mail for the prior local calendar day

`last_hour`:

- fetches inbox mail for the last rolling hour

The fetch windows use the node local timezone.

## Local Storage

Fetched Gmail message metadata is stored locally in SQLite at:

- `runtime/providers/gmail/messages.sqlite3`

Current table:

- `gmail_messages`

Stored fields include:

- `account_id`
- `message_id`
- `thread_id`
- `subject`
- `sender`
- `recipients`
- `snippet`
- `label_ids`
- `received_at`
- `fetched_at`
- `raw_payload`

The store upserts by:

- primary key: `(account_id, message_id)`

That means repeated fetches update existing rows instead of duplicating them.

## Retention

Retention policy:

- keep the last six months of fetched messages
- prune older rows during store updates

The store summary returned through status includes:

- `total_count`
- `latest_received_at`
- `latest_fetched_at`

## Dashboard Usage

The Gmail dashboard status card currently displays:

- provider state
- account
- unread inbox
- unread today
- unread yesterday
- unread last hour
- stored emails
- last fetch

The Gmail action card:

- runs the manual fetch endpoints
- disables buttons while a fetch is in progress
- shows success/error notices
- merges the returned store summary back into the current React state

## Runtime Notes

The background Gmail status poll interval is configured through:

- `GMAIL_STATUS_POLL_INTERVAL_SECONDS`

Current default:

- `600` seconds
- 10 minutes

This background status poll updates unread counts and upserts the currently unread message metadata into the local SQLite store.

Manual fetch actions populate the SQLite message store.
