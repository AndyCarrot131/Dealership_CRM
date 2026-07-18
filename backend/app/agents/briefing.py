"""Pre-appointment briefing orchestrator.

Workflow:
  1. Load the customer's deal history from the database.
  2. Load all currently active support docs.
  3. Fan out one LLM sub-agent call per support doc (parallel via asyncio.gather).
     - system prompt  = doc.checks
     - user message   = doc.content + serialised customer deal history
     - expected JSON  = {"triggered": bool, "alert": str, "suggestion": str}
  4. Collect only the triggered results.
  5. Run a single summariser call to produce a scannable briefing.
  6. Return the structured briefing dict.
"""

import asyncio
import json
import re
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.llm.client import LLMClient
from app.models.customer import Customer
from app.models.deal import Deal
from app.models.inventory import Inventory
from app.models.support_doc import SupportDoc

# ---------------------------------------------------------------------------
# Sub-agent
# ---------------------------------------------------------------------------

_SUB_SYSTEM_SUFFIX = (
    "\n\nYou MUST respond with ONLY a JSON object in exactly this format "
    "(no extra text, no markdown fences):\n"
    '{"triggered": true/false, "alert": "...", "suggestion": "..."}\n'
    'Set "triggered" to true only when the check genuinely applies to this customer. '
    'If triggered is false, "alert" and "suggestion" may be empty strings.'
)


async def _run_sub_agent(
    doc: SupportDoc,
    customer_history: dict[str, Any],
    llm: LLMClient,
) -> dict[str, Any]:
    system_prompt = (doc.checks or "").strip() + _SUB_SYSTEM_SUFFIX
    user_message = (
        f"Knowledge base:\n{doc.content}\n\n"
        f"Customer deal history:\n{json.dumps(customer_history, default=str)}"
    )

    try:
        response = await llm.chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            timeout=45,
            max_tokens=400,
        )
        raw = response["choices"][0]["message"].get("content", "")
        # Strip <think>…</think> blocks emitted by some models
        clean = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        json_match = re.search(r"\{.*\}", clean, flags=re.DOTALL)
        parsed: dict[str, Any] = json.loads(json_match.group() if json_match else clean)
    except Exception:
        parsed = {"triggered": False, "alert": "", "suggestion": ""}

    return {
        "doc_id": str(doc.id),
        "category": doc.category,
        "title": doc.title,
        "triggered": bool(parsed.get("triggered", False)),
        "alert": str(parsed.get("alert", "")).strip(),
        "suggestion": str(parsed.get("suggestion", "")).strip(),
    }


# ---------------------------------------------------------------------------
# Summariser
# ---------------------------------------------------------------------------

_SUMMARISER_SYSTEM = (
    "You are a concise sales briefing writer for a car dealership.\n"
    "You will receive a list of triggered alerts for a customer appointment.\n"
    "Write a short, scannable 'Suggested Opener' paragraph (2-3 sentences) that "
    "a sales rep can use to open the conversation naturally. "
    "Do not repeat the alerts verbatim — synthesise them into a warm, helpful opener.\n"
    "Respond with ONLY the opener text, no preamble."
)


async def _run_summariser(
    triggered: list[dict[str, Any]],
    customer_name: str,
    llm: LLMClient,
) -> str:
    if not triggered:
        return ""
    items = "\n".join(
        f"- [{r['category']} / {r['title']}] Alert: {r['alert']}  Suggestion: {r['suggestion']}"
        for r in triggered
    )
    user_message = f"Customer: {customer_name}\n\nTriggered alerts:\n{items}"
    try:
        response = await llm.chat(
            [
                {"role": "system", "content": _SUMMARISER_SYSTEM},
                {"role": "user", "content": user_message},
            ],
            timeout=45,
            max_tokens=300,
        )
        raw = response["choices"][0]["message"].get("content", "")
        clean = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        return clean
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _build_customer_history(customer: Customer, deals: list[Deal]) -> dict[str, Any]:
    """Serialise customer + deal history into a compact dict for LLM consumption."""
    deal_list = []
    for d in deals:
        entry: dict[str, Any] = {
            "deal_type": d.deal_type,
            "contract_date": str(d.contract_date) if d.contract_date else None,
            "make": d.make,
            "model": d.model,
            "model_year": d.model_year,
            "trim": d.trim_base,
            "trim_package": d.trim_package,
            "selling_price": str(d.selling_price) if d.selling_price is not None else None,
            "rate_pct": str(d.rate_pct) if d.rate_pct is not None else None,
            "term": d.term,
            "payment_frequency": d.payment_frequency,
            "payment_amount": str(d.payment_amount) if d.payment_amount is not None else None,
            "cash_down": str(d.cash_down) if d.cash_down is not None else None,
        }
        deal_list.append(entry)

    return {
        "customer_name": customer.full_name,
        "phone": customer.phone,
        "email": customer.email,
        "note": customer.note,
        "deals": deal_list,
    }


