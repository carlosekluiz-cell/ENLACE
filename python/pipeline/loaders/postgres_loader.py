"""Generic PostgreSQL upsert helper for data pipelines."""
import psycopg2
from psycopg2.extras import execute_values
from typing import Optional
from python.pipeline.config import DatabaseConfig


def upsert_batch(
    table: str,
    columns: list[str],
    values: list[tuple],
    conflict_columns: list[str],
    update_columns: Optional[list[str]] = None,
    db_config: Optional[DatabaseConfig] = None,
) -> tuple[int, int]:
    """Batch upsert rows into a PostgreSQL table.

    Returns (inserted_count, updated_count).
    """
    config = db_config or DatabaseConfig()
    conn = psycopg2.connect(config.url)
    cur = conn.cursor()

    col_str = ", ".join(columns)
    conflict_str = ", ".join(conflict_columns)

    if update_columns:
        update_str = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_columns)
        sql = f"""
            INSERT INTO {table} ({col_str}) VALUES %s
            ON CONFLICT ({conflict_str}) DO UPDATE SET {update_str}
        """
    else:
        sql = f"""
            INSERT INTO {table} ({col_str}) VALUES %s
            ON CONFLICT ({conflict_str}) DO NOTHING
        """

    # Get count before
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    count_before = cur.fetchone()[0]

    execute_values(cur, sql, values, page_size=1000)

    cur.execute(f"SELECT COUNT(*) FROM {table}")
    count_after = cur.fetchone()[0]

    conn.commit()
    inserted = count_after - count_before
    updated = len(values) - inserted if update_columns else 0

    cur.close()
    conn.close()

    return inserted, updated


def refresh_materialized_view(view_name: str, concurrently: bool = True, db_config: Optional[DatabaseConfig] = None):
    """Refresh a materialized view."""
    config = db_config or DatabaseConfig()
    conn = psycopg2.connect(config.url)
    cur = conn.cursor()

    concurrent = "CONCURRENTLY" if concurrently else ""
    cur.execute(f"REFRESH MATERIALIZED VIEW {concurrent} {view_name}")

    conn.commit()
    cur.close()
    conn.close()
