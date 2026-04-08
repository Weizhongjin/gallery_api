from sqlalchemy import inspect, text


def test_database_connection(db):
    result = db.execute(text("SELECT 1")).scalar()
    assert result == 1


def test_all_tables_created(db_engine):
    inspector = inspect(db_engine)
    tables = inspector.get_table_names()
    expected = [
        "user", "image_group", "asset", "taxonomy_node", "taxonomy_candidate",
        "asset_tag", "asset_embedding", "lookbook", "lookbook_item", "lookbook_access",
    ]
    for table in expected:
        assert table in tables, f"Table '{table}' not found"


def test_asset_embedding_has_vector_column(db_engine):
    inspector = inspect(db_engine)
    cols = {c["name"] for c in inspector.get_columns("asset_embedding")}
    assert "vector" in cols
