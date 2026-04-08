# Sender Reputation Behavior

Sender reputation is computed from the local Gmail message store and currently uses these persisted signals:

- local classification counts
- Spamhaus clean results
- Spamhaus listed results

Operator-visible behavior:

- Gmail dashboard shows sender/domain reputation counts and the most recent reputation records
- Training view shows the same sender reputation summary and lets the operator inspect one sender/domain in place
- action-required and order notifications now include sender reputation state and rating when reputation data exists
- AI-node email classification requests now include sender reputation state/rating context for the sender when available

Current reputation states:

- `trusted`
- `neutral`
- `risky`
- `blocked`

Current scoring notes:

- positive operational labels increase reputation
- newsletter/marketing classifications decrease reputation
- Spamhaus listed results strongly reduce reputation and force the `blocked` state

Current gap notes:

- there is currently no dedicated semantic sender/domain tag such as `probably_financial`
- there is currently no explicit domain heuristic that boosts future classification toward `financial`
- the current manual sender/domain controls are reputation overrides, not mail-type hints

Future planning reference:

- [training-and-sender-reputation-future-features.md](/home/dan/Projects/HexeEmail/docs/training-and-sender-reputation-future-features.md)

This is a node-owned implementation detail and can be adjusted later as more sender-quality signals are added.
