---
name: series-architect
description: Design and maintain the long narrative arc of a multi-episode Dula series. Use when planning across episodes — managing the foreshadow lifecycle (plant, cooldown, advance, payoff), tracking who-knows-what between audience and characters, setting season-level emotional rhythm, and handing single-episode briefs to story-writer. Episode scripts themselves are written by story-writer; this skill owns the arc above them.
---

# Series Architect

Own the long arc. Single-episode craft belongs to `story-writer`
(including `references/directing-craft.md`); this skill decides what the
episodes collectively build toward and when each hidden thread moves.

The series bible in the content repository (e.g.
`dula-story/docs/<series>_series_bible.md`) is the source of truth this
skill maintains: worldview locks, the foreshadow registry, and the
information ledger. Read the target series bible before any planning.

## Core Rules

- **Episode integrity is untouchable.** Every episode must satisfy a
  viewer who never sees another episode: one small event, one emotional
  landing. The arc is carried by planted elements that cost no runtime
  and change no plot. Never sacrifice a single episode to the arc.
- **The audience runs ahead of the characters.** In a series with a
  hidden layer, that gap is the engine — but the gap must create
  yearning, not apprehension. Every planned movement of a hidden thread
  must specify its emotional sign, and in warm-toned series the sign is
  always positive (wonder, fondness, awe). No character may explain the
  hidden layer in dialogue; information reaches characters through
  witnesses who do not understand what they saw, or through images
  nobody interprets. Witnesses are keepers and friends of the wonder,
  not frightened reporters of it.
- **Register before writing.** A foreshadow element enters the series
  bible registry before it enters any script. The registry update and
  the episode are separate commits of intent.

## Foreshadow Lifecycle

Every registered thread moves through four phases. Skipping cooldown is
the most common way long arcs fail.

1. **Plant.** One-prompt-element form: a single line of dialogue, one
   static frame, one background detail. No runtime cost, no plot change.
   State at plant time which convergence the thread points at.
2. **Cooldown.** Mandatory silence of at least one full episode. A
   thread paid off while the audience still remembers it is wasted;
   payoff lands when the audience has forgotten and then remembers. Cooldown
   episodes carry other threads or none.
3. **Advance.** Change the form, never repeat it: verbal → visual,
   object → behavior, light → living thing. Each advance raises the
   claim one step (someone said it → it appeared → it is alive → it is
   near). Only one thread advances per episode, unless threads converge.
4. **Payoff.** The payoff must recontextualize already-shown material —
   earlier scenes must read differently afterward. Converge multiple
   threads into one scene when possible; convergence multiplies the
   recontextualization. After payoff, update the registry.

Registry columns per thread: planted in / form / cooldown until /
planned advance (form change) / planned payoff / status. Template:
[references/ledger-format.md](references/ledger-format.md).

## Information Ledger

Maintain a matrix of hidden-layer facts: rows are facts, columns are the
audience and each major character, cells hold the episode and degree of
knowledge (unaware / witnessed-uninterpreted / suspects / knows).
Review the ledger at every planning session:

- No cell may jump from unaware to knows without an intermediate.
- A character who "knows" must have earned it on screen.
- The audience column leads every character column by design; flag any
  character who catches up, because that changes the engine.

## Season Rhythm

- Every 3–4 episodes, plant or advance exactly one thread. Less starves
  the arc; more turns texture into noise.
- Alternate texture episodes (pure single-episode stories, empty beats
  dominant) with advancement episodes (one thread moves). Never run two
  advancement episodes back to back unless converging.
- The season-level intensity curve obeys the same rule as the episode
  curve in `directing-craft.md`: the quietest stretch sits immediately
  before the convergence arc begins.

## Workflow

1. **Read the bible.** Load the series bible, the registry, and the
   ledger. List every open thread and its phase.
2. **Position the episode.** Decide whether the next episode is texture
   or advancement. If advancement, pick exactly one thread and its new
   form. Check cooldowns first.
3. **Write the brief, not the script.** Hand `story-writer` a brief:
   premise direction, the planted element (one element only), the
   target aftertaste, and any continuity constraints. Never dictate
   dialogue or shot lists.
4. **Review the draft against the arc.** After story-writer drafts,
   check: is the planted element present in its registered form? Does
   the episode stand alone? Did any character learn something the
   ledger forbids?
5. **Update the bible.** After the episode ships, update registry
   phases and ledger cells, and record the next planned movement.

## Boundaries

- Do not write or edit `script.story`; that is story-writer's layer.
- Do not invent retroactive continuity to rescue a thread. If a thread
  can no longer pay off honestly, close it with a small on-screen beat
  and mark it closed rather than forcing a convergence.
- Third-party works and author names stay in discussion only; nothing
  written to the bible or this skill references them.
