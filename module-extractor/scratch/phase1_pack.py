#!/usr/bin/env python3
"""Build the deterministic T1.1 CSV-contract prototype pack.

The source-native unit JSON files are the reviewed output of the Phase 0
prototype.  This script deliberately does not call a model and does not turn
the draft vocabulary into a production contract; T1.4/T1.5 own that decision.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
UNIT_TABLE = ROOT / "module-extractor/scratch/unit-tables/module-lair-of-the-lamb.json"
DEFAULT_OUTPUT = ROOT / "_exchange/pack-001.zip"

UNITS = (
    ("p21.1-bowls", "adventure"),
    ("p33.27-ballista", "adventure"),
    ("p28.lantern-worm", "adventure"),
    ("p18.active-encounters-2", "tables"),
    ("p8.wooden-doors", "rules"),
    ("p46.haste", "spells"),
)


DRAFT_SCHEMA = """# CSV fact contract (T1.1 draft)

This is a Phase 1 prototype. The predicate vocabulary, list/scalar choices,
and structured-value choices are deliberately provisional until T1.3 and T1.4
measure real model responses.

## Wire rule

Every non-empty response line is parsed with `line.split(",", 3)`. The first
three fields are controlled tokens and may not contain commas. The fourth field
is free text unless the predicate declares a JSON value below. No quoting or
escaping is requested.

## Structural rows

```text
#unit,<unit-id>,pages,<page-list>
#entity,<local-id>,<kind>,<name>
#option,<local-id>,<slot>,<text>
#uncertain,<local-id>,<about>,<note>
```

Facts use:

```text
<subject>,<predicate>,<visibility>,<value>
```

Visibility is one of `public`, `hidden`, `discoverable`, or empty. Local
entity IDs are scoped to the unit and must be declared by `#entity` first.

## Draft vocabularies

Entity kinds: `place`, `mechanism`, `actor`, `situation`, `procedure`,
`knowledge`, `rule`, `table`, `item`, `spell`, `class`, `effect`.

Predicates currently observed in the prototype examples:

| Predicate | Draft kind | Draft value | Notes |
| --- | --- | --- | --- |
| `title` | any | scalar text | Entity display name when needed |
| `text` | any | scalar text | Unstructured source assertion |
| `description` | any | scalar text | Source description |
| `visible` | any | scalar text | Player-visible material |
| `hidden` | any | list text | GM-only material |
| `contents` | place | list text | Visible contents |
| `dimensions` | place | scalar text | Size or distance |
| `exit` | place | JSON object | Destination and route |
| `activation` | mechanism/situation | scalar text | Trigger condition |
| `cycle` | mechanism | JSON object | Timings or repeated mechanics |
| `mechanism` | mechanism | scalar text | How a mechanism works |
| `consequence` | mechanism/situation | JSON object | Structured result |
| `disarm-from` | mechanism | scalar text | Source-faithful route or action |
| `appearance` | actor | scalar text | Immediately observable material |
| `role` | actor | scalar text | Operational role |
| `capabilities` | actor | list text | Mechanics and statistics |
| `entries` | table | list text | Table rows |
| `effect` | effect | scalar text | Source possibility |
| `condition` | any | scalar text | Required condition |
| `range` | spell | scalar text | Spell range |
| `target` | spell | scalar text | Spell target |
| `duration` | spell | scalar text | Spell duration |
| `option` | any | scalar text | A player-facing choice |
| `result` | any | scalar text | Result of an option |

The production schema must either close this vocabulary or explicitly choose
an open extension rule. It must also declare every predicate's list/scalar and
text/JSON behaviour before Stage 6 is implemented.

## Prohibited facts

Do not emit mutable campaign state such as current hit points, position,
inventory, attitude, mood, active/resolved status, or applied effects.
"""


def _load_units() -> dict[str, dict[str, Any]]:
    payload = json.loads(UNIT_TABLE.read_text(encoding="utf-8"))
    return {unit["unit_id"]: unit for unit in payload}


def _manifest(units: list[dict[str, Any]]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(("unit_id", "heading", "pages", "labels", "text_bytes"))
    for unit in units:
        writer.writerow(
            (
                unit["unit_id"],
                unit["heading"],
                ";".join(unit.get("labels", [])),
                ";".join(map(str, unit["pages"])),
                unit["text_bytes"],
            )
        )
    return buffer.getvalue()


def _readme(pack_id: str, units: list[dict[str, Any]]) -> str:
    pages = sorted({page for unit in units for page in unit["pages"]})
    return f"""# CSV contract prototype pack

Pack ID: `{pack_id}`
Source: `Module - Lair of the Lamb.pdf`
Units: {len(units)}
Physical pages: {', '.join(map(str, pages))}

This pack is a T1.1 manual-exchange prototype. Read `prompt.md`, `schema.md`,
and every file under `units/`. Return one CSV response, preserving one
`#unit` block for each listed unit. Do not add Markdown fences or a prose
preamble.

The selected units intentionally cover a keyed room, an adventure/stat-block
entry, a random encounter table, a rules section, and a spell.
"""


def _prompt(pack_id: str) -> str:
    return f"""# Semantic extraction prompt (T1.1 draft)

You are extracting source facts from pack `{pack_id}`. Follow `schema.md`.
Answer what each unit asserts; do not design cards, mint canonical IDs, or
invent facts. Use local IDs declared in the same unit. Preserve names,
numbers, measurements, dice, durations, and mechanics exactly.

Return only plain CSV lines. Split each line into four fields on the first
three commas only. The fourth field is free text unless `schema.md` declares
that predicate as JSON. Put one `#unit` marker at the start of each unit block,
then its `#entity` declarations and facts. Include every packed unit exactly
once. Use one row per assertion; do not combine unrelated prose in JSON.

The response is a prototype input for a parser. It will be rejected if a fact
uses a mutable campaign state, an undeclared subject, an unknown token, or a
malformed structured value.
"""


def build(output: Path) -> Path:
    by_id = _load_units()
    units = []
    for unit_id, _label in UNITS:
        try:
            units.append(by_id[unit_id])
        except KeyError as exc:
            raise SystemExit(f"unit table does not contain {unit_id}") from exc

    # Import through the repository package without adding a dependency.
    sys.path.insert(0, str(ROOT / "module-extractor"))
    from module_extractor.util import deterministic_zip, sha256_file

    entries: dict[str, bytes] = {
        "README.md": _readme("pack-001", units).encode("utf-8"),
        "prompt.md": _prompt("pack-001").encode("utf-8"),
        "schema.md": DRAFT_SCHEMA.encode("utf-8"),
        "units.csv": _manifest(units).encode("utf-8"),
    }
    for unit, (_unit_id, label) in zip(units, UNITS):
        entries[f"units/{unit['unit_id']}.txt"] = (
            f"# {unit['heading']}\n"
            f"# pages: {', '.join(map(str, unit['pages']))}\n"
            f"# draft label: {label}\n\n"
            f"{unit['text'].rstrip()}\n"
        ).encode("utf-8")

    output.parent.mkdir(parents=True, exist_ok=True)
    deterministic_zip(output, entries)
    print(f"{output} {sha256_file(output)}")
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    build(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
