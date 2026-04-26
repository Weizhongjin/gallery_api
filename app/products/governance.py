from dataclasses import dataclass


@dataclass(frozen=True)
class GovernanceState:
    completeness_state: str
    aux_tags: list[str]
    recommended_action: str


def derive_product_governance_state(
    *,
    flatlay_count: int,
    model_count: int,
    advertising_count: int,
    has_ai_assets: bool,
    lookbook_count: int,
    tag_count: int,
) -> GovernanceState:
    display_count = model_count + advertising_count
    total_assets = flatlay_count + display_count

    if total_assets == 0:
        return GovernanceState(
            "missing_all_assets",
            ["lookbook_unused", "tagging_incomplete"],
            "bind_assets",
        )

    if flatlay_count == 0:
        tags: list[str] = []
        if lookbook_count == 0:
            tags.append("lookbook_unused")
        return GovernanceState("missing_flatlay", tags, "bind_assets")

    if display_count == 0:
        tags: list[str] = []
        if advertising_count == 0:
            tags.append("low_advertising")
        if lookbook_count == 0:
            tags.append("lookbook_unused")
        if tag_count < 2:
            tags.append("tagging_incomplete")
        return GovernanceState("missing_display", tags, "start_aigc")

    # Complete — hard requirements (flatlay + display) are met.
    tags: list[str] = []
    if advertising_count == 0:
        tags.append("low_advertising")
    if lookbook_count == 0:
        tags.append("lookbook_unused")
    if has_ai_assets:
        tags.append("has_ai_assets")
    if tag_count < 2:
        tags.append("tagging_incomplete")

    recommended_action = (
        "generate_advertising_asset" if advertising_count == 0 else "add_to_lookbook"
    )
    return GovernanceState("complete", tags, recommended_action)
