"""Regression tests for natural-language outreach rule parsing."""

import json

import pytest

from app.agents.rule_parser import run_rule_parser


class CapturingLLM:
    def __init__(self, parsed_filter: dict):
        self.parsed_filter = parsed_filter
        self.messages = None

    async def chat(self, messages, **kwargs):
        self.messages = messages
        return {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "function": {
                                    "arguments": json.dumps(self.parsed_filter)
                                }
                            }
                        ]
                    }
                }
            ]
        }


@pytest.mark.asyncio
async def test_relative_lease_window_can_stay_relative():
    parsed_filter = {
        "op": "and",
        "conditions": [
            {
                "col": "customer_car.ownership_type",
                "cmp": "eq",
                "val": "lease",
            },
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
    llm = CapturingLLM(parsed_filter)

    result = await run_rule_parser("customer whose lease expires in 6 months", llm)

    assert result == parsed_filter
    system_prompt = llm.messages[0]["content"]
    assert "days_from_now_lte" in system_prompt
    assert "Do not invent an absolute calendar date" in system_prompt
