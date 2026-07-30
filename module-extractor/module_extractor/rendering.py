"""Deterministic selective LLM-loading views."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .util import write_json


REFERENCE_TYPES = {"rule", "table", "item", "spell", "class", "effect"}


def _display(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _card(record: Mapping[str, Any]) -> str:
    title = str(record["fields"].get("title", record["id"]))
    lines = [
        f"# {title}",
        "",
        f"- ID: `{record['id']}`",
        f"- Type: `{record['record_type']}`",
        "- Source pages: " + ", ".join(map(str, record["source_pages"])),
    ]
    if record["references"]:
        lines.append(
            "- References: " + ", ".join(f"`{item}`" for item in record["references"])
        )
    lines.extend(["", "## Operational fields", ""])
    for field, value in sorted(record["fields"].items()):
        if field == "title":
            continue
        label = field.replace("_", " ").capitalize()
        if isinstance(value, list):
            lines.append(f"### {label}")
            lines.append("")
            if value:
                lines.extend(f"- {_display(item)}" for item in value)
            else:
                lines.append("- None recorded.")
            lines.append("")
        else:
            lines.extend([f"### {label}", "", _display(value), ""])
    return "\n".join(lines).rstrip() + "\n"


def _coverage_report(coverage: Mapping[str, Any]) -> str:
    extracted = sum(page["status"] == "extracted" for page in coverage["pages"])
    excluded = sum(page["status"] == "excluded" for page in coverage["pages"])
    lines = [
        "# Coverage report",
        "",
        f"- Schema: `{coverage['schema']}`",
        f"- Physical pages: {coverage['physical_pages']}",
        f"- Extracted pages: {extracted}",
        f"- Explicitly excluded pages: {excluded}",
        f"- Complete: {'yes' if coverage['complete'] else 'no'}",
        "",
        "| Page | Status | Tasks or exclusion |",
        "| ---: | --- | --- |",
    ]
    for page in coverage["pages"]:
        detail = (
            ", ".join(page["routing_tasks"])
            if page["routing_tasks"]
            else page["exclusion_reason"]
        )
        lines.append(f"| {page['pdf_page']} | {page['status']} | {detail} |")
    return "\n".join(lines) + "\n"


def _conflict_report(module: Mapping[str, Any]) -> str:
    conflicts = module["unresolved_conflicts"]
    pending = module["pending_uncertainties"]
    lines = [
        "# Conflict and gap report",
        "",
        f"- Coverage gaps: {len(module['coverage']['gaps'])}",
        f"- Unresolved blocking conflicts: {len(conflicts)}",
        f"- Unreviewed uncertainties: {len(pending)}",
        "",
    ]
    for item in conflicts:
        lines.append(f"- `{item['id']}`: {item['object_id']}.{item['field']}")
    for item in pending:
        lines.append(f"- `{item['id']}`: {item['description']}")
    if not conflicts and not pending and not module["coverage"]["gaps"]:
        lines.append("No blocking gaps, conflicts, or unreviewed uncertainties.")
    return "\n".join(lines) + "\n"


def _review_report(module: Mapping[str, Any]) -> str:
    review = module["review"]
    return "\n".join(
        [
            "# Review report",
            "",
            f"- Overlay schema: `{review['schema']}`",
            f"- Overlay SHA-256: `{module['review_sha256']}`",
            f"- Aliases: {len(review['aliases'])}",
            f"- Canonical field selections: {len(review['values'])}",
            (
                "- Accepted uncertainties: "
                f"{len(review['accepted_uncertainties'])}"
            ),
            "",
            review.get("notes", ""),
            "",
        ]
    )


def render_module(stage: Path, module: Mapping[str, Any]) -> None:
    stage.mkdir(parents=True, exist_ok=True)
    write_json(stage / "module.json", module)
    write_json(stage / "topology.json", module["topology"])
    cards_root = stage / "cards"
    entity_root = cards_root / "entities"
    reference_root = cards_root / "reference"
    entity_root.mkdir(parents=True)
    reference_root.mkdir(parents=True)
    index_records = []
    for record in module["records"]:
        parent = (
            reference_root if record["record_type"] in REFERENCE_TYPES else entity_root
        )
        relative = (
            f"cards/reference/{record['id']}.md"
            if parent == reference_root
            else f"cards/entities/{record['id']}.md"
        )
        (parent / f"{record['id']}.md").write_text(
            _card(record), encoding="utf-8", newline="\n"
        )
        index_records.append(
            {
                "id": record["id"],
                "record_type": record["record_type"],
                "title": record["fields"].get("title", record["id"]),
                "source_pages": record["source_pages"],
                "path": relative,
                "references": record["references"],
            }
        )
    adjacency: dict[str, list[str]] = {
        node["id"]: [] for node in module["topology"]["nodes"]
    }
    for passage in module["topology"]["passages"]:
        adjacency[passage["from"]].append(passage["to"])
        adjacency[passage["to"]].append(passage["from"])
    write_json(
        stage / "index.json",
        {
            "schema": "operational-module-index/v1",
            "source_sha256": module["source"]["sha256"],
            "records": index_records,
            "topology": [
                {
                    "id": node["id"],
                    "labels": node["labels"],
                    "adjacent": sorted(set(adjacency[node["id"]])),
                    "source_pages": node["source_pages"],
                }
                for node in module["topology"]["nodes"]
            ],
            "aliases": module["aliases"],
        },
    )
    reports = stage / "reports"
    reports.mkdir()
    (reports / "coverage.md").write_text(
        _coverage_report(module["coverage"]), encoding="utf-8", newline="\n"
    )
    (reports / "conflicts-and-gaps.md").write_text(
        _conflict_report(module), encoding="utf-8", newline="\n"
    )
    (reports / "review.md").write_text(
        _review_report(module), encoding="utf-8", newline="\n"
    )
    write_json(
        stage / "GENERATED_OUTPUT.json",
        {
            "schema": "module-extractor-generated-output/v1",
            "source_sha256": module["source"]["sha256"],
            "module_sha256": module["module_sha256"],
        },
    )
