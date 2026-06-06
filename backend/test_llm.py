"""
Standalone LLM connectivity tester.
Run from the project root:  python backend/test_llm.py
Or from backend/:           python test_llm.py
"""
import asyncio
import json
import os
import sys
from pathlib import Path

# Locate .env (project root is one level above this file's directory)
_here = Path(__file__).parent
_env = _here / ".env"
if not _env.exists():
    _env = _here.parent / ".env"

# Load .env manually so this script needs no extra dependencies
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip())

from app.llm import LLMClient

BASE_URL = os.environ.get("LLM_BASE_URL", "")
API_KEY  = os.environ.get("LLM_API_KEY", "")
MODEL    = os.environ.get("LLM_MODEL", "")

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"


def header(title: str) -> None:
    print(f"\n{'─' * 50}")
    print(f"  {title}")
    print(f"{'─' * 50}")


async def test_plain_completion(client: LLMClient) -> bool:
    header("Test 1: plain completion")
    try:
        reply = await client.complete(
            messages=[{"role": "user", "content": "Reply with exactly: hello from llm"}],
            max_tokens=20,
        )
        print(f"  Response: {reply!r}")
        ok = isinstance(reply, str) and len(reply) > 0
        print(f"  {PASS if ok else FAIL}")
        return ok
    except Exception as e:
        print(f"  {FAIL}: {e}")
        return False


async def test_tool_call(client: LLMClient) -> bool:
    header("Test 2: tool call / structured output")
    tools = [
        {
            "type": "function",
            "function": {
                "name": "extract_customer",
                "description": "Extract customer fields from a description.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "first_name": {"type": "string"},
                        "last_name":  {"type": "string"},
                        "phone":      {"type": "string"},
                    },
                    "required": ["first_name", "last_name"],
                },
            },
        }
    ]
    try:
        result = await client.tool_call(
            messages=[
                {
                    "role": "user",
                    "content": "New customer: Jane Smith, phone 416-555-0123.",
                }
            ],
            tools=tools,
        )
        print(f"  Tool name : {result['name']}")
        print(f"  Arguments : {json.dumps(result['arguments'], indent=4)}")
        args = result["arguments"]
        ok = (
            result["name"] == "extract_customer"
            and "first_name" in args
            and "last_name" in args
        )
        print(f"  {PASS if ok else FAIL}")
        return ok
    except Exception as e:
        print(f"  {FAIL}: {e}")
        return False


async def main() -> None:
    print(f"\nLLM client tester")
    print(f"  base_url : {BASE_URL or '(not set)'}")
    print(f"  model    : {MODEL or '(not set)'}")
    print(f"  api_key  : {'***' + API_KEY[-4:] if len(API_KEY) > 4 else '(not set)'}")

    if not BASE_URL or not API_KEY or not MODEL:
        print(f"\n{FAIL}: LLM_BASE_URL / LLM_API_KEY / LLM_MODEL not set in .env")
        sys.exit(1)

    client = LLMClient(BASE_URL, API_KEY, MODEL)

    results = await asyncio.gather(
        test_plain_completion(client),
        test_tool_call(client),
    )

    passed = sum(results)
    total  = len(results)
    print(f"\n{'─' * 50}")
    print(f"  {passed}/{total} tests passed")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    asyncio.run(main())
