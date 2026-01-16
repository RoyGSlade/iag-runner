You are Codex GPT-5.2 working inside a local-first mono-repo called iag-runner/ with backend/, frontend/, db/, docs/, ollama/, tests/.
Hard rules:

The backend is the single source of truth for all mechanics and math.

The LLM is used only for (a) intent extraction into strict JSON and (b) narration. No mechanics, no math, no state updates in LLM text.

Everything must run locally (no cloud dependencies).

Prefer deterministic, testable code. Use per-session RNG seeding for replayability.

Attributes: CON/DEX/CHA/WIS/INT start at 0; only modified by race/training/profession/leveling.

Combat rules: d20 initiative; 1A/1R base; AR=10+DEX+armor; AP absorbs damage first; nat19-20 crit double; reactions dodge/block/counter; called shots -5 for effects.

Statuses include: Bleeding, Ignited, Stun, Asphyxiation, Toxin, Injured, Concentration, Hidden, Cold, Disease with ramping progressions.

Superpowers MVP: Sherlock, Teleportation, Power Drain, Superspeed and they are era-locked (no superpowers pre-Space).

Eras: Prehistoric, Medieval, Colonial, Modern, Space with era “profiles + patches” for skills/professions/gear.
Output rules:

Always implement via concrete file changes (create/update files).

Keep changes small and incremental; do not do unrelated refactors.

When done, provide: (1) summary of changes, (2) list of files changed, (3) how to run/tests.
Start by reading the current repo tree before making changes.
