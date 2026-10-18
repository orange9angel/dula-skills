# dula-skills

Dula 动画短片生成系统的 **AI 创作知识库**（第四层：知识层）。

本仓库与代码仓库分离、独立演进：

| 仓库 | 职责 |
|------|------|
| `dula-engine` | 纯净框架——怎么执行（渲染、音频、CLI） |
| `dula-assets` | 官方资产库——有什么（角色、动画、场景、运镜） |
| `dula-story` | 内容仓库——拍什么（剧本、配置、输出） |
| **`dula-skills`** | 创作知识——怎么创作（本仓库） |

## Skill 目录

| Skill | 用途 |
|-------|------|
| `story-writer` | 剧本创作规范（.story DSL、验证器） |
| `performance-director` | 表情/动作表演优化 |
| `scene-designer` | 场景设计与实现规范 |
| `character-modeler` | 程序化角色建模（Three.js 手绘 + sketch 手绘描边） |
| `f5-tts-voice` | 个性化配音生成 |
| `episode-scoring` | 语义化 BGM 生成 |
| `walk-director` | 走路/移动镜头：walk-cycle cel 选择、`walk_follow`+`motionGroup` 跟随运镜、时间线展开与抽帧验收 |
| `pixabay-downloader` | 音频素材下载 |

## 使用约定

### 本机 Codex 发现工程技能

正本仍留在本仓库；下载到新机器后运行一次：

```powershell
.\scripts\link-codex-skills.ps1 -StartupGuide
```

脚本将每个技能目录关联到用户的技能目录，并验证内容摘要；已有同目标关联会复用，
同名副本或其他 checkout 则报冲突而不覆盖。当前客户端若已有 `~/.codex/skills`，
继续使用该入口；新安装默认使用 `~/.agents/skills`，也可用 `-Destination` 指定。
`-StartupGuide` 只维护全局 `AGENTS.md` 内带标记的 Dula 指引，其他内容保留。
关联后下个会话应可发现；若客户端未刷新，重新启动会话。工程移动后需核对旧关联，
不要把旧副本当正本。新增技能后再跑一次脚本。

技能目录只提供名称和用途供选择，详细工艺仍需按任务读取；入口规则见
[Codex 官方说明](https://learn.chatgpt.com/docs/build-skills)。

- 每个 skill 目录含 `SKILL.md`（规范）+ `references/`（资料）+ `scripts/`（工具，可选）。
- 从 `dula-story` 调用脚本的路径形式：`python ../dula-skills/<skill>/scripts/<tool>.py ...`
- **翻车写回纪律**：任何生产事故/新发现，任务收尾时必须把教训写回对应 skill 的 references。
- 契约类文档（如 CharacterBase 契约）可能滞后于代码，动手前以源码为准。
