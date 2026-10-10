"""init_viewer_episode.py — viewer 链新集脚手架（direct-animation-craft）。

从参照集（默认 bio_armor_academy_s1e3）把 viewer 链骨架复制到新集目录：
  原样复制：render.mjs（含 --check/--shots/--trace 基建）、viewer.html、
            bootstrap.js（注册入口模板）、tools/check_contact.py（薄包装）
  模板生成（带注释骨架，标明要填什么）：viewer.js、performance.js、
            config/timeline.json、config/contact_contract.json、
            config/review_shots.json、config/voice_config.json
  不复制：scenes/（场景是集专属）、assets3d/ storyboard/ output/（产物）、
          performance.js 原版、其它 tools（音频链按集再接）

验收接 episode_gate.py（同目录）。脚手架本身不渲染。

用法：
  python init_viewer_episode.py <new_episode_dir> [--reference <ref_episode_dir>]
  python init_viewer_episode.py <new_episode_dir> --smoke   # 生成后自查（node --check + JSON 合法）
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_REF = HERE.parents[2] / 'dula-story/episodes/bio_armor_academy_s1e3'

COPY_FILES = ['render.mjs', 'viewer.html', 'bootstrap.js', 'tools/check_contact.py']

VIEWER_JS = """// TODO(集名)：viewer 链主循环骨架——参照 bio_armor_academy_s1e3/viewer.js 填：
// 场景（scenes/）、角色、道具状态机、contact 探针日志（contact/locomotion/worn 契约见
// dula-skills/direct-animation-craft/references/physics-gate.md）。
// window 契约（render.mjs 依赖）：duration / checkTimes / renderAt / stepAt / setFreeCamera / ready。
import * as THREE from 'three';
const q=new URLSearchParams(location.search);
const TL=await fetch('./config/timeline.json').then(r=>r.json());
window.duration=TL.duration;
const renderer=new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});
renderer.setSize(1280,720);renderer.outputColorSpace=THREE.SRGBColorSpace;
const canvas=document.createElement('canvas');canvas.width=1280;canvas.height=720;document.body.append(canvas);
const ctx=canvas.getContext('2d');
const camera=new THREE.PerspectiveCamera(44,1280/720,.05,200);
const scene=new THREE.Scene(); // TODO: new XxxScene();scene.add(...) + 角色
scene.add(new THREE.Mesh(new THREE.PlaneGeometry(40,40).rotateX(-Math.PI/2),
  new THREE.MeshToonMaterial({color:'#888880'}))); // 占位地面，接场景后删
