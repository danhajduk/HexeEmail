# Core Compatibility Checklist

The email node expects the following Core conditions for Phase 1:

- `email-node` is present in `SYNTHIA_NODE_ONBOARDING_SUPPORTED_TYPES`
- `POST /api/system/nodes/onboarding/sessions` is reachable from the node
- `GET /api/system/nodes/onboarding/sessions/{session_id}/finalize` is reachable from the node
- Core approval UI is reachable by operators through the returned `approval_url`
- the activation payload returns a non-loopback `operational_mqtt_host`
- the MQTT host and `operational_mqtt_port` are reachable from the node runtime
- trust-status signaling remains available at `GET /api/system/nodes/trust-status/{node_id}`

If Core still uses the default supported node type list, add `email-node` before attempting onboarding.
