# Shared Email Pipeline Core

The shared email pipeline core is the first migration seam for multi-flow processing.

Current scope:

- shared orchestration for Phase 2 through Phase 7
- flow-family identity carried with the pipeline result
- family config loaded from one shared entry point
- flow-specific logic remains injected as hooks

Current flow families:

- `order`
- `action_needed`

Shared family entry point:

- [src/email_node/shared_pipeline_core/families.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/families.py)

Current family config responsibilities:

- scrub heuristic pack reference
- profile detector pack reference
- template directory
- probation template directory
- probation state directory
- validation policy reference
- decision policy reference
- action router policy reference
- output schema family

Current ORDER integration:

- [src/email_node/pipeline/order_flow.py](/home/dan/Projects/HexeEmail/src/email_node/pipeline/order_flow.py) now delegates phase orchestration to [src/email_node/shared_pipeline_core/pipeline.py](/home/dan/Projects/HexeEmail/src/email_node/shared_pipeline_core/pipeline.py)
- ORDER still owns its current scrubber, profile detector, template extraction, probation lifecycle, decisioning, persistence, and action handlers

Why this exists:

- create a real shared package boundary before family-specific configs are extracted
- preserve existing ORDER output contracts while enabling later migration tasks
- keep Phase 2 through Phase 7 execution order and aggregation consistent across future flow families

Not migrated yet:

- Phase 1 shared normalization interface
- flow family config loader
- external heuristic packs
- shared validation/decision/action policy packs
- ACTION_NEEDED runner
