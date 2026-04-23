import uuid
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.assets.models import (
    Asset, AssetProduct, Lookbook, LookbookAccess, LookbookItem,
    LookbookProductSection, LookbookSectionItem,
)

_ROLE_PRIORITY = {
    "flatlay_primary": 1,
    "manual": 2,
    "model_ref": 3,
    "advertising_ref": 4,
}


def create_lookbook(db: Session, title: str, created_by: uuid.UUID, cover_asset_id: uuid.UUID | None = None) -> Lookbook:
    lb = Lookbook(title=title, created_by=created_by, cover_asset_id=cover_asset_id)
    db.add(lb)
    db.commit()
    db.refresh(lb)
    return lb


def list_lookbooks(db: Session) -> list[Lookbook]:
    return db.query(Lookbook).order_by(Lookbook.created_at.desc()).all()


def update_lookbook(db: Session, lb_id: uuid.UUID, **kwargs) -> Lookbook | None:
    lb = db.get(Lookbook, lb_id)
    if not lb:
        return None
    for k, v in kwargs.items():
        setattr(lb, k, v)
    db.commit()
    db.refresh(lb)
    return lb


def add_item(db: Session, lb_id: uuid.UUID, asset_id: uuid.UUID, sort_order: int = 0, note: str | None = None) -> LookbookItem:
    item = LookbookItem(lookbook_id=lb_id, asset_id=asset_id, sort_order=sort_order, note=note)
    db.add(item)
    db.commit()
    return item


def remove_item(db: Session, lb_id: uuid.UUID, asset_id: uuid.UUID) -> bool:
    item = db.get(LookbookItem, (lb_id, asset_id))
    if not item:
        return False
    db.delete(item)
    db.commit()
    return True


def set_published(db: Session, lb_id: uuid.UUID, published: bool) -> Lookbook | None:
    lb = db.get(Lookbook, lb_id)
    if not lb:
        return None
    lb.is_published = published
    db.commit()
    db.refresh(lb)
    return lb


def grant_access(db: Session, lb_id: uuid.UUID, user_id: uuid.UUID, granted_by: uuid.UUID) -> LookbookAccess:
    existing = db.get(LookbookAccess, (lb_id, user_id))
    if existing:
        return existing
    access = LookbookAccess(lookbook_id=lb_id, user_id=user_id, granted_by=granted_by)
    db.add(access)
    db.commit()
    db.refresh(access)
    return access


