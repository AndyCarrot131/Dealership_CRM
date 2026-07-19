import json
import re
from datetime import datetime
from typing import Any

from app.llm.client import LLMClient
from app.services.pii_placeholders import customer_pii_placeholders

_SYSTEM = """You are an AI email-writing assistant for a car dealership sales representative.
Your task is to compose a personalised outreach email to a specific customer.

You will receive:
1. Email purpose (the reason for reaching out)
2. Customer profile (name, note, vehicles they own/lease)
3. Matching inventory vehicles that may be relevant to this customer
4. The sales representative's writing style guide (in Markdown)
5. Customer's full contact log (channel, date, summary of each prior interaction)

Rules:
- Match the representative's voice and style exactly as described in the style guide
- Treat any "Extra hard rules" as mandatory requirements that override default phrasing
- If the style guide includes a concrete format template, headings, or option-label pattern, follow it exactly
- Make the email feel personal and relevant to this specific customer's situation
- Use the contact log to avoid repeating topics already covered, acknowledge the relationship naturally, and pick up where the last conversation left off
- Reference their vehicle(s) naturally (e.g., lease end dates, age, type)
- Mention 1-2 inventory options at most; do not list every car
- Follow the style guide's paragraph flow and any paragraph-level length suggestions when provided
- Always include a warm closing paragraph thanking the customer, a soft CTA (reply or call), and a professional sign-off with name and title
- For lease/finance ending emails, prioritize a lease-end guidance format (upgrade vs buyout vs return) over inventory sales copy
- Do NOT turn lease-end emails into price-led inventory advertisements unless explicitly requested by the user template/rules
- Do NOT include a subject line in the body
- Customer PII appears as opaque [[PII_...]] placeholders; copy those placeholders exactly when personalising the draft
- Respond ONLY with a JSON object in the exact format:
  {"subject": "...", "body": "..."}"""

_TYPE_CONTEXT: dict[str, str] = {
    "test_drive_followup": (
        "The customer recently test-drove a vehicle. "
        "Write a warm follow-up email thanking them for the test drive and keeping them engaged."
    ),
    "lease_finance_ending": (
        "The customer's lease or financing is ending soon. "
        "Write an email about upgrade options and next steps."
    ),
}

_TYPE_STYLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "test_drive_followup": ("test drive", "test-drive"),
    "lease_finance_ending": ("lease", "finance", "expiration", "ending", "end-of-lease"),
}


def _build_user_message(
    customer: dict[str, Any],
    inventory_matches: list[dict[str, Any]],
    style_md: str,
    extra_rules: list[str] | None = None,
    email_type: str = "lease_finance_ending",
    custom_template: str | None = None,
) -> str:
    car_lines = []
    for car in customer.get("cars", []):
        parts = [
            car.get("year") and str(car["year"]),
            car.get("make"),
            car.get("model"),
            car.get("ownership_type") and f"({car['ownership_type']})",
            car.get("lease_end_date") and f"lease ends {car['lease_end_date']}",
        ]
        car_lines.append(" ".join(p for p in parts if p))

    style_for_prompt = _style_for_email_type(style_md, email_type)
    strict_lease_format = _requires_option_labels(style_for_prompt, email_type)

    inventory_lines = []
    if not strict_lease_format:
        for item in inventory_matches[:2]:
            parts = [
                item.get("year") and str(item["year"]),
                item.get("make"),
                item.get("model"),
                item.get("trim"),
                item.get("price") and f"${item['price']:,.0f}",
            ]
            inventory_lines.append(" ".join(p for p in parts if p))

    if email_type == "custom" and custom_template:
        purpose = f"Use the following dealer-provided topic as the theme of this email:\n{custom_template}"
    else:
        purpose = _TYPE_CONTEXT.get(email_type, _TYPE_CONTEXT["lease_finance_ending"])

    contact_lines = []
    for entry in customer.get("interactions", []):
        contact_lines.append(
            f"  • [{entry.get('date', '?')}] {entry.get('channel', '?')}: {entry.get('summary', '')}"
        )

    format_requirements = _build_format_requirements(style_for_prompt, email_type)

    sections = [
        f"Email purpose: {purpose}",
        f"Customer: {customer['full_name']}",
        f"Customer phone: {customer.get('phone') or '(unknown)'}",
        f"Note: {customer.get('note') or '(none)'}",
        "Customer vehicles:\n" + ("\n".join(f"  • {l}" for l in car_lines) or "  (none)"),
        "Relevant inventory:\n" + ("\n".join(f"  • {l}" for l in inventory_lines) or "  (none)"),
        "Contact history (newest first):\n" + ("\n".join(contact_lines) or "  (no prior contact logged)"),
        "Style guide:\n" + (style_for_prompt or "(no style guide — write professionally)"),
        "Required format checklist:\n" + format_requirements,
    ]
    if extra_rules:
        sections.append(
            "Extra hard rules (non-negotiable):\n"
            + "\n".join(f"  • {rule}" for rule in extra_rules)
        )
    return "\n\n".join(sections)


