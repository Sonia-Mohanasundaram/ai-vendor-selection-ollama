from __future__ import annotations

from typing import Iterable

from sqlalchemy import Engine, inspect, text


def _column_exists(engine: Engine, table: str, column: str) -> bool:
    insp = inspect(engine)
    cols = insp.get_columns(table)
    return any(c.get("name") == column for c in cols)


def ensure_analysis_columns(engine: Engine) -> None:
    """Best-effort schema sync for the `analysis` table.

    This project doesn't use Alembic migrations. `Base.metadata.create_all()` creates tables
    but does NOT add new columns to existing tables, which can make it look like only a
    subset of fields are stored.

    We keep this intentionally small and idempotent.
    """

    insp = inspect(engine)
    if "analysis" not in insp.get_table_names():
        return

    dialect = engine.dialect.name.lower()

    def add_column(sql: str) -> None:
        with engine.begin() as conn:
            conn.execute(text(sql))

    # Title (simple text)
    if not _column_exists(engine, "analysis", "title"):
        add_column('ALTER TABLE "analysis" ADD COLUMN title VARCHAR')

    # JSON fields: use native JSON/JSONB on Postgres, TEXT elsewhere.
    json_type = "JSON" if dialect == "postgresql" else "TEXT"

    if not _column_exists(engine, "analysis", "input_json"):
        add_column(f'ALTER TABLE "analysis" ADD COLUMN input_json {json_type} NULL')

    if not _column_exists(engine, "analysis", "output_json"):
        add_column(f'ALTER TABLE "analysis" ADD COLUMN output_json {json_type} NULL')

    if not _column_exists(engine, "analysis", "files_json"):
        add_column(f'ALTER TABLE "analysis" ADD COLUMN files_json {json_type} NULL')

    if not _column_exists(engine, "analysis", "output_files_json"):
        add_column(f'ALTER TABLE "analysis" ADD COLUMN output_files_json {json_type} NULL')


def ensure_uploaded_files_columns(engine: Engine) -> None:
    """Best-effort schema sync for the `uploaded_files` table."""

    insp = inspect(engine)
    if "uploaded_files" not in insp.get_table_names():
        return

    def add_column(sql: str) -> None:
        with engine.begin() as conn:
            conn.execute(text(sql))

    if not _column_exists(engine, "uploaded_files", "analysis_id"):
        add_column('ALTER TABLE "uploaded_files" ADD COLUMN analysis_id INTEGER NULL')
