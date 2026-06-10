import re
from collections import defaultdict

from app.llm.client import LLMClient

_SYSTEM_BASE = """You are a writing style analyst for a car dealership sales team.
Your task is to study the provided sample messages and distill the writer's unique communication style
into a concise, actionable markdown guide. Another AI will use this guide to write new messages
that faithfully match this person's voice and style.

{category_instruction}

Each category section MUST contain exactly two sub-sections:

### Format
Describe the structural/layout conventions observed in the samples:
- Message length (e.g. 2-3 short paragraphs, under 80 words)
- Opening line pattern (greeting style, whether name is used)
- Body structure (e.g. one hook sentence → offer → CTA)
- Closing line pattern (sign-off, signature style)
- Paragraph count and spacing habits
- Use of bullet points, line breaks, or lists

### Style
Describe the voice and language patterns:
- Tone and formality level for this situation
- Energy level (urgent, warm, casual, professional)
- Vocabulary preferences and any signature phrases or pet words
- How they reference vehicles (make/model/year/trim usage)
- Use of emojis, punctuation quirks, or capitalisation habits
- Anything that makes this person's writing instantly recognisable

Output a clean markdown document. Do NOT include any samples verbatim."""

_CATEGORY_INSTRUCTION_DEFAULT = """The samples are grouped by condition (e.g. "Leasing Ending", "Test Drive"). Produce a ## section
for each condition. If there is a "General" group, produce it first as "## General"."""

_CATEGORY_INSTRUCTION_MANAGED = """The writer's samples are organized into the following categories:
{category_list}

Produce one ## section for each category that has samples provided, using the exact category name as the ## heading.
If any sample does not match a named category, place it under ## General.
Do NOT produce sections for categories that have no samples."""


async def run_style_summarizer(
    samples: list[tuple[str, str]],  # (label, raw_content)
    channel: str,
    llm: LLMClient,
    categories: list[str] | None = None,
) -> str:
    if not samples:
        return ""

    groups: dict[str, list[str]] = defaultdict(list)
    for label, content in samples:
        key = label.strip() if label.strip() else "General"
        groups[key].append(content)

    if categories:
        category_set = {c.strip() for c in categories}
        ordered_keys: list[str] = []
        for cat in categories:
            cat_stripped = cat.strip()
            if cat_stripped in groups:
                ordered_keys.append(cat_stripped)
        for key in groups:
            if key not in category_set and key not in ordered_keys:
                ordered_keys.append(key)
        category_instruction = _CATEGORY_INSTRUCTION_MANAGED.format(
            category_list="\n".join(f"- {c}" for c in categories)
        )
    else:
        ordered_keys = list(groups.keys())
        category_instruction = _CATEGORY_INSTRUCTION_DEFAULT

    system_prompt = _SYSTEM_BASE.format(category_instruction=category_instruction)

    sections: list[str] = []
    for key in ordered_keys:
        joined = "\n\n---\n\n".join(groups[key])
        sections.append(f"### {key}\n\n{joined}")

    user_content = f"Channel: {channel}\n\n" + "\n\n".join(sections)

    response = await llm.chat(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
    )
    raw = response["choices"][0]["message"].get("content", "")
    cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    return cleaned.strip()
