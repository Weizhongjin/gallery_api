import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user, require_role
from app.auth.models import User, UserRole
from app.database import get_db
from app.taxonomy.schemas import CandidateOut, TaxonomyNodeCreate, TaxonomyNodeOut, TaxonomyNodeUpdate
from app.taxonomy.service import (
    create_node, deactivate_node, delete_candidate,
    list_candidates, list_nodes, promote_candidate, update_node,
)

router = APIRouter(prefix="/taxonomy", tags=["taxonomy"])


@router.get("", response_model=list[TaxonomyNodeOut])
def get_taxonomy(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return list_nodes(db)


@router.post("/nodes", response_model=TaxonomyNodeOut, status_code=status.HTTP_201_CREATED)
def create(
    body: TaxonomyNodeCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    return create_node(db, body.dimension, body.name, body.name_en, body.parent_id, body.sort_order)


@router.patch("/nodes/{node_id}", response_model=TaxonomyNodeOut)
def patch(
    node_id: uuid.UUID,
    body: TaxonomyNodeUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    node = update_node(db, node_id, **body.model_dump(exclude_none=True))
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return node


@router.delete("/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_node(
    node_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    if not deactivate_node(db, node_id):
        raise HTTPException(status_code=404, detail="Node not found")


@router.get("/candidates", response_model=list[CandidateOut])
def get_candidates(
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    return list_candidates(db)


@router.post("/candidates/{candidate_id}/promote", response_model=TaxonomyNodeOut, status_code=status.HTTP_201_CREATED)
def promote(
    candidate_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    node = promote_candidate(db, candidate_id)
    if not node:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return node


@router.delete("/candidates/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
def discard_candidate(
    candidate_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    if not delete_candidate(db, candidate_id):
        raise HTTPException(status_code=404, detail="Candidate not found")
