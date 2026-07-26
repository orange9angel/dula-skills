# Alibaba Bailian / DashScope adapter

The bundled adapter is generalized from the locally proven `wan2.7-image-pro` basketball sequence. It uses the DashScope asynchronous image-generation API and the `DASHSCOPE_API_KEY` environment variable.

## Known working shape

- Generation endpoint: `https://dashscope.aliyuncs.com/api/v1/services/aigc/image-generation/generation`
- Task endpoint: `https://dashscope.aliyuncs.com/api/v1/tasks/<task-id>`
- Async header: `X-DashScope-Async: enable`
- Authorization: `Bearer $DASHSCOPE_API_KEY`
- Message content: image data URLs followed by the compiled text prompt
- Sequential parameters: `enable_sequential=true`, `n=<desired-shot-count>`
- Tested model in the local example: `wan2.7-image-pro`

Provider contracts can change. Treat this as a tested adapter shape, not a guarantee for every DashScope image model.
Treat `n` as a requested count. The adapter records and handles the actual returned count separately.

## Prepare

Set the credential without placing it in source:

```powershell
$env:DASHSCOPE_API_KEY="<your-key>"
```

Set the plan provider section:

```json
{
  "name": "dashscope",
  "model": "wan2.7-image-pro",
  "capabilities": {
    "referenceImages": true,
    "multiImageReference": true,
    "sequentialGroup": true,
    "acceptsRequestedCount": true,
    "guaranteesRequestedCount": false,
    "orderedSequentialOutputs": true,
    "imageEdit": true,
    "seed": false,
    "negativePrompt": false,
    "maskEdit": false
  },
  "options": {
    "size": "2K",
    "watermark": false
  }
}
```

Validate and compile before any billable call:

```bash
python scripts/validate_sequence.py <sequence-plan.json> --strict
python scripts/build_generation_request.py <sequence-plan.json>
python scripts/run_dashscope_sequence.py <generation-request.json> --dry-run
```

Generate only after reviewing the dry-run:

```bash
python scripts/run_dashscope_sequence.py <generation-request.json>
```

Use `--overwrite` only when intentionally replacing existing generated frames.

## Group-first behavior

The adapter:

1. sends master identity, style, and setting references with one ordered group prompt;
2. requests one result per planned shot without assuming the count is guaranteed;
3. writes positionally matched results in shot order because this tested preset declares ordered output;
4. falls back only for missing shots;
5. supplies master references plus the nearest explicitly accepted frame to each fallback;
6. marks outputs `generated` for later human or vision review;
7. saves surplus images as unassigned candidates;
8. records requested and returned counts separately;
9. appends sanitized provider task records to the sequence plan.

The fallback output is still only `generated`. Review it before treating it as an anchor in a later run.

## Limits and failure handling

- Keep groups within the plan's `maxShotsPerGroup`.
- If the service returns fewer images, inspect completed frames before allowing fallback frames to inherit them.
- If it returns more images, keep the surplus under `_candidates/` for review.
- If subject scale or camera changes inside a group, strengthen camera locks or split at the intended cut.
- If a ball or hand is wrong but identity and staging are sound, prefer a local edit over full regeneration.
- Never store response image URLs; they may be signed and temporary.
