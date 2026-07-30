"""Validation, draft/release assembly, and safe generated-output replacement."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import tempfile
from typing import Any, Mapping

from .contracts import (
    CANONICAL_SCHEMA,
    REVIEW_SCHEMA,
    validate_pack_manifest,
    validate_review,
    validate_routing,
    validate_source,
)
from .coverage import build_coverage
from .errors import ExtractorError
from .evidence import ingest_responses
from .identity import apply_identity_review
from .operations import resolve_operational_records
from .reconciliation import reconcile_records, reconcile_topology
from .rendering import (
    generated_output_is_replaceable,
    render_module,
    validate_rendered_module,
)
from .review import apply_review, release_gate
from .topology import resolve_operational_topology
from .util import (
    atomic_publish,
    canonical_json_bytes,
    load_json,
    sha256_bytes,
    sha256_file,
)


def load_run(run_dir: Path) -> dict[str, Any]:
    source = validate_source(load_json(run_dir / "source.json"))
    routing = validate_routing(load_json(run_dir / "routing.json"), source)
    packs = validate_pack_manifest(load_json(run_dir / "packs.json"), source)
    review_path = run_dir / "review.json"
    if review_path.is_file():
        review = validate_review(load_json(review_path), source)
    else:
        review = {
            "schema": REVIEW_SCHEMA,
            "source_sha256": source["sha256"],
            "canonical_ids": [],
            "aliases": [],
            "distinct": [],
            "values": [],
            "accepted_uncertainties": [],
            "topology_composites": [],
            "notes": "",
        }
    return {
        "source": source,
        "routing": routing,
        "packs": packs,
        "review": review,
        "review_path": review_path,
    }


def evaluate(run_dir: Path) -> dict[str, Any]:
    loaded = load_run(run_dir)
    evidence = ingest_responses(run_dir, loaded["packs"], loaded["source"])
    identity = apply_identity_review(
        evidence, loaded["review"], loaded["source"]
    )
    canonical_evidence = identity["evidence"]
    records, content_conflicts = reconcile_records(
        canonical_evidence["content_observations"]
    )
    topology, topology_conflicts = reconcile_topology(
        canonical_evidence["map_results"]
    )
    conflicts = sorted(
        content_conflicts + topology_conflicts, key=lambda item: item["id"]
    )
    coverage = build_coverage(
        loaded["source"],
        loaded["routing"],
        loaded["packs"],
        evidence["responses"],
    )
    reviewed = resolve_operational_records(
        resolve_operational_topology(
            apply_review(
                records,
                topology,
                conflicts,
                canonical_evidence["uncertainties"],
                loaded["review"],
                identity,
            )
        )
    )
    gate_errors = release_gate(reviewed, coverage)
    return {
        **loaded,
        "evidence": evidence,
        "canonical_evidence": canonical_evidence,
        "identity": identity,
        "raw_records": records,
        "raw_topology": topology,
        "conflicts": conflicts,
        "coverage": coverage,
        "reviewed": reviewed,
        "gate_errors": gate_errors,
    }


def canonical_module(
    evaluated: Mapping[str, Any], *, profile: str
) -> dict[str, Any]:
    if profile not in {"draft", "release"}:
        raise ExtractorError("assembly profile must be draft or release")
    if profile == "release" and evaluated["gate_errors"]:
        raise ExtractorError(
            "release gate failed: " + "; ".join(evaluated["gate_errors"])
        )
    review_hash = (
        sha256_file(evaluated["review_path"])
        if evaluated["review_path"].is_file()
        else sha256_bytes(canonical_json_bytes(evaluated["review"]))
    )
    module = {
        "schema": CANONICAL_SCHEMA,
        "profile": profile,
        "source": evaluated["source"],
        "coverage": evaluated["coverage"],
        "packs": [
            {
                "pack_id": pack["pack_id"],
                "task": pack["task"],
                **(
                    {
                        "tasks": pack["tasks"],
                        "page_tasks": pack["page_tasks"],
                        "text_bytes": pack["text_bytes"],
                    }
                    if pack["task"] == "content"
                    else {"render_bytes": pack["render_bytes"]}
                ),
                "physical_pages": pack["physical_pages"],
                "pack_sha256": pack["pack_sha256"],
                "response_sha256": next(
                    response["response_sha256"]
                    for response in evaluated["evidence"]["responses"]
                    if response["pack_id"] == pack["pack_id"]
                ),
            }
            for pack in evaluated["packs"]
        ],
        "review_sha256": review_hash,
        "review": evaluated["review"],
        "records": evaluated["reviewed"]["records"],
        "topology": evaluated["reviewed"]["topology"],
        "topology_links": evaluated["reviewed"]["topology_links"],
        "topology_errors": evaluated["reviewed"]["topology_errors"],
        "record_errors": evaluated["reviewed"]["record_errors"],
        "aliases": evaluated["reviewed"]["aliases"],
        "identity": {
            "candidate_groups": evaluated["identity"]["candidate_groups"],
            "confirmed_aliases": evaluated["identity"]["confirmed_aliases"],
            "canonical_ids": evaluated["identity"]["canonical_ids"],
            "rejected_merges": evaluated["identity"]["rejected_merges"],
            "keyed_area_conflicts": evaluated["identity"][
                "keyed_area_conflicts"
            ],
            "errors": evaluated["reviewed"]["identity_errors"],
        },
        "raw_observations": {
            "content": evaluated["evidence"]["content_observations"],
            "topology": evaluated["evidence"]["map_results"],
        },
        "uncertainties": evaluated["evidence"]["uncertainties"],
        "accepted_uncertainties": evaluated["reviewed"][
            "accepted_uncertainties"
        ],
        "pending_uncertainties": evaluated["reviewed"]["pending_uncertainties"],
        "conflicts": evaluated["conflicts"],
        "unresolved_conflicts": evaluated["reviewed"]["unresolved_conflicts"],
        "unresolved_duplicate_candidates": evaluated["reviewed"][
            "unresolved_duplicate_candidates"
        ],
        "release_gate": {
            "passed": not evaluated["gate_errors"],
            "errors": evaluated["gate_errors"],
        },
    }
    payload_without_hash = deepcopy(module)
    module["module_sha256"] = sha256_bytes(canonical_json_bytes(payload_without_hash))
    return module


def _replaceable_output(path: Path) -> bool:
    return not path.exists() or generated_output_is_replaceable(path)


def assemble(
    run_dir: Path,
    output: Path,
    *,
    profile: str,
    replace_generated_output: bool = False,
) -> dict[str, Any]:
    evaluated = evaluate(run_dir)
    module = canonical_module(evaluated, profile=profile)
    output = output.resolve()
    if output.exists() and any(output.iterdir() if output.is_dir() else [output]):
        if not replace_generated_output:
            raise ExtractorError(f"refusing to overwrite non-empty output: {output}")
        if not _replaceable_output(output):
            raise ExtractorError(
                f"refusing to replace output without a generated-output marker: {output}"
            )
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{output.name}-stage-", dir=output.parent
    ) as temporary:
        temporary_path = Path(temporary)
        stage = temporary_path / "product"
        render_module(stage, module)
        validate_rendered_module(stage, module)
        atomic_publish(
            stage,
            output,
            replace=output.exists() and replace_generated_output,
        )
    return module
