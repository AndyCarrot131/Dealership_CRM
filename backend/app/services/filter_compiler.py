from datetime import datetime, timedelta, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.models.customer import Customer, CustomerCar

# Maps predicate tree column keys to SQLAlchemy columns.
_COLUMN_MAP: dict[str, sa.Column] = {
    "customers.last_contacted_at": Customer.last_contacted_at,
    "customer_car.make": CustomerCar.make,
    "customer_car.model": CustomerCar.model,
    "customer_car.year": CustomerCar.year,
    "customer_car.ownership_type": CustomerCar.ownership_type,
    "customer_car.lease_end_date": CustomerCar.lease_end_date,
}

_CAR_COLUMNS = frozenset(
    {
        "customer_car.make",
        "customer_car.model",
        "customer_car.year",
        "customer_car.ownership_type",
        "customer_car.lease_end_date",
    }
)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _compile_condition(cond: dict[str, Any]) -> sa.ColumnElement:
    col_key: str = cond["col"]
    cmp: str = cond["cmp"]
    val = cond["val"]

    col = _COLUMN_MAP[col_key]

    if cmp == "eq":
        return col == val
    if cmp == "ne":
        return col != val
    if cmp == "lt":
        return col < val
    if cmp == "lte":
        return col <= val
    if cmp == "gt":
        return col > val
    if cmp == "gte":
        return col >= val
    if cmp == "in":
        return col.in_(val)
    if cmp == "days_ago_gte":
        threshold = _now() - timedelta(days=int(val))
        return sa.or_(col.is_(None), col <= threshold)
    if cmp == "days_ago_lte":
        threshold = _now() - timedelta(days=int(val))
        return col >= threshold
    raise ValueError(f"Unknown operator: {cmp!r}")


def _has_car_conditions(tree: dict[str, Any]) -> bool:
    return any(c["col"] in _CAR_COLUMNS for c in tree.get("conditions", []))


def preview_sql(filter_tree: dict[str, Any]) -> str:
    """Return a human-readable SQL WHERE string compiled from filter_tree, for UI display."""
    try:
        clause = compile_filter(filter_tree)
        compiled = clause.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
        return str(compiled)
    except Exception:
        return ""


def compile_filter(filter_tree: dict[str, Any]) -> sa.ColumnElement:
    """Return a SQLAlchemy WHERE clause for use in a customers query.

    Car-column conditions are wrapped in an EXISTS subquery so that the
    caller's outer query stays a flat SELECT on customers without fan-out.
    """
    op: str = filter_tree["op"]
    conditions: list[dict[str, Any]] = filter_tree["conditions"]

    customer_clauses: list[sa.ColumnElement] = []
    car_clauses: list[sa.ColumnElement] = []

    for cond in conditions:
        clause = _compile_condition(cond)
        if cond["col"] in _CAR_COLUMNS:
            car_clauses.append(clause)
        else:
            customer_clauses.append(clause)

    parts: list[sa.ColumnElement] = list(customer_clauses)

    if car_clauses:
        car_expr = sa.and_(*car_clauses) if op == "and" else sa.or_(*car_clauses)
        exists_subq = (
            sa.select(CustomerCar.id)
            .where(CustomerCar.customer_id == Customer.id)
            .where(car_expr)
            .correlate(Customer)
            .exists()
        )
        parts.append(exists_subq)

    if not parts:
        return sa.true()
    if op == "and":
        return sa.and_(*parts)
    return sa.or_(*parts)
