import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user, require_role
from app.auth.models import User, UserRole
from app.database import get_db
from app.lookbooks.schemas import (
    AccessIn,
    AccessOut,
    LookbookCreate,
    LookbookItemIn,
    LookbookItemOut,
    LookbookOut,
    LookbookSectionCreateFromProduct,
    LookbookSectionItemAdd,
    LookbookSectionItemOut,
    LookbookSectionOut,
    LookbookUpdate,
)
from app.lookbooks.service import (
    add_item, add_product_section, add_section_items, create_lookbook, flattened_buyer_items,
    get_buyer_lookbooks, get_lookbook_items,
    grant_access, list_access, list_lookbooks, list_sections, remove_item, remove_section,
    remove_section_item,
    revoke_access, set_published, update_lookbook,
)

router = APIRouter(tags=["lookbooks"])
_EDITORS = (UserRole.admin, UserRole.editor)


@router.post("/lookbooks", response_model=LookbookOut, status_code=status.HTTP_201_CREATED)
def create(
    body: LookbookCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_EDITORS)),
):
    return create_lookbook(db, body.title, current_user.id, body.cover_asset_id)


@router.get("/lookbooks", response_model=list[LookbookOut])
def list_all(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return list_lookbooks(db)


@router.patch("/lookbooks/{lb_id}", response_model=LookbookOut)
def patch(
    lb_id: uuid.UUID,
    body: LookbookUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(*_EDITORS)),
):
    lb = update_lookbook(db, lb_id, **body.model_dump(exclude_none=True))
    if not lb:
        raise HTTPException(status_code=404, detail="Lookbook not found")
    return lb


@router.post("/lookbooks/{lb_id}/items", status_code=status.HTTP_201_CREATED)
def add(
    lb_id: uuid.UUID,
    body: LookbookItemIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(*_EDITORS)),
):
    add_item(db, lb_id, body.asset_id, body.sort_order, body.note)
    return {"ok": True}


@router.get("/lookbooks/{lb_id}/items", response_model=list[LookbookItemOut])
def list_items(
    lb_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(*_EDITORS)),
):
    return get_lookbook_items(db, lb_id)


@router.delete("/lookbooks/{lb_id}/items/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove(
    lb_id: uuid.UUID,
    asset_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(*_EDITORS)),
):
    if not remove_item(db, lb_id, asset_id):
        raise HTTPException(status_code=404, detail="Item not found")


@router.post("/lookbooks/{lb_id}/publish", response_model=LookbookOut)
def publish_lb(
    lb_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(*_EDITORS)),
):
    lb = set_published(db, lb_id, True)
    if not lb:
        raise HTTPException(status_code=404, detail="Lookbook not found")
    return lb


@router.delete("/lookbooks/{lb_id}/unpublish", response_model=LookbookOut)
def unpublish_lb(
    lb_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(*_EDITORS)),
):
    lb = set_published(db, lb_id, False)
    if not lb:
        raise HTTPException(status_code=404, detail="Lookbook not found")
    return lb


@router.post("/lookbooks/{lb_id}/access", response_model=AccessOut, status_code=status.HTTP_201_CREATED)
def assign(
    lb_id: uuid.UUID,
    body: AccessIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_EDITORS)),
):
    return grant_access(db, lb_id, body.user_id, current_user.id)


@router.delete("/lookbooks/{lb_id}/access/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke(
    lb_id: uuid.UUID,
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(*_EDITORS)),
):
    if not revoke_access(db, lb_id, user_id):
        raise HTTPException(status_code=404, detail="Access not found")


@router.get("/lookbooks/{lb_id}/access", response_model=list[AccessOut])
def list_acc(
    lb_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(*_EDITORS)),
):
    return list_access(db, lb_id)


# --- Section editor APIs ---

@router.get("/lookbooks/{lb_id}/sections", response_model=list[LookbookSectionOut])
def get_sections(
    lb_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor, UserRole.viewer)),
):
    sections = list_sections(db, lb_id)
    if sections:
        return sections

    legacy = get_lookbook_items(db, lb_id)
    if not legacy:
        return []

    return [LookbookSectionOut(
        id=uuid.uuid5(uuid.NAMESPACE_URL, f"legacy:{lb_id}"),
        lookbook_id=lb_id,
        product_id=None,
        sort_order=0,
        cover_asset_id=legacy[0].asset_id,
        items=[LookbookSectionItemOut(
            id=uuid.uuid5(uuid.NAMESPACE_URL, f"legacy-item:{item.asset_id}"),
            asset_id=item.asset_id,
            sort_order=i,
            source="legacy",
            is_cover=i == 0,
            note=item.note,
        ) for i, item in enumerate(legacy)],
    )]


@router.post(
    "/lookbooks/{lb_id}/sections/products",
    response_model=LookbookSectionOut,
    status_code=status.HTTP_201_CREATED,
)
def add_product_section_route(
    lb_id: uuid.UUID,
    body: LookbookSectionCreateFromProduct,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor)),
):
    return add_product_section(db, lb_id, body.product_id)


@router.delete(
    "/lookbooks/{lb_id}/sections/{section_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_section_route(
    lb_id: uuid.UUID,
    section_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor)),
):
    if not remove_section(db, section_id):
        raise HTTPException(status_code=404, detail="Section not found")


@router.post(
    "/lookbooks/{lb_id}/sections/{section_id}/items",
    response_model=LookbookSectionOut,
)
def add_items_route(
    lb_id: uuid.UUID,
    section_id: uuid.UUID,
    body: LookbookSectionItemAdd,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor)),
):
    return add_section_items(db, section_id, body.asset_ids)


# --- Buyer view ---

@router.get("/my/lookbooks", response_model=list[LookbookOut])
def my_lookbooks(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.buyer)),
):
    return get_buyer_lookbooks(db, current_user.id)


@router.get("/my/lookbooks/{lb_id}/items")
def my_lookbook_items(
    lb_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.buyer)),
):
    from app.assets.models import LookbookAccess
    access = db.get(LookbookAccess, (lb_id, current_user.id))
    if not access:
        raise HTTPException(status_code=403, detail="No access to this lookbook")
    return flattened_buyer_items(db, lb_id)


# --- Section item management ---

@router.delete(
    "/lookbooks/{lb_id}/sections/{section_id}/items/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_section_item_route(
    lb_id: uuid.UUID,
    section_id: uuid.UUID,
    asset_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor)),
):
    remove_section_item(db, section_id, asset_id)