def _extract_fixed_signoff(extra_rules: list[str]) -> str | None:
    for raw_rule in extra_rules:
        rule = (raw_rule or "").strip()
        if not rule:
            continue
        lower = rule.lower()
        if not any(
            key in lower
            for key in (
                "fixed email ending",
                "fix email ending",
                "must end",
                "always end",
                "fixed signature",
                "sign-off",
                "signoff",
            )
        ):
            continue

        lines = [line.strip() for line in rule.splitlines() if line.strip()]
        if len(lines) >= 2 and any(
            token in lines[0].lower()
            for token in ("fixed", "ending", "sign-off", "signoff", "signature", "always end", "must end")
        ):
            return "\n".join(lines[1:]).strip()

        quoted = re.search(r'["“](.+?)["”]', rule, flags=re.DOTALL)
        if quoted:
            return quoted.group(1).strip()

        after_colon = rule.split(":", 1)
        if len(after_colon) == 2 and after_colon[1].strip():
            return after_colon[1].strip()

        after_ending = re.search(r"ending\s+(.+)$", rule, flags=re.IGNORECASE | re.DOTALL)
        if after_ending:
            return after_ending.group(1).strip()

        regards_block = re.search(
            r"((?:best|warm|kind)\s+regards[\s\S]*)$",
            rule,
            flags=re.IGNORECASE,
        )
        if regards_block:
            return regards_block.group(1).strip()
    return None


def _strip_rule_leakage(body: str, extra_rules: list[str]) -> str:
    text = (body or "").strip()
    if not text:
        return text
    for rule in extra_rules:
        cleaned_rule = (rule or "").strip()
        if not cleaned_rule:
            continue
        text = text.replace(cleaned_rule, "").strip()
    # Remove leftover instruction-like lines if the model echoed them.
    text = re.sub(
        r"(?im)^\s*(?:make this|fixed email ending|fix email ending|always end|must end).*$",
        "",
        text,
    )
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def _style_for_email_type(style_md: str, email_type: str) -> str:
    text = (style_md or "").strip()
    if not text:
        return ""

    keywords = _TYPE_STYLE_KEYWORDS.get(email_type)
    if not keywords:
        return text

    lines = text.splitlines()
    section_ranges: list[tuple[int, int]] = []
    starts = [idx for idx, line in enumerate(lines) if line.startswith("## ")]
    if not starts:
        return text
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(lines)
        section_ranges.append((start, end))

    for start, end in section_ranges:
        heading = lines[start][3:].strip().lower()
        if any(key in heading for key in keywords):
            focused = "\n".join(lines[start:end]).strip()
            return (
                "Primary section to follow for this email type:\n"
                f"{focused}\n\n"
                "Also stay consistent with the rest of the style guide."
            )

    return text


