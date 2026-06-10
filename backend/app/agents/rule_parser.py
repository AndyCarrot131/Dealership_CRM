import json
from typing import Any

from app.llm.client import LLMClient

ALLOWED_COLUMNS = frozenset(
    {
        "customers.last_contacted_at",
        "customer_car.make",
        "customer_car.model",
        "customer_car.year",
        "customer_car.ownership_type",
        "customer_car.lease_end_date",
    }
)

ALLOWED_OPERATORS = frozenset(
    {"eq", "ne", "lt", "lte", "gt", "gte", "in", "days_ago_gte", "days_ago_lte"}
)

_FILTER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "op": {"type": "string", "enum": ["and", "or"]},
        "conditions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "col": {
                        "type": "string",
                        "enum": sorted(ALLOWED_COLUMNS),
                        "description": "Column to filter on (table.column)",
                    },
                    "cmp": {
                        "type": "string",
                        "enum": sorted(ALLOWED_OPERATORS),
                        "description": (
                            "Comparison operator. "
                            "days_ago_gte/days_ago_lte compare against (now - N days)"
                        ),
                    },
                    "val": {
                        "description": "Value to compare against (string, number, or list for 'in')"
                    },
                },
                "required": ["col", "cmp", "val"],
            },
        },
    },
    "required": ["op", "conditions"],
}

_PARSE_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "parse_outreach_rule",
        "description": "Convert a natural-language outreach rule into a structured filter predicate.",
        "parameters": _FILTER_SCHEMA,
    },
}

_SYSTEM = f"""You are a rule-parsing assistant for a car dealership CRM.
Convert natural-language customer outreach rules into a structured JSON filter.

Available columns:
{chr(10).join(f"  • {c}" for c in sorted(ALLOWED_COLUMNS))}

Available operators: {', '.join(sorted(ALLOWED_OPERATORS))}

Notes:
- days_ago_gte(N) means "the date was at least N days ago" (i.e., old / not recently contacted)
- days_ago_lte(N) means "the date was at most N days ago" (i.e., recently)
- For ownership_type use: own, lease, or finance
- For lease_end_date use ISO date strings (YYYY-MM-DD)
- Always use AND for independent conditions unless the user explicitly means OR

Only call parse_outreach_rule with a valid predicate tree."""


def _validate_tree(tree: dict[str, Any]) -> None:
    op = tree.get("op")
    if op not in {"and", "or"}:
        raise ValueError(f"Invalid op: {op!r}. Must be 'and' or 'or'.")
    conditions = tree.get("conditions")
    if not isinstance(conditions, list) or len(conditions) == 0:
        raise ValueError("conditions must be a non-empty list.")
    for cond in conditions:
        col = cond.get("col")
        cmp = cond.get("cmp")
        if col not in ALLOWED_COLUMNS:
            raise ValueError(f"Column not in whitelist: {col!r}")
        if cmp not in ALLOWED_OPERATORS:
            raise ValueError(f"Operator not in whitelist: {cmp!r}")
        if "val" not in cond:
            raise ValueError(f"Missing 'val' in condition: {cond}")


async def run_rule_parser(rule_text: str, llm: LLMClient) -> dict[str, Any]:
    response = await llm.chat(
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": rule_text},
        ],
        tools=[_PARSE_TOOL],
        tool_choice="required",
    )

    choice = response["choices"][0]
    message = choice["message"]
    tool_calls = message.get("tool_calls") or []
    if not tool_calls:
        raise ValueError("Rule Parser did not produce a structured filter.")

    raw: dict[str, Any] = json.loads(tool_calls[0]["function"]["arguments"])
    _validate_tree(raw)
    return raw
