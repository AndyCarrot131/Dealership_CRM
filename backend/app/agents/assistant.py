"""General chat assistant for sales: answers natural-language questions about
CRM data through a guarded read-only SQL tool (see services/sql_tool.py).
Also composes email drafts on request via the compose_email_draft tool."""
import json
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.email_composer import compose_email
from app.llm.client import LLMClient
from app.models.customer import Customer
from app.models.inventory import Inventory
from app.models.style import StyleProfile
from app.models.user import User
from app.services.sql_tool import run_select


@dataclass(frozen=True)
class _UserContext:
    """Plain snapshot of the requesting user.

    The SQL tool rolls back the session after every query, which expires ORM
    objects — so the loop must never touch the User instance again.
    """

    id: int
    name: str
    role: str

MAX_TOOL_STEPS = 8

_SCHEMA_DOC = """Tables you can query (PostgreSQL):

customers(id, assigned_sales_id, full_name, email, phone, note, last_contacted_at, created_at, updated_at)
customer_car(id, customer_id, make, model, year, ownership_type, lease_end_date, is_primary, created_at, updated_at)
  - ownership_type is one of: 'own', 'lease', 'finance'
interactions(id, customer_id, sales_id, channel, summary, contacted_at, created_at)
  - channel is one of: 'call', 'text', 'email', 'in-person'
inventory(id, make, model, year, trim, mileage, price, vin, status, features, notes, added_at)
  - status is one of: 'available', 'sold', 'reserved'
outreach_rules(id, sales_id, name, rule_text, compiled_filter, cadence_days, active, email_type, custom_template, created_at)
email_drafts(id, sales_id, customer_id, rule_id, subject, body, status, created_at, approved_at)
  - status is one of: 'pending', 'approved', 'dismissed'
sample_messages(id, sales_id, channel, raw_content, label, created_at)
style_profiles(id, sales_id, channel, style_md, updated_at)"""

_QUERY_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "query_db",
        "description": (
            "Run a single read-only SQL SELECT statement against the CRM "
            "database and get the matching rows back. Use this whenever the "
            "user asks about their customers, cars, interactions, inventory, "
            "outreach rules, or email drafts."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "One SELECT statement in PostgreSQL dialect. No INSERT/UPDATE/DELETE/DDL.",
                }
            },
            "required": ["sql"],
        },
    },
}

_COMPOSE_DRAFT_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "compose_email_draft",
        "description": (
            "Compose a personalised email draft for a specific customer. "
            "Use this when the user says 'write an email to [name]', "
            "'draft an email for [name]', 'compose an email to [name]', or similar. "
            "Do NOT use query_db for this — call this tool directly."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "customer_name": {
                    "type": "string",
                    "description": "The customer's name as mentioned by the user.",
                },
                "purpose": {
                    "type": "string",
                    "description": (
                        "Optional free-text description of the email's purpose, "
                        "e.g. 'reminding her about her lease', 'follow up on test drive'. "
                        "Passed to the email composer as a custom theme."
                    ),
                },
            },
            "required": ["customer_name"],
        },
    },
}

# table -> ownership column that non-managers must filter on
_OWNERSHIP_COLUMNS = {
    "customers": "assigned_sales_id",
    "interactions": "sales_id",
    "outreach_rules": "sales_id",
    "email_drafts": "sales_id",
    "sample_messages": "sales_id",
    "style_profiles": "sales_id",
}


def _system_prompt(user: _UserContext) -> str:
    if user.role == "manager":
        scope_rule = "The user is a manager and may see data for all sales reps."
    else:
        scope_rule = (
            f"The user is a sales rep (user id {user.id}). Queries are "
            f"automatically restricted to their own customers, interactions, "
            f"outreach rules, email drafts, samples and style profiles — you do "
            f"not need to add ownership filters, and you cannot see other reps' "
            f"data. Inventory is dealership-wide."
        )
    return f"""You are the data assistant for a car dealership CRM, chatting with {user.name}.
Today's date is {date.today().isoformat()}.

You answer questions about CRM data by calling the query_db tool with read-only SQL.
You can also compose email drafts by calling the compose_email_draft tool.

{_SCHEMA_DOC}

Rules:
- {scope_rule}
- Only SELECT statements. Never attempt to modify data; if asked to add or change records, tell the user to use the Add Customer or Edit Customer agent instead.
- Results are capped at 50 rows; use aggregates (COUNT, GROUP BY) or ORDER BY + narrower filters for large questions.
- Answer in the same language the user writes in.
- Present answers as short plain text or "-" bullet lists (no markdown tables). Mention counts and the most relevant fields; don't dump raw rows verbatim.
- Do not show the SQL you ran unless the user explicitly asks for it.
- If a query returns nothing, say so plainly and suggest what to check.
- For follow-up questions that reference a customer, vehicle, or result from earlier in the conversation, run a SQL query to fetch that entity's full details (especially their id) if you need them to answer precisely. Use names or other identifiers visible in the conversation history to look them up.
- When looking for matching inventory, search broadly: by vehicle segment (SUV, sedan, truck, etc.), price range, or a group of similar makes — not only by the exact brand the customer currently drives. A customer with a Hyundai Tucson likely fits any compact/mid-size SUV.
- For complex questions, run multiple queries in sequence: gather context first, then query the target table with the details you found.
- When an inventory query returns nothing for a narrow filter, widen the search (drop a constraint, try adjacent segments or a price range) before concluding nothing is available.
- When the user asks you to write, draft, or compose an email to a customer, call the compose_email_draft tool with the customer's name and the purpose. Do not use query_db for this."""


