# Dula Scene Runtime Constraints

## Lifecycle And Registration

- `SceneBase` owns `scene`, `lights`, `characters`, and `cameraObstacles`.
- The registry constructs a scene with `new SceneClass()` and then calls `build()`. Scene constructors must work with zero arguments.
- `build()` runs before characters are added. Resolve character-dependent targets inside events or `update()`.
- Scene switching creates a fresh instance. Keep mutable episode state on the instance, not globals or static properties.
- Register official assets with `registerAll()`. Register aliases and episode-local scenes explicitly in the bootstrap imported before Storyboard creation.

## Story Placement

- `{Position:Hero|x=...|y=...|z=...|face=...}` establishes explicit blocking.
- `{Event:Move|character=Hero|x=...|z=...|duration=...}` is an engine event, not a scene handler.
- If placement is absent, Storyboard may apply default layout or transition configuration. Contract anchors alone do not position characters.

## Event Dispatch

Generic custom events use:

```javascript
const method = eventName[0].toLowerCase() + eventName.slice(1);
scene[method]();
```

The runtime also tries the exact event name. It does not pass custom options. Reserve `Move`, `Animate`, `Face`, `Hide`, `Show`, `ShowAura`, `HideAura`, `ShowBeam`, `HideBeam`, and `JointMarkers` for engine behavior.

Prefer event methods that capture deterministic event start data:

```javascript
openDoor() {
  this._events.set('openDoor', { start: this._sceneTime, duration: 0.8 });
}
```

Then derive animation from absolute scene time in `update()`. This makes sequential playback and verification replay converge.

## Coordinate Spaces And Parenting

Three.js child positions are parent-local. Writing a world target into a child under a transformed parent produces an offset bug.

Use one of these patterns:

```javascript
// Preserve current world transform while moving the prop under the scene.
this.scene.attach(prop);

// Or convert a world target into the current parent's local space.
const localTarget = parent.worldToLocal(worldTarget.clone());
```

Use `add()` only when a local-space jump is intentional. Record every important prop's parent, transform space, and reparent strategy in the contract.

## Presence And State

Do not treat `mesh.visible = false` as an implementation detail when it changes story meaning. Contract the state as:

- `offstage`: not currently in the location.
- `onstage`: available to cameras and interactions.
- `concealed`: physically present but hidden by a named prop or occluder.

Every concealment needs a later reveal or exit unless the story ends while concealment is intentional. Keep prop state transitions and scene state bindings consistent with these presence effects.

## Camera Obstacles And Shots

`registerCameraObstacle()` supports:

```javascript
{ type: 'sphere', center: Vector3, radius: number }
{ type: 'capsule', start: Vector3, end: Vector3, radius: number }
{ type: 'box', center: Vector3, size: Vector3, rotation?: Quaternion }
```

`Static`, `CloseUp`, `OverShoulder`, and `TrackingCloseUp` currently use the collision guard. Treat other cameras as unguarded and add critical shot checks.

Camera obstacles prevent clipping; they do not prove composition. Verify subject visibility, projected area, safe margins, occlusion, facing, and relationship shots at exact contract times.

## Async Assets

The renderer waits on `currentScene.readyPromise`. A GLTF or other async scene must expose that promise and resolve it only when required assets and fallback handling are ready. Record asset dependencies and readiness mode in the contract.

## Final Gate Order

1. `node --check` for bootstrap, scenes, characters, and episode animations.
2. `story_tool.py validate --warnings-as-errors`.
3. `scene_tool.py validate --warnings-as-errors`.
4. `npx dula-inspect-team`.
5. `npx dula-verify`.
6. Exact-time screenshots for contract shot checks and full visual review.
7. `npx dula-render` only after the previous gates are understood.
