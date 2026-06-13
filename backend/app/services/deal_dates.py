"""Date helpers for deal contracts — lease/finance maturity from terms + deal dates."""
from __future__ import annotations

import calendar
from datetime import date
from typing import Optional


def add_months(d: date, months: int) -> date:
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return d.replace(year=year, month=month, day=day)


def compute_contract_end_date(
    deal_type: Optional[str],
    contract_date: Optional[date],
    *,
    delivery_date: Optional[date] = None,
    first_payment_date: Optional[date] = None,
    term: Optional[int] = None,
    num_payments: Optional[int] = None,
) -> Optional[date]:
    """Lease/finance maturity from start date + term.

    ``contract_date`` is the authoritative deal date on the worksheet. When
    ``term`` is missing, ``num_payments`` is used as a fallback month count.
    """
    if deal_type not in ("lease", "finance"):
        return None
    start = contract_date or first_payment_date or delivery_date
    if start is None:
        return None
    months = term if term is not None else num_payments
    if months is None or months <= 0:
        return None
    return add_months(start, int(months))
