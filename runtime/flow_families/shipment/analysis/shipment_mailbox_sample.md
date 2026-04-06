# SHIPMENT Mailbox Sample

- Generated at: `2026-04-06T03:10:47.818503-07:00`
- Sample size: `30` of `586` labelled messages

## Aggregate

- Phase 1 validation statuses: `{'partial': 1, 'success': 29}`
- Phase 2 scrub statuses: `{'failed': 1, 'partial': 29}`
- Phase 3 profile counts: `{'delivered': 8, 'shipped': 5}`

## Taxonomy Inputs

- Candidate vendor domains:
  - `amazon.com`: `12`
  - `email.informeddelivery.usps.com`: `10`
  - `parcelpending.com`: `3`
  - `instacart.com`: `2`
  - `doordash.com`: `1`
  - `mg.homedepot.com`: `1`
  - `proxyvote.com`: `1`
- Candidate subject phrases:
  - `daily digest`: `10`
  - `ready view`: `10`
  - `parcel pending`: `3`
  - `ordinary azelaic acid`: `2`
  - `ordinary azelaic`: `2`
  - `azelaic acid`: `2`
  - `esp32-s3-box-3b development`: `2`
  - `kawaye meta quest`: `2`
  - `kawaye meta`: `2`
  - `meta quest`: `2`
- Candidate scrubbed phrases:
  - `mailpiece package`: `10`
  - `mailpiece inbound package arriving`: `10`
  - `2026 mailpiece package slobodan`: `10`
  - `slobodan mailpiece inbound package`: `10`
  - `package slobodan mailpiece`: `10`
  - `inbound package arriving`: `10`
  - `mailpiece package slobodan`: `10`
  - `inbound package`: `10`
  - `package slobodan mailpiece inbound`: `10`
  - `slobodan mailpiece`: `10`

## Top Sender Domains

- `amazon.com`: `12`
- `email.informeddelivery.usps.com`: `10`
- `parcelpending.com`: `3`
- `instacart.com`: `2`
- `doordash.com`: `1`
- `mg.homedepot.com`: `1`
- `proxyvote.com`: `1`

## Top Subject Phrases

- `daily digest`: `10`
- `ready view`: `10`
- `parcel pending`: `3`
- `ordinary azelaic acid`: `2`
- `ordinary azelaic`: `2`
- `azelaic acid`: `2`
- `esp32-s3-box-3b development`: `2`
- `kawaye meta quest`: `2`
- `kawaye meta`: `2`
- `meta quest`: `2`
- `pending cortland village`: `2`
- `daily reminder parcel`: `2`

## Top Scrubbed Phrases

- `mailpiece package`: `10`
- `mailpiece inbound package arriving`: `10`
- `2026 mailpiece package slobodan`: `10`
- `slobodan mailpiece inbound package`: `10`
- `package slobodan mailpiece`: `10`
- `inbound package arriving`: `10`
- `mailpiece package slobodan`: `10`
- `inbound package`: `10`
- `package slobodan mailpiece inbound`: `10`
- `slobodan mailpiece`: `10`
- `coming slobodan`: `10`
- `package slobodan`: `10`

## Unresolved Patterns

- Sender domains without a Phase 3 profile:
  - `email.informeddelivery.usps.com`: `10`
  - `parcelpending.com`: `2`
  - `amazon.com`: `2`
  - `doordash.com`: `1`
  - `instacart.com`: `1`
  - `proxyvote.com`: `1`
- Leading scrubbed lines from unresolved messages:
  - `Hi Slobodan, Just a friendly reminder that you have a Parcel Pending at Cortland Village. To avoid paying a storage fee please pick it up by 11:59 PM on 04/03/2026. Your access code is: 46062503 Your`: `2`
  - `COMING TO YOU SOON Hi, Slobodan! You have 1 mailpiece(s) and 0 inbound package(s) arriving soon. Saturday 4 April 2026 1 Mailpiece(s) 0 Package(s) Hi, Slobodan! You have 1 mailpiece(s) and 0 inbound`: `1`
  - `COMING TO YOU SOON Hi, Slobodan! You have 1 mailpiece(s) and 0 inbound package(s) arriving soon. Friday 3 April 2026 1 Mailpiece(s) 0 Package(s) Hi, Slobodan! You have 1 mailpiece(s) and 0 inbound`: `1`
  - `You can add items until your shopper checks out. Hi Dan, your family order from Fred Meyer is all set. Delivery address Delivery time 6937 Northeast Ronler Way, 2021 Today from 11:26am - 12:11pm`: `1`
  - `COMING TO YOU SOON Hi, Slobodan! You have 1 mailpiece(s) and 0 inbound package(s) arriving soon. Tuesday 31 March 2026 1 Mailpiece(s) 0 Package(s) Hi, Slobodan! You have 1 mailpiece(s) and 0 inbound`: `1`
  - `You are receiving this notification to educate you on important information related to one or more of your holdings. Details in this material may include investment strategy, performance tracking and`: `1`
  - `COMING TO YOU SOON Hi, Slobodan! You have 1 mailpiece(s) and 0 inbound package(s) arriving soon. Monday 30 March 2026 1 Mailpiece(s) 0 Package(s) Hi, Slobodan! You have 1 mailpiece(s) and 0 inbound`: `1`
  - `COMING TO YOU SOON Hi, Slobodan! You have 1 mailpiece(s) and 0 inbound package(s) arriving soon. Friday 27 March 2026 1 Mailpiece(s) 0 Package(s) Hi, Slobodan! You have 1 mailpiece(s) and 0 inbound`: `1`
  - `COMING TO YOU SOON Hi, Slobodan! You have 1 mailpiece(s) and 0 inbound package(s) arriving soon. Thursday 26 March 2026 1 Mailpiece(s) 0 Package(s) Hi, Slobodan! You have 1 mailpiece(s) and 0 inbound`: `1`
  - `COMING TO YOU SOON Hi, Slobodan! You have 2 mailpiece(s) and 0 inbound package(s) arriving soon. Wednesday 25 March 2026 2 Mailpiece(s) 0 Package(s) Hi, Slobodan! You have 2 mailpiece(s) and 0 inbound`: `1`

## Sample Highlights

- `19d5b8c171b3c821` `no_profile` from `doordash.com`: ``
- `19d5b50523d6f418` `delivered` from `amazon.com`: `Delivered: &quot;The Ordinary Azelaic Acid...&quot;`
- `19d5b1562b4dd7e0` `delivered` from `amazon.com`: `Delivered: &quot;ESP32-S3-BOX-3B Development...&quot;`
- `19d58e3c7129bac9` `no_profile` from `email.informeddelivery.usps.com`: `COMING TO YOU SOON Hi, Slobodan! You have 1 mailpiece(s) and 0 inbound package(s) arriving soon. Saturday 4 April 2026 1 Mailpiece(s) 0 Pac…`
- `19d583d108097dac` `delivered` from `amazon.com`: `Delivered: &quot;Kawaye for Meta Quest...&quot;`
- `19d57f846f2184d9` `shipped` from `amazon.com`: `Shipped: &quot;The Ordinary Azelaic Acid...&quot;`
- `19d577980397df6c` `shipped` from `amazon.com`: `Shipped: &quot;ESP32-S3-BOX-3B Development...&quot;`
- `19d57232da437c76` `shipped` from `amazon.com`: `Shipped: &quot;Kawaye for Meta Quest...&quot;`
