# INVOICE Mailbox Sample

- Generated at: `2026-04-06T03:09:28.251620-07:00`
- Sample size: `30` of `146` labelled messages

## Aggregate

- Phase 1 validation statuses: `{'success': 30}`
- Phase 2 scrub statuses: `{'partial': 25, 'failed': 5}`
- Phase 3 profile counts: `{'generic_invoice_update': 2, 'invoice_ready': 2, 'receipt_issued': 1}`

## Taxonomy Inputs

- Candidate vendor domains:
  - `robinhood.com`: `5`
  - `uber.com`: `4`
  - `statefarmservice.com`: `3`
  - `post.applecard.apple`: `2`
  - `sequoiaequities.com`: `2`
  - `google.com`: `2`
  - `service.paypal.com`: `2`
  - `mygoodtogo.com`: `1`
  - `notify.cloudflare.com`: `1`
  - `tm1.openai.com`: `1`
- Candidate subject phrases:
  - `statement ready`: `5`
  - `account statement`: `5`
  - `monthly statement`: `4`
  - `statement available`: `4`
  - `card statement`: `3`
  - `card statement ready`: `3`
  - `reservation confirmed`: `3`
  - `account statement available`: `3`
  - `statement changes form`: `2`
  - `account statement changes`: `2`
- Candidate scrubbed phrases:
  - `account statement`: `6`
  - `slobodan hajduk`: `5`
  - `monthly statement`: `4`
  - `dan latest`: `4`
  - `available dan latest`: `4`
  - `available dan`: `4`
  - `account statement available`: `4`
  - `statement available`: `4`
  - `insurance financial`: `3`
  - `financial services state`: `3`

## Top Sender Domains

- `robinhood.com`: `5`
- `uber.com`: `4`
- `statefarmservice.com`: `3`
- `post.applecard.apple`: `2`
- `sequoiaequities.com`: `2`
- `google.com`: `2`
- `service.paypal.com`: `2`
- `mygoodtogo.com`: `1`
- `notify.cloudflare.com`: `1`
- `tm1.openai.com`: `1`

## Top Subject Phrases

- `statement ready`: `5`
- `account statement`: `5`
- `monthly statement`: `4`
- `statement available`: `4`
- `card statement`: `3`
- `card statement ready`: `3`
- `reservation confirmed`: `3`
- `account statement available`: `3`
- `statement changes form`: `2`
- `account statement changes`: `2`
- `statement changes form crs`: `2`
- `changes form crs`: `2`

## Top Scrubbed Phrases

- `account statement`: `6`
- `slobodan hajduk`: `5`
- `monthly statement`: `4`
- `dan latest`: `4`
- `available dan latest`: `4`
- `available dan`: `4`
- `account statement available`: `4`
- `statement available`: `4`
- `insurance financial`: `3`
- `financial services state`: `3`
- `services state farm`: `3`
- `state farm insurance financial`: `3`

## Unresolved Patterns

- Sender domains without a Phase 3 profile:
  - `robinhood.com`: `5`
  - `uber.com`: `4`
  - `statefarmservice.com`: `3`
  - `post.applecard.apple`: `2`
  - `google.com`: `2`
  - `service.paypal.com`: `2`
  - `mygoodtogo.com`: `1`
  - `notification.capitalone.com`: `1`
  - `pgn.com`: `1`
  - `mail.santanderconsumerusa.com`: `1`
- Leading scrubbed lines from unresolved messages:
  - `View your individual account statement and additional account notices Your account statement and additional account notices are available Hi Dan, your latest individual account statement is now`: `2`
  - `Apple Card Customer: Slobodan Hajduk dan.hajduk@gmail.com You can view your balance or pay your bill by tapping Apple Card in the Wallet app. To view a PDF of the statement, tap Apple Card in the`: `2`
  - `View your billing information securely online. State Farm Insurance and Financial Services State Farm Insurance and Financial Services Hello, Dan. Your automated payment is scheduled soon. Your bill`: `2`
  - `Dear SLOBODAN D HAJDUK, Customer ID: 10182641 Your new Good To Go! monthly statement is ready to be downloaded at MyGoodToGo.com. Important: Please review your statement to ensure it is accurate. You`: `1`
  - `Pickup is at 5:20am from 6937 NE Ronler Way`: `1`
  - `Financial Privacy Notice and US User Privacy Statement Updates Hi Dan, we&#39;re writing to let you know that we&#39;ve updated our Financial Privacy Notice as well as our Robinhood US User Privacy`: `1`
  - `Google Fi Your monthly statement Here&#39;s a quick summary of your March 15 statement: Your total is $124.50 Auto-payment is scheduled for March 26, 2026. No need to remember to pay just make sure`: `1`
  - `Slobodan Hajduk - Your February account statement is available. View Online PayPal Your February account statement is available. Hi Slobodan Hajduk, Access your account statements quickly and easily.`: `1`
  - `View your statement now.`: `1`
  - `PGE Your bill is ready Service from: 02/11/2026 - 03/12/2026 Auto Pay amount: $127.10 Will be deducted: 04/06/2026 This bill is set up for Auto Pay Account: 1365113041 Service address: 6937 NE Ronler`: `1`

## Sample Highlights

- `19d563a8761029cf` `no_profile` from `mygoodtogo.com`: `Dear SLOBODAN D HAJDUK, Customer ID: 10182641 Your new Good To Go! monthly statement is ready to be downloaded at MyGoodToGo.com. Important…`
- `19d503bb43106e5d` `no_profile` from `robinhood.com`: `View your individual account statement and additional account notices Your account statement and additional account notices are available H…`
- `19d4880ddfc4c7f9` `no_profile` from `post.applecard.apple`: `Apple Card Customer: Slobodan Hajduk dan.hajduk@gmail.com You can view your balance or pay your bill by tapping Apple Card in the Wallet ap…`
- `19d1cea3cfc5f121` `no_profile` from `statefarmservice.com`: `View your billing information securely online. State Farm Insurance and Financial Services State Farm Insurance and Financial Services Hell…`
- `19d0db4e762a0cac` `generic_invoice_update` from `sequoiaequities.com`: `Dear Resident, Your current utility billing statement from YES Energy Management is attached as a PDF. Please direct any questions you may…`
- `19d0d549814edcb7` `invoice_ready` from `notify.cloudflare.com`: `Invoice ID IN-60317639 is due on March 20, 2026. Thank you for using Cloudflare. Cloudflare logo Your invoice is available. Thank you for u…`
- `19d08d332fdcae37` `no_profile` from `uber.com`: `Pickup is at 5:20am from 6937 NE Ronler Way`
- `19cf7b9ab01a2f11` `no_profile` from `robinhood.com`: `Financial Privacy Notice and US User Privacy Statement Updates Hi Dan, we&#39;re writing to let you know that we&#39;ve updated our Financi…`
