"""Verify a complete drawing export, preserving the accepted source audio."""
from pathlib import Path
from fractions import Fraction
import argparse
import json
from package_pilot import bounds, probe, sha
from replace_window import audio_hash


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--episode', required=True)
    parser.add_argument('--config', required=True)
    parser.add_argument('--repair-config', help='Optional window repair assembled into this full export')
    args = parser.parse_args()
    root = Path(args.episode).resolve()
    cfg = json.loads((root / args.config).read_text(encoding='utf-8'))
    pilot = cfg['pilot']
    source, output = root / cfg['source']['video'], root / pilot['output']
    start, end = bounds(root, pilot)
    source_info, output_info = probe(source), probe(output)
    src_video = next(s for s in source_info['streams'] if s['codec_type'] == 'video')
    out_video = next(s for s in output_info['streams'] if s['codec_type'] == 'video')
    board = root / pilot['board']
    checks = {
        'accepted_source_unchanged': sha(source) == cfg['source']['sha256'],
        'whole_episode_window': start == 0 and abs(end - float(src_video['duration'])) < 1e-5,
        'frame_count': int(out_video['nb_frames']) == round((end - start) * pilot['fps']),
        'frame_rate': float(Fraction(out_video['r_frame_rate'])) == pilot['fps'],
        'dimensions': (out_video['width'], out_video['height']) == (pilot['width'], pilot['height']),
        'duration': abs(float(out_video['duration']) - end) < 1e-5,
        'audio_packets_identical': audio_hash(source, True) == audio_hash(output, True),
        'audio_pcm_identical': audio_hash(source, False) == audio_hash(output, False),
    }
    deterministic = json.loads((board / 'determinism.json').read_text(encoding='utf-8'))
    checks['deterministic'] = deterministic['passed']
    acting = json.loads((root / cfg['probe']['output']).read_text(encoding='utf-8'))
    checks['episode_probe'] = acting['passed']
    build = json.loads((board / 'build.json').read_text(encoding='utf-8'))
    sources = {item['path']: item['sha256'] for item in build['source']}
    repair = None
    if args.repair_config:
        repair_cfg = json.loads((root / args.repair_config).read_text(encoding='utf-8'))
        repair_board = root / repair_cfg['pilot']['board']
        repair = json.loads((root / repair_cfg['integration']['report']).read_text(encoding='utf-8'))
        repair_build = json.loads((repair_board / 'build.json').read_text(encoding='utf-8'))
        repair_determinism = json.loads((repair_board / 'determinism.json').read_text(encoding='utf-8'))
        sources.update({item['path']: item['sha256'] for item in repair_build['source']})
        checks['repair_assembly'] = (repair['passed'] and
            (root / repair['output']).resolve() == output.resolve() and
            repair['output_sha256'] == sha(output) and
            repair['source_sha256'] == sha(root / repair['source']) and
            repair['replacement_sha256'] == sha(root / repair['replacement']))
        checks['repair_deterministic'] = repair_determinism['passed']
    checks['render_sources_current'] = all(sha(root / path) == digest for path, digest in sources.items())
    report = {
        'scope': 'complete episode',
        'source': cfg['source']['video'], 'source_sha256': sha(source),
        'output': pilot['output'], 'output_sha256': sha(output),
        'media': output_info, 'checks': checks, 'passed': all(checks.values()),
        'determinism_checks': len(deterministic['checks']),
        'artwork_scope': acting.get('coverage', []),
        'repair': repair,
        'note': 'Technical checks are separate from the recorded visual review.',
    }
    (board / 'full_delivery.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'passed': report['passed'], 'checks': checks, 'output': str(output)}, ensure_ascii=False))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
