#!/usr/bin/env python3
"""Build the deterministic T1.1 CSV-contract prototype pack.

The source-native unit JSON files are the output of the Phase 0 prototype. This
script deliberately does not call a model and does not turn the draft vocabulary
into a production contract; T1.4/T1.5 own that decision.

**The worked example is a unit the pack does not contain.** T1.3 measures how
reliably a model follows the row format, and a pack that ships the finished
answer to one of its own units cannot measure that for the unit it answered.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
UNIT_TABLE = ROOT / "module-extractor/scratch/unit-tables/module-lair-of-the-lamb.json"
DEFAULT_OUTPUT = ROOT / "_exchange/pack-001.zip"
PACK_ID = "pack-001"

# Six units spanning the material T1.1 asks for: a keyed room with a trap and a
# procedure, a keyed room with actors and an embedded stat block, a standalone
# stat block, a random table, a rules section, and a spell.
#
# **The zip in `_exchange/` predates the T0.5 boundary fixes and is not
# reproducible from this list.** It was built when `p28.lantern-worm` was a unit
# of its own; the fixes merged it into `p28.indirect-encounters`, which carries
# the same stat block together with the encounter table that rolls it. The two
# model responses in `_exchange/` answer the shipped pack, so `csv_check.py`
# reads that zip rather than rebuilding one. Rebuilding here produces a valid
# pack, not that pack.
UNITS = (
    "p31.24-crush-hallway",
    "p33.27-ballista",
    "p28.indirect-encounters",
    "p18.active-encounters-2",
    "p8.doors",
    "p46.haste",
)

# Held out of the pack on purpose -- see the module docstring.
EXAMPLE_UNIT = "p24.11-crab-mural"

EXAMPLE_ROWS = """#unit,p24.11-crab-mural,pages,24
#entity,a11,place,11 CRAB MURAL
#entity,mural,feature,mural of a crab
#entity,rat,actor,friendly rat
#entity,door,portal,wooden door to the east
a11,contents,public,A mural of a crab being groomed in a woman's lap.
a11,contents,public,A friendly rat.
mural,depicts,public,A crab being groomed in a woman's lap.
rat,disposition,public,Friendly.
door,state,public,Locked.
a11,exit,,{"to":"east","via":"wooden door"}
"""


SCHEMA = """# CSV fact contract (T1.1 draft)

This is a Phase 1 prototype. The vocabulary below is **closed for this
prototype** so that T1.3 can count violations against it -- an open vocabulary
has nothing to violate and would make the measurement meaningless. Whether the
production contract stays closed is decision D-4, taken at T1.4.

## Wire rule

Every non-empty response line is parsed with `line.split(",", 3)`. The first
three fields are controlled tokens and may not contain commas. The fourth field
absorbs everything after the third comma, so prose commas, semicolons, quotation
marks and embedded JSON all pass through untouched.

**Never escape anything, and never quote anything.** No rule to apply is a rule
that cannot be applied wrongly.

A row carries **at most one** free-text field and it is always last. Where a
concept needs two pieces of prose it becomes two rows.

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

`<subject>` is a local ID declared by `#entity` earlier in the same unit. Local
IDs are short and scoped to their unit -- `a24`, `ceil`, `trap`. Code expands
them into global identifiers on ingest, so do not spend tokens on long names.

`#option` slots are `action`, `result`, `cost`, and `requires`.

## Visibility

Column three, and **only** column three, says who knows a fact:

| Value | Meaning |
|---|---|
| `public` | Apparent on entering or looking |
| `hidden` | Known to the referee, not to the players |
| `discoverable` | Found by a stated action -- state the action in the value |
| *(empty)* | Not a matter of perception: dimensions, timings, exits, statistics |

There is deliberately no `hidden` *predicate*. A fact is hidden by its
visibility column, never by its predicate name, so that the two can never
disagree.

## Entity kinds