def _inventory_to_dict(item: Inventory) -> dict[str, Any]:
    return {
        "id": item.id,
        "make": item.make,
        "model": item.model,
        "year": item.year,
        "trim": item.trim,
        "mileage": item.mileage,
        "price": str(item.price) if item.price is not None else None,
        "features": item.features,
        "notes": item.notes,
        "status": item.status,
    }


# ---------------------------------------------------------------------------
# Orchestrator (public entry point)
# ---------------------------------------------------------------------------

async def run_briefing(
    customer_id: int,
    db: AsyncSession,
    llm: LLMClient,
) -> dict[str, Any]:
    """Generate a pre-appointment briefing for the given customer.

    Returns a dict with keys:
      customer_name, generated_at, triggered_count, sections (list), summary (str)
    """
    # 1. Load customer
    customer_result = await db.execute(
        select(Customer)
        .where(Customer.id == customer_id)
        .options(selectinload(Customer.cars))
    )
    customer = customer_result.scalar_one_or_none()
    if customer is None:
        raise ValueError(f"Customer {customer_id} not found")

    # 2. Load customer's deals
    deals_result = await db.execute(
        select(Deal)
        .where(Deal.customer_id == customer_id)
        .order_by(Deal.contract_date.desc())
    )
    deals = list(deals_result.scalars().all())

    # 3. Load matching available inventory for appointment preparation.
    owned_makes = {
        value.lower()
        for value in [
            *(car.make for car in customer.cars),
            *(deal.make for deal in deals),
        ]
        if value
    }
    inventory_result = await db.execute(
        select(Inventory)
        .where(Inventory.status == "available")
        .order_by(Inventory.added_at.desc())
        .limit(20)
    )
    available_inventory = list(inventory_result.scalars().all())
    matching_inventory = [
        item for item in available_inventory if item.make.lower() in owned_makes
    ]
    if not matching_inventory:
        matching_inventory = available_inventory
    inventory = [_inventory_to_dict(item) for item in matching_inventory[:5]]

    # 4. Load active support docs
    today = date.today()
    docs_result = await db.execute(
        select(SupportDoc).where(
            (SupportDoc.effective_to.is_(None)) | (SupportDoc.effective_to >= today)
        )
    )
    docs = list(docs_result.scalars().all())

    if not docs:
        return {
            "customer_name": customer.full_name,
            "generated_at": date.today().isoformat(),
            "triggered_count": 0,
            "sections": [],
            "summary": "",
            "inventory": inventory,
        }

    # 5. Fan-out — one sub-agent call per active support doc (parallel)
    customer_history = _build_customer_history(customer, deals)
    customer_history["matching_available_inventory"] = inventory
    results: list[dict[str, Any]] = await asyncio.gather(
        *[_run_sub_agent(doc, customer_history, llm) for doc in docs]
    )

    # 6. Filter to triggered only
    triggered = [r for r in results if r["triggered"]]

    # 7. Summariser
    summary = await _run_summariser(triggered, customer.full_name, llm)

    return {
        "customer_name": customer.full_name,
        "generated_at": date.today().isoformat(),
        "triggered_count": len(triggered),
        "sections": triggered,
        "summary": summary,
        "inventory": inventory,
    }
