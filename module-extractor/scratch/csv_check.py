#!/usr/bin/env python3
"""T1.3 -- parse a pack response and measure compliance with Contract B.

Throwaway by design. Stage 6's real ingest lives in `facts.py` at T2.7; this
exists only to answer whether the row format survives contact with a model
before any code is written against it.

The vocabulary is read out of the pack's own `schema.md` rather than restated
here. A checker carrying its own copy would measure agreement with itself.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import sys
import zipfile


STRUCTURAL = {"#unit", "#entity", "#option", "#uncertain"}

# Mutable campaign state belongs to a campaign, never to an immutable module.
CAMPAIGN_STATE = re.compile(
    r"\b(currently|current hp|hit points remaining|has already|so far this|"
    r"the party has|players have|is now|has been (?:killed|looted|opened|taken))\b",
    re.IGNORECASE,
)


@dataclass
class Schema:
    predicates: dict[str, tuple[str, str]]   # name -> (arity, value kind)
    kinds: set[str]
    visibilities: set[str]
    option_slots: set[str]
    structured: dict[str, set[str]]          # predicate -> declared JSON keys

    @property
    def json_predicates(self) -> set[str]:
        return {name for name, (_arity, value) in self.predicates.items()
                if value == "json"}


def parse_schema(text: str) -> Schema:
    predicates: dict[str, tuple[str, str]] = {}
    section = text.split("## Predicates", 1)[1].split("## Structured", 1)[0]
    for row in section.splitlines():
        if not row.startswith("| `"):
            continue
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        predicates[cells[0].strip("`")] = (cells[2], cells[3].strip("*").lower())

    kinds_block = text.split("## Entity kinds", 1)[1].split("##", 1)[0]
    kinds = set(re.findall(r"`([a-z-]+)`", kinds_block))

    visibility_block = text.split("## Visibility", 1)[1].split("## Entity", 1)[0]
    visibilities = set(re.findall(r"^\| `([a-z]+)`", visibility_block, re.M)) | {""}

    slots_line = re.search(r"`#option` slots are ([^.]+)\.", text)
    option_slots = set(re.findall(r"`([a-z]+)`", slots_line.group(1) if slots_line else ""))

    structured: dict[str, set[str]] = {}
    keys_block = text.split("## Structured values", 1)[1].split("## Prohibited", 1)[0]
    for line in keys_block.splitlines():
        match = re.match(r"^([a-z-]+)\s+\{(.*)\}\s*$", line.strip())
        if match:
            structured[match.group(1)] = set(re.findall(r'"([^"]+)":', match.group(2)))
    return Schema(predicates, kinds, visibilities, option_slots, structured)


@dataclass
class Report:
    source: str
    lines: int = 0
    rows: int = 0
    facts: int = 0
    structural: int = 0
    problems: list[str] = field(default_factory=list)
    counts: Counter = field(default_factory=Counter)
    units_seen: list[str] = field(default_factory=list)

    def fail(self, category: str, number: int, detail: str) -> None:
        self.counts[category] += 1
        self.problems.append(f"{category:22s} line {number:>4}  {detail}")


def clean(text: str) -> tuple[list[str], int]:
    """Strip transport artefacts only. Nothing may be invented or altered.

    A stray Markdown fence and trailing blank lines are permitted removals; the
    dataflow document names them explicitly. Everything else is content.
    """
    fences = 0
    kept = []
    for line in text.splitlines():
        if line.strip().startswith("```"):
            fences += 1
            continue
        if line.strip():
            kept.append(line)
    return kept, fences


def check(text: str, schema: Schema, expected: list[str], source: str) -> Report:
    report = Report(source=source)
    lines, fences = clean(text)
    report.lines = len(lines)
    if fences:
        report.counts["markdown fence"] = fences

    unit: str | None = None
    entities: dict[str, set[str]] = {}
    asserted: dict[tuple[str, str, str], int] = {}

    for number, line in enumerate(lines, 1):
        fields = line.split(",", 3)
        if len(fields) != 4:
            report.fail("field count", number, f"{len(fields)} fields: {line[:60]!r}")
            continue
        report.rows += 1
        first, second, third, value = fields

        if first.startswith("#"):
            report.structural += 1
            if first not in STRUCTURAL:
                report.fail("unknown row type", number, first)
                continue
            if first == "#unit":
                unit = second
                report.units_seen.append(second)
                entities.setdefault(unit, set())
                if third != "pages":
                    report.fail("unit marker", number, f"third field {third!r}")
                if not re.fullmatch(r"\d+(?:[;, ]\s*\d+)*", value.strip()):
                    report.fail("unit pages", number, f"{value!r}")
            elif first == "#entity":
                if unit is None:
                    report.fail("entity before unit", number, second)
                    continue
                if third not in schema.kinds:
                    report.fail("entity kind", number, f"{third!r}")
                entities[unit].add(second)
            elif first == "#option":
                if third not in schema.option_slots:
                    report.fail("option slot", number, f"{third!r}")
            continue

        report.facts += 1
        if unit is None:
            report.fail("fact before unit", number, line[:60])
            continue
        if second not in schema.predicates:
            report.fail("unknown predicate", number, f"{second!r}")
            continue
        if third not in schema.visibilities:
            report.fail("unknown visibility", number, f"{third!r}")
        if second not in schema.predicates or first not in entities[unit]:
            report.fail("undeclared subject", number, f"{first!r} in {unit}")

        arity, value_kind = schema.predicates[second]
        key = (unit, first, second)
        if key in asserted:
            if arity == "scalar":
                report.fail("scalar repeated", number,
                            f"{first}.{second} first seen at line {asserted[key]}")
        else:
            asserted[key] = number

        if value_kind == "json":
            try:
                parsed = json.loads(value)
            except ValueError as exc:
                report.fail("json parse", number, f"{second}: {exc}")
            else:
                if not isinstance(parsed, dict):
                    report.fail("json shape", number, f"{second}: not an object")
                else:
                    unknown = set(parsed) - schema.structured.get(second, set())
                    if unknown:
                        report.fail("json key", number,
                                    f"{second}: {sorted(unknown)}")
        if CAMPAIGN_STATE.search(value):
            report.fail("campaign state", number, value[:60])

    counted = Counter(report.units_seen)
    for unit_id in expected:
        if counted[unit_id] == 0:
            report.fail("unit missing", 0, unit_id)
        elif counted[unit_id] > 1:
            report.fail("unit duplicated", 0, f"{unit_id} x{counted[unit_id]}")
    for unit_id in counted:
        if unit_id not in expected:
            report.fail("unit unpacked", 0, unit_id)
    return report


def render(report: Report) -> str:
    total = sum(report.counts.values())
    out = [
        f"### {report.source}",
        "",
        f"- non-blank lines: {report.lines}",
        f"- rows splitting into exactly four fields: "
        f"{report.rows}/{report.lines}",
        f"- structural rows: {report.structural}, facts: {report.facts}",
        f"- units marked: {len(set(report.units_seen))}",
        f"- **violations: {total}**",
        "",
    ]
    if report.counts:
        out += ["| Category | Count |", "|---|---:|"]
        out += [f"| {name} | {count} |"
                for name, count in sorted(report.counts.items())]
        out.append("")
    if report.problems:
        out += ["```text", *report.problems, "```", ""]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("responses", nargs="+", type=Path)
    parser.add_argument("--pack", type=Path,
                        default=root / "_exchange/pack-001.zip")
    args = parser.parse_args(argv)

    with zipfile.ZipFile(args.pack) as archive:
        schema = parse_schema(archive.read("schema.md").decode("utf-8"))
        manifest = archive.read("units.csv").decode("utf-8").splitlines()
    expected = [row.split(",", 1)[0] for row in manifest[1:] if row.strip()]

    for response in args.responses:
        report = check(response.read_text(encoding="utf-8"), schema, expected,
                       response.name)
        print(render(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
