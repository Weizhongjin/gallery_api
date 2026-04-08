import uuid
from sqlalchemy.orm import Session

from app.assets.models import Lookbook, LookbookAccess, LookbookItem


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