def revoke_access(db: Session, lb_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    access = db.get(LookbookAccess, (lb_id, user_id))
    if not access:
        return False
    db.delete(access)
    db.commit()
    return True


def list_access(db: Session, lb_id: uuid.UUID) -> list[LookbookAccess]:
    return db.query(LookbookAccess).filter(LookbookAccess.lookbook_id == lb_id).all()


def get_buyer_lookbooks(db: Session, user_id: uuid.UUID) -> list[Lookbook]:
    return (
        db.query(Lookbook)
        .join(LookbookAccess, LookbookAccess.lookbook_id == Lookbook.id)
        .filter(LookbookAccess.user_id == user_id, Lookbook.is_published == True)
        .all()
    )


def get_lookbook_items(db: Session, lb_id: uuid.UUID) -> list[LookbookItem]:
    return (
        db.query(LookbookItem)
        .filter(LookbookItem.lookbook_id == lb_id)
        .order_by(LookbookItem.sort_order)
        .all()
    )


def _recommended_product_assets(db: Session, product_id: uuid.UUID, limit: int = 3) -> list[tuple[Asset, AssetProduct]]:
    rows = (
        db.query(Asset, AssetProduct)
        .join(AssetProduct, AssetProduct.asset_id == Asset.id)
        .filter(AssetProduct.product_id == product_id)
        .all()
    )
    ranked = sorted(
        rows,
        key=lambda row: (
            _ROLE_PRIORITY.get(row[1].relation_role.value, 99),
            row[0].filename,
            str(row[0].id),
        ),
    )
    return ranked[:limit]


def add_product_section(db: Session, lookbook_id: uuid.UUID, product_id: uuid.UUID) -> LookbookProductSection:
    existing = (
        db.query(LookbookProductSection)
        .filter(LookbookProductSection.lookbook_id == lookbook_id, LookbookProductSection.product_id == product_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Product already exists in this lookbook")

    recommended = _recommended_product_assets(db, product_id)
    if not recommended:
        raise HTTPException(status_code=422, detail="该商品暂无关联图片，暂时不能加入画册")

    next_sort = db.query(func.coalesce(func.max(LookbookProductSection.sort_order), -1)).filter(
        LookbookProductSection.lookbook_id == lookbook_id
    ).scalar() + 1

    section = LookbookProductSection(
        lookbook_id=lookbook_id,
        product_id=product_id,
        sort_order=next_sort,
        cover_asset_id=recommended[0][0].id,
    )
    db.add(section)
    db.flush()

    for index, (asset, _) in enumerate(recommended):
        db.add(
            LookbookSectionItem(
                section_id=section.id,
                asset_id=asset.id,
                sort_order=index,
                source="system",
                is_cover=index == 0,
            )
        )

    db.flush()
    db.commit()
    db.refresh(section)
    section.items = (
        db.query(LookbookSectionItem)
        .filter(LookbookSectionItem.section_id == section.id)
        .order_by(LookbookSectionItem.sort_order.asc())
        .all()
    )
    return section


def list_sections(db: Session, lb_id: uuid.UUID) -> list[LookbookProductSection]:
    sections = (
        db.query(LookbookProductSection)
        .filter(LookbookProductSection.lookbook_id == lb_id)
        .order_by(LookbookProductSection.sort_order.asc(), LookbookProductSection.created_at.asc())
        .all()
    )
    for section in sections:
        section.items = (
            db.query(LookbookSectionItem)
            .filter(LookbookSectionItem.section_id == section.id)
            .order_by(LookbookSectionItem.sort_order.asc(), LookbookSectionItem.created_at.asc())
            .all()
        )
    return sections


def flattened_buyer_items(db: Session, lb_id: uuid.UUID) -> list[dict]:
    payload: list[dict] = []
    section_asset_ids: set[str] = set()
    global_order = 0

    for section in list_sections(db, lb_id):
        for item in section.items:
            payload.append({
                "asset_id": str(item.asset_id),
                "sort_order": global_order,
                "note": item.note,
            })
            section_asset_ids.add(str(item.asset_id))
            global_order += 1

    for item in get_lookbook_items(db, lb_id):
        if str(item.asset_id) not in section_asset_ids:
            payload.append({
                "asset_id": str(item.asset_id),
                "sort_order": global_order,
                "note": item.note,
            })
            global_order += 1

    return payload


def remove_section_item(db: Session, lookbook_id: uuid.UUID, section_id: uuid.UUID, asset_id: uuid.UUID) -> None:
    section = db.get(LookbookProductSection, section_id)
    if not section or section.lookbook_id != lookbook_id:
        raise HTTPException(status_code=404, detail="Section not found")
    item = (
        db.query(LookbookSectionItem)
        .filter(LookbookSectionItem.section_id == section_id, LookbookSectionItem.asset_id == asset_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Section item not found")
    db.delete(item)
    db.flush()

    remaining = (
        db.query(LookbookSectionItem)
        .filter(LookbookSectionItem.section_id == section_id)
        .order_by(LookbookSectionItem.sort_order.asc(), LookbookSectionItem.created_at.asc())
        .all()
    )
    section = db.get(LookbookProductSection, section_id)
    if section:
        if not remaining:
            section.cover_asset_id = None
        else:
            remaining[0].is_cover = True
            section.cover_asset_id = remaining[0].asset_id
    db.flush()
    db.commit()


def remove_section(db: Session, lookbook_id: uuid.UUID, section_id: uuid.UUID) -> bool:
    section = db.get(LookbookProductSection, section_id)
    if not section or section.lookbook_id != lookbook_id:
        return False
    db.query(LookbookSectionItem).filter(LookbookSectionItem.section_id == section_id).delete()
    db.delete(section)
    db.flush()
    db.commit()
    return True


def add_section_items(db: Session, lookbook_id: uuid.UUID, section_id: uuid.UUID, asset_ids: list[uuid.UUID]) -> LookbookProductSection:
    section = db.get(LookbookProductSection, section_id)
    if not section or section.lookbook_id != lookbook_id:
        raise HTTPException(status_code=404, detail="Section not found")

    existing = set(
        row[0] for row in
        db.query(LookbookSectionItem.asset_id)
        .filter(LookbookSectionItem.section_id == section_id)
        .all()
    )

    next_sort = db.query(func.coalesce(func.max(LookbookSectionItem.sort_order), -1)).filter(
        LookbookSectionItem.section_id == section_id
    ).scalar() + 1

    for asset_id in asset_ids:
        if asset_id not in existing:
            db.add(LookbookSectionItem(
                section_id=section_id,
                asset_id=asset_id,
                sort_order=next_sort,
                source="manual",
                is_cover=False,
            ))
            next_sort += 1

    db.flush()
    db.commit()
    db.refresh(section)
    section.items = (
        db.query(LookbookSectionItem)
        .filter(LookbookSectionItem.section_id == section_id)
        .order_by(LookbookSectionItem.sort_order.asc())
        .all()
    )
    return section


def reorder_sections(
    db: Session,
    lookbook_id: uuid.UUID,
    section_ids: list[uuid.UUID],
) -> list[LookbookProductSection]:
    sections = (
        db.query(LookbookProductSection)
        .filter(LookbookProductSection.lookbook_id == lookbook_id)
        .order_by(LookbookProductSection.sort_order.asc(), LookbookProductSection.created_at.asc())
        .all()
    )
    existing_ids = [section.id for section in sections]

    if len(section_ids) != len(existing_ids):
        raise HTTPException(status_code=400, detail="Section reorder payload does not match current lookbook sections")
    if len(set(section_ids)) != len(section_ids):
        raise HTTPException(status_code=400, detail="Section reorder payload contains duplicate ids")
    if set(section_ids) != set(existing_ids):
        raise HTTPException(status_code=400, detail="Section reorder payload contains invalid section ids")

    sections_by_id = {section.id: section for section in sections}
    for index, section_id in enumerate(section_ids):
        sections_by_id[section_id].sort_order = index

    db.commit()
    return list_sections(db, lookbook_id)
