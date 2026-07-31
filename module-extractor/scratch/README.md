# Scratch

Prototype work for [../../architecture-new-implementation.md](../../architecture-new-implementation.md).
Nothing here is imported by `module_extractor/`, and nothing here is on the
pipeline's execution path. Phase 2 promotes what survives into the package.

```text
bbox.py       T0.1  word-level geometry from pdftotext -bbox-layout
baseline/     T3.1  the recovered comparison build (gitignored, 4 MB)
```

Standard library and Poppler only, matching the extractor's own rule. Run
anything here directly:

```bash
python3 module-extractor/scratch/bbox.py --all
```
