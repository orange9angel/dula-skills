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
| `fighting-sfx` | 格斗音效生成 |
| `pixabay-downloader` | 音频素材下载 |

## 使用约定

- 每个 skill 目录含 `SKILL.md`（规范）+ `references/`（资料）+ `scripts/`（工具，可选）。
- 从 `dula-story` 调用脚本的路径形式：`python ../dula-skills/<skill>/scripts/<tool>.py ...`
- **翻车写回纪律**：任何生产事故/新发现，任务收尾时必须把教训写回对应 skill 的 references。
- 契约类文档（如 CharacterBase 契约）可能滞后于代码，动手前以源码为准。
