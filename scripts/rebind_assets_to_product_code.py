#!/usr/bin/env python3
"""Rebind matched assets from placeholder TMPUID links to a real product code."""

from __future__ import annotations

import argparse
from collections import Counter

from sqlalchemy import or_

from app.assets.models import (
    Asset,
    AssetProduct,
    AssetProductRole,
    AssetType,
    ParseStatus,
    Product,
)
from app.database import SessionLocal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product-code", required=True, help="Target real product code.")
    parser.add_argument(
        "--pattern",
        action="append",
        required=True,
        help="SQL LIKE pattern for source_relpath, can be passed multiple times.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview only, do not commit.",
    )
    return parser.parse_args()


def relation_role_for_asset(asset_type: AssetType) -> AssetProductRole:
    if asset_type == AssetType.flatlay:
        return AssetProductRole.flatlay_primary
    if asset_type == AssetType.model_set:
        return AssetProductRole.model_ref
    if asset_type == AssetType.advertising:
        return AssetProductRole.advertising_ref
    return AssetProductRole.manual


def upsert_product(db, product_code: str) -> Product:
    code = (product_code or "").strip().upper()
    product = db.query(Product).filter(Product.product_code == code).first()
    if product:
        return product
    product = Product(product_code=code)
    db.add(product)
    db.flush()
    return product


def main() -> None:
    args = parse_args()
    db = SessionLocal()
    counters = Counter()
    try:
        filters = [Asset.source_relpath.like(pat) for pat in args.pattern]
        assets = db.query(Asset).filter(or_(*filters)).all()
        target = upsert_product(db, args.product_code)

        for asset in assets:
            counters["assets_matched"] += 1

            old_tmp_links = (
                db.query(AssetProduct)
                .join(Product, Product.id == AssetProduct.product_id)
                .filter(
                    AssetProduct.asset_id == asset.id,
                    Product.product_code.like("TMPUID-%"),
                )
                .all()
            )
            for link in old_tmp_links:
                db.delete(link)
                counters["tmp_links_removed"] += 1

            existing = (
                db.query(AssetProduct)
                .filter(
                    AssetProduct.asset_id == asset.id,
                    AssetProduct.product_id == target.id,
                )
                .first()
            )
            if not existing:
                db.add(
                    AssetProduct(
                        asset_id=asset.id,
                        product_id=target.id,
                        relation_role=relation_role_for_asset(asset.asset_type),
                        source="manual_rebind",
                    )
                )
                counters["real_links_added"] += 1

            if asset.parse_status != ParseStatus.parsed:
                asset.parse_status = ParseStatus.parsed
                counters["parse_status_updated"] += 1

        if args.dry_run:
            db.rollback()
        else:
            db.commit()

        print("rebind_done")
        print(f"dry_run={args.dry_run}")
        print(f"product_code={target.product_code}")
        for k, v in sorted(counters.items()):
            print(f"{k}={v}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
