#!/usr/bin/env python3
"""Re-upload asset objects to MinIO from local files and rewrite asset URI buckets."""

from __future__ import annotations

import argparse
import io
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import boto3
import psycopg2
from botocore.client import Config
from PIL import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db-dsn",
        default="postgresql://postgres:postgres@localhost:5432/cloth_gallery",
        help="PostgreSQL DSN.",
    )
    parser.add_argument(
        "--src-root",
        default="/Users/weizhongjin/develop_program/lines/qiaofei/projects/active/cloth_gallery/data/images",
        help="Local root directory mapped by asset.source_relpath.",
    )
    parser.add_argument("--endpoint-url", default="http://localhost:9000", help="MinIO/S3 endpoint.")
    parser.add_argument("--access-key", default="minioadmin", help="MinIO/S3 access key.")
    parser.add_argument("--secret-key", default="minioadmin", help="MinIO/S3 secret key.")
    parser.add_argument("--region", default="us-east-1", help="S3 region.")
    parser.add_argument("--bucket", default="cloth-gallery", help="Target bucket.")
    parser.add_argument("--limit", type=int, default=0, help="Limit asset rows for test run.")
    parser.add_argument("--dry-run", action="store_true", help="Do not upload or update DB.")
    return parser.parse_args()


def resize_to_jpeg(data: bytes, max_side: int) -> bytes:
    image = Image.open(io.BytesIO(data))
    if image.mode != "RGB":
        image = image.convert("RGB")

    longest = max(image.width, image.height)
    if longest > max_side:
        ratio = max_side / longest
        size = (round(image.width * ratio), round(image.height * ratio))
        image = image.resize(size, Image.LANCZOS)

    out = io.BytesIO()
    image.save(out, format="JPEG", quality=85, optimize=True)
    return out.getvalue()


def key_from_uri(uri: str) -> str:
    if not uri.startswith("s3://"):
        raise ValueError(f"Invalid s3 uri: {uri!r}")
    parts = uri.split("/", 3)
    if len(parts) < 4:
        raise ValueError(f"Invalid s3 uri: {uri!r}")
    return parts[3]


def iter_assets(cur, limit: int) -> List[Tuple[str, str, str, str, str]]:
    sql = """
        SELECT id::text, source_relpath, original_uri, display_uri, thumb_uri
        FROM asset
        ORDER BY created_at ASC
    """
    if limit > 0:
        sql += f" LIMIT {limit:d}"
    cur.execute(sql)
    return cur.fetchall()


def ensure_bucket(s3, bucket: str) -> None:
    try:
        s3.head_bucket(Bucket=bucket)
    except Exception:
        s3.create_bucket(Bucket=bucket)


def main() -> int:
    args = parse_args()
    src_root = Path(args.src_root)

    s3 = boto3.client(
        "s3",
        endpoint_url=args.endpoint_url,
        aws_access_key_id=args.access_key,
        aws_secret_access_key=args.secret_key,
        region_name=args.region,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    ensure_bucket(s3, args.bucket)

    conn = psycopg2.connect(args.db_dsn)
    conn.autocommit = False
    cur = conn.cursor()

    stats = Counter()
    rows = iter_assets(cur, args.limit)
    print(f"total_assets={len(rows)} dry_run={args.dry_run}")

    for idx, (asset_id, source_relpath, original_uri, display_uri, thumb_uri) in enumerate(rows, 1):
        stats["assets_seen"] += 1

        if not source_relpath:
            stats["missing_relpath"] += 1
            continue

        src_path = src_root / source_relpath
        if not src_path.exists():
            stats["missing_file"] += 1
            if stats["missing_file"] <= 20:
                print(f"missing_file={src_path}")
            continue

        try:
            raw = src_path.read_bytes()
            display = resize_to_jpeg(raw, 1200)
            thumb = resize_to_jpeg(raw, 400)

            upload_plan: Dict[str, bytes] = {}
            for uri, payload in (
                (original_uri, raw),
                (display_uri, display),
                (thumb_uri, thumb),
            ):
                key = key_from_uri(uri)
                # Keep original if keys collide.
                if key not in upload_plan:
                    upload_plan[key] = payload

            if not args.dry_run:
                for key, payload in upload_plan.items():
                    s3.put_object(Bucket=args.bucket, Key=key, Body=payload, ContentType="image/jpeg")
                    stats["objects_uploaded"] += 1

            stats["assets_uploaded"] += 1
        except Exception as exc:
            stats["upload_error"] += 1
            if stats["upload_error"] <= 20:
                print(f"upload_error asset_id={asset_id} err={type(exc).__name__}: {exc}")

        if idx % 100 == 0:
            print(
                f"progress={idx}/{len(rows)} "
                f"uploaded_assets={stats['assets_uploaded']} "
                f"missing_file={stats['missing_file']} "
                f"upload_error={stats['upload_error']}"
            )

    if not args.dry_run:
        cur.execute(
            """
            UPDATE asset
            SET
              original_uri = regexp_replace(original_uri, '^s3://[^/]+/', %s),
              display_uri  = regexp_replace(display_uri,  '^s3://[^/]+/', %s),
              thumb_uri    = regexp_replace(thumb_uri,    '^s3://[^/]+/', %s)
            """,
            (f"s3://{args.bucket}/", f"s3://{args.bucket}/", f"s3://{args.bucket}/"),
        )
        stats["rows_uri_updated"] = cur.rowcount
        conn.commit()

    cur.execute(
        """
        SELECT split_part(thumb_uri, '/', 3) AS bucket, count(*)
        FROM asset
        GROUP BY 1
        ORDER BY 2 DESC
        """
    )
    bucket_counts = cur.fetchall()

    print("--- migration stats ---")
    for key in sorted(stats.keys()):
        print(f"{key}={stats[key]}")
    print(f"bucket_counts={bucket_counts}")

    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
