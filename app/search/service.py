import uuid
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

from app.assets.models import Asset, AssetTag, AssetType, DimensionEnum, TaxonomyNode


def attribute_search(
    db: Session,
    tag_ids: list[uuid.UUID],
    dimension: DimensionEnum | None,
    page: int,
    page_size: int,
    asset_type: AssetType | None = None,
) -> list[Asset]:
    query = db.query(Asset)

    if asset_type:
        query = query.filter(Asset.asset_type == asset_type)

    if dimension:
        dim_node_ids = db.query(TaxonomyNode.id).filter(TaxonomyNode.dimension == dimension).scalar_subquery()
        has_dim_tag = db.query(AssetTag.asset_id).filter(AssetTag.node_id.in_(dim_node_ids)).scalar_subquery()
        query = query.filter(Asset.id.in_(has_dim_tag))

    for node_id in tag_ids:
        sub = db.query(AssetTag.asset_id).filter(AssetTag.node_id == node_id).scalar_subquery()
        query = query.filter(Asset.id.in_(sub))

    return query.order_by(Asset.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()


def vector_search(db: Session, query_vector: list[float], limit: int = 50) -> list:
    """pgvector cosine similarity search. Returns rows with asset fields + distance."""
    vector_str = "[" + ",".join(str(x) for x in query_vector) + "]"
    rows = db.execute(
        sa_text("""
            SELECT a.id, a.filename, a.thumb_uri, a.display_uri, a.width, a.height, a.created_at,
                   (e.vector <=> CAST(:qv AS vector)) AS distance
            FROM asset a
            JOIN asset_embedding e ON a.id = e.asset_id
            ORDER BY distance
            LIMIT :limit
        """),
        {"qv": vector_str, "limit": limit},
    ).fetchall()
    return rows
