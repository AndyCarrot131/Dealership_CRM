"""Guarded read-only SQL execution for the assistant chat agent.

The CRM rule is that AI never writes through raw SQL. This tool relaxes the
read side only, behind several layers of defense:

  1. Single SELECT/WITH statement only — no semicolons, no comments.
  2. Forbidden-keyword scan (DML/DDL, SET, COPY, pg_* functions, ...).
  3. Sensitive tables are blocked outright (credentials, API keys).
  4. The statement is wrapped in a subquery with a hard row cap.
  5. Postgres executes with a statement timeout, and the transaction is
     always rolled back afterwards so nothing can persist.
"""
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

MAX_ROWS = 50
STATEMENT_TIMEOUT_MS = 5000

# Tables holding credentials/secrets or engine internals. "public" and "main"
# are blocked so schema-qualified names (public.customers) can't bypass the
# per-user CTE shadowing applied by the assistant agent.
BLOCKED_IDENTIFIERS = frozenset(
    {
        "users",
        "user_settings",
        "app_settings",
        "llm_request_logs",
        "alembic_version",
        "pg_catalog",
        "information_schema",
        "pg_shadow",
        "pg_authid",
        "public",
        "main",
    }
)

# "recursive" is forbidden because WITH RECURSIVE would make the scoping CTEs
# self-referential and break the shadowing guarantee.
_FORBIDDEN_WORDS = (
    "insert|update|delete|drop|alter|create|truncate|grant|revoke|copy|merge|"
    "call|do|execute|prepare|deallocate|set|reset|vacuum|reindex|cluster|"
    "listen|notify|refresh|comment|security|lock|into|recursive"
)
_FORBIDDEN_RE = re.compile(rf"\b(?:{_FORBIDDEN_WORDS})\b", re.IGNORECASE)
_STARTS_WITH_SELECT_RE = re.compile(r"^\s*(?:select|with)\b", re.IGNORECASE)
_WORD_RE = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*")


def _strip_string_literals(sql: str) -> str:
    """Replace '...' literals with '' so values can't trip keyword checks."""
    return re.sub(r"'(?:[^']|'')*'", "''", sql)


def validate_sql(sql: str) -> str:
    """Return the normalized statement, or raise ValueError with the reason."""
    cleaned = sql.strip().rstrip(";").strip()
    if not cleaned:
        raise ValueError("Empty SQL statement.")
    if ";" in cleaned:
        raise ValueError("Only a single SQL statement is allowed.")
    if "--" in cleaned or "/*" in cleaned:
        raise ValueError("SQL comments are not allowed.")
    if not _STARTS_WITH_SELECT_RE.match(cleaned):
        raise ValueError("Only SELECT queries are allowed.")

    scannable = _strip_string_literals(cleaned)
    forbidden = _FORBIDDEN_RE.search(scannable)
    if forbidden:
        raise ValueError(f"Keyword not allowed in queries: {forbidden.group(0).upper()}.")

    for word in _WORD_RE.findall(scannable):
        lowered = word.lower()
        if lowered in BLOCKED_IDENTIFIERS or lowered.startswith("pg_"):
            raise ValueError(f"Access to '{word}' is not allowed.")

    return cleaned


def build_scoped_sql(
    sql: str, scope_filters: dict[str, tuple[str, int]], schema: str
) -> str:
    """Enforce per-user isolation by shadowing scoped tables with CTEs.

    Prepending `WITH customers AS (SELECT * FROM <schema>.customers WHERE
    assigned_sales_id = <uid>)` makes every reference to a scoped table — in
    any JOIN, subquery, or UNION branch — resolve to the pre-filtered set.
    This does not trust the model's SQL at all: schema-qualified bypasses
    (public.customers) and WITH RECURSIVE are rejected by validate_sql before
    this runs, and the CTE bodies use schema-qualified names so they reach the
    real tables on both Postgres and SQLite. If the model defines a CTE with
    the same name, the database rejects the duplicate, which fails safe.
    """
    ctes = ", ".join(
        f"{table} AS (SELECT * FROM {schema}.{table} WHERE {column} = {int(value)})"
        for table, (column, value) in scope_filters.items()
    )
    stripped = sql.strip()
    match = re.match(r"^with\b", stripped, re.IGNORECASE)
    if match:
        return f"WITH {ctes}, {stripped[match.end():].lstrip()}"
    return f"WITH {ctes} {stripped}"


async def run_select(
    db: AsyncSession,
    sql: str,
    max_rows: int = MAX_ROWS,
    scope_filters: dict[str, tuple[str, int]] | None = None,
) -> dict[str, Any]:
    """Validate and execute a SELECT, returning columns/rows for the agent.

    `scope_filters` maps table name -> (ownership column, required value);
    when given, those tables are CTE-shadowed so the query can only see the
    matching rows. The session is rolled back in all cases — this tool must
    never commit.
    """
    validated = validate_sql(sql)

    is_postgres = db.bind is not None and db.bind.dialect.name == "postgresql"
    if scope_filters:
        schema = "public" if is_postgres else "main"
        validated = build_scoped_sql(validated, scope_filters, schema)

    wrapped = f"SELECT * FROM ({validated}) AS _result LIMIT {max_rows + 1}"

    try:
        if is_postgres:
            await db.execute(
                text(f"SET LOCAL statement_timeout = {STATEMENT_TIMEOUT_MS}")
            )
        result = await db.execute(text(wrapped))
        columns = list(result.keys())
        raw_rows = result.fetchall()
    except Exception as exc:
        await db.rollback()
        raise ValueError(f"Query failed: {exc}") from exc

    await db.rollback()

    truncated = len(raw_rows) > max_rows
    rows = [
        [None if value is None else str(value) for value in row]
        for row in raw_rows[:max_rows]
    ]
    return {
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "truncated": truncated,
    }
