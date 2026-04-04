# Non-Amazon ORDER Regression Candidates

Use this list as a final regression set to make sure the ORDER flow is not overfit to Amazon-only layouts.

Selection goals:

- exclude Amazon senders and Amazon-branded subjects
- keep a mix of physical-goods, grocery, restaurant, travel, ticketing, and receipt-style orders
- prefer messages with strong transactional cues in subject/snippet

Recommended core set:

- `19d4a57678c79266` | `Your Instacart family order receipt`
  sender: `Instacart <orders@instacart.com>`
  reason: grocery receipt with itemized delivery/order language

- `19d4a320bca36b57` | `Your family order from Fred Meyer is confirmed for April 1`
  sender: `Instacart <orders@instacart.com>`
  reason: pre-delivery confirmation flow instead of final receipt

- `19d3f37013612fdc` | `Order Receipt`
  sender: `"Recreation.gov" <communications@recreation.gov>`
  reason: reservation-style receipt; less retail/Amazon-like structure

- `19d30f6a0b67b832` | `Order Confirmation: Tiësto`
  sender: `"Tiësto" <ticketsupport@taogroup.com>`
  reason: ticketing/event purchase confirmation

- `19c2b5e7594e7300` | `Your Costco order receipt`
  sender: `Costco Same-Day <no-reply@costco.com>`
  reason: same-day grocery receipt with delivery/order framing

- `19d46cacf0b44362` | `Order Confirmation for Dan from Sushi Zen`
  sender: `DoorDash Order <no-reply@doordash.com>`
  reason: restaurant order confirmation; useful for sparse/non-retail HTML

- `19c2b0d86187e3ca` | `Your Costco order is confirmed for February 04, 2026`
  sender: `Costco Same-Day <no-reply@costco.com>`
  reason: confirmation-style order before fulfillment

Optional secondary set:

- `19d2c286d43f19df` | `Order Receipt`
  sender: `"Recreation.gov" <communications@recreation.gov>`

- `19cc0ac1e94f9b29` | `Your Instacart family order receipt`
  sender: `Instacart <orders@instacart.com>`

- `19cb9a30a2a62acb` | `Order Confirmation: PDX Rated - Bound By Love`
  sender: `Tixr <no-reply@tixr.com>`

- `19cc0684412e7b3d` | `Your family order from Fred Meyer is confirmed for March 5`
  sender: `Instacart <orders@instacart.com>`

Receipt/subscription edge cases:

- `19d28fafe596f7cd` | `Samsung Checkout on TV - Subscription Payment Receipt`
  sender: `receipt.noreply@samsungcheckout.com`
  reason: subscription receipt; good boundary test for whether recurring billing belongs in `order`

- `19d3bbea84a53dee` | `Your receipt from Apple.`
  sender: `Apple <no_reply@email.apple.com>`
  reason: invoice/order-receipt hybrid; useful for category-boundary testing

- `19be290553b26c98` | `Your Google Play Order Receipt from Jan 21, 2026`
  sender: `Google Play <googleplay-noreply@google.com>`
  reason: digital subscription/order receipt boundary case
