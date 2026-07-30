# Canonical identity policy

Runtime records use exactly one canonical identifier for each reviewed source
concept:

```text
place.<module>.<slug>
actor.<module>.<slug>
situation.<module>.<slug>
knowledge.<module>.<slug>
procedure.<module>.<slug>
item.<module>.<slug>
```

`<module>` is the normalized source slug. `<slug>` is normally derived from
the source title. Extracted IDs are observations, not runtime identity, and
remain available in audit data.

Identity matching normalizes Unicode and case, removes apostrophes, treats
punctuation (including hyphens and dots) as token separators, removes leading
record-type and module prefixes when comparing extracted IDs, and renders
number tokens without leading zeroes. Thus `Area 03`, `area-3`, and map label
`03` may contribute the same keyed-area signal. Map labels remain evidence
signals rather than titles and never establish identity by themselves.

Normalization is only candidate evidence. Titles are not globally unique.
When separate concepts produce the same default canonical slug, the extractor
adds a deterministic keyed-area or identity suffix instead of merging them.
Only a current-run review alias may merge extracted identities.

Duplicate candidates are detected after ingestion and before reconciliation.
High-confidence unresolved candidates block release. A reviewer records:

- `canonical_ids`: the canonical ID declared for an extracted ID;
- `aliases`: one current-run extracted ID targeting another;
- `distinct`: a reviewed decision that a candidate pair is not equivalent;
- `values`: a `select` or `compose` operation for canonical field content;
- source pages and an evidence-based rationale for every decision.

Review operations may cite only observations and evidence from the active
extraction. Alias cycles, ambiguous aliases, unknown targets, unsupported
canonical IDs, dangling rewritten references, and unreviewed duplicate
keyed-area claims are successful review-required states, never publishable
release states.
