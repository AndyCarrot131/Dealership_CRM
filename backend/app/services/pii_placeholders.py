"""Replace customer PII with opaque placeholders around external LLM calls."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from typing import Any, Iterable


_PII_FIELDS = ("full_name", "name", "address", "street_address", "mailing_address", "phone")


@dataclass(frozen=True)
class PIIPlaceholderMap:
    replacements: tuple[tuple[str, str], ...]

    def redact(self, text: str) -> str:
        redacted = text
        # Longer values first avoids replacing a first name inside a full name.
        for original, placeholder in sorted(self.replacements, key=lambda item: len(item[0]), reverse=True):
            redacted = redacted.replace(original, placeholder)
        return redacted

    def restore(self, text: str) -> str:
        restored = text
        for original, placeholder in self.replacements:
            restored = restored.replace(placeholder, original)
        return restored


def customer_pii_placeholders(customer: dict[str, Any]) -> PIIPlaceholderMap:
    """Build per-request hashed tokens for the customer's identifying fields."""
    salt = secrets.token_bytes(16)
    values: list[tuple[str, str]] = []
    seen: set[str] = set()

    for field, raw_value in _iter_pii(customer):
        value = str(raw_value).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        digest = hashlib.sha256(salt + field.encode() + value.encode()).hexdigest()[:16]
        values.append((value, f"[[PII_{field.upper()}_{digest}]]"))

    return PIIPlaceholderMap(tuple(values))


def _iter_pii(customer: dict[str, Any]) -> Iterable[tuple[str, Any]]:
    for field in _PII_FIELDS:
        value = customer.get(field)
        if value is not None:
            yield field, value

