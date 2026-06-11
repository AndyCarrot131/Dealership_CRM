"""General chat assistant for sales: answers natural-language questions about
CRM data through a guarded read-only SQL tool (see services/sql_tool.py)."""
import json
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.client import LLMClient
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

MAX_TOOL_STEPS = 5

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

{_SCHEMA_DOC}

Rules:
- {scope_rule}
- Only SELECT statements. Never attempt to modify data; if asked to add or change records, tell the user to use the Add Customer or Edit Customer agent instead.
- Results are capped at 50 rows; use aggregates (COUNT, GROUP BY) or ORDER BY + narrower filters for large questions.
- Answer in the same language the user writes in.
- Present answers as short plain text or "-" bullet lists (no markdown tables). Mention counts and the most relevant fields; don't dump raw rows verbatim.
- Do not show the SQL you ran unless the user explicitly asks for it.
- If a query returns nothing, say so plainly and suggest what to check."""


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


async def run_assistant(
    history: list[dict[str, Any]],
    user: User,
    db: AsyncSession,
    llm: LLMClient,
) -> str:
    user_ctx = _UserContext(id=user.id, name=user.name, role=user.role)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _system_prompt(user_ctx)},
        *history,
    ]

    for _ in range(MAX_TOOL_STEPS):
        response = await llm.chat(messages, tools=[_QUERY_TOOL])
        message = response["choices"][0]["message"]
        tool_calls = message.get("tool_calls")

        if not tool_calls:
            return message.get("content") or "I couldn't find an answer to that."

        messages.append(message)
        for tool_call in tool_calls:
            try:
                args = json.loads(tool_call["function"]["arguments"])
                sql = str(args.get("sql", ""))
            except (json.JSONDecodeError, TypeError):
                sql = ""
            payload = await _execute_tool_call(sql, user_ctx, db)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps(payload, default=str),
                }
            )

    return (
        "I couldn't finish answering within the allowed number of lookups. "
        "Try asking a more specific question."
    )
