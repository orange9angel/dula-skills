"""Blender background: decimate the original textured mesh and transfer an audited rig.

Candidate preparation only; requires a matching source in its actual bind pose.
Preserves the original UV/textures instead of baking through a low-detail remesh.
Run: blender -b --python this.py -- --high high.glb --rig walk.glb --out candidate.glb
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import bpy
from mathutils import Vector

ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--high',type=Path,required=True)
ap.add_argument('--rig',type=Path,required=True)
ap.add_argument('--out',type=Path,required=True)
ap.add_argument('--triangles',type=int,default=160000)
args=ap.parse_args(sys.argv[sys.argv.index('--')+1:])
if args.out.resolve() in [args.high.resolve(),args.rig.resolve()]:raise ValueError('Never overwrite source assets')
if args.triangles<1:raise ValueError('Triangle target must be positive')
started=time.time()
bpy.ops.wm.read_factory_settings(use_empty=True)

def load(path):
    before=set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path.resolve()))
    return [o for o in bpy.data.objects if o not in before]

high_objects=load(args.high)
high_meshes=[o for o in high_objects if o.type=='MESH']
rig_objects=load(args.rig)
sources=[o for o in rig_objects if o.type=='MESH' and any(m.type=='ARMATURE' for m in o.modifiers)]
rigs=[o for o in rig_objects if o.type=='ARMATURE']
if len(high_meshes)!=1 or len(sources)!=1 or len(rigs)!=1:raise ValueError(f'Expected single high mesh, source mesh and armature; high={[(o.name,o.type) for o in high_objects]}, rig={[(o.name,o.type) for o in rig_objects]}')
high,source,rig=high_meshes[0],sources[0],rigs[0]
rig.data.pose_position='REST';bpy.context.view_layer.update()

def bounds(obj):
    pts=[obj.matrix_world@Vector(p) for p in obj.bound_box]
    return [[min(p[i] for p in pts) for i in range(3)],[max(p[i] for p in pts) for i in range(3)]]

hb,sb=bounds(high),bounds(source)
extent=max(hb[1][i]-hb[0][i] for i in range(3))
alignment=max(abs(hb[j][i]-sb[j][i]) for i in range(3) for j in range(2))
if alignment>extent*.015:raise ValueError(f'Bind-space bounds differ: {hb} versus {sb}; align explicitly first')
source_tris=sum(len(p.vertices)-2 for p in high.data.polygons)
bpy.ops.object.select_all(action='DESELECT');high.select_set(True);bpy.context.view_layer.objects.active=high
dec=high.modifiers.new('Original surface LOD','DECIMATE');dec.decimate_type='COLLAPSE'
dec.ratio=min(1,args.triangles/source_tris);dec.use_collapse_triangulate=True
bpy.ops.object.modifier_apply(modifier=dec.name)
for group in source.vertex_groups:high.vertex_groups.new(name=group.name)
transfer=high.modifiers.new('Transfer audited bind weights','DATA_TRANSFER')
transfer.object=source;transfer.use_vert_data=True;transfer.data_types_verts={'VGROUP_WEIGHTS'}
transfer.vert_mapping='POLYINTERP_NEAREST';transfer.layers_vgroup_select_src='ALL';transfer.layers_vgroup_select_dst='NAME'
bpy.ops.object.modifier_apply(modifier=transfer.name)
bpy.ops.object.vertex_group_limit_total(limit=4)
bpy.ops.object.vertex_group_normalize_all(lock_active=False)
world=high.matrix_world.copy();high.parent=rig;high.matrix_world=world
arm=high.modifiers.new('Character armature','ARMATURE');arm.object=rig
actual=sum(len(p.vertices)-2 for p in high.data.polygons)
empty=sum(not any(g.weight>0 for g in v.groups) for v in high.data.vertices)
if empty:raise ValueError(f'Unweighted vertices: {empty}')
rig.data.pose_position='POSE'
bpy.context.scene.frame_set(0);bpy.context.view_layer.update()
bpy.ops.object.select_all(action='DESELECT');high.select_set(True);rig.select_set(True)
args.out.parent.mkdir(parents=True,exist_ok=True)
bpy.ops.export_scene.gltf(filepath=str(args.out.resolve()),export_format='GLB',use_selection=True,
                         export_animations=True,export_animation_mode='ACTIONS',
                         export_skins=True,export_influence_nb=4,export_normals=True,export_tangents=True)
report={'high':str(args.high),'rigSource':str(args.rig),'output':str(args.out),
        'inputTriangles':source_tris,'outputTriangles':actual,'boundsHigh':hb,'boundsRig':sb,
        'boundsMaxDifference':alignment,'unweightedVertices':empty,'seconds':time.time()-started,
        'sha256':{k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in [('high',args.high),('rig',args.rig),('output',args.out)]},
        'status':'candidate_requires_deformation_and_appearance_review'}
args.out.with_suffix('.process.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