def _build_format_requirements(style_for_prompt: str, email_type: str) -> str:
    rules = [
        "Use a greeting line with the customer's first name.",
        "Keep clean paragraph spacing.",
        "Include a soft CTA paragraph before the sign-off.",
    ]
    lower = (style_for_prompt or "").lower()
    if email_type == "lease_finance_ending":
        rules.append("Reference the lease/finance end date in the opening.")
        if "end-of-lease options" in lower or "option 1" in lower:
            rules.append('Use the heading "Your End-of-Lease Options:".')
            rules.append("Format choices as Option 1 / Option 2 / Option 3 (not generic numbered bullets).")
            rules.append("Include all 3 options explicitly: upgrade, purchase current vehicle, return vehicle.")
            rules.append("Do not include dollar prices, stock-style vehicle listings, or inventory bullet pitches.")
    return "\n".join(f"  • {r}" for r in rules)


def _requires_option_labels(style_md: str, email_type: str) -> bool:
    if email_type != "lease_finance_ending":
        return False
    lower = (style_md or "").lower()
    if any(
        token in lower
        for token in (
            "option 1",
            "end-of-lease options",
            "numbered options",
            "three options",
            "upgrade, purchase, return",
        )
    ):
        return True
    # Lease emails should default to a clear 3-option structure.
    return True


def _looks_like_lease_style(style_md: str) -> bool:
    lower = (style_md or "").lower()
    return any(
        token in lower
        for token in (
            "lease expiration",
            "end-of-lease",
            "option 1",
            "option 2",
            "option 3",
            "lease end",
            "lease maturity",
        )
    )


