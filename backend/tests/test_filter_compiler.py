"""Unit tests for the outreach filter compiler — the SQL safety boundary."""
from datetime import date

import pytest
from sqlalchemy.dialects import postgresql

from app.services.filter_compiler import compile_filter, preview_sql


def _compile_str(tree: dict) -> str:
    clause = compile_filter(tree)
    return str(clause.compile(dialect=postgresql.dialect()))


def test_eq_condition_uses_bind_parameters():
    tree = {
        "op": "and",
        "conditions": [{"col": "customers.last_contacted_at", "cmp": "eq", "val": "2026-01-01"}],
    }
    clause = compile_filter(tree)
    compiled = clause.compile(dialect=postgresql.dialect())
    # The value must travel as a bind parameter, never inline in the SQL text.
    assert "2026-01-01" not in str(compiled)
    assert "2026-01-01" in [str(v) for v in compiled.params.values()]


def test_unknown_column_is_rejected():
    tree = {
        "op": "and",
        "conditions": [{"col": "users.password_hash", "cmp": "eq", "val": "x"}],
    }
    with pytest.raises(KeyError):
        compile_filter(tree)


def test_sql_injection_in_column_name_is_rejected():
    tree = {
        "op": "and",
        "conditions": [{"col": "1=1; DROP TABLE customers; --", "cmp": "eq", "val": "x"}],
    }
    with pytest.raises(KeyError):
        compile_filter(tree)


def test_unknown_operator_is_rejected():
    tree = {
        "op": "and",
        "conditions": [{"col": "customer_car.make", "cmp": "like_raw", "val": "x"}],
    }
    with pytest.raises(ValueError):
        compile_filter(tree)


def test_empty_conditions_compile_to_true():
    sql = _compile_str({"op": "and", "conditions": []})
    assert sql.lower() == "true"


def test_car_conditions_wrap_in_exists_subquery():
    tree = {
        "op": "and",
        "conditions": [{"col": "customer_car.make", "cmp": "eq", "val": "Toyota"}],
    }
    sql = _compile_str(tree)
    assert "EXISTS" in sql
    assert "customer_car" in sql


def test_in_operator_compiles():
    tree = {
        "op": "and",
        "conditions": [{"col": "customer_car.ownership_type", "cmp": "in", "val": ["lease", "finance"]}],
    }
    sql = _compile_str(tree)
    assert "IN" in sql


def test_days_ago_gte_includes_never_contacted():
    tree = {
        "op": "and",
        "conditions": [{"col": "customers.last_contacted_at", "cmp": "days_ago_gte", "val": 90}],
    }
    sql = _compile_str(tree)
    assert "IS NULL" in sql


def test_future_lease_window_excludes_expired_leases(monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 7, 12)

    monkeypatch.setattr("app.services.filter_compiler.date", FixedDate)
    tree = {
        "op": "and",
        "conditions": [
            {
                "col": "customer_car.lease_end_date",
                "cmp": "days_from_now_gte",
                "val": 0,
            },
            {
                "col": "customer_car.lease_end_date",
                "cmp": "days_from_now_lte",
                "val": 180,
            },
        ],
    }

    preview = preview_sql(tree)

    assert "customer_car.lease_end_date >= '2026-07-12'" in preview
    assert "customer_car.lease_end_date <= '2027-01-08'" in preview


def test_or_op_joins_with_or():
    tree = {
        "op": "or",
        "conditions": [
            {"col": "customers.last_contacted_at", "cmp": "days_ago_gte", "val": 90},
            {"col": "customers.last_contacted_at", "cmp": "eq", "val": None},
        ],
    }
    sql = _compile_str(tree)
    assert " OR " in sql


def test_mixed_customer_and_car_conditions():
    tree = {
        "op": "and",
        "conditions": [
            {"col": "customers.last_contacted_at", "cmp": "days_ago_gte", "val": 30},
            {"col": "customer_car.ownership_type", "cmp": "eq", "val": "lease"},
        ],
    }
    sql = _compile_str(tree)
    assert "EXISTS" in sql
    assert " AND " in sql


def test_preview_sql_returns_readable_string():
    tree = {
        "op": "and",
        "conditions": [{"col": "customer_car.make", "cmp": "eq", "val": "Honda"}],
    }
    preview = preview_sql(tree)
    assert "Honda" in preview
    assert "EXISTS" in preview


def test_preview_sql_returns_empty_string_on_invalid_tree():
    assert preview_sql({"op": "and", "conditions": [{"col": "bad.col", "cmp": "eq", "val": 1}]}) == ""
