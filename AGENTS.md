# Dula 项目 AI 开发规范

本仓库是 Dula 动画短片生成系统的 **AI 创作知识库**（第四层）。整个工作区由四个独立 git 仓库组成：

| 仓库 | 职责 |
|------|------|
| `dula-engine/` | 纯净框架（渲染、音频执行、CLI）——怎么执行 |
| `dula-assets/` | 官方资产库（角色、动画、场景、运镜、配音）——有什么 |
| `dula-story/` | 内容仓库（剧本、配置、素材、输出）——拍什么 |
| `dula-skills/` | AI 创作知识库（本仓库）——怎么创作 |

## Skill 目录

```
dula-skills/
├── story-writer/        # 剧本创作规范（含导演工艺 directing-craft 与对抗式批评 pass）
├── series-architect/    # 系列长线架构（伏笔生命周期、信息不对称台账、季度节奏）
├── performance-director/# 表情/动作表演优化
├── scene-designer/      # 场景设计与实现规范
├── character-modeler/   # 程序化角色建模（Three.js 手绘 + sketch 描边 + 手部造型纪律）
├── cel-look/            # 三维做二维感：描边/boil/一拍二抽帧/赛璐璐阴影/脸部平面化
├── build-continuous-story-images/# 跨模型的连续分镜生图与角色锁定
├── direct-episode-audio/# 配音、环境音、音效、配乐的声音总导演
├── build-character-voice/# 语境化角色配音与逐句后期
├── build-ambience-foley/# 环境音、Foley 与事件音效
├── f5-tts-voice/        # 可选的 F5 个性化配音后端
├── episode-scoring/     # 剧情与画面驱动的 BGM
├── fighting-sfx/        # 格斗音效生成
├── walk-director/       # 走路/移动镜头：cel 选择、跟随运镜、时间线展开与验收
├── motion-transfer-video/# 动作迁移短视频（抖音素材下载 + seedance 多模态参考）
├── beatcut-edit/        # 音乐卡点剪辑（节奏检测 + 特效栈 + 表情卡点 + 变速）
├── promo-cut/           # 正片 → 15-30s 卡点广告片（选段 + 定格语法 + 字卡，直出 mp4）
├── map-transition-ad/   # 地图转场创意广告（陶阿狗君式：地图 UI + 巡城变装 + swipe 卡点 + 音频驱动开口）
├── previz-animatic/     # 零成本平面预演（flatpreviz 库用法 + 镜头表/口型/视差纪律）
├── pixabay-downloader/  # 音频素材下载
├── volc-balance/        # 火山引擎账户工具（余额查询 QueryBalanceAcct + seed-tts 音色列表 ListSpeakers）
├── volc-song-gen/       # 豆包音乐模型人声歌曲生成（GenSongForTime + 海外 IP 的 veFaaS 中转）
└── song-lipsync/        # 程序角色歌唱口型全链路（人声分离 + DTW 逐字对齐 + 起音锚定 + 拼音视素 + 防颤音包络）
```

AI 在开发时应直接阅读对应目录下的 `SKILL.md` 和 `references/` 资料。

## 常用工作流

### 创作新剧集

1. （连载系列）先阅读 `dula-skills/series-architect/SKILL.md`，检查系列圣经中的
   伏笔登记表与信息不对称台账，确定本集是质感集还是推进集、推进哪条线
2. 阅读 `dula-skills/story-writer/SKILL.md`
3. 在 `dula-story/episodes/` 下创建新目录
4. 编写 `script.story` 和 `bootstrap.js`
5. （可选）用 `performance-director` 优化表情和动作：
   ```bash
   cd dula-story
   python ../dula-skills/performance-director/scripts/run_director.py \
     ./episodes/<episode> \
     --output ./episodes/<episode>/script.story.perf
   ```
6. 运行验证：
   ```bash
   cd dula-story
   python ../dula-skills/story-writer/scripts/story_tool.py validate \
     --story ./episodes/<episode>/script.story \
     --episode-dir ./episodes/<episode>
   ```

### 设计场景

1. 阅读 `dula-skills/scene-designer/SKILL.md`
2. 编写 `config/scene_contract.json` 和 `scenes/<Scene>.js`
3. 运行验证：
   ```bash
   cd dula-story
   python ../dula-skills/scene-designer/scripts/scene_tool.py validate \
     --contract ./episodes/<episode>/config/scene_contract.json \
     --episode-dir ./episodes/<episode>
   ```

### 生成音频

```bash
cd dula-story
python ../dula-skills/direct-episode-audio/scripts/init_audio_direction.py \
  ./episodes/<episode>
# 人工/AI 完成 config/audio_direction.json 的语境导演审阅后：
python ../dula-skills/direct-episode-audio/scripts/validate_audio_direction.py \
  ./episodes/<episode>
python ../dula-skills/build-character-voice/scripts/compile_voice_direction.py \
  ./episodes/<episode> --force
python ../dula-skills/episode-scoring/scripts/run_scoring.py ./episodes/<episode>
python ../dula-engine/tools/generate_audio.py ./episodes/<episode>
```

### 生成连续分镜图

```bash
cd dula-story
python ../dula-skills/build-continuous-story-images/scripts/init_sequence.py \
  ./episodes/<episode> --sequence-id <sequence> \
  --reference ./episodes/<episode>/assets/character_reference.png \
  --shot "<动作阶段1>" --shot "<动作阶段2>" --shot "<动作阶段3>"
# 完成 config/image_sequences/<sequence>.json 的人物、场景、机位锁定后：
python ../dula-skills/build-continuous-story-images/scripts/validate_sequence.py \
  ./episodes/<episode>/config/image_sequences/<sequence>.json --strict
python ../dula-skills/build-continuous-story-images/scripts/build_generation_request.py \
  ./episodes/<episode>/config/image_sequences/<sequence>.json
```

### 渲染视频

```bash
cd dula-story
npx dula-verify ./episodes/<episode>
npx dula-render ./episodes/<episode>
```

## 重要约定

- 所有新增 skill 或开发规范统一放到 `dula-skills/`（本仓库），不要在其他仓库或根目录新建规范文档。
- **翻车写回纪律**：任何生产事故/新发现，任务收尾时必须把教训写回对应 skill 并提交。
- `script.story` 是唯一的时序数据源，所有配置标签的优先级：`.story` DSL > `config/choreography.json` > 硬编码默认值。
- 新增动画、场景、角色时，必须同时在 `bootstrap.js` 中注册，并通过 `story_tool.py catalog` 确认可用性。
- 验证通过前不要 claim 渲染就绪。
- **原创表述纪律**：所有文档、skill、prompt 中不出现第三方作品/作者名——
  参考与灵感只存在于讨论层，落盘必须用自己的表述（2026-09-05 已全库清理
  一轮；历史遗留 demo 目录名与资产标识符除外）。

## 历史说明

原 `.agents/skills/`、`dula-story/.agents/skills/`、`docs/skills/` 中的内容已合并迁移到本仓库。工作区根目录只放四个 git 仓库，不放任何文件；旧文档中的 `.agents/skills/`、`docs/skills/` 路径引用均已更新为 `dula-skills/`。
