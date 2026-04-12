#!/usr/bin/env python3
"""Fix advertising set numeric-folder assets to share one group TEMPUID per folder."""

from __future__ import annotations

import re
from collections import Counter

from app.assets.models import Asset, AssetProduct, AssetProductRole, ParseStatus, Product
from app.assets.service import _build_group_tempuid
from app.database import SessionLocal

TARGET_DATASET = "2026春季广告logo"
TARGET_CATEGORY = "套装"
SINGLE_DIGIT_RE = re.compile(r"^\d$")


def _upsert_product(db, code: str) -> Product:
    product = db.query(Product).filter(Product.product_code == code).first()
    if product:
        return product
    product = Product(product_code=code)
    db.add(product)
    db.flush()
    return product


def _folder_from_relpath(relpath: str) -> str:
    parts = [x for x in (relpath or "").split("/") if x]
    return parts[2] if len(parts) >= 4 else ""


def main() -> None:
    db = SessionLocal()
    counters = Counter()
    try:
        assets = (
            db.query(Asset)
            .filter(Asset.source_relpath.like(f"{TARGET_DATASET}/{TARGET_CATEGORY}/%/%"))
            .all()
        )

        for asset in assets:
            folder = _folder_from_relpath(asset.source_relpath or "")
            if not SINGLE_DIGIT_RE.fullmatch(folder):
                continue

            target_code = _build_group_tempuid(TARGET_DATASET, TARGET_CATEGORY, folder)
            target_product = _upsert_product(db, target_code)

            # Remove old temporary auto links for this asset.
            old_links = (
                db.query(AssetProduct)
                .join(Product, Product.id == AssetProduct.product_id)
                .filter(
                    AssetProduct.asset_id == asset.id,
                    Product.product_code.like("TMPUID-%"),
                    Product.product_code != target_code,
                )
                .all()
            )
            for link in old_links:
                db.delete(link)
                counters["old_tmp_links_removed"] += 1

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
                        relation_role=AssetProductRole.advertising_ref,
                        source="folder_temp_group",
                    )
                )
                counters["group_links_added"] += 1

            asset.parse_status = ParseStatus.parsed
            counters["assets_touched"] += 1

        db.commit()
        print("fix_done")
        for k, v in sorted(counters.items()):
            print(f"{k}={v}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