`place`, `actor`, `mechanism`, `item`, `portal`, `feature`, `rule`, `table`,
`spell`, `effect`.

## Predicates

`list` means one entity may assert the predicate more than once in a unit; the
rows keep their source order. `scalar` means once only.

| Predicate | Kind | Arity | Value |
|---|---|---|---|
| `dimensions` | place | scalar | text |
| `visible` | place, feature | scalar | text |
| `contents` | place | list | text |
| `exit` | place | list | **JSON** |
| `depicts` | feature | scalar | text |
| `activation` | mechanism, effect | scalar | text |
| `cycle` | mechanism | scalar | **JSON** |
| `mechanism` | mechanism | scalar | text |
| `concealment` | mechanism, item, portal | scalar | text |
| `consequence` | mechanism, effect | list | **JSON** |
| `disarm-from` | mechanism | scalar | text |
| `state` | portal, item | scalar | text |
| `disposition` | actor | scalar | text |
| `appearance` | actor | scalar | text |
| `role` | actor | scalar | text |
| `stat` | actor | list | **JSON** |
| `ability` | actor | list | text |
| `awareness` | actor | scalar | text |
| `carries` | actor | list | text |
| `entry` | table | list | text |
| `rule` | rule | list | text |
| `range` | spell | scalar | text |
| `target` | spell | scalar | text |
| `duration` | spell | scalar | text |
| `effect` | spell, effect | scalar | text |
| `note` | any | list | text |

## Structured values

Only these four carry JSON, and only these key sets:

```text
exit         {"to": <place name or local id>, "via": <portal type>}
cycle        {"fall_ft": n, "fall_s": n, "rest_s": n, "then": <text>}
consequence  {"damage": <dice>, "fall_ft": n, "destination": <text>}
stat         {"Lvl": n, "Def": <text>, "<attack>": <dice>, ...}
```

Omit any key the source does not state. Do not invent keys; if a structured
value does not fit, use `note` with plain text and add an `#uncertain` row.

## Prohibited

Do not emit mutable campaign state: current hit points, position, inventory,
attitude, mood, active or resolved status, applied effects. A module describes
what can happen; a campaign records what did.
"""


def _prompt() -> str:
    return f"""# Semantic extraction prompt (T1.1 draft)

You are extracting source facts from pack `{PACK_ID}`. Read `schema.md` first.

Answer one question per unit: **what does this unit assert?** Do not design
cards, do not mint global identifiers, do not build cross-references between
units, and do not write player-facing prose. Preserve names, numbers,
measurements, dice, durations and mechanics exactly as the source states them.

Emit one `#unit` marker per unit, then that unit's `#entity` declarations, then
its facts. Every unit listed in `units.csv` must appear exactly once.

## How to return it

Return the whole response as a **single fenced code block** and nothing else:

````text
```csv
#unit,...
...
```
````

No preamble, no commentary, no second block, nothing after the closing fence.
If you can write files, also save the same content as `{PACK_ID}.csv` and offer
it for download; the fenced block is still required either way.

Each unit file opens with a short header giving its id, pages and the section it
sits under. The header is context; extract facts from the body below the `---`.

## Worked example

Given a unit whose body reads:

```text
11  CRAB MURAL
A  mural of a crab  being groomed in a woman's lap.
A  friendly rat .
A  locked wooden door  to the east.
```

a correct response for that unit is:

```text
{EXAMPLE_ROWS}```

