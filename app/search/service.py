import uuid
from sqlalchemy.orm import Session

from app.assets.models import Asset, AssetTag, DimensionEnum, TaxonomyNode


def attribute_search(
    db: Session,
    tag_ids: list[uuid.UUID],
    dimension: DimensionEnum | None,
    page: int,
    page_size: int,
) -> list[Asset]:
    query = db.query(Asset)

    if dimension:
        dim_node_ids = db.query(TaxonomyNode.id).filter(TaxonomyNode.dimension == dimension).scalar_subquery()
        has_dim_tag = db.query(AssetTag.asset_id).filter(AssetTag.node_id.in_(dim_node_ids)).scalar_subquery()
        query = query.filter(Asset.id.in_(has_dim_tag))

    for node_id in tag_ids:
        sub = db.query(AssetTag.asset_id).filter(AssetTag.node_id == node_id).scalar_subquery()
        query = query.filter(Asset.id.in_(sub))

    return query.order_by(Asset.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
