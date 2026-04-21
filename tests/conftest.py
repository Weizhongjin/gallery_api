import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/cloth_gallery_test"
)

@pytest.fixture(scope="session")
def db_engine():
    engine = create_engine(TEST_DATABASE_URL)
    yield engine
    engine.dispose()

@pytest.fixture
def db(db_engine):
    connection = db_engine.connect()
    transaction = connection.begin()
    connection.execute(text("ALTER TABLE product ADD COLUMN IF NOT EXISTS year INTEGER"))
    connection.execute(text("ALTER TABLE aigc_task ADD COLUMN IF NOT EXISTS workflow_type varchar NOT NULL DEFAULT 'base'"))
    connection.execute(text("ALTER TABLE aigc_task ADD COLUMN IF NOT EXISTS source_task_id uuid NULL"))
    connection.execute(text("ALTER TABLE aigc_task ADD COLUMN IF NOT EXISTS source_candidate_id uuid NULL"))
    connection.execute(text("ALTER TABLE aigc_task ADD COLUMN IF NOT EXISTS optimize_prompt varchar NULL"))
    connection.execute(
        text(
            """
            DO $$
            BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_aigc_task_candidate_task_id_id'
              ) THEN
                ALTER TABLE aigc_task_candidate
                  ADD CONSTRAINT uq_aigc_task_candidate_task_id_id UNIQUE (task_id, id);
              END IF;
            END $$;
            """
        )
    )
    connection.execute(
        text(
            """
            DO $$
            BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_aigc_task_source_task_id_aigc_task'
              ) THEN
                ALTER TABLE aigc_task
                  ADD CONSTRAINT fk_aigc_task_source_task_id_aigc_task
                  FOREIGN KEY (source_task_id) REFERENCES aigc_task(id);
              END IF;
            END $$;
            """
        )
    )
    connection.execute(
        text(
            """
            DO $$
            BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_aigc_task_source_candidate_id_aigc_task_candidate'
              ) THEN
                ALTER TABLE aigc_task
                  ADD CONSTRAINT fk_aigc_task_source_candidate_id_aigc_task_candidate
                  FOREIGN KEY (source_candidate_id) REFERENCES aigc_task_candidate(id);
              END IF;
            END $$;
            """
        )
    )
    connection.execute(
        text(
            """
            DO $$
            BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_aigc_task_source_task_source_candidate_pair'
              ) THEN
                ALTER TABLE aigc_task
                  ADD CONSTRAINT fk_aigc_task_source_task_source_candidate_pair
                  FOREIGN KEY (source_task_id, source_candidate_id)
                  REFERENCES aigc_task_candidate(task_id, id);
              END IF;
            END $$;
            """
        )
    )
    connection.execute(
        text(
            """
            DO $$
            BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'ck_aigc_task_source_pair_nullity'
              ) THEN
                ALTER TABLE aigc_task
                  ADD CONSTRAINT ck_aigc_task_source_pair_nullity
                  CHECK (
                    (source_task_id IS NULL AND source_candidate_id IS NULL)
                    OR
                    (source_task_id IS NOT NULL AND source_candidate_id IS NOT NULL)
                  );
              END IF;
            END $$;
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS product_sales_summary (
              product_id uuid PRIMARY KEY REFERENCES product(id),
              product_code varchar NOT NULL,
              sales_total_qty integer NOT NULL DEFAULT 0,
              updated_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS sales_order_raw (
              id serial PRIMARY KEY,
              source varchar NOT NULL DEFAULT 'budan',
              source_order_id integer NOT NULL,
              order_date date NULL,
              style_no_norm varchar NOT NULL,
              total_qty integer NOT NULL DEFAULT 0,
              customer varchar NULL,
              salesperson varchar NULL,
              order_type varchar NULL,
              source_file varchar NULL,
              raw_payload jsonb NULL,
              created_at timestamptz NOT NULL DEFAULT now(),
              updated_at timestamptz NOT NULL DEFAULT now(),
              CONSTRAINT uq_sales_order_raw_source_order UNIQUE (source, source_order_id)
            )
            """
        )
    )
    session = Session(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


from fastapi.testclient import TestClient

@pytest.fixture
def client(db):
    from app.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
