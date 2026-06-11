"""Assistant agent: tool loop, ownership guard, and the /api/chat wiring."""
import json

from app.agents.assistant import _execute_tool_call, _UserContext, run_assistant
from app.services.sql_tool import build_scoped_sql
from app.llm.client import get_llm_client
from app.main import app
from app.models.customer import Customer
from tests.conftest import auth_header


class FakeLLM:
    """Scripted stand-in for LLMClient: returns queued responses in order."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    async def chat(self, messages, tools=None, tool_choice="auto"):
        self.calls.append(messages)
        return self._responses.pop(0)


def _tool_call_response(sql: str) -> dict:
    return {
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "query_db",
                                "arguments": json.dumps({"sql": sql}),
                            },
                        }
                    ],
                },
            }
        ]
    }


def _text_response(content: str) -> dict:
    return {
        "choices": [
            {"finish_reason": "stop", "message": {"role": "assistant", "content": content}}
        ]
    }


# ─── per-user scoping (CTE shadowing) ───────────────────────────────────────────


def test_scope_sql_prepends_shadowing_ctes():
    scoped = build_scoped_sql(
        "SELECT * FROM customers", {"customers": ("assigned_sales_id", 7)}, "public"
    )
    assert scoped.startswith(
        "WITH customers AS (SELECT * FROM public.customers WHERE assigned_sales_id = 7)"
    )
    assert scoped.endswith("SELECT * FROM customers")


def test_scope_sql_merges_with_model_cte():
    scoped = build_scoped_sql(
        "WITH recent AS (SELECT id FROM inventory) SELECT * FROM recent",
        {"customers": ("assigned_sales_id", 7)},
        "public",
    )
    assert scoped.lower().count("with ") == 1
    assert ", recent AS (SELECT id FROM inventory)" in scoped


async def _seed_two_owners(db_session, sales_user, other_sales_user):
    db_session.add_all(
        [
            Customer(assigned_sales_id=sales_user.id, full_name="Mine"),
            Customer(assigned_sales_id=other_sales_user.id, full_name="Theirs"),
        ]
    )
    await db_session.commit()


async def test_unscoped_query_returns_only_own_rows(db_session, sales_user, other_sales_user):
    await _seed_two_owners(db_session, sales_user, other_sales_user)
    ctx = _UserContext(id=sales_user.id, name=sales_user.name, role="sales")

    # The model "forgot" the ownership filter — shadowing applies it anyway.
    result = await _execute_tool_call("SELECT full_name FROM customers", ctx, db_session)
    assert result["rows"] == [["Mine"]]


async def test_union_branch_cannot_leak_other_reps_data(
    db_session, sales_user, other_sales_user
):
    await _seed_two_owners(db_session, sales_user, other_sales_user)
    ctx = _UserContext(id=sales_user.id, name=sales_user.name, role="sales")

    sql = (
        f"SELECT full_name FROM customers WHERE assigned_sales_id = {sales_user.id} "
        "UNION SELECT full_name FROM customers"
    )
    result = await _execute_tool_call(sql, ctx, db_session)
    assert result["rows"] == [["Mine"]]


async def test_wrong_owner_filter_cannot_widen_scope(
    db_session, sales_user, other_sales_user
):
    await _seed_two_owners(db_session, sales_user, other_sales_user)
    ctx = _UserContext(id=sales_user.id, name=sales_user.name, role="sales")

    # Explicitly requesting another rep's id intersects to nothing.
    sql = f"SELECT full_name FROM customers WHERE assigned_sales_id = {other_sales_user.id}"
    result = await _execute_tool_call(sql, ctx, db_session)
    assert result["rows"] == []


async def test_manager_queries_are_not_scoped(db_session, sales_user, other_sales_user, manager_user):
    await _seed_two_owners(db_session, sales_user, other_sales_user)
    ctx = _UserContext(id=manager_user.id, name=manager_user.name, role="manager")

    result = await _execute_tool_call(
        "SELECT full_name FROM customers ORDER BY full_name", ctx, db_session
    )
    assert result["rows"] == [["Mine"], ["Theirs"]]


async def test_model_cte_named_after_scoped_table_fails_safe(db_session, sales_user):
    ctx = _UserContext(id=sales_user.id, name=sales_user.name, role="sales")
    sql = "WITH customers AS (SELECT 1 AS x) SELECT * FROM customers"
    result = await _execute_tool_call(sql, ctx, db_session)
    assert "error" in result  # duplicate CTE name rejected by the database


# ─── agent loop ─────────────────────────────────────────────────────────────────


async def test_run_assistant_executes_tool_and_answers(db_session, sales_user):
    db_session.add(Customer(assigned_sales_id=sales_user.id, full_name="Looped Lead"))
    await db_session.commit()

    fake = FakeLLM(
        [
            _tool_call_response(
                f"SELECT full_name FROM customers WHERE assigned_sales_id = {sales_user.id}"
            ),
            _text_response("You have 1 customer: Looped Lead."),
        ]
    )
    reply = await run_assistant(
        [{"role": "user", "content": "How many customers do I have?"}],
        sales_user,
        db_session,
        fake,
    )
    assert reply == "You have 1 customer: Looped Lead."

    # Second LLM call must include the tool result with the queried row.
    tool_messages = [m for m in fake.calls[1] if m.get("role") == "tool"]
    assert len(tool_messages) == 1
    assert "Looped Lead" in tool_messages[0]["content"]


async def test_run_assistant_feeds_sql_error_back_to_model(db_session, sales_user):
    fake = FakeLLM(
        [
            _tool_call_response("DELETE FROM customers"),  # rejected by validator
            _text_response("I can only read data, not change it."),
        ]
    )
    reply = await run_assistant(
        [{"role": "user", "content": "Delete everything"}],
        sales_user,
        db_session,
        fake,
    )
    assert reply == "I can only read data, not change it."

    tool_messages = [m for m in fake.calls[1] if m.get("role") == "tool"]
    assert "error" in tool_messages[0]["content"]


async def test_run_assistant_stops_after_max_steps(db_session, sales_user):
    looping = _tool_call_response("SELECT id FROM inventory")
    fake = FakeLLM([looping] * 5)
    reply = await run_assistant(
        [{"role": "user", "content": "loop forever"}], sales_user, db_session, fake
    )
    assert "more specific" in reply


# ─── /api/chat wiring ───────────────────────────────────────────────────────────


async def test_chat_endpoint_assistant_mode(client, sales_user):
    fake = FakeLLM([_text_response("There are 0 customers.")])
    app.dependency_overrides[get_llm_client] = lambda: fake
    try:
        resp = await client.post(
            "/api/chat",
            json={"message": "How many customers?", "mode": "assistant"},
            headers=auth_header(sales_user),
        )
    finally:
        del app.dependency_overrides[get_llm_client]

    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "assistant"
    assert body["reply"] == "There are 0 customers."
    assert body["pending_fields"] is None
