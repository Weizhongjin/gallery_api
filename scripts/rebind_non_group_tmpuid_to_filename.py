#!/usr/bin/env python3
"""Rebind non-group TMPUID links to filename-based product codes."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.assets.models import (
    Asset,
    AssetProduct,
    AssetProductRole,
    AssetType,
    ParseStatus,
    Product,
)
from app.database import SessionLocal


def relation_role_for_asset(asset_type: AssetType) -> AssetProductRole:
    if asset_type == AssetType.flatlay:
        return AssetProductRole.flatlay_primary
    if asset_type == AssetType.model_set:
        return AssetProductRole.model_ref
    if asset_type == AssetType.advertising:
        return AssetProductRole.advertising_ref
    return AssetProductRole.manual


def derive_code(asset: Asset) -> str | None:
    filename = (asset.filename or "").strip()
    if not filename and asset.source_relpath:
        filename = Path(asset.source_relpath).name
    stem = Path(filename).stem.strip().upper()
    if not stem:
        return None
    # Guard against tiny camera-index names like 1/2/12.
    if stem.isdigit() and len(stem) < 5:
        return None
    return stem


def upsert_product(db, code: str) -> Product:
    product = db.query(Product).filter(Product.product_code == code).first()
    if product:
        return product
    product = Product(product_code=code)
    db.add(product)
    db.flush()
    return product


def main() -> None:
    db = SessionLocal()
    counters = Counter()
    try:
        assets = (
            db.query(Asset)
            .join(AssetProduct, AssetProduct.asset_id == Asset.id)
            .join(Product, Product.id == AssetProduct.product_id)
            .filter(
                Product.product_code.like("TMPUID-%"),
                ~Product.product_code.like("TMPUID-GRP-%"),
            )
            .distinct()
            .all()
        )

        for asset in assets:
            counters["assets_seen"] += 1
            target_code = derive_code(asset)
            if not target_code:
                counters["assets_skipped_no_code"] += 1
                continue

            target_product = upsert_product(db, target_code)

            old_links = (
                db.query(AssetProduct)
                .join(Product, Product.id == AssetProduct.product_id)
                .filter(
                    AssetProduct.asset_id == asset.id,
                    Product.product_code.like("TMPUID-%"),
                    ~Product.product_code.like("TMPUID-GRP-%"),
                )
                .all()
            )
            for link in old_links:
                db.delete(link)
                counters["tmp_links_removed"] += 1

            existing = (
                db.query(AssetProduct)
                .filter(
                    AssetProduct.asset_id == asset.id,
                    AssetProduct.product_id == target_product.id,
                )
                .first()
            )
            if not existing:
                db.add(
                    AssetProduct(
                        asset_id=asset.id,
                        product_id=target_product.id,
                        relation_role=relation_role_for_asset(asset.asset_type),
                        source="filename_rebind",
                    )
                )
                counters["real_links_added"] += 1

            if asset.parse_status != ParseStatus.parsed:
                asset.parse_status = ParseStatus.parsed
                counters["parse_status_updated"] += 1

        # Remove orphan TMPUID products after rebind.
        orphan_tmp = (
            db.query(Product)
            .outerjoin(AssetProduct, AssetProduct.product_id == Product.id)
            .filter(
                Product.product_code.like("TMPUID-%"),
                AssetProduct.asset_id.is_(None),
            )
            .all()
        )
        for product in orphan_tmp:
            db.delete(product)
            counters["orphan_tmp_products_deleted"] += 1

        db.commit()
        print("rebind_non_group_tmpuid_done")
        for k, v in sorted(counters.items()):
            print(f"{k}={v}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
