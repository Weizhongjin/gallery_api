import uuid
from dataclasses import dataclass
from datetime import datetime
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

from app.assets.models import (
    Asset,
    AssetProduct,
    AssetProductRole,
    AssetTag,
    AssetType,
    DimensionEnum,
    Product,
    TaxonomyNode,
)

_COVER_ROLE_PRIORITY: dict[AssetProductRole, int] = {
    AssetProductRole.flatlay_primary: 1,
    AssetProductRole.manual: 2,
    AssetProductRole.model_ref: 3,
    AssetProductRole.advertising_ref: 4,
}

_COVER_ASSET_TYPE_PRIORITY: dict[AssetType, int] = {
    AssetType.flatlay: 1,
    AssetType.model_set: 2,
    AssetType.advertising: 3,
    AssetType.unknown: 4,
}


@dataclass
class AssetCandidate:
    id: uuid.UUID
    filename: str
    thumb_uri: str
    display_uri: str
    width: int
    height: int
    created_at: datetime | None
    asset_type: AssetType | None
    score: float
    match_reason: str


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
            SELECT a.id, a.filename, a.thumb_uri, a.display_uri, a.width, a.height, a.created_at, a.asset_type,
                   (e.vector <=> CAST(:qv AS vector)) AS distance
            FROM asset a
            JOIN asset_embedding e ON a.id = e.asset_id
            ORDER BY distance
            LIMIT :limit
        """),
        {"qv": vector_str, "limit": limit},
    ).fetchall()
    return rows


def _asset_to_candidate(asset: Asset, *, score: float, reason: str) -> AssetCandidate:
    return AssetCandidate(
        id=asset.id,
        filename=asset.filename,
        thumb_uri=asset.thumb_uri,
        display_uri=asset.display_uri,
        width=asset.width,
        height=asset.height,
        created_at=asset.created_at,
        asset_type=asset.asset_type,
        score=max(0.0, float(score)),
        match_reason=reason,
    )


def _vector_row_to_candidate(row, *, reason: str) -> AssetCandidate:
    distance = float(row.distance or 1.0)
    similarity = max(0.0, 1.0 - distance)
    return AssetCandidate(
        id=row.id,
        filename=row.filename,
        thumb_uri=row.thumb_uri,
        display_uri=row.display_uri,
        width=row.width,
        height=row.height,
        created_at=row.created_at,
        asset_type=row.asset_type,
        score=similarity,
        match_reason=reason,
    )


def _pick_cover_asset(asset_matches: list[dict]) -> dict | None:
    if not asset_matches:
        return None

    def sort_key(item: dict) -> tuple:
        candidate: AssetCandidate = item["candidate"]
        role = item["relation_role"]
        role_priority = _COVER_ROLE_PRIORITY.get(role, 99)
        type_priority = _COVER_ASSET_TYPE_PRIORITY.get(candidate.asset_type or AssetType.unknown, 99)
        ts = candidate.created_at.timestamp() if candidate.created_at else 0.0
        return (role_priority, type_priority, -candidate.score, -ts)

    return sorted(asset_matches, key=sort_key)[0]


def _aggregate_product_candidates(
    db: Session,
    candidates: list[AssetCandidate],
    *,
    q: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    list_price_min: float | None = None,
    list_price_max: float | None = None,
    page: int,
    page_size: int,
) -> tuple[list[dict], int]:
    if not candidates:
        return [], 0

    best_by_asset: dict[uuid.UUID, AssetCandidate] = {}
    reasons_by_asset: dict[uuid.UUID, set[str]] = {}
    for cand in candidates:
        prev = best_by_asset.get(cand.id)
        if not prev or cand.score > prev.score:
            best_by_asset[cand.id] = cand
        reasons_by_asset.setdefault(cand.id, set()).add(cand.match_reason)

    asset_ids = list(best_by_asset.keys())
    links_query = (
        db.query(
            AssetProduct.asset_id,
            AssetProduct.product_id,
            AssetProduct.relation_role,
            Product.product_code,
            Product.name,
            Product.year,
            Product.list_price,
            Product.sale_price,
            Product.currency,
        )
        .join(Product, Product.id == AssetProduct.product_id)
        .filter(AssetProduct.asset_id.in_(asset_ids))
    )
    if q:
        key = f"%{q.strip().upper()}%"
        links_query = links_query.filter(
            Product.product_code.ilike(key) | Product.name.ilike(key)
        )
    if year_from is not None:
        links_query = links_query.filter(Product.year.isnot(None), Product.year >= year_from)
    if year_to is not None:
        links_query = links_query.filter(Product.year.isnot(None), Product.year <= year_to)
    if list_price_min is not None:
        links_query = links_query.filter(Product.list_price.isnot(None), Product.list_price >= list_price_min)
    if list_price_max is not None:
        links_query = links_query.filter(Product.list_price.isnot(None), Product.list_price <= list_price_max)

    links = links_query.all()

    buckets: dict[uuid.UUID, dict] = {}
    for link in links:
        candidate = best_by_asset.get(link.asset_id)
        if not candidate:
            continue

        bucket = buckets.setdefault(
            link.product_id,
            {
                "product_id": link.product_id,
                "product_code": link.product_code,
                "name": link.name,
                "year": link.year,
                "list_price": link.list_price,
                "sale_price": link.sale_price,
                "currency": link.currency,
                "score": 0.0,
                "match_reasons": set(),
                "asset_matches": {},
            },
        )

        bucket["score"] = max(bucket["score"], candidate.score)
        bucket["match_reasons"].update(reasons_by_asset.get(link.asset_id, {candidate.match_reason}))

        current = bucket["asset_matches"].get(link.asset_id)
        if not current or candidate.score > current["candidate"].score:
            bucket["asset_matches"][link.asset_id] = {
                "candidate": candidate,
                "relation_role": link.relation_role,
            }

    items: list[dict] = []
    for bucket in buckets.values():
        asset_matches = list(bucket["asset_matches"].values())
        if not asset_matches:
            continue

        cover = _pick_cover_asset(asset_matches)
        cover_candidate: AssetCandidate | None = cover["candidate"] if cover else None
        matched_asset_count = len(asset_matches)
        score = min(1.0, bucket["score"] + max(0, matched_asset_count - 1) * 0.02)

        items.append(
            {
                "product_id": bucket["product_id"],
                "product_code": bucket["product_code"],
                "name": bucket["name"],
                "year": bucket["year"],
                "list_price": float(bucket["list_price"]) if bucket["list_price"] is not None else None,
                "sale_price": float(bucket["sale_price"]) if bucket["sale_price"] is not None else None,
                "currency": bucket["currency"],
                "score": score,
                "match_reasons": sorted(bucket["match_reasons"]),
                "cover_asset_id": cover_candidate.id if cover_candidate else None,
                "cover_filename": cover_candidate.filename if cover_candidate else None,
                "cover_thumb_uri": cover_candidate.thumb_uri if cover_candidate else None,
                "cover_display_uri": cover_candidate.display_uri if cover_candidate else None,
                "cover_width": cover_candidate.width if cover_candidate else None,
                "cover_height": cover_candidate.height if cover_candidate else None,
                "matched_asset_count": matched_asset_count,
            }
        )

    items.sort(key=lambda x: (-float(x["score"]), -int(x["matched_asset_count"]), x["product_code"]))
    total = len(items)
    start = max(0, (page - 1) * page_size)
    end = start + page_size
    return items[start:end], total


def product_attribute_search(
    db: Session,
    *,
    tag_ids: list[uuid.UUID],
    dimension: DimensionEnum | None,
    asset_type: AssetType | None,
    q: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    list_price_min: float | None = None,
    list_price_max: float | None = None,
    page: int,
    page_size: int,
    candidate_limit: int | None = None,
) -> tuple[list[dict], int]:
    max_candidates = candidate_limit or max(200, page_size * 20, page * page_size * 5)
    assets = attribute_search(
        db=db,
        tag_ids=tag_ids,
        dimension=dimension,
        page=1,
        page_size=max_candidates,
        asset_type=asset_type,
    )
    if not assets:
        return [], 0

    denom = max(1, len(assets) - 1)
    candidates = [
        _asset_to_candidate(
            asset,
            score=1.0 - (idx / denom),
            reason="attribute",
        )
        for idx, asset in enumerate(assets)
    ]
    return _aggregate_product_candidates(
        db,
        candidates,
        q=q,
        year_from=year_from,
        year_to=year_to,
        list_price_min=list_price_min,
        list_price_max=list_price_max,
        page=page,
        page_size=page_size,
    )


def product_vector_search(
    db: Session,
    *,
    query_vector: list[float],
    mode: str,
    q: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    list_price_min: float | None = None,
    list_price_max: float | None = None,
    page: int,
    page_size: int,
    candidate_limit: int,
) -> tuple[list[dict], int]:
    rows = vector_search(db, query_vector, candidate_limit)
    candidates = [_vector_row_to_candidate(row, reason=mode) for row in rows]
    return _aggregate_product_candidates(
        db,
        candidates,
        q=q,
        year_from=year_from,
        year_to=year_to,
        list_price_min=list_price_min,
        list_price_max=list_price_max,
        page=page,
        page_size=page_size,
    )
