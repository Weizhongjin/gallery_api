from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.assets.models import ProductSalesSummary, SalesOrderRaw


def _normalize_code(code: str | None) -> str:
    return (code or "").strip().upper()


def sync_sales_from_budan(
    db: Session,
    *,
    budan_database_url: str,
    source: str = "budan",
) -> dict[str, int]:
    """Sync budan.orders into sales_order_raw and rebuild product_sales_summary.

    This operation is idempotent: raw rows are upserted by (source, source_order_id),
    summary rows are rebuilt from normalized style_no aggregation.
    """
    budan_engine = create_engine(budan_database_url)

    with budan_engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, salesperson, source_file, order_type, order_date, customer,
                       style_no, color, total_qty, remark
                FROM public.orders
                ORDER BY id
                """
            )
        ).mappings().all()

    upsert_payload: list[dict[str, Any]] = []
    for row in rows:
        style_no_norm = _normalize_code(row.get("style_no"))
        if not style_no_norm:
            continue
        total_qty = int(row.get("total_qty") or 0)
        upsert_payload.append(
            {
                "source": source,
                "source_order_id": int(row["id"]),
                "order_date": row.get("order_date"),
                "style_no_norm": style_no_norm,
                "total_qty": total_qty,
                "customer": row.get("customer"),
                "salesperson": row.get("salesperson"),
                "order_type": row.get("order_type"),
                "source_file": row.get("source_file"),
                "raw_payload": {
                    "style_no": row.get("style_no"),
                    "color": row.get("color"),
                    "remark": row.get("remark"),
                },
            }
        )

    raw_upserts = 0
    if upsert_payload:
        stmt = insert(SalesOrderRaw).values(upsert_payload)
        stmt = stmt.on_conflict_do_update(
            index_elements=["source", "source_order_id"],
            set_={
                "order_date": stmt.excluded.order_date,
                "style_no_norm": stmt.excluded.style_no_norm,
                "total_qty": stmt.excluded.total_qty,
                "customer": stmt.excluded.customer,
                "salesperson": stmt.excluded.salesperson,
                "order_type": stmt.excluded.order_type,
                "source_file": stmt.excluded.source_file,
                "raw_payload": stmt.excluded.raw_payload,
            },
        )
        db.execute(stmt)
        raw_upserts = len(upsert_payload)

    db.execute(text("DELETE FROM product_sales_summary"))
    db.execute(
        text(
            """
            INSERT INTO product_sales_summary (product_id, product_code, sales_total_qty, updated_at)
            SELECT p.id, p.product_code, agg.sales_total_qty, now()
            FROM product p
            JOIN (
                SELECT style_no_norm, SUM(COALESCE(total_qty, 0))::int AS sales_total_qty
                FROM sales_order_raw
                WHERE style_no_norm IS NOT NULL AND style_no_norm <> ''
                GROUP BY style_no_norm
            ) agg
              ON upper(trim(p.product_code)) = agg.style_no_norm
            """
        )
    )

    summary_count = db.execute(select(func.count()).select_from(ProductSalesSummary)).scalar_one()

    db.commit()
    return {
        "raw_rows_read": len(rows),
        "raw_rows_upserted": raw_upserts,
        "summary_rows": int(summary_count),
    }
