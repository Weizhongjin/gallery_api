import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.assets.models import Product
from app.auth.deps import get_current_user, require_role
from app.auth.models import User, UserRole
from app.database import get_db
from app.products.schemas import (
    ProductAssetOut,
    ProductPageOut,
    ProductOut,
    ProductPatchIn,
    ProductTagOut,
    ProductTagPatchIn,
    ProductUpsertIn,
)
from app.products.service import (
    list_product_assets,
    list_product_tags,
    list_products,
    list_unresolved_assets,
    patch_product,
    patch_product_human_tags,
    rebuild_product_tags_for_product,
    upsert_product,
)

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
        list_price=body.list_price,
        sale_price=body.sale_price,
        currency=body.currency,
    )


@router.get("", response_model=ProductPageOut)
def list_all(
    q: str | None = None,
    tag_ids: list[uuid.UUID] = Query(default=[]),
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    items, total = list_products(db, q=q, tag_ids=tag_ids, page=page, page_size=page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{product_id}", response_model=ProductOut)
def get_one(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


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
