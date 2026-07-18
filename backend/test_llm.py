"""Live Gemini deal-extraction smoke test.

Run from the project root with ``python backend/test_llm.py``. The script reads
``GEMINI_API_KEY`` from .env and never prints it.
"""

import asyncio
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())

# The live extraction smoke test does not access the CRM database, but importing
# the shared client initializes application settings. Avoid requiring a running
# Postgres instance solely for this standalone test.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from app.agents.deal_extractor import run_deal_extractor
from app.llm import GEMINI_BASE_URL, GEMINI_MODEL
from app.llm.client import LLMClient
from app.services.llm_config import LLMRuntimeConfig


async def main() -> None:
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY is not set in .env")

    image_path = ROOT / "test_files" / "test_deal1.jpg"
    client = LLMClient(
        LLMRuntimeConfig(GEMINI_BASE_URL, api_key, GEMINI_MODEL),
        log_requests=False,
    )
    result = await run_deal_extractor(image_path.read_bytes(), "image/jpeg", client)
    extracted = result["extracted"]
    # Validate fields that are visibly present in the fixture. The photographed
    # page crops the date at the right edge, so a cautious model should leave
    # contract_date null instead of inventing one.
    required = (
        "deal_type",
        "make",
        "model",
        "model_year",
        "vin",
        "selling_price",
        "payment_amount",
    )
    missing = [field for field in required if not extracted.get(field)]

    print(json.dumps(extracted, indent=2, ensure_ascii=False, default=str))
    if missing:
        raise SystemExit(f"Gemini extraction missing required fields: {', '.join(missing)}")
    print(f"PASS: {GEMINI_MODEL} extracted {image_path.name}")


if __name__ == "__main__":
    asyncio.run(main())