async def _execute_tool_call(
    sql: str, user: _UserContext, db: AsyncSession
) -> dict[str, Any]:
    scope_filters = None
    if user.role != "manager":
        # CTE-shadow every ownership-scoped table so the query can only see
        # this rep's rows, no matter what SQL the model produced.
        scope_filters = {
            table: (column, user.id) for table, column in _OWNERSHIP_COLUMNS.items()
        }
    try:
        return await run_select(db, sql, scope_filters=scope_filters)
    except ValueError as exc:
        return {"error": str(exc)}


def _match_inventory_for_customer(
    customer: dict[str, Any],
    inventory: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    customer_makes = {
        (car.get("make") or "").lower()
        for car in customer.get("cars", [])
        if car.get("make")
    }
    if customer_makes:
        matched = [i for i in inventory if (i.get("make") or "").lower() in customer_makes]
        if matched:
            return matched[:3]
    return inventory[:3]


async def _execute_compose_draft(
    customer_name: str,
    purpose: str | None,
    user: _UserContext,
    db: AsyncSession,
    llm: LLMClient,
) -> dict[str, Any]:
    q = (
        select(Customer)
        .options(selectinload(Customer.cars))
        .where(Customer.full_name.ilike(f"%{customer_name}%"))
    )
    if user.role != "manager":
        q = q.where(Customer.assigned_sales_id == user.id)
    result = await db.execute(q)
    customers = result.scalars().all()

    if len(customers) > 1:
        names = ", ".join(c.full_name for c in customers[:5])
        return {"error": f"Multiple customers match '{customer_name}': {names}. Please be more specific."}
    if not customers:
        return {"error": f"No customer found matching '{customer_name}'."}
    customer = customers[0]

    style_result = await db.execute(
        select(StyleProfile).where(
            StyleProfile.sales_id == user.id,
            StyleProfile.channel == "email",
        )
    )
    style_profile = style_result.scalar_one_or_none()
    style_md = style_profile.style_md if style_profile else ""

    inv_result = await db.execute(
        select(Inventory).where(Inventory.status == "available").limit(20)
    )
    inventory_dicts = [
        {
            "id": i.id,
            "make": i.make,
            "model": i.model,
            "year": i.year,
            "trim": i.trim,
            "price": float(i.price) if i.price else None,
        }
        for i in inv_result.scalars().all()
    ]

    customer_dict = {
        "id": customer.id,
        "full_name": customer.full_name,
        "note": customer.note,
        "cars": [
            {
                "make": car.make,
                "model": car.model,
                "year": car.year,
                "ownership_type": car.ownership_type,
                "lease_end_date": str(car.lease_end_date) if car.lease_end_date else None,
            }
            for car in customer.cars
        ],
    }
    matched_inv = _match_inventory_for_customer(customer_dict, inventory_dicts)

    email_type = "custom" if purpose else "lease_finance_ending"
    try:
        email = await compose_email(
            customer_dict,
            matched_inv,
            style_md,
            llm,
            email_type=email_type,
            custom_template=purpose or None,
        )
    except Exception as exc:
        return {"error": f"Failed to compose email: {exc}"}

    return {
        "customer_id": customer.id,
        "customer_name": customer.full_name,
        "subject": email["subject"],
        "body": email["body"],
    }


async def run_assistant(
    history: list[dict[str, Any]],
    user: User,
    db: AsyncSession,
    llm: LLMClient,
) -> dict[str, Any]:
    user_ctx = _UserContext(id=user.id, name=user.name, role=user.role)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _system_prompt(user_ctx)},
        *history,
    ]

    for _ in range(MAX_TOOL_STEPS):
        response = await llm.chat(messages, tools=[_QUERY_TOOL, _COMPOSE_DRAFT_TOOL])
        message = response["choices"][0]["message"]
        tool_calls = message.get("tool_calls")

        if not tool_calls:
            return {
                "reply": message.get("content") or "I couldn't find an answer to that.",
                "intent": "assistant",
                "pending_draft": None,
            }

        messages.append(message)
        for tool_call in tool_calls:
            fn_name = tool_call["function"]["name"]
            try:
                args = json.loads(tool_call["function"]["arguments"])
            except (json.JSONDecodeError, TypeError):
                args = {}

            if fn_name == "compose_email_draft":
                payload = await _execute_compose_draft(
                    customer_name=str(args.get("customer_name", "")),
                    purpose=args.get("purpose"),
                    user=user_ctx,
                    db=db,
                    llm=llm,
                )
                if "error" not in payload:
                    return {
                        "reply": (
                            f"I've drafted an email for {payload['customer_name']}. "
                            "Review the preview below and click \"Save to Inbox\" to save it."
                        ),
                        "intent": "compose_draft",
                        "pending_draft": payload,
                    }
                # Let the LLM relay the error to the user
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps(payload),
                    }
                )
            else:
                try:
                    sql = str(args.get("sql", ""))
                except (AttributeError, TypeError):
                    sql = ""
                result_payload = await _execute_tool_call(sql, user_ctx, db)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps(result_payload, default=str),
                    }
                )

    return {
        "reply": (
            "I couldn't finish answering within the allowed number of lookups. "
            "Try asking a more specific question."
        ),
        "intent": "assistant",
        "pending_draft": None,
    }
