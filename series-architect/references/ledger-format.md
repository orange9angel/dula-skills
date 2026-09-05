# Ledger Formats

Templates for the tables a series bible maintains. These extend, not
replace, the bible's existing sections.

## Foreshadow Registry (Lifecycle Form)

| # | Thread | Planted in | Form | Cooldown until | Planned advance (form change) | Planned payoff | Status |
|---|--------|-----------|------|----------------|------------------------------|----------------|--------|
| F01 | … | E07 | one dialogue line | E08 | E11: appears on screen for one shot | convergence arc | planted, cooling |

Status values: `planted, cooling` → `cooling done` → `advanced`
→ `paid off` → `closed` (abandoned honestly, see SKILL.md boundaries).

Rules that make the table enforceable:

- "Form" is one phrase naming exactly what the audience perceives
  ("one static frame", "a symbol in a sketchbook corner"). If the form
  needs a sentence to describe, the plant is too heavy.
- "Planned advance" must name a *different* form. Copying the planted
  form is repetition, not advancement.
- Cooldown is measured in whole episodes of silence — no mention, no
  image, no tease.

## Information Ledger

One row per hidden-layer fact. Cell format: `E<nn>: <degree>`.
Degrees: `unaware` / `witnessed` (saw it, did not understand) /
`suspects` / `knows`.

| Hidden fact | Audience | Character A | Character B | Character C |
|-------------|----------|-------------|-------------|-------------|
| The light in the river is real | E07: witnessed | E07: witnessed | — | E07: unaware |

Review questions at each planning session:

1. Did any cell move without an on-screen cause? (Invalid.)
2. Did any cell skip a degree? (Invalid.)
3. Has any character reached `knows`? If yes, the engine changed —
   replan the remaining threads around it.
4. Which character is the best next `witnessed` candidate, and do they
   have a plausible reason to be present?

## Season Rhythm Table

| Episode | Type (texture / advancement) | Thread moved | Aftertaste |
|---------|------------------------------|--------------|------------|
| E08 | texture | F01 planted | warmth |

Constraints checked against this table:

- One thread moved per row, except a marked convergence.
- No two consecutive advancement rows unless converging.
- At least one plant-or-advance row in every sliding window of 4
  episodes.