Note what it does not contain: no source hashes, no pack id, no per-fact page
citations, no global identifiers, no repeated field names. The runner attaches
all of that on receipt, because it already knows it.
"""


def _load_units() -> dict[str, dict[str, Any]]:
    payload = json.loads(UNIT_TABLE.read_text(encoding="utf-8"))
    return {unit["unit_id"]: unit for unit in payload}


def _manifest(units: list[dict[str, Any]]) -> str:
    """The unit manifest, under the same rule as the wire format.

    Free text last, so a comma in a heading needs no quoting and the file can be
    read with ``split(",", 4)``. An earlier version wrote the columns in one
    order and the header in another, which handed the model an empty ``pages``
    column and its page numbers filed under ``labels``.
    """
    rows = ["unit_id,pages,labels,text_bytes,heading"]
    for unit in units:
        rows.append(",".join((
            unit["unit_id"],
            ";".join(str(page) for page in unit["pages"]),
            ";".join(unit.get("labels", [])),
            str(unit["text_bytes"]),
            unit["heading"],
        )))
    return "\n".join(rows) + "\n"


def _unit_file(unit: dict[str, Any]) -> str:
    """Verbatim unit text under a header the CSV contract cannot be confused by.

    The header lines carry no ``#``: in this pack ``#`` opens a structural row,
    and a source file whose every header line starts with one is teaching the
    opposite of the format it accompanies. ``section`` is the unit's heading
    path, which is the only place the model can learn that these table rows
    belong to the Lamb-Dead table rather than the Lamb-Alive one.
    """
    header = [
        f"unit-id: {unit['unit_id']}",
        f"pages: {', '.join(str(page) for page in unit['pages'])}",
    ]
    if unit.get("heading_path"):
        header.append(f"section: {' > '.join(unit['heading_path'])}")
    return "\n".join(header) + "\n---\n" + unit["text"].rstrip() + "\n"


def _readme(units: list[dict[str, Any]]) -> str:
    pages = sorted({page for unit in units for page in unit["pages"]})
    listing = "\n".join(
        f"- `{unit['unit_id']}` — {unit['heading']}" for unit in units
    )
    return f"""# CSV contract prototype pack

Pack ID: `{PACK_ID}`
Source: `Module - Lair of the Lamb.pdf`
Units: {len(units)}
Physical pages: {', '.join(str(page) for page in pages)}

This pack is a T1.1 manual-exchange prototype. Read `prompt.md`, `schema.md`,
and every file under `units/`. Return one CSV response preserving one `#unit`
block for each unit listed below, as a single fenced block so it can be copied
or downloaded whole, and save it as `{PACK_ID}.csv`.

{listing}

Between them they cover a keyed room with a trap and a procedure, a keyed room
with actors and an embedded stat block, a standalone monster stat block, a
random encounter table, a rules section, and a spell.

The schema is a **draft**. T1.3 measures compliance with it and T1.4 decides
whether the vocabulary is closed, which predicates are list-valued, and which
carry JSON. Nothing here is a production contract yet.
"""


def build(output: Path) -> Path:
    by_id = _load_units()
    missing = [unit_id for unit_id in (*UNITS, EXAMPLE_UNIT) if unit_id not in by_id]
    if missing:
        raise SystemExit(f"unit table does not contain {', '.join(missing)}")
    if EXAMPLE_UNIT in UNITS:
        raise SystemExit(f"{EXAMPLE_UNIT} is the worked example and cannot be packed")
    units = [by_id[unit_id] for unit_id in UNITS]

    # Import through the repository package without adding a dependency.
    sys.path.insert(0, str(ROOT / "module-extractor"))
    from module_extractor.util import deterministic_zip

    entries: dict[str, bytes] = {
        "README.md": _readme(units).encode("utf-8"),
        "prompt.md": _prompt().encode("utf-8"),
        "schema.md": SCHEMA.encode("utf-8"),
        "units.csv": _manifest(units).encode("utf-8"),
    }
    for unit in units:
        entries[f"units/{unit['unit_id']}.txt"] = _unit_file(unit).encode("utf-8")

    output.parent.mkdir(parents=True, exist_ok=True)
    deterministic_zip(output, entries)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    output = build(args.output.resolve())

    sys.path.insert(0, str(ROOT / "module-extractor"))
    from module_extractor.util import sha256_file

    print(f"{output} {sha256_file(output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
