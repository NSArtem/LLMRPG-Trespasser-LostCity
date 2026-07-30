# Module Extractor

Module Extractor turns an adventure PDF into a source-cited module for an LLM
game master. ChatGPT performs bounded extraction, Codex performs final semantic
review, and deterministic local code remains authoritative for validation and
release assembly.

- [User guide](USER_GUIDE.md) — the four-step extraction workflow.
- [Codex workflow](CODEX_WORKFLOW.md) — the stable final-review handoff.
- [Developer reference](DEVELOPER.md) — commands, contracts, state, and safety.
- [Canonical identity policy](IDENTITY.md) — runtime IDs, duplicate candidates,
  and review decisions.

Released place cards are the scene entry points. They separate player-safe and
GM-only information, derive immediate exits from canonical topology, and expose
typed bounded context through `status --scene PLACE_ID`.

Actor and situation cards carry enough structure to run the encounter there:
observable appearance, role, goals, behavior, and capabilities separated from
GM-only material, and situations with one identity, an explicit activation,
participants, approaches, consequences, and hypothetical possible effects.
Add `--situation SITUATION_ID` to make one available situation active.
