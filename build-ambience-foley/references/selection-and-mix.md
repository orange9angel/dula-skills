# Ambience and Foley Selection

## Decide Whether a Sound Is Needed

Add a sound when at least one is true:

- It confirms contact or weight that the picture alone does not communicate.
- It establishes a new location or maintains spatial continuity.
- It signals an offscreen cause the audience must understand.
- It marks a story consequence or rhythmic beat.
- It supports a clearly stylized sound language already established by the episode.

Omit or reduce a sound when:

- The motion is already obvious and the sound adds only decoration.
- It competes with a line ending, punchline, or reaction.
- Its pitch contour suggests the wrong event.
- It duplicates music rhythm or another impact.
- The perspective does not match the shot.
- It was explicitly rejected in `audio_direction.exclusions`.

## Layer Types

### Ambience Beds

Use one main spatial bed per location and add sparse detail rather than stacking several loud loops. Favor real room tone for gyms, classrooms, homes, streets, and other recognizable spaces.

Crossfade beds across scene changes. Avoid restarting the same loop on every shot.

### Foley

Use close, concrete sounds for:

- footsteps and shoe squeaks
- cloth or uniform motion when readable
- door, bag, prop, and ball handling
- landings, catches, contacts, and rebounds

Align the main transient to contact. A ball bounce belongs at floor contact; a swish belongs at the rim/net event, not the start of the throw.

### Designed Effects

Reserve whooshes, energy tones, exaggerated impacts, and procedural effects for a consistent stylized language. Do not automatically assign a whoosh to every fast pose change or camera move.

## Perspective

Match the shot:

- close: more detail and high-frequency presence
- medium: balanced direct sound and room
- far: lower level, reduced high frequencies, more environmental masking
- offscreen: direction and room must imply location without becoming louder than visible action

Do not change perspective on every cut if the source remains in the same physical place.

## Dialogue and Breath

Keep dialogue intelligible. Lower or remove events under quiet consonants and line endings.

Do not add generic inhale, sigh, cry, or “woo” samples to create naturalism. Direct those inside the voice performance. Use a separate vocal effect only when the script calls for a distinct nonverbal event and it matches the character.

## Source and License

For every external asset, retain:

- direct source page or recording origin
- creator
- license and version
- attribution text when required
- local filename and any edits

Prefer CC0 or clearly licensed material. Do not claim a generated or downloaded asset is cleared without evidence.

## Review Pass

1. Solo the ambience bed and detect loops, clicks, or tonal distractions.
2. Solo event sounds and frame-step contacts.
3. Add dialogue and remove masking.
4. Add music and resolve rhythmic or tonal collisions.
5. Watch once at normal speed without looking at the timeline.
6. Remove at least every sound that draws attention for the wrong reason.

## Quiet Indoor Movement (2026-10-17)

Repeated short noise can turn a soft shoe recording into conspicuous rustling when
triggered on every landing. If the user chooses silent walking for a scene, remove its
footstep cue and record the scene-scoped exclusion; do not replace it with cloth noise.
Retain landing anchors for motion validation, but make audio validation conditional on
the reviewed cue plan. A silent-footstep decision should pass with zero step cues and
zero Foley in the entry walk. Configuration regeneration must preserve reviewed decisions.
This is a scene choice, not a rule that all indoor scenes have no footsteps.

If rustling remains after removing footsteps, solo every bus at its actual mix level.
S1E4's room bed was documented as −53 dBFS but executed at −43 dBFS; starting it with
the entry walk suggested footsteps. Verify the written level against rendered PCM.
For a deliberately quiet interior, removing an unhelpful bed is valid. Persist an
ambience stem even when it is zero, and check the rejected sound across ambience,
Foley and score; zero Foley alone cannot prove a rustle-free opening.