scene.add(new THREE.DirectionalLight(0xffffff,2.4));scene.add(new THREE.AmbientLight(0xbfd4e6,.9));
function draw(t,capture=true){
  // TODO: performance.poseAt 驱动角色 + props/secondary；探针 state 按契约组装
  camera.position.set(0,2.2,6);camera.lookAt(0,1,0);
  if(window.freeCamera){const c=window.freeCamera;camera.position.set(...c.pos);camera.lookAt(...c.look);
    camera.fov=c.fov??44;camera.updateProjectionMatrix();}
  const state={t}; // TODO: contact/locomotion/worn 探针键
  if(!capture)return state;
  renderer.render(scene,camera);
  ctx.clearRect(0,0,1280,720);ctx.drawImage(renderer.domElement,0,0);
  return {image:canvas.toDataURL('image/jpeg',.93).split(',')[1],state};
}
window.renderAt=t=>draw(t);window.stepAt=t=>draw(t,false);
window.setFreeCamera=c=>window.freeCamera=c;
// checkTimes=check 模式抽帧表：TODO 按时间轴关键点填（条目始末/交互事件帧）
window.checkTimes=TL.segments.flatMap(s=>[s.start+.15,(s.start+s.end)/2]).filter(t=>t<TL.duration);
window.ready=true;
"""

PERFORMANCE_JS = """// TODO(集名)：表演谱骨架——(t,state) 纯函数、seek 一致是铁律（参照
// bio_armor_academy_s1e3/performance.js：条目→角色 phase 映射、关键点插值 key()、
// 道具状态机派生姿势、walkingFeet 有限落脚）。
// 每个节拍先按 physical-completeness.md 的矩阵声明断言，再写姿势。
export const clamp=x=>Math.max(0,Math.min(1,x)),ease=x=>{x=clamp(x);return x*x*(3-2*x);};
export function poseAt(entries,t){
  const entry=entries.findLast(e=>e.startTime<=t)??entries[0];
  // TODO: 逐角色 buildPose（twoBone IK / 步态 / 手势库 gL gR）
  return {entry,opts:entry.opts};
}
"""

TIMELINE = {
    "duration": 10.0, "step": 0.01,
    "segments": [
        {"id": "establish", "kind": "action", "character": None, "start": 0.0, "end": 3.0,
         "move": "establish", "shot": "establish"},
        {"id": "beat_1", "kind": "dialogue", "character": "TODO", "start": 3.0, "end": 10.0,
         "move": "TODO", "shot": "two"},
    ],
    "_comment": "TODO: 唯一时序数据源；每个道具交互事件同步在 review_shots.json 加近景组",
}

CONTRACT = {
    "scope": "TODO: 障碍物/主体/采样率声明",
    "fps_min": 30, "pose_tick_hz": 15,
    "env": {"state_key": "env", "frame_min": 100,
            "comment": "TODO: 环境净空（铁丝网/墙薄板代理），任何命中即失败；按矩阵补 doorway/whitelist/gait 等段"},
    "_matrix": "dula-skills/direct-animation-craft/references/physical-completeness.md 的类目×节拍矩阵",
}

REVIEW_SHOTS = [
    {"name": "01_example_event_close", "t": 1.0, "camera": [0, 1.4, 2.2, 0, 1.0, 0, 36],
     "_comment": "TODO: 每个道具交互事件 2-3 机位（特写+侧写）；过五点清单：掌向/接触/支撑/连接/穿戴件"},
]

VOICE_CONFIG = {"TODO_Character": {"voice": "TODO", "rate": "+0%", "pitch": "+0Hz"}}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('target', type=Path)
    ap.add_argument('--reference', type=Path, default=DEFAULT_REF)
    ap.add_argument('--smoke', action='store_true', help='生成后自查：node --check + JSON 合法性')
    args = ap.parse_args()
    ref, tgt = args.reference.resolve(), args.target.resolve()
    if tgt.exists() and any(tgt.iterdir()):
        print(f'target not empty: {tgt}')
        sys.exit(2)
    for rel in COPY_FILES:
        src = ref / rel
        if not src.exists():
            print(f'reference missing {rel}')
            sys.exit(2)
        out = tgt / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(src.read_bytes())
        print(f'  copy  {rel}')
    for rel, text in [('viewer.js', VIEWER_JS), ('performance.js', PERFORMANCE_JS)]:
        (tgt / rel).write_text(text, encoding='utf-8')
        print(f'  tmpl  {rel}')
    for rel, data in [('config/timeline.json', TIMELINE), ('config/contact_contract.json', CONTRACT),
                      ('config/review_shots.json', REVIEW_SHOTS), ('config/voice_config.json', VOICE_CONFIG)]:
        out = tgt / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        print(f'  tmpl  {rel}')
    print(f'scaffold -> {tgt}')
    print('下一步：按 config/contact_contract.json 的矩阵注记铺断言 → episode_gate.py 验收')

    if args.smoke:
        ok = True
        for rel in ['render.mjs', 'viewer.js', 'performance.js', 'bootstrap.js']:
            p = subprocess.run(['node', '--check', str(tgt / rel)], capture_output=True, text=True)
            ok &= p.returncode == 0
            print(f'  node --check {rel}: {"OK" if p.returncode == 0 else p.stderr.strip()[:200]}')
        for rel in ['config/timeline.json', 'config/contact_contract.json',
                    'config/review_shots.json', 'config/voice_config.json']:
            try:
                json.loads((tgt / rel).read_text(encoding='utf-8'))
                print(f'  json {rel}: OK')
            except Exception as e:
                ok = False
                print(f'  json {rel}: FAIL {e}')
        print('smoke', 'OK' if ok else 'FAIL')
        sys.exit(0 if ok else 2)


if __name__ == '__main__':
    main()
