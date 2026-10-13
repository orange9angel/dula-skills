"""Dense surface trace validation; coverage failures cannot become a green result."""
import hashlib
import math
from pathlib import Path


def audit_surfaces(data, config):
    fps = data.get('fps', 0)
    if not isinstance(fps, (float, int)) or not math.isfinite(fps) or fps < config.get('fps_min', 30):
        return {'passed': False, 'coverage_errors': ['invalid or insufficient fps'], 'events': [], 'pairs': {}}
    errors, events, summary = [], [], {}
    frames = data.get('frames', [])
    ticks = {}
    previous = -math.inf
    for frame in frames:
        t = frame.get('t')
        if not isinstance(t, (int, float)) or not math.isfinite(t) or t <= previous:
            errors.append('nonfinite or nonmonotonic timestamp')
            continue
        previous = t
        tick = round(t * fps)
        if abs(t - tick / fps) > .0011 or tick in ticks:
            errors.append(f'invalid or duplicate frame tick: {t}')
        ticks[tick] = frame
    for rule in config['pairs']:
        key = rule['key']
        limit = rule['max_depth']
        if not math.isfinite(limit) or limit < 0:
            errors.append(f'invalid depth limit: {key}')
            continue
        start, end = rule['window']
        active = None
        stat = summary[key] = {'frames': 0, 'worst_depth': 0, 'worst_t': None, 'max_depth': limit}
        missing = 0
        for tick in range(math.ceil(start * fps - 1e-7), math.ceil(end * fps - 1e-7)):
            frame = ticks.get(tick, {})
            value = (frame.get('surface') or {}).get('pairs', {}).get(key)
            if not value or not isinstance(value.get('depth'), (int, float)) or not math.isfinite(value['depth']) or value['depth'] < 0 or not isinstance(value.get('evaluated'), int) or value['evaluated'] <= 0:
                missing += 1
                active = None
                continue
            if value.get('method') != rule['method']:
                missing += 1
                active = None
                continue
            depth, t = value['depth'], frame['t']
            stat['frames'] += 1
            if depth > stat['worst_depth']:
                stat.update(worst_depth=depth, worst_t=t)
            if depth > limit + 1e-7:
                if active is None:
                    active = {'pair': key, 'start': t, 'end': t, 'frames': 0, 'worst_depth': 0, 'worst_t': t, 'max_depth': limit}
                    events.append(active)
                active['end'] = t
                active['frames'] += 1
                if depth > active['worst_depth']:
                    active.update(worst_depth=depth, worst_t=t, point=value.get('point'), part=value.get('part'))
            else:
                active = None
        if missing:
            errors.append(f'{key}: {missing} missing/invalid required samples')
    if config.get('require_build'):
        build = data.get('build', {}).get('inputs', [])
        if not build:
            errors.append('missing input fingerprint')
        for item in build:
            path = Path(item['path'])
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
                errors.append(f'stale or missing input: {path.name}')
    events.sort(key=lambda event: event['worst_depth'], reverse=True)
    return {'passed': not errors and not events, 'coverage_errors': errors, 'events': events,
            'pairs': summary, 'event_count': len(events),
            'scope': 'sampled rendered vertices and finite cloth proxy; not continuous collision or artistic approval'}
