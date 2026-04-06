from pathlib import Path

from email_node.flow_families.order.profiles import DEFAULT_PHASE3_RULES as DEFAULT_ORDER_PHASE3_RULES
from email_node.flow_families.order.profiles import build_profile_definition_pack


class GmailOrderProfileRulesStore:
    def __init__(self, runtime_dir: Path | None = None) -> None:
        self.runtime_dir = Path(runtime_dir) if runtime_dir is not None else Path("runtime")

    def load(self) -> dict[str, object]:
        return build_profile_definition_pack(runtime_dir=self.runtime_dir).load_rules()


__all__ = ["DEFAULT_ORDER_PHASE3_RULES", "GmailOrderProfileRulesStore"]
