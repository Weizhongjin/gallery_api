import uuid
from sqlalchemy.orm import Session

from app.assets.models import DimensionEnum, TaxonomyCandidate, TaxonomyNode


def create_node(db: Session, dimension: DimensionEnum, name: str, name_en: str | None = None,
                parent_id: uuid.UUID | None = None, sort_order: int = 0) -> TaxonomyNode:
    node = TaxonomyNode(
        dimension=dimension,
        name=name,
        name_en=name_en,
        parent_id=parent_id,
        sort_order=sort_order,
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    return node


def list_nodes(db: Session) -> list[TaxonomyNode]:
    return db.query(TaxonomyNode).order_by(TaxonomyNode.dimension, TaxonomyNode.sort_order).all()


def update_node(db: Session, node_id: uuid.UUID, **kwargs) -> TaxonomyNode | None:
    node = db.get(TaxonomyNode, node_id)
    if not node:
        return None
    for k, v in kwargs.items():
        setattr(node, k, v)
    db.commit()
    db.refresh(node)
    return node


def deactivate_node(db: Session, node_id: uuid.UUID) -> bool:
    node = db.get(TaxonomyNode, node_id)
    if not node:
        return False
    node.is_active = False
    db.commit()
    return True


def list_candidates(db: Session) -> list[TaxonomyCandidate]:
    return (
        db.query(TaxonomyCandidate)
        .filter(TaxonomyCandidate.reviewed == False)
        .order_by(TaxonomyCandidate.hit_count.desc())
        .all()
    )


def promote_candidate(db: Session, candidate_id: uuid.UUID) -> TaxonomyNode | None:
    cand = db.get(TaxonomyCandidate, candidate_id)
    if not cand:
        return None
    node = TaxonomyNode(dimension=cand.dimension, name=cand.raw_label)
    db.add(node)
    cand.reviewed = True
    db.commit()
    db.refresh(node)
    return node


def delete_candidate(db: Session, candidate_id: uuid.UUID) -> bool:
    cand = db.get(TaxonomyCandidate, candidate_id)
    if not cand:
        return False
    cand.reviewed = True
    db.commit()
    return True
