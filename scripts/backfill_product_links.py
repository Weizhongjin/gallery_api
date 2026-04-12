#!/usr/bin/env python3
"""Backfill asset_type + product links from legacy folder naming.

Usage:
  cd gallery-api
  python scripts/backfill_product_links.py
"""

import re
from collections import Counter

from sqlalchemy import text

from app.assets.models import Asset, AssetProduct, AssetProductRole, AssetType, ParseStatus, Product
from app.assets.service import _build_group_tempuid
from app.database import SessionLocal
from app.products.service import rebuild_product_tags_for_product

TOKEN_RE = re.compile(r"(?:[A-Z]\d{5,}[A-Z]?|\d{8}[A-Z]?)", re.IGNORECASE)
SINGLE_DIGIT_RE = re.compile(r"^\d$")


def extract_codes(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for tok in TOKEN_RE.findall((text or "").upper()):
        if tok not in seen:
            seen.add(tok)
            out.append(tok)
    return out


def infer_asset_type(dataset: str) -> AssetType:
    ds = (dataset or "").strip()
    if "广告" in ds:
        return AssetType.advertising
    if "平铺图" in ds:
        return AssetType.flatlay
    if "季图片" in ds:
        return AssetType.model_set
    return AssetType.unknown


def infer_from_relpath(rel: str) -> tuple[AssetType, str | None, ParseStatus, list[str]]:
    parts = [x for x in (rel or "").split("/") if x]
    if not parts:
        return AssetType.unknown, None, ParseStatus.unresolved, []
    dataset = parts[0]
    asset_type = infer_asset_type(dataset)
    stem = parts[-1].rsplit(".", 1)[0]

    codes: list[str] = []
    if asset_type == AssetType.flatlay:
        codes = extract_codes(stem)
    elif asset_type == AssetType.advertising:
        category = parts[1] if len(parts) >= 3 else ""
        folder = parts[2] if len(parts) >= 4 else ""
        if category == "套装" and SINGLE_DIGIT_RE.fullmatch(folder):
            codes = [_build_group_tempuid(dataset, category, folder)]
        else:
            codes = extract_codes(folder)
    elif asset_type == AssetType.model_set:
        folder = parts[1] if len(parts) >= 3 else ""
        codes = extract_codes(folder)
        if not codes:
            codes = extract_codes(stem)
    else:
        codes = extract_codes(stem)
        if not codes and len(parts) >= 2:
            codes = extract_codes(parts[-2])
    status = ParseStatus.parsed if codes else ParseStatus.unresolved
    return asset_type, dataset, status, codes


def role_for_type(asset_type: AssetType) -> AssetProductRole:
    if asset_type == AssetType.flatlay:
        return AssetProductRole.flatlay_primary
    if asset_type == AssetType.advertising:
        return AssetProductRole.advertising_ref
    if asset_type == AssetType.model_set:
        return AssetProductRole.model_ref
    return AssetProductRole.manual


def upsert_product(db, code: str) -> Product:
    c = code.strip().upper()
    p = db.query(Product).filter(Product.product_code == c).first()
    if p:
        return p
    p = Product(product_code=c)
    db.add(p)
    db.flush()
    return p


def main() -> None:
    db = SessionLocal()
    try:
        group_map = {
            gid: path
            for gid, path in db.execute(text("SELECT id::text, path FROM image_group")).all()
        }
        assets = db.query(Asset).all()
        counters = Counter()
        touched_products: set = set()

        for asset in assets:
            group_path = group_map.get(str(asset.group_id)) if asset.group_id else None

            rel = asset.source_relpath
            if not rel:
                if group_path:
                    gp = group_path.replace("imports/data-images/", "").strip("/")
                    rel = f"{gp}/{asset.filename}" if gp else asset.filename
                else:
                    rel = asset.filename

            asset_type, dataset, parse_status, codes = infer_from_relpath(rel)
            asset.asset_type = asset_type
            asset.source_dataset = dataset
            asset.source_relpath = rel
            asset.parse_status = parse_status
            counters[f"type:{asset_type.value}"] += 1
            counters[f"status:{parse_status.value}"] += 1

            for code in codes:
                product = upsert_product(db, code)
                link = (
                    db.query(AssetProduct)
                    .filter(AssetProduct.asset_id == asset.id, AssetProduct.product_id == product.id)
                    .first()
                )
                if not link:
                    db.add(
                        AssetProduct(
                            asset_id=asset.id,
                            product_id=product.id,
                            relation_role=role_for_type(asset_type),
                            source="legacy_backfill",
                        )
                    )
                    counters["links_added"] += 1
                touched_products.add(product.id)

        db.flush()
        for pid in touched_products:
            rebuild_product_tags_for_product(db, pid)
        db.commit()

        print("backfill_done")
        for k, v in sorted(counters.items()):
            print(f"{k}={v}")
        print(f"products_touched={len(touched_products)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
