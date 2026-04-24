import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config import settings
from app.auth.deps import get_current_user, require_role
from app.auth.models import User, UserRole
from app.database import get_db
from app.products.schemas import (
    ProductAssetOut,
    ProductGovernanceSummaryOut,
    ProductPageOut,
    ProductOut,
    ProductPatchIn,
    ProductTagOut,
    ProductTagPatchIn,
    ProductUpsertIn,
    ProductWorkbenchOut,
)
from app.products.service import (
    get_product_governance_summary,
    get_product_workbench,
    get_product_with_sales,
    list_product_assets,
    list_product_governance_items,
    list_product_tags,
    list_products,
    list_unresolved_assets,
    patch_product,
    patch_product_human_tags,
    rebuild_product_tags_for_product,
    upsert_product,
)
from app.products.sales_sync import sync_sales_from_budan

router = APIRouter(prefix="/products", tags=["products"])


@router.post("/upsert", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def upsert(
    body: ProductUpsertIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor)),
):
    return upsert_product(
        db,
        product_code=body.product_code,
        name=body.name,
        year=body.year,
        list_price=body.list_price,
        sale_price=body.sale_price,
        currency=body.currency,
    )


@router.get("", response_model=ProductPageOut)
def list_all(
    q: str | None = None,
    tag_ids: list[uuid.UUID] = Query(default=[]),
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
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    items, total = list_products(
        db,
        q=q,
        tag_ids=tag_ids,
        has_assets=has_assets,
        year_from=year_from,
        year_to=year_to,
        list_price_min=list_price_min,
        list_price_max=list_price_max,
        sales_min=sales_min,
        sales_max=sales_max,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    out_items = [
        ProductOut.model_validate(product, from_attributes=True).model_copy(
            update={"sales_total_qty": int(sales_total_qty or 0)}
        )
        for product, sales_total_qty in items
    ]
    return {"items": out_items, "total": total, "page": page, "page_size": page_size}


@router.get("/{product_id}", response_model=ProductOut)
def get_one(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    row = get_product_with_sales(db, product_id)
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    product, sales_total_qty = row
    return ProductOut.model_validate(product, from_attributes=True).model_copy(
        update={"sales_total_qty": int(sales_total_qty or 0)}
    )


@router.patch("/{product_id}", response_model=ProductOut)
def patch(
    product_id: uuid.UUID,
    body: ProductPatchIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor)),
):
    product = patch_product(db, product_id, **body.model_dump(exclude_none=True))
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/{product_id}/assets", response_model=list[ProductAssetOut])
def assets(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    rows = list_product_assets(db, product_id)
    return [
        ProductAssetOut(
            asset_id=asset.id,
            filename=asset.filename,
            asset_type=asset.asset_type,
            thumb_uri=asset.thumb_uri,
            display_uri=asset.display_uri,
            width=asset.width,
            height=asset.height,
            created_at=asset.created_at,
            relation_role=link.relation_role,
            source=link.source,
            confidence=link.confidence,
        )
        for asset, link in rows
    ]


@router.get("/{product_id}/tags", response_model=list[ProductTagOut])
def tags(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    rows = list_product_tags(db, product_id)
    return [ProductTagOut(node_id=r.node_id, source=r.source, confidence=r.confidence) for r in rows]


@router.patch("/{product_id}/tags", response_model=list[ProductTagOut])
def patch_tags(
    product_id: uuid.UUID,
    body: ProductTagPatchIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor)),
):
    product = patch_product_human_tags(db, product_id, body.add, body.remove)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    rows = list_product_tags(db, product_id)
    return [ProductTagOut(node_id=r.node_id, source=r.source, confidence=r.confidence) for r in rows]


@router.post("/{product_id}/tags/rebuild")
def rebuild_tags(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor)),
):
    summary = rebuild_product_tags_for_product(db, product_id)
    db.commit()
    return {"product_id": str(product_id), **summary}


@router.get("/{product_id}/workbench", response_model=ProductWorkbenchOut)
def product_workbench(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    payload = get_product_workbench(db, product_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Product not found")
    return payload


@router.get("/governance/summary", response_model=ProductGovernanceSummaryOut)
def governance_summary(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return get_product_governance_summary(db)


@router.get("/governance/items")
def governance_items(
    problem: str | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 24,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    items, total = list_product_governance_items(
        db, problem=problem, q=q, page=page, page_size=page_size
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/admin/unresolved-assets")
def unresolved_assets(
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor)),
):
    rows = list_unresolved_assets(db, page=page, page_size=page_size)
    return [
        {
            "asset_id": str(a.id),
            "filename": a.filename,
            "asset_type": a.asset_type,
            "source_dataset": a.source_dataset,
            "source_relpath": a.source_relpath,
            "parse_status": a.parse_status,
        }
        for a in rows
    ]


@router.post("/admin/sales/sync")
def sync_sales(
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor)),
):
    summary = sync_sales_from_budan(
        db,
        budan_database_url=settings.budan_database_url,
        source="budan",
    )
    return summary
