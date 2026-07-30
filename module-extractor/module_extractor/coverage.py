"""Physical-page coverage manifest construction."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .contracts import CONTENT_TASKS, COVERAGE_SCHEMA
from .errors import ExtractorError


def build_coverage(
    source: Mapping[str, Any],
    routing: Sequence[Mapping[str, Any]],
    packs: Sequence[Mapping[str, Any]],
    responses: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    response_by_pack = {item["pack_id"]: item for item in responses}
    pack_by_id = {pack["pack_id"]: pack for pack in packs}
    task_results: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for response in responses:
        for item in response["task_coverage"]:
            task_results.setdefault(
                (item["pdf_page"], item["task"]), []
            ).append({**item, "pack_id": response["pack_id"]})
    pages = []
    gaps = []
    for row in sorted(routing, key=lambda item: item["pdf_page"]):
        page = row["pdf_page"]
        task_states = []
        routed_tasks = (set(row["tasks"]) & CONTENT_TASKS) | (
            {"maps"} if "maps" in row["tasks"] else set()
        )
        for task in sorted(routed_tasks):
            results = task_results.get((page, task), [])
            if not results:
                gaps.append({"pdf_page": page, "task": task, "reason": "no-pack"})
            if len(results) > 1:
                raise ExtractorError(
                    f"multiple packs cover physical page {page} task {task}"
                )
            for result in results:
                pack_id = result["pack_id"]
                pack = pack_by_id[pack_id]
                response = response_by_pack.get(pack_id)
                state = (
                    result["status"]
                    if response and response["validation"] == "valid"
                    else "missing"
                )
                if state != "extracted":
                    gaps.append(
                        {
                            "pdf_page": page,
                            "task": task,
                            "reason": (
                                "not-found"
                                if state == "not-found"
                                else "no-valid-response"
                            ),
                        }
                    )
                task_states.append(
                    {
                        "task": task,
                        "pack_id": pack_id,
                        "pack_sha256": pack["pack_sha256"],
                        "response_sha256": (
                            response["response_sha256"] if response else None
                        ),
                        "record_ids": result["record_ids"],
                        "validation": state,
                        "notes": result["notes"],
                    }
                )
        if row["exclusion_reason"]:
            status = "excluded"
        elif not task_states:
            status = "gap"
            gaps.append(
                {"pdf_page": page, "task": None, "reason": "no-operational-task"}
            )
        elif any(item["validation"] != "extracted" for item in task_states):
            status = "gap"
        else:
            status = "extracted"
        pages.append(
            {
                "pdf_page": page,
                "routing_tasks": row["tasks"],
                "exclusion_reason": row["exclusion_reason"],
                "tasks": task_states,
                "status": status,
            }
        )
    expected = set(range(1, source["pdf_pages"] + 1))
    actual = {page["pdf_page"] for page in pages}
    if expected != actual:
        raise ExtractorError("coverage construction lost physical pages")
    return {
        "schema": COVERAGE_SCHEMA,
        "source_sha256": source["sha256"],
        "physical_pages": source["pdf_pages"],
        "pages": pages,
        "gaps": sorted(
            gaps, key=lambda item: (item["pdf_page"], item["task"] or "")
        ),
        "complete": not gaps,
    }