def _extract_style_signoff(style_md: str) -> str | None:
    text = (style_md or "").strip()
    if not text:
        return None

    always_ends_match = re.search(
        r'Always ends with\s*[“"](.+?)[”"]',
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if always_ends_match:
        signoff = always_ends_match.group(1).strip()
        return signoff or None

    fallback_match = re.search(
        r"((?:Warm|Best|Kind)\s+regards,\s*\n?[^\n]+(?:\|[^\n]+)?)",
        text,
        flags=re.IGNORECASE,
    )
    if fallback_match:
        signoff = fallback_match.group(1).strip()
        return signoff or None
    return None


def _enforce_option_labels(body: str, enabled: bool) -> str:
    if not enabled:
        return body
    lines = body.splitlines()
    normalized: list[str] = []
    for line in lines:
        match = re.match(r"^(\s*)(\d+)\.\s+(.*)$", line)
        if match:
            indent, idx, rest = match.groups()
            normalized.append(f"{indent}Option {idx}: {rest}")
        else:
            normalized.append(line)
    return "\n".join(normalized)


def _primary_vehicle_label(customer: dict[str, Any]) -> str:
    cars = customer.get("cars", [])
    if not cars:
        return "your current vehicle"
    primary = cars[0]
    parts = [primary.get("year"), _normalize_vehicle_word(primary.get("make")), _normalize_vehicle_word(primary.get("model"))]
    label = " ".join(str(p) for p in parts if p)
    return label if label else "your current vehicle"


def _normalize_vehicle_word(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) <= 3 and text.isupper():
        return text
    if text.isupper():
        return text.title()
    return text


def _humanize_date(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return "[Lease End Date]"
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            parsed = datetime.strptime(raw, fmt)
            return parsed.strftime("%B %d, %Y")
        except ValueError:
            continue
    return raw


def _options_format_from_style(style_md: str) -> str:
    lower = (style_md or "").lower()
    if any(token in lower for token in ("option 1", "numbered options", "option labels")):
        return "numbered"
    if any(token in lower for token in ("bulleted", "bullet points", "bullets used for clarity")):
        return "bulleted"
    return "numbered"


def _dedupe_greeting(text: str, first_name: str) -> str:
    lines = text.splitlines()
    greeting_pattern = re.compile(rf"^\s*hi\s+{re.escape(first_name)}\s*,\s*$", flags=re.IGNORECASE)
    seen = False
    out: list[str] = []
    for line in lines:
        if greeting_pattern.match(line.strip()):
            if seen:
                continue
            seen = True
        out.append(line)
    return "\n".join(out).strip()


def _enforce_lease_options_structure(
    body: str, customer: dict[str, Any], enabled: bool, options_format: str = "numbered"
) -> str:
    if not enabled:
        return body
    text = (body or "").strip()
    if not text:
        return text

    lines = text.splitlines()
    filtered_lines: list[str] = []
    for line in lines:
        lower = line.strip().lower()
        if any(
            lower.startswith(prefix)
            for prefix in (
                "here are a few options",
                "we've got a few options",
                "we have a few options",
                "your end-of-lease options:",
            )
        ):
            continue
        if re.match(r"^\s*(?:option\s*\d+[:.]|\d+\.)\s+", line, flags=re.IGNORECASE):
            # Drop model-generated option lines so we can enforce exact 3-option copy.
            continue
        if lower.startswith("either option"):
            continue
        if line.strip().startswith("- "):
            # Avoid inventory-style bullet pitches for strict lease format.
            continue
        filtered_lines.append(line)
    text = "\n".join(filtered_lines).strip()

    has_heading = re.search(r"(?im)^\s*your end-of-lease options\s*:", text) is not None
    has_three_options = (
        len(re.findall(r"(?im)^\s*option\s*[123]\s*:", text)) >= 3
        or len(re.findall(r"(?im)^\s*•\s+", text)) >= 3
        or len(re.findall(r"(?im)^\s*-\s+", text)) >= 3
    )
    if has_heading and has_three_options:
        return text

    vehicle_label = _primary_vehicle_label(customer)
    if options_format == "bulleted":
        options_block = (
            "Your End-of-Lease Options:\n"
            "• Upgrade to a new model with the latest technology, safety features, and a fresh warranty.\n"
            f"• Purchase your current vehicle. If you love your {vehicle_label}, "
            "you can buy it out for the residual value listed in your contract.\n"
            "• Return the vehicle by scheduling an inspection and handing over the keys at lease end."
        )
    else:
        options_block = (
            "Your End-of-Lease Options:\n"
            "Option 1: Upgrade to a new model with the latest technology, safety features, and warranty coverage.\n"
            f"Option 2: Purchase your current vehicle. If you love your {vehicle_label}, "
            "you can buy it out for the residual value listed in your contract.\n"
            "Option 3: Return the vehicle. We can help you schedule an inspection and handle your return smoothly."
        )
    return f"{text}\n\n{options_block}".strip()


def _first_name(full_name: str | None) -> str:
    value = (full_name or "").strip()
    if not value:
        return "there"
    return value.split()[0]


def _enforce_lease_subject(subject: str, customer: dict[str, Any], enabled: bool) -> str:
    if not enabled:
        return subject
    first = _first_name(customer.get("full_name"))
    vehicle = _primary_vehicle_label(customer)
    return f"{first}, Your {vehicle} Lease Options"


def _enforce_lease_cta(body: str, customer: dict[str, Any], enabled: bool) -> str:
    if not enabled:
        return body
    text = (body or "").strip()
    if not text:
        return text
    phone = customer.get("phone") or "[Phone]"
    cta = (
        f"Please reply directly to this email or call us at {phone} "
        "to schedule a convenient time for you to drop by."
    )
    if re.search(r"(?i)\breply\b.*\bcall\b", text):
        text = re.sub(r"(?im)^.*\breply\b.*\bcall\b.*$", cta, text).strip()
        return text
    return f"{text}\n\n{cta}".strip()


def _extract_lease_date(customer: dict[str, Any]) -> str | None:
    for car in customer.get("cars", []):
        lease_end = car.get("lease_end_date")
        if lease_end:
            return str(lease_end)
    return None


def _lease_options_block(vehicle: str, options_format: str) -> str:
    if options_format == "bulleted":
        return (
            "Your End-of-Lease Options:\n"
            "• Upgrade to a new model. Get behind the wheel of a brand-new vehicle with the latest technology, safety features, and a fresh warranty.\n"
            f"• Purchase your current vehicle. If you've fallen in love with your {vehicle}, "
            "you can buy it out for the residual value listed in your contract.\n"
            "• Return the vehicle. Simply schedule an inspection and return the keys to us at the end of your term."
        )
    return (
        "Your End-of-Lease Options:\n"
        "Option 1: Upgrade to a new model. Get behind the wheel of a brand-new vehicle with the latest technology, safety features, and a fresh warranty.\n"
        f"Option 2: Purchase your current vehicle. If you've fallen in love with your {vehicle}, "
        "you can buy it out for the residual value listed in your contract.\n"
        "Option 3: Return the vehicle. Simply schedule an inspection and return the keys to us at the end of your term."
    )


_MONTH_NAMES = (
    "january|february|march|april|may|june|july|august|"
    "september|october|november|december"
)


def _extract_lease_personalization(body: str, first_name: str) -> str:
    """Pull genuine, non-boilerplate content out of the model's body.

    Everything the strict lease template re-adds (greeting, openers, the options
    block, CTA, the "Let's Find…" invite, the thank-you note, and the sign-off)
    is removed so it cannot be duplicated. Paragraphs that merely restate the
    lease maturity/date are dropped too, since the canonical opener already
    states it.
    """
    text = (body or "").strip()
    if not text:
        return ""

    # Drop any trailing valediction block first (sign-off form only).
    text = re.sub(
        r"(?is)(?:\n+)(best regards|warm regards|kind regards|regards|sincerely|thanks|thank you)\s*(?:,|\n|$)[\s\S]*$",
        "",
        text,
    ).strip()

    drop_line = [
        re.compile(rf"(?i)^\s*hi\s+{re.escape(first_name)}\s*,\s*$"),
        re.compile(r"(?i)i hope this email finds you well"),
        re.compile(r"(?i)can you believe how quickly time flies"),
        re.compile(r"(?i)your end-of-lease options"),
        re.compile(r"(?i)^\s*option\s*\d+\s*[:.]"),
        re.compile(r"^\s*[•\-]\s+"),
        re.compile(r"(?i)\breply\b.*\bcall\b"),
        re.compile(r"(?i)let'?s find the best path forward"),
        re.compile(r"(?i)we would love to invite you back"),
        re.compile(r"(?i)thank you so much for being a valued part"),
        re.compile(r"(?i)^\s*(best|warm|kind)\s+regards"),
        re.compile(r"(?i)\|\s*sales consultant"),
    ]
    kept_lines = [line for line in text.splitlines() if not any(p.search(line) for p in drop_line)]
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(kept_lines)).strip()

    keep_paragraphs: list[str] = []
    for para in re.split(r"\n\s*\n", cleaned):
        para = para.strip()
        if not para:
            continue
        low = para.lower()
        mentions_lease = any(
            k in low for k in ("lease", "mature", "maturity", "end of your term")
        )
        mentions_date = bool(re.search(rf"(?i)\b(20\d{{2}}|{_MONTH_NAMES})\b", low))
        if mentions_lease and mentions_date:
            continue
        keep_paragraphs.append(para)
    return "\n\n".join(keep_paragraphs).strip()


def _enforce_lease_body_depth(
    body: str, customer: dict[str, Any], enabled: bool, options_format: str = "numbered"
) -> str:
    if not enabled:
        return body

    first = _first_name(customer.get("full_name"))
    vehicle = _primary_vehicle_label(customer)
    lease_date = _humanize_date(_extract_lease_date(customer))
    phone = customer.get("phone") or "[Phone]"

    middle = _extract_lease_personalization(body, first)

    parts: list[str] = [
        f"Hi {first},",
        "I hope this email finds you well.",
        (
            "Can you believe how quickly time flies? We want to remind you that the lease on your "
            f"{vehicle} is scheduled to mature on {lease_date}."
        ),
    ]
    if middle:
        parts.append(middle)
    else:
        parts.append(
            "As you approach the end of your lease, you have a few great options available to you, "
            "and we want to make sure the transition is as smooth and seamless as possible."
        )
    parts.append(_lease_options_block(vehicle, options_format))
    parts.append(
        "Let's Find the Best Path Forward\n"
        "We would love to invite you back into the dealership for a quick, no-pressure chat "
        "to review these options and see what fits best for you."
    )
    parts.append(
        f"Please reply directly to this email or call us at {phone} "
        "to schedule a convenient time for you to drop by."
    )
    parts.append(
        "Thank you so much for being a valued part of the O'Regan's VW family. "
        "We look forward to assisting you with your next automotive chapter."
    )
    return "\n\n".join(parts).strip()


def _enforce_fixed_signoff(body: str, fixed_signoff: str | None) -> str:
    text = (body or "").strip()
    if not text or not fixed_signoff:
        return text

    signoff = fixed_signoff.strip()
    if not signoff:
        return text

    # Remove any existing valediction block at the end so we can apply the fixed
    # one. The keyword must be in a sign-off form (followed by a comma or a line
    # break) so body sentences like "Thank you so much for…" are not treated as a
    # closing and deleted.
    text = re.sub(
        r"(?is)(?:\n\n|\n)(best regards|warm regards|kind regards|regards|sincerely|thanks|thank you)\s*(?:,|\n|$)[\s\S]*$",
        "",
        text,
    ).rstrip()
    return f"{text}\n\n{signoff}"


async def compose_email(
    customer: dict[str, Any],
    inventory_matches: list[dict[str, Any]],
    style_md: str,
    llm: LLMClient,
    extra_rules: list[str] | None = None,
    email_type: str = "lease_finance_ending",
    custom_template: str | None = None,
) -> dict[str, str]:
    pii = customer_pii_placeholders(customer)
    user_msg = _build_user_message(
        customer,
        inventory_matches,
        style_md,
        extra_rules=extra_rules,
        email_type=email_type,
        custom_template=custom_template,
    )
    user_msg = pii.redact(user_msg)
    response = await llm.chat(
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        # Outreach drafts are short, structured responses. Without an output
        # Some models may spend the entire request timeout generating thousands
        # of reasoning tokens before returning the JSON email.
        max_tokens=2000,
        temperature=0.2,
        reasoning_effort="low",
        response_format={"type": "json_object"},
        chat_template_kwargs={"enable_thinking": False},
    )
    content = pii.restore(response["choices"][0]["message"].get("content", ""))
    # Strip <think>...</think> reasoning blocks emitted by some models
    clean = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    # Extract the first {...} JSON object from the cleaned text
    json_match = re.search(r"\{.*\}", clean, flags=re.DOTALL)
    try:
        parsed = json.loads(json_match.group() if json_match else clean)
        subject = str(parsed.get("subject", "")).strip()
        body = str(parsed.get("body", "")).strip()
    except (json.JSONDecodeError, AttributeError):
        lines = clean.split("\n", 1)
        subject = lines[0].removeprefix("Subject:").strip()
        body = lines[1].strip() if len(lines) > 1 else clean

    if not subject:
        subject = f"Checking in — {customer['full_name']}"
    rules = extra_rules or []
    style_for_prompt = _style_for_email_type(style_md, email_type)
    strict_lease_format = _requires_option_labels(style_for_prompt, email_type) or _looks_like_lease_style(
        style_for_prompt
    )
    options_format = _options_format_from_style(style_for_prompt)
    body = _enforce_option_labels(body, strict_lease_format)
    body = _enforce_lease_options_structure(body, customer, strict_lease_format, options_format=options_format)
    body = _strip_rule_leakage(body, rules)
    body = _enforce_lease_cta(body, customer, strict_lease_format)
    body = _enforce_lease_body_depth(
        body, customer, strict_lease_format, options_format=options_format
    )
    subject = _enforce_lease_subject(subject, customer, strict_lease_format)
    fixed_signoff = _extract_fixed_signoff(rules)
    if not fixed_signoff:
        fixed_signoff = _extract_style_signoff(style_for_prompt)
    if strict_lease_format:
        fixed_signoff = "Warm regards,\nWilson Xing | Sales Consultant"
    return {"subject": subject, "body": _enforce_fixed_signoff(body, fixed_signoff)}
