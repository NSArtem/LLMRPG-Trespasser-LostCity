"""Routing templates and page-total routing validation."""

from __future__ import annotations

from typing import Any, Mapping

from .contracts import ROUTING_SCHEMA, validate_routing


def routing_template(source: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": ROUTING_SCHEMA,
        "source_sha256": source["sha256"],
        "pages": [
            {
                "pdf_page": page,
                "tasks": [],
                "exclusion_reason": "blank",
                "confidence": "low",
                "notes": "",
            }
            for page in range(1, source["pdf_pages"] + 1)
        ],
    }


def routing_prompt(source: Mapping[str, Any]) -> str:
    return f"""Route every physical page for operational extraction.

Return only a JSON file matching response-template.json. Keep the schema and
source_sha256 unchanged. Include every physical page 1 through
{source['pdf_pages']} exactly once. Assign every applicable semantic task:
adventure, rules, tables, items, spells, classes, effects, maps, illustrations.
Routing is multi-label. If a page has no operational content, use no tasks and
set exactly one exclusion_reason: cover, divider, blank, or
non-operational-illustration. An illustration-only page must be excluded.

Use only visible source material. Do not run tools, inspect a repository,
invent content, or generate module files.

source_sha256: {source['sha256']}
schema: {ROUTING_SCHEMA}
"""


def routing_pack_readme(source: Mapping[str, Any]) -> str:
    return f"""# Routing pack

This archive is the first extraction step for **{source['title']}**. It contains
one thumbnail for every physical PDF page. ChatGPT must classify every page so
Module Extractor can build smaller, focused evidence packs.

## In ChatGPT

1. Attach this ZIP to a new chat.
2. Send this message:

   > Open the attached ZIP, read `prompt.md`, follow it exactly, and return only
   > the completed JSON response as a downloadable file.

3. Download the response and save it as `routing.json`.
4. Place it beside `routing.zip` in the repository's `_exchange/` directory.
5. Run `python3 module-extractor/cli.py run`.

If ChatGPT cannot inspect the ZIP, extract it locally, attach `prompt.md`,
`response-template.json`, and all files under `thumbnails/`, then send the same
message.

Do not edit `response-template.json` in this archive. Save ChatGPT's completed
copy separately.
"""


__all__ = [
    "routing_pack_readme",
    "routing_prompt",
    "routing_template",
    "validate_routing",
]
