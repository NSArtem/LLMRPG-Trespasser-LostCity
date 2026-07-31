#!/usr/bin/env python3
"""T0.2 -- group words into lines, then cluster line heights into tiers.

A **tier** is a cluster of line heights that a document uses consistently. Most
documents turn out to have three to five: body text, one or two heading levels,
a title, sometimes a caption or marginal size.

**Thresholds are derived per document and never hardcoded.** The measured tier
values for *Lair of the Lamb* (56.1 / 20.8 / 14.5 / 12.2) are a fact about that
one PDF. Winter's Daughter is A5 rather than US Letter and shares none of them.

**Bigger does not mean heading.** *The Lost City* sets a section heading at
h=8.64 above body text at h=9.07 -- the heading is the *smaller* line. So this
module identifies the **body** tier, as the one carrying the most text, and
reports every other tier relative to it. Deciding which tiers are headings needs
more than size (isolation on the line, capitalisation, position) and belongs to
T0.4, not here.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bbox import BboxError, SOURCES  # noqa: E402
from columns import Line, document_lines  # noqa: E402


# Heights within this relative distance are one tier. Digital typesetting gives
# near-identical values; scans wobble, so the tolerance is relative rather than
# absolute and works on both.
TIER_TOLERANCE = 0.04

# Tiers holding less than this share of the document's lines are noise --
# a stray ligature, a dropped cap, one oversized glyph.
TIER_FLOOR = 0.004


@dataclass(frozen=True)
class Tier:
    height: float  # representative (median) height
    lines: int
    words: int
    share: float  # fraction of the document's lines
    samples: tuple[str, ...]

    @property
    def label(self) -> str:
        return f"h={self.height:.1f}"


def cluster(values: list[float], tolerance: float = TIER_TOLERANCE) -> list[list[float]]:
    """Single-link clustering of sorted heights, with a relative gap."""
    clusters: list[list[float]] = []
    for value in sorted(values):
        if clusters and value - clusters[-1][-1] <= max(value, 1.0) * tolerance:
            clusters[-1].append(value)
        else:
            clusters.append([value])
    return clusters


def tier_table(lines: list[Line], floor: float = TIER_FLOOR) -> list[Tier]:
    """Return the document's height tiers, tallest first."""
    if not lines:
        return []
    by_height: dict[float, list[Line]] = {}
    for line in lines:
        by_height.setdefault(line.height, []).append(line)

    tiers = []
    for group in cluster(list(by_height)):
        members = [line for height in group for line in by_height[height]]
        share = len(members) / len(lines)
        if share < floor:
            continue
        samples = tuple(
            dict.fromkeys(  # de-duplicate, keep order
                line.text.strip()[:52]
                for line in sorted(members, key=lambda item: (item.page, item.y))
                if line.text.strip()
            )
        )[:3]
        tiers.append(
            Tier(
                height=round(statistics.median(line.height for line in members), 1),
                lines=len(members),
                words=sum(len(line.text.split()) for line in members),
                share=share,
                samples=samples,
            )
        )
    return sorted(tiers, key=lambda tier: -tier.height)


def body_tier(tiers: list[Tier]) -> Tier | None:
    """The tier carrying the most words -- the document's running text."""
    return max(tiers, key=lambda tier: tier.words) if tiers else None


def report(pdf: Path) -> None:
    lines = document_lines(pdf)
    tiers = tier_table(lines)
    body = body_tier(tiers)
    print(f"\n=== {pdf.name}  ({len(lines)} lines, {len(tiers)} tiers) ===")
    print(f"{'height':>7} {'lines':>6} {'words':>7} {'share':>7}  {'role':<6} sample")
    for tier in tiers:
        role = "BODY" if tier is body else ""
        sample = tier.samples[0] if tier.samples else ""
        print(f"{tier.height:>7.1f} {tier.lines:>6} {tier.words:>7} "
              f"{tier.share:>6.1%}  {role:<6} {sample}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pdf", nargs="*", type=Path)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args(argv)
    targets = list(SOURCES) if args.all else args.pdf
    if not targets:
        parser.error("give at least one PDF, or --all")
    failures = 0
    for pdf in targets:
        try:
            report(pdf)
        except BboxError as exc:
            print(f"\n=== {pdf.name} === ERROR: {exc}")
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
