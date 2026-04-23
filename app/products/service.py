import uuid
from collections import defaultdict

from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app.assets.models import (
    Asset,
    AssetProduct,
    AssetProductRole,
    AssetTag,
    AssetType,
    DimensionEnum,
    ParseStatus,
    Product,
    ProductSalesSummary,
    ProductTag,
    ProductTagSource,
    TagSource,
    TaxonomyNode,
)

_ASSET_TYPE_WEIGHT: dict[AssetType, float] = {
    AssetType.flatlay: 3.0,
    AssetType.model_set: 2.0,
    AssetType.advertising: 1.0,
    AssetType.unknown: 1.0,
}
_ASSET_TAG_BONUS: dict[TagSource, float] = {
    TagSource.human: 2.0,
    TagSource.ai: 1.0,
}


def _normalize_product_code(code: str) -> str:
    return (code or "").strip().upper()


def upsert_product(
    db: Session,
    *,
    product_code: str,
    name: str | None = None,
    year: int | None = None,
    list_price: float | None = None,
    sale_price: float | None = None,
    currency: str = "CNY",
) -> Product:
    code = _normalize_product_code(product_code)
    product = db.query(Product).filter(Product.product_code == code).first()
    if not product:
        product = Product(product_code=code)
        db.add(product)

    if name is not None:
        product.name = name
    if year is not None:
        product.year = year
    if list_price is not None:
        product.list_price = list_price
    if sale_price is not None:
        product.sale_price = sale_price
    if currency:
        product.currency = currency

    db.commit()
    db.refresh(product)
    return product


