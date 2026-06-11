"""Guarded read-only SQL tool — the assistant's safety boundary."""
import pytest

from app.models.customer import Customer
from app.services.sql_tool import run_select, validate_sql


# ─── validate_sql ───────────────────────────────────────────────────────────────


def test_plain_select_is_allowed():
    assert validate_sql("SELECT id FROM customers") == "SELECT id FROM customers"


def test_with_cte_is_allowed():
    sql = "WITH recent AS (SELECT id FROM customers) SELECT id FROM recent"
    assert validate_sql(sql) == sql


def test_trailing_semicolon_is_stripped():
    assert validate_sql("SELECT id FROM customers;") == "SELECT id FROM customers"


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO customers (full_name) VALUES ('x')",
        "UPDATE customers SET full_name = 'x'",
        "DELETE FROM customers",
        "DROP TABLE customers",
        "ALTER TABLE customers ADD COLUMN x text",
        "TRUNCATE customers",
        "CREATE TABLE evil (id int)",
        "GRANT ALL ON customers TO PUBLIC",
    ],
)
def test_write_statements_are_rejected(sql):
    with pytest.raises(ValueError):
        validate_sql(sql)


def test_multi_statement_is_rejected():
    with pytest.raises(ValueError, match="single"):
        validate_sql("SELECT 1; DELETE FROM customers")


def test_comments_are_rejected():
    with pytest.raises(ValueError, match="comment"):
        validate_sql("SELECT id FROM customers -- sneaky")


def test_select_into_is_rejected():
    with pytest.raises(ValueError):
        validate_sql("SELECT * INTO evil FROM customers")


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT password_hash FROM users",
        "SELECT value FROM user_settings",
        "SELECT value FROM app_settings",
        "SELECT * FROM information_schema.tables",
        "SELECT pg_sleep(10)",
        "SELECT * FROM pg_shadow",
        "SELECT * FROM public.customers",  # schema qualification would bypass CTE shadowing
    ],
)
def test_sensitive_tables_and_functions_are_blocked(sql):
    with pytest.raises(ValueError):
        validate_sql(sql)


def test_with_recursive_is_rejected():
    # RECURSIVE would make the per-user scoping CTEs self-referential.
    with pytest.raises(ValueError):
        validate_sql("WITH RECURSIVE r AS (SELECT 1) SELECT * FROM r")


def test_forbidden_word_inside_string_literal_is_fine():
    # 'update' appears only as data, not as a keyword.
    sql = "SELECT id FROM customers WHERE note = 'please update me'"
    assert validate_sql(sql) == sql


def test_blocked_table_hidden_in_literal_is_fine():
    sql = "SELECT id FROM customers WHERE note = 'users'"
    assert validate_sql(sql) == sql


# ─── run_select ─────────────────────────────────────────────────────────────────


async def test_run_select_returns_rows(db_session, sales_user):
    db_session.add_all(
        [
            Customer(assigned_sales_id=sales_user.id, full_name="Alpha"),
            Customer(assigned_sales_id=sales_user.id, full_name="Beta"),
        ]
    )
    await db_session.commit()

    result = await run_select(
        db_session, "SELECT full_name FROM customers ORDER BY full_name"
    )
    assert result["columns"] == ["full_name"]
    assert result["rows"] == [["Alpha"], ["Beta"]]
    assert result["row_count"] == 2
    assert result["truncated"] is False


async def test_run_select_caps_rows(db_session, sales_user):
    db_session.add_all(
        Customer(assigned_sales_id=sales_user.id, full_name=f"C{i}") for i in range(5)
    )
    await db_session.commit()

    result = await run_select(db_session, "SELECT id FROM customers", max_rows=3)
    assert result["row_count"] == 3
    assert result["truncated"] is True


async def test_run_select_rejects_invalid_sql(db_session):
    with pytest.raises(ValueError):
        await run_select(db_session, "DELETE FROM customers")


async def test_run_select_wraps_db_errors(db_session):
    with pytest.raises(ValueError, match="Query failed"):
        await run_select(db_session, "SELECT nope FROM customers")
    # Session must still be usable after a failed query.
    result = await run_select(db_session, "SELECT COUNT(*) AS n FROM customers")
    assert result["rows"] == [["0"]]
