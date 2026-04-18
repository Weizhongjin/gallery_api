#!/usr/bin/env python3
from __future__ import annotations

from app.database import SessionLocal
from app.config import settings
from app.products.sales_sync import sync_sales_from_budan


def main() -> None:
    db = SessionLocal()
    try:
        summary = sync_sales_from_budan(
            db,
            budan_database_url=settings.budan_database_url,
            source="budan",
        )
        print("sales sync done:", summary)
    finally:
        db.close()


if __name__ == "__main__":
    main()
