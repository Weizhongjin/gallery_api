import json
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.assets.models import Asset, AssetEmbedding, AssetTag, DimensionEnum, TagSource, TaxonomyCandidate, TaxonomyNode
from app.ai.vlm_client import VLMClient
from app.ai.embed_client import EmbeddingClient
from app.storage import uri_to_key

_DIMENSION_MAP = {
    "category": DimensionEnum.category,
    "style": DimensionEnum.style,
    "color": DimensionEnum.color,
    "scene": DimensionEnum.scene,
    "detail": DimensionEnum.detail,
}


def classify_asset(db: Session, asset: Asset, vlm_client: VLMClient, storage) -> None:
    """Run VLM classification on asset.display_uri, write tags, update feature_status.

    Clears existing ai tags before writing new ones.
    Unknown labels go to taxonomy_candidate with hit_count++.
    Human tags (source=human) are never touched.
    """
    key = uri_to_key(asset.display_uri)
    image_url = storage.get_presigned_url(key)

    result = vlm_client.classify(image_url=image_url)

    # Clear existing ai tags
    db.query(AssetTag).filter(
        AssetTag.asset_id == asset.id,
        AssetTag.source == TagSource.ai,
    ).delete(synchronize_session=False)

    # Load active taxonomy nodes for fast lookup
    nodes = {n.name: n for n in db.query(TaxonomyNode).filter(TaxonomyNode.is_active == True).all()}

    for dim_key, dim_enum in _DIMENSION_MAP.items():
        raw = result.get(dim_key)
        if not raw:
            continue
        labels = [raw] if isinstance(raw, str) else raw
        for label in labels:
            if not label:
                continue
            node = nodes.get(label)
            if node:
                db.add(AssetTag(asset_id=asset.id, node_id=node.id, source=TagSource.ai))
            else:
                existing = db.query(TaxonomyCandidate).filter(
                    TaxonomyCandidate.raw_label == label
                ).first()
                if existing:
                    existing.hit_count += 1
                else:
                    db.add(TaxonomyCandidate(raw_label=label, dimension=dim_enum))

    status = dict(asset.feature_status or {})
    status["classify"] = "done"
    asset.feature_status = status
    db.flush()


def embed_asset(db: Session, asset: Asset, embed_client: EmbeddingClient, storage, model_ver: str = "v1") -> None:
    """Generate embedding for asset.display_uri, write to asset_embedding, update feature_status."""
    key = uri_to_key(asset.display_uri)
    image_url = storage.get_presigned_url(key)

    vector = embed_client.embed_image(image_url=image_url)

    existing = db.query(AssetEmbedding).filter(AssetEmbedding.asset_id == asset.id).first()
    vector_str = "[" + ",".join(str(x) for x in vector) + "]"

    if existing:
        existing.model_ver = model_ver
        db.execute(
            text("UPDATE asset_embedding SET vector = CAST(:v AS vector) WHERE asset_id = :id"),
            {"v": vector_str, "id": str(asset.id)},
        )
    else:
        db.add(AssetEmbedding(asset_id=asset.id, model_ver=model_ver))
        db.flush()
        db.execute(
            text("UPDATE asset_embedding SET vector = CAST(:v AS vector) WHERE asset_id = :id"),
            {"v": vector_str, "id": str(asset.id)},
        )

    status = dict(asset.feature_status or {})
    status["embed"] = "done"
    asset.feature_status = status
    db.flush()