def list_products(
    db: Session,
    *,
    q: str | None = None,
    tag_ids: list[uuid.UUID] | None = None,
    has_assets: bool = False,
    year_from: int | None = None,
    year_to: int | None = None,
    list_price_min: float | None = None,
    list_price_max: float | None = None,
    sales_min: int | None = None,
    sales_max: int | None = None,
    sort_by: str | None = None,
    sort_order: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[tuple[Product, int]], int]:
    sales_expr = func.coalesce(ProductSalesSummary.sales_total_qty, 0).label("sales_total_qty")
    query = (
        db.query(Product, sales_expr)
        .outerjoin(ProductSalesSummary, ProductSalesSummary.product_id == Product.id)
    )
    if q:
        key = f"%{q.strip().upper()}%"
        query = query.filter(
            Product.product_code.ilike(key) | Product.name.ilike(key)
        )

    if has_assets:
        linked_product_ids = (
            db.query(AssetProduct.product_id)
            .distinct()
            .scalar_subquery()
        )
        query = query.filter(Product.id.in_(linked_product_ids))

    if tag_ids:
        unique_ids = list(dict.fromkeys(tag_ids))
        rows = (
            db.query(TaxonomyNode.id, TaxonomyNode.dimension)
            .filter(TaxonomyNode.id.in_(unique_ids))
            .all()
        )
        if not rows:
            return [], 0

        ids_by_dimension: dict[DimensionEnum, list[uuid.UUID]] = defaultdict(list)
        for node_id, dimension in rows:
            ids_by_dimension[dimension].append(node_id)

        for ids_in_dim in ids_by_dimension.values():
            matched_products_by_product_tag = (
                db.query(ProductTag.product_id)
                .filter(ProductTag.node_id.in_(ids_in_dim))
                .scalar_subquery()
            )
            matched_products_by_asset_tag = (
                db.query(AssetProduct.product_id)
                .join(AssetTag, AssetTag.asset_id == AssetProduct.asset_id)
                .filter(AssetTag.node_id.in_(ids_in_dim))
                .scalar_subquery()
            )
            query = query.filter(
                or_(
                    Product.id.in_(matched_products_by_product_tag),
                    Product.id.in_(matched_products_by_asset_tag),
                )
            )

    if year_from is not None:
        query = query.filter(Product.year.isnot(None), Product.year >= year_from)
    if year_to is not None:
        query = query.filter(Product.year.isnot(None), Product.year <= year_to)
    if list_price_min is not None:
        query = query.filter(Product.list_price.isnot(None), Product.list_price >= list_price_min)
    if list_price_max is not None:
        query = query.filter(Product.list_price.isnot(None), Product.list_price <= list_price_max)
    if sales_min is not None:
        query = query.filter(func.coalesce(ProductSalesSummary.sales_total_qty, 0) >= sales_min)
    if sales_max is not None:
        query = query.filter(func.coalesce(ProductSalesSummary.sales_total_qty, 0) <= sales_max)

    tmpuid_last = case((Product.product_code.ilike("TMPUID-%"), 1), else_=0)
    if sort_by == "sales_total_qty":
        sales_order = sales_expr.desc() if (sort_order or "desc").lower() != "asc" else sales_expr.asc()
        order_clauses = [tmpuid_last.asc(), sales_order, Product.created_at.desc()]
    else:
        created_order = Product.created_at.asc() if (sort_order or "desc").lower() == "asc" else Product.created_at.desc()
        order_clauses = [tmpuid_last.asc(), created_order]

    total = query.count()
    items = (
        query.order_by(*order_clauses)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def get_product_with_sales(db: Session, product_id: uuid.UUID) -> tuple[Product, int] | None:
    row = (
        db.query(
            Product,
            func.coalesce(ProductSalesSummary.sales_total_qty, 0).label("sales_total_qty"),
        )
        .outerjoin(ProductSalesSummary, ProductSalesSummary.product_id == Product.id)
        .filter(Product.id == product_id)
        .first()
    )
    if not row:
        return None
    return row[0], int(row[1] or 0)


def patch_product(db: Session, product_id: uuid.UUID, **fields) -> Product | None:
    product = db.get(Product, product_id)
    if not product:
        return None

    for name in ("name", "year", "list_price", "sale_price", "currency"):
        if name in fields and fields[name] is not None:
            setattr(product, name, fields[name])
    db.commit()
    db.refresh(product)
    return product


def list_product_assets(db: Session, product_id: uuid.UUID) -> list[tuple[Asset, AssetProduct]]:
    return (
        db.query(Asset, AssetProduct)
        .join(AssetProduct, AssetProduct.asset_id == Asset.id)
        .filter(AssetProduct.product_id == product_id)
        .order_by(Asset.created_at.desc())
        .all()
    )


def list_unresolved_assets(db: Session, page: int = 1, page_size: int = 50) -> list[Asset]:
    return (
        db.query(Asset)
        .filter(Asset.parse_status == ParseStatus.unresolved)
        .order_by(Asset.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )


def patch_product_human_tags(
    db: Session,
    product_id: uuid.UUID,
    add: list[uuid.UUID],
    remove: list[uuid.UUID],
) -> Product | None:
    product = db.get(Product, product_id)
    if not product:
        return None

    if remove:
        db.query(ProductTag).filter(
            ProductTag.product_id == product_id,
            ProductTag.node_id.in_(remove),
            ProductTag.source == ProductTagSource.human,
        ).delete(synchronize_session=False)

    for node_id in add:
        exists = db.query(ProductTag).filter(
            ProductTag.product_id == product_id,
            ProductTag.node_id == node_id,
            ProductTag.source == ProductTagSource.human,
        ).first()
        if not exists:
            db.add(ProductTag(product_id=product_id, node_id=node_id, source=ProductTagSource.human))

    rebuild_product_tags_for_product(db, product_id)
    db.commit()
    db.refresh(product)
    return product


def list_product_tags(db: Session, product_id: uuid.UUID) -> list[ProductTag]:
    return (
        db.query(ProductTag)
        .filter(ProductTag.product_id == product_id)
        .all()
    )


def rebuild_product_tags_for_asset(db: Session, asset_id: uuid.UUID) -> None:
    product_ids = [
        row[0]
        for row in db.query(AssetProduct.product_id)
        .filter(AssetProduct.asset_id == asset_id)
        .all()
    ]
    for product_id in product_ids:
        rebuild_product_tags_for_product(db, product_id)


def rebuild_product_tags_for_product(db: Session, product_id: uuid.UUID) -> dict:
    # Human tags remain source of truth; aggregated tags are rebuilt from asset tags.
    human_dims = {
        row[0]
        for row in db.query(TaxonomyNode.dimension)
        .join(ProductTag, ProductTag.node_id == TaxonomyNode.id)
        .filter(
            ProductTag.product_id == product_id,
            ProductTag.source == ProductTagSource.human,
        )
        .all()
    }

    db.query(ProductTag).filter(
        ProductTag.product_id == product_id,
        ProductTag.source == ProductTagSource.aggregated,
    ).delete(synchronize_session=False)

    rows = (
        db.query(
            AssetTag.node_id,
            TaxonomyNode.dimension,
            Asset.asset_type,
            AssetTag.source,
        )
        .join(Asset, Asset.id == AssetTag.asset_id)
        .join(AssetProduct, AssetProduct.asset_id == Asset.id)
        .join(TaxonomyNode, TaxonomyNode.id == AssetTag.node_id)
        .filter(AssetProduct.product_id == product_id)
        .all()
    )

    score_map: dict[DimensionEnum, dict[uuid.UUID, float]] = defaultdict(lambda: defaultdict(float))
    for node_id, dim, asset_type, tag_source in rows:
        if dim in human_dims:
            continue
        base = _ASSET_TYPE_WEIGHT.get(asset_type, 1.0)
        bonus = _ASSET_TAG_BONUS.get(tag_source, 1.0)
        score_map[dim][node_id] += (base + bonus)

    inserted = 0
    for dim, node_scores in score_map.items():
        if not node_scores:
            continue
        total = sum(node_scores.values()) or 1.0
        node_id, score = max(node_scores.items(), key=lambda x: x[1])
        db.add(
            ProductTag(
                product_id=product_id,
                node_id=node_id,
                source=ProductTagSource.aggregated,
                confidence=min(1.0, score / total),
            )
        )
        inserted += 1

    db.flush()
    return {"aggregated_count": inserted, "locked_dims": len(human_dims)}
