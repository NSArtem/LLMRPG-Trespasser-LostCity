# Module Extractor user guide

Module Extractor turns one adventure PDF into the repository's generated
`module/`. ChatGPT extracts bounded source evidence from ZIPs, Codex performs
the final source-based semantic review, and local Python code validates and
assembles the result.

You need Python 3, Poppler (`pdfinfo`, `pdftotext`, and `pdftoppm`), a PDF, and
ChatGPT with file attachments. Upload only material you are permitted to share.

## 1. Start

From the repository root, run:

```bash
python3 module-extractor/cli.py run path/to/adventure.pdf
```

The filename determines the module slug. A non-empty PDF title is used as the
title; otherwise the readable filename is used. Override either when needed:

```bash
python3 module-extractor/cli.py run path/to/adventure.pdf \
  --slug example-adventure --title "Example Adventure"
```

This creates `_exchange/routing.zip`.

## 2. Route

Upload `_exchange/routing.zip` to ChatGPT and say:

> Open the attached ZIP, read `prompt.md`, follow it exactly, and return only
> the completed JSON response as a downloadable file.

Save the download as `_exchange/routing.json`, then run:

```bash
python3 module-extractor/cli.py run
```

The command validates routing and creates focused ZIPs in the same flat
`_exchange/` directory.

## 3. Extract

For every focused ZIP, start a fresh ChatGPT conversation, upload that one ZIP,
and use the same instruction. Save each returned JSON beside its ZIP with the
same basename:

```text
_exchange/content.001.zip
_exchange/content.001.json
```

Do not combine packs in one conversation. JSON responses remain JSON files;
do not wrap them in ZIPs.

## 4. Finish with Codex

Tell Codex exactly:

> Finish the module extraction by following module-extractor/CODEX_WORKFLOW.md.

Codex runs the same state-aware command, checks cited source evidence, records
permitted corrections and canonical decisions, and reruns the command until
the release is assembled or a genuine evidence blocker remains. Review the
uncommitted `module-input/` and `module/` afterward.

## Troubleshooting

To see completed work, missing filenames, and the next action without changing
anything:

```bash
python3 module-extractor/cli.py status
```

If a response is missing, save it under the exact filename printed by `run`.
Partial sets are safe: valid available responses are ingested and the remaining
basenames are listed.

If a response is rejected, the message names the JSON, explains why, and names
the ZIP to retry. Ask ChatGPT to process that ZIP again, replace only the named
JSON, and rerun `python3 module-extractor/cli.py run`.

`_exchange/` and `.module-extractor-cache/` are disposable. `module-input/`
contains durable inputs, and `module/` is extractor-generated output.

A release starts at `module/MODULE.md`, with compact lookup in `index.md` and
`index.json` and selectively loadable cards under `cards/`. Full extraction
state and reports are isolated under `module/audit/`; they are for review and
repair, not normal gameplay context. `GENERATED_OUTPUT.json` identifies the
verified output contract and owns the complete generated tree. Play consumers
accept output only when `play_contract` is `module-play/v1`, `verification` is
`verified`, and both `MODULE.md` and `index.json` exist. A missing or unknown
play contract is an explicit incompatibility, never a signal to infer an older
layout.

To resolve the exact bounded context for one released place without loading
the complete index or topology into play context:

```bash
python3 module-extractor/cli.py status \
  --scene place.example-adventure.gate
```

The JSON result lists the place card, typed `load_with` card paths, byte count,
current node, only its adjacent edges, and the situations available at that
place. `audit/` and the source PDF are excluded.

Choosing which available situation is running is your decision, never the
extractor's. Name it explicitly to add the actors, procedures, and knowledge
that situation needs:

```bash
python3 module-extractor/cli.py status \
  --scene place.example-adventure.gate \
  --situation situation.example-adventure.parley-at-the-gate
```

The active situation reports its possible effects with `applied: false`. Those
effects describe what the source says may happen. Nothing applies them, and
nothing copies them into a checkpoint.
