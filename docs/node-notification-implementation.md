# Node Notification Implementation

This repo now implements the node-side half of the Core MQTT notification proxy contract documented in:

- `docs/Core Docs/nodes/node-notification-mqtt-contract.md`
- `docs/Core Docs/mqtt/notifications.md`

## Current implementation

Trusted nodes publish user-facing notification requests to:

- `hexe/nodes/<node_id>/notify/request`

Core publishes request results back to:

- `hexe/nodes/<node_id>/notify/result`

The reusable sender lives in:

- `src/service.py` -> `NodeService.send_user_notification(...)`

The MQTT publish and result-subscribe support lives in:

- `src/mqtt.py`

## Current notification triggers

The first repo-side notification implementation is wired to Gmail fetch scheduler state transitions:

- success: node MQTT runtime connects to Core on startup
- success: node MQTT runtime reconnects to Core after a disconnect
- warning: Gmail scheduling pauses because Gmail is disabled
- warning: Gmail scheduling pauses because no eligible Gmail account is connected
- error: Gmail fetch scheduler loop raises an exception
- back online: Gmail fetch scheduling recovers after a warning or error state

## Delivery defaults

Current node requests use:

- `kind=event`
- `targets.broadcast=true`
- `targets.external=["ha"]`

Severity and urgency mapping:

- warning -> `severity=warning`, `urgency=actions_needed`
- error -> `severity=error`, `urgency=urgent`
- back online -> `severity=success`, `urgency=notification`

Each notification also includes a dedupe key and a node-scoped source component so Core can apply its normal dedupe and bridge behavior.
