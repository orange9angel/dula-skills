# CharacterBase Contract

What `dula-engine/characters/CharacterBase.js` (and the systems built on it — viseme lip-sync, blink, eye tracking, facial expressions, animations, combat) expects a character subclass to provide. Verified against the engine source; `dula-assets/characters/Doraemon.js` satisfies every item and is the reference implementation.

## Required Structure

```js
import * as THREE from 'three';
import { CharacterBase } from 'dula-engine';

export class MyChar extends CharacterBase {
  constructor() {
    super('MyChar');                      // registered name
    this.archetypes = ['round', 'mascot']; // free-form tags, used for limit presets etc.
    this.boundingRadius = 0.85;            // camera/collision sizing — measure your build
  }

  build() { /* assemble primitives into this.mesh */ }

  update(time, delta) {
    super.update(time, delta);             // ALWAYS first
    /* optional ambient motion */
  }
}
```

- `this.mesh` is a `THREE.Group` created by the base class — add everything to it, never replace it.
- Ground contact is y=0, the character faces **+Z**. Face parts go on the +Z side of the head.

## Fields the Engine Reads

| Field | Type | Who uses it |
|-------|------|-------------|
| `headGroup` | Group at head pivot | head turns, eye tracking (`headBaseY` if you set it) |
| `mouth` | Group | viseme/mouth-cue lip-sync scales it from base values |
| `mouthBaseScaleX/Y/Z`, `mouthBaseY` | numbers | mouth reset between cues |
| `upperLip`, `lowerLip`, `mouthCavity` | meshes (optional) | finer mouth posing; cavity hidden when closed |
| `leftPupil`, `rightPupil` | meshes | eye tracking shifts them within `userData.eyeRadius`; record `userData.baseX/baseY` after placement |
| `leftEyelid`, `rightEyelid` | half-sphere meshes | blink: hidden at factor < 0.05, else `scale.y = 1 - factor*0.95` |
| `leftEyebrow`, `rightEyebrow` | meshes | expression system saves/poses position+rotation |
| `leftArm`, `rightArm` | Groups at shoulders | animations rotate these; record `leftArmBaseZ/rightArmBaseZ` (and `rightArmLength` if props attach to the hand) |
| `leftLeg`, `rightLeg` | Groups at hips | walk/run/jump animations |
| `jaw` | mesh (optional) | alternative to mouth scaling |
| `archetypes` | string[] | joint-limit presets, director behavior |
| `boundingRadius` | number | camera framing, collisions |

Optional but recommended: per-eye `Group`s so pupil + eyelid + catchlight move as a unit.

## Registration

In `dula-assets/index.js`:

```js
import { MyChar } from './characters/MyChar.js';
// inside registerAll():
registerCharacter('MyChar', MyChar);
```

Then confirm with `python dula-skills/story-writer/scripts/story_tool.py catalog --episode-dir <dir>` that `MyChar` appears, before using it in a `.story`.

## Conventions from Existing Characters

- One material per color, shared across meshes; build the shared 4-step `toonGradient` once in `build()`.
- `castShadow = true` on head/body only.
- Paired parts are built in a `for (const side of [-1, 1])` loop; `side === -1` is the character's left.
- Record every "base" value (positions, rotations, scales) immediately after placing a part — the expression/lip-sync systems restore to these.
- Props (hidden by default) are children of the limb/head that carries them, toggled via `visible` in small helper methods (`attachX`/`detachX`).
