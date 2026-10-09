"""Offline GLB metadata inventory; does not certify topology or animation quality."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys


def read_glb(path):
    raw = path.read_bytes()
    if len(raw) < 20:
        raise ValueError('File is too short for a GLB header and JSON chunk')
    magic, version, length = struct.unpack_from('<4sII', raw)
    if magic != b'glTF' or version != 2 or length != len(raw):
        raise ValueError('Expected a GLB v2 with a correct declared file length')
    offset, chunks = 12, []
    while offset < len(raw):
        if offset + 8 > len(raw):
            raise ValueError('Truncated chunk header')
        size, kind = struct.unpack_from('<II', raw, offset)
        offset += 8
        if size % 4 or offset + size > len(raw):
            raise ValueError('Misaligned or truncated chunk')
        chunks.append((kind, raw[offset:offset + size]))
        offset += size
    if not chunks or chunks[0][0] != 0x4E4F534A:
        raise ValueError('First chunk must be JSON')
    if sum(kind == 0x4E4F534A for kind, _ in chunks) != 1:
        raise ValueError('Expected exactly one JSON chunk')
    doc = json.loads(chunks[0][1].decode('utf-8'))
    if not isinstance(doc, dict) or doc.get('asset', {}).get('version') != '2.0':
        raise ValueError('Expected a glTF 2.0 document')
    return doc, raw


def inventory(path, doc, raw):
    accessors = doc.get('accessors', [])

    def count(index):
        if index is None:
            return 0
        if not isinstance(index, int) or not 0 <= index < len(accessors):
            raise ValueError(f'Invalid accessor index: {index}')
        value = accessors[index].get('count')
        if not isinstance(value, int) or value < 0:
            raise ValueError(f'Invalid accessor count: {value}')
        return value

    meshes, triangles, morphs = [], 0, 0
    warnings = []
    for i, mesh in enumerate(doc.get('meshes', [])):
        primitives = []
        for p in mesh.get('primitives', []):
            attrs = p.get('attributes', {})
            vertices = count(attrs.get('POSITION'))
            n = count(p['indices']) if 'indices' in p else vertices
            mode = p.get('mode', 4)
            faces = n // 3 if mode == 4 else max(0, n - 2) if mode in (5, 6) else 0
            # Strip counts include degenerate triangles; no index buffer decoding here.
            triangles += faces
            targets = len(p.get('targets', []))
            morphs = max(morphs, targets)
            primitives.append({'vertices': vertices, 'triangle_upper_bound': faces,
                               'mode': mode, 'material': p.get('material'),
                               'attributes': sorted(attrs), 'morph_targets': targets})
        meshes.append({'index': i, 'name': mesh.get('name'), 'primitives': primitives,
                       'target_names': mesh.get('extras', {}).get('targetNames', [])})
    skinned_nodes = []
    for i, node in enumerate(doc.get('nodes', [])):
        if 'skin' in node and 'mesh' in node:
            mesh_index, skin_index = node['mesh'], node['skin']
            if not 0 <= mesh_index < len(meshes) or not 0 <= skin_index < len(doc.get('skins', [])):
                raise ValueError('Skinned node has an invalid mesh or skin reference')
            skinned_nodes.append(i)
            for p in meshes[mesh_index]['primitives']:
                if not {'JOINTS_0', 'WEIGHTS_0'}.issubset(p['attributes']):
                    warnings.append(f'Node {i} references skin but a primitive lacks joint/weight attributes')
    external = [item['uri'] for key in ('buffers', 'images') for item in doc.get(key, [])
                if 'uri' in item and not item['uri'].startswith('data:')]
    if external:
        warnings.append('External resources listed; existence/content has not been checked')
    if not skinned_nodes:
        warnings.append('No mesh node references a skin; no skeletal animation readiness established')
    if not morphs:
        warnings.append('No morph targets; facial animation requires another system or added targets')
    return {
        'path': str(path.resolve()), 'sha256': hashlib.sha256(raw).hexdigest(),
        'bytes': len(raw), 'generator': doc.get('asset', {}).get('generator'),
        'mesh_count': len(meshes), 'unique_mesh_triangle_upper_bound': triangles,
        'triangle_count_scope': 'Unique stored meshes, before instancing; strips may include degenerates',
        'meshes': meshes, 'node_count': len(doc.get('nodes', [])),
        'skin_count': len(doc.get('skins', [])), 'skinned_mesh_nodes': skinned_nodes,
        'joints_per_skin': [len(s.get('joints', [])) for s in doc.get('skins', [])],
        'max_morph_targets_per_primitive': morphs,
        'animations': [{'name': a.get('name'), 'channel_count': len(a.get('channels', []))}
                       for a in doc.get('animations', [])],
        'materials': [{'name': m.get('name'), 'alpha_mode': m.get('alphaMode', 'OPAQUE'),
                       'double_sided': m.get('doubleSided', False),
                       'has_base_color_texture': 'baseColorTexture' in m.get('pbrMetallicRoughness', {}),
                       'has_normal_texture': 'normalTexture' in m}
                      for m in doc.get('materials', [])],
        'texture_count': len(doc.get('textures', [])),
        'required_extensions': doc.get('extensionsRequired', []),
        'external_resources': external, 'warnings': warnings,
        'limits': 'Metadata only. Buffer contents, weights, world dimensions, deformation, collisions and visual quality are not validated.',
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('file', type=Path)
    p.add_argument('--out', type=Path)
    p.add_argument('--require-skin', action='store_true')
    p.add_argument('--require-morph', action='store_true')
    p.add_argument('--max-triangles', type=int)
    args = p.parse_args()
    if args.max_triangles is not None and args.max_triangles < 0:
        p.error('--max-triangles must be nonnegative')
    try:
        doc, raw = read_glb(args.file)
        report = inventory(args.file, doc, raw)
        failures = []
        if args.require_skin:
            if not report['skinned_mesh_nodes'] or any('lacks joint/weight' in w for w in report['warnings']):
                failures.append('Required skinned mesh metadata is absent or incomplete')
            elif not all(report['joints_per_skin'][doc['nodes'][n]['skin']] for n in report['skinned_mesh_nodes']):
                failures.append('A referenced skin has no joints')
        if args.require_morph and not report['max_morph_targets_per_primitive']:
            failures.append('Required morph target metadata is absent')
        if args.max_triangles is not None and report['unique_mesh_triangle_upper_bound'] > args.max_triangles:
            failures.append('Triangle budget exceeded')
        report['requested_metadata_checks_passed'] = not failures
        report['failures'] = failures
        serialized = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
        if args.out:
            if args.out.resolve() == args.file.resolve():
                raise ValueError('Output must not overwrite the input GLB')
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(serialized, encoding='utf-8')
        print(serialized)
        return 2 if failures else 0
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        print(f'GLB inspection failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
