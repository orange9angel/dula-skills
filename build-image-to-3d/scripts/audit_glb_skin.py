"""Decode embedded GLB skin weights; structural checks are not visual approval.

Requires numpy. Sparse/compressed/external accessor data is explicitly unsupported.
"""
import argparse
import json
from pathlib import Path
import struct
import sys
import numpy as np
from inspect_glb import read_glb


def audit(path, humanoid=False):
    doc, raw = read_glb(path)
    chunks, offset = [], 12
    while offset < len(raw):
        size, kind = struct.unpack_from('<II', raw, offset)
        if kind == 0x004E4942:
            chunks.append(raw[offset + 8:offset + 8 + size])
        offset += 8 + size
    if len(chunks) != 1:
        raise ValueError('Expected one embedded BIN chunk')
    binary = chunks[0]
    dtype = {5120:'i1',5121:'u1',5122:'<i2',5123:'<u2',5125:'<u4',5126:'<f4'}
    widths = {'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}

    def accessor(index):
        a = doc['accessors'][index]
        if 'sparse' in a or 'bufferView' not in a:
            raise ValueError('Sparse or absent bufferView is unsupported')
        view = doc['bufferViews'][a['bufferView']]
        if view.get('buffer', 0) != 0 or doc['buffers'][0].get('uri') or view.get('extensions'):
            raise ValueError('External or compressed buffer is unsupported')
        dt = np.dtype(dtype[a['componentType']]); width = widths[a['type']]
        start = view.get('byteOffset', 0) + a.get('byteOffset', 0)
        stride = view.get('byteStride', dt.itemsize * width)
        end = start + max(0, a['count'] - 1) * stride + (dt.itemsize * width if a['count'] else 0)
        if stride < dt.itemsize * width or end > len(binary) or end > view.get('byteOffset', 0) + view['byteLength']:
            raise ValueError('Accessor exceeds its buffer view')
        values = np.ndarray((a['count'], width), dtype=dt, buffer=binary,
                            offset=start, strides=(stride,dt.itemsize)).copy()
        if a.get('normalized') and a['componentType'] != 5126:
            values = values.astype(float) / np.iinfo(dt).max
            if dt.kind == 'i': values = np.maximum(values, -1)
        return values

    report = {'file':str(path), 'humanoid':humanoid, 'primitives':[], 'failures':[],
              'limits':'Weights only: no deformation, clothing, face, collision or appearance approval.'}
    for node in doc.get('nodes', []):
        if 'skin' not in node or 'mesh' not in node: continue
        skin = doc['skins'][node['skin']]
        names = [doc['nodes'][i].get('name',str(i)) for i in skin['joints']]
        for primitive in doc['meshes'][node['mesh']]['primitives']:
            attrs = primitive['attributes']
            if 'JOINTS_1' in attrs or 'WEIGHTS_1' in attrs:
                raise ValueError('Additional influence sets require an extended audit')
            joints, weights = accessor(attrs['JOINTS_0']), accessor(attrs['WEIGHTS_0'])
            if joints.shape != weights.shape or joints.shape[1] != 4 or not len(joints):
                raise ValueError('Mismatched or empty joint/weight arrays')
            if not np.isfinite(weights).all() or (weights < 0).any():
                raise ValueError('Non-finite or negative skin weights')
            if (joints >= len(names)).any() or (joints < 0).any():
                raise ValueError('Skin joint index out of bounds')
            sums = weights.sum(1)
            if np.max(np.abs(sums-1)) > .001: report['failures'].append('Weights do not sum to one')
            dominant = joints[np.arange(len(joints)),weights.argmax(1)].astype(int)
            counts = np.bincount(dominant,minlength=len(names)); peak = int(counts.argmax())
            fraction = float(counts[peak]/len(joints))
            if humanoid and fraction > .98:
                report['failures'].append(f'Humanoid weights concentrated on {names[peak]}: {fraction:.6f}')
            report['primitives'].append({'vertices':len(joints),'joints':len(names),
                'weight_sum_range':[float(sums.min()),float(sums.max())],
                'dominant_joint':names[peak],'dominant_fraction':fraction,
                'dominant_vertices_by_joint':{name:int(n) for name,n in zip(names,counts) if n}})
    if not report['primitives']: report['failures'].append('No skinned mesh')
    report['passed'] = not report['failures']
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('file',type=Path);ap.add_argument('--humanoid',action='store_true')
    ap.add_argument('--out',type=Path);args=ap.parse_args()
    try:
        report=audit(args.file,args.humanoid)
        if args.out:
            if args.out.resolve()==args.file.resolve(): raise ValueError('Output must not overwrite GLB')
            args.out.parent.mkdir(parents=True,exist_ok=True)
            args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'file':str(args.file),'passed':report['passed'],'failures':report['failures']}))
        return 0 if report['passed'] else 2
    except (OSError,ValueError,KeyError,IndexError,TypeError) as e:
        print(json.dumps({'passed':False,'error':str(e)}));return 1


if __name__=='__main__':sys.exit(main())
