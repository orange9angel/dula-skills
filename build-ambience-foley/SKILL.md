---
name: build-ambience-foley
description: Design, source, generate, place, and validate environmental ambience and story-driven Foley against dialogue and picture. Use for room tone, weather, crowds, footsteps, doors, props, impacts, sports sounds, action effects, missing or excessive SFX, false sound associations, licensing, and ambience continuity in an episode, animation, film, or motion comic.
---

# Build Ambience and Foley

Make the world audible without narrating every visible motion. Use picture, dialogue, and the reviewed sound plan to decide what deserves sound and what should remain silent.

## Workflow

1. Read the episode context.
   - Read `script.story`, `config/audio_direction.json`, the active picture timeline, scene contract, existing SFX assets/tags, music cues, and exclusions.
   - Read [references/selection-and-mix.md](references/selection-and-mix.md) before adding sounds.
   - Preserve rejected sounds recorded in `exclusions`.

2. Separate sound roles.
   - Use ambience beds to establish continuous space.
   - Use Foley for human-scale contact: steps, cloth, doors, ball bounces, handling, and landings.
   - Use story effects for narratively important impacts, mechanisms, transformations, or offscreen information.
   - Keep vocal breaths, sighs, sobs, and exertion inside the character-voice workflow unless they are explicitly nonverbal performance cues.

3. Select only motivated events.
   - Prioritize sounds that clarify contact, weight, location, consequence, or an offscreen cause.
   - Skip generic whooshes for ordinary thrown objects or camera motion unless the style is deliberately exaggerated.
   - Do not add a sound merely because a generator exists.
   - Leave room around dialogue, punchlines, reveals, and visually self-explanatory motion.

4. Anchor to picture and story.
   - Reference stable entry, shot, or event IDs; resolve seconds from the current story/picture.
   - Align impact transients to visible contact, not motion onset.
   - Start ambience before or at scene entry and crossfade beds across location changes.
   - Materialize Dula decisions as explicit `{SFX:...}` tags or the engine's established cue inputs so `script.story` remains the timing authority.

5. Choose sources.
   - Prefer a clean, appropriate recorded or curated sound with compatible perspective.
   - Preserve source URL, creator, license, and any attribution requirement.
   - Use procedural synthesis as a fallback or for stylized/non-real sounds.
   - Use the sibling `fighting-sfx` workflow only for deliberately stylized combat effects.

6. Build and mix the layer.
   - Keep beds low and stable; avoid audible looping.
   - Match distance, room, and material across consecutive shots.
   - Give story-critical effects transient space without masking speech.
   - Avoid embedding music-like tonal glides in Foley when they may be mistaken for a narrative sound.

7. Review against picture.
   - Solo ambience, solo Foley/SFX, then listen with dialogue and music.
   - Check sync, perspective, repetition, abrupt bed changes, excessive density, and sounds that imply the wrong object or action.
   - Remove any sound whose absence improves clarity or naturalness.

## Ownership

- Own environmental beds, Foley/event assets, cue placement, source records, and this layer's review.
- Do not alter dialogue performance, voice timing, or music composition.
- Do not compensate for a weak visual edit by filling every gap with sound.
- Respect the director plan's priority: dialogue, then story-critical SFX, then ambience, then music.
