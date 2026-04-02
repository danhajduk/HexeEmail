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
