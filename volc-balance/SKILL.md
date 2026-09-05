---
name: volc-balance
description: Volcengine (火山引擎) account utilities — check account balance via billing-center QueryBalanceAcct (现金/可用/冻结/欠费) without logging into the console, and list seed-tts speaker voices via ListSpeakers (filter by age/gender, with trial text/audio URLs) for casting characters. Use before running paid Volcengine pipelines (Seedance I2V, seed-tts/Seed-Audio, OmniHuman) to check funds, or when picking TTS voices.
---

# Volc Balance（火山引擎余额查询）

一条命令查火山引擎账户余额，不用登录控制台。项目里方舟 Seedance I2V、
语音 seed-tts/Seed-Audio、即梦 OmniHuman 都是按量付费，余额是账户级共享的，
跑批量管线前先查一下，避免跑到一半欠费停服。

## 用法

```bash
# 在 dula-story 目录下（凭证在 .env.cv，脚本会自动解析）
set -a && source .env.cv && set +a
.venv/Scripts/python.exe ../dula-skills/volc-balance/scripts/check_balance.py

# 或不 source —— 脚本会自动找 dula-story/.env.cv 解析凭证
dula-story/.venv/Scripts/python.exe dula-skills/volc-balance/scripts/check_balance.py

# 只输出原始 JSON（给其他脚本管道用）
.../check_balance.py --json
```

必须用装了 `volcengine` SDK 的解释器（`dula-story/.venv/Scripts/python.exe`）。
签名复用 SDK 的 `BillingService`（service=billing, region=cn-north-1），
脚本只追加了 SDK 未内置的 `QueryBalanceAcct`（GET，Version=2022-01-01）api_info。

## 权限前提

IAM 子用户（`VOLC_ACCESSKEY` / `VOLC_SECRETKEY`，存 `dula-story/.env.cv`）
除 CVFullAccess 等管线权限外，还需要费用中心只读权限：
去 console.volcengine.com/iam 给子用户加系统预设策略
**BillingCenterReadOnlyAccess**（费用中心全部只读，含账户总览的余额查询和
相关 OpenAPI；官方文档 https://docs.volcengine.com/docs/6269/1186807）。

## 输出字段

| 字段 | 说明 |
|------|------|
| `AvailableBalance` | 可用余额（现金 - 冻结，按量扣费从这里扣） |
| `CashBalance` | 现金余额 |
| `FreezeAmount` | 冻结金额（在途订单预扣） |
| `ArrearsBalance` | 欠费金额（>0 时脚本会打印欠费警告） |
| `CreditLimit` | 信控额度 |
| `AccountID` | 主账号 ID |

金额均为字符串形式，单位元（CNY）。

## 常见错误

| 现象 | 退出码 | 原因 / 处理 |
|------|--------|------------|
| `凭证缺失：环境变量 VOLC_ACCESSKEY/VOLC_SECRETKEY 未设置` | 2 | source `dula-story/.env.cv`，或确认文件存在且含这两个键 |
| `权限不足（AccessDenied: ... billing:QueryBalanceAcct ...）` | 3 | 子用户加 `BillingCenterReadOnlyAccess` 策略（见上节） |
| `凭证无效（InvalidAccessKeyId / SignatureDoesNotMatch ...）` | 1 | `.env.cv` 里的 AK/SK 过期或粘贴有误，重新生成 |
| `网络超时 / 网络错误` | 1 | 检查本机网络后重试 |
| `RecordNoFound / InternalError` 等费用中心业务错误 | 1 | 见官方错误码文档 https://www.volcengine.com/docs/6269/1223898 |

退出码约定：0 成功 / 2 凭证缺失 / 3 权限不足 / 1 其他错误。

## 附：seed-tts 音色列表工具（scripts/list_speakers.py）

调火山语音 `ListSpeakers`（Version=2025-05-20，service=speech_saas_prod，
region=cn-beijing，host=open.volcengineapi.com）拉音色库，自动翻页拉全
（seed-tts-2.0 实测 444 个音色，每页 100 共 5 页）。给角色选音色用。

```bash
cd dula-story
.venv/Scripts/python.exe ../dula-skills/volc-balance/scripts/list_speakers.py
# 筛选（打详情，含试听文本和试听链接）：
.../list_speakers.py --age 老年 --gender 男
# 原始 JSON（合并全部分页的音色数组）：
.../list_speakers.py --json
```

- `--age` / `--gender` 精确匹配返回字段（老年/中年/青年/儿童，男/女）。
- 不带筛选参数时打摘要行；带筛选时打详情块（描述、`Languages[0].Text`
  试听文本、`TrialURL` 试听音频直链，可直接下载试听）。
- 支持多情感的音色会标 `[多情感:生气,快乐,...]`。
- `--resource-id` 可切 `seed-tts-1.0`。
- 权限：凭证加载与退出码纪律同 check_balance.py；实测现有子用户
  （CVFullAccess + TOSFullAccess，余额查询授权后）可直接调用 ListSpeakers，
  **无需额外语音服务策略**。若遇 AccessDenied，去 IAM 控制台加语音技术
  相关读权限，策略名以控制台列表为准。

### 老周（河边钓鱼老爷爷）选音色实测（2026-09-06）

老年男声中文**只有 1 个**：`ICL_uranus_zh_male_youmodaye_tob`（幽默大爷 2.0，
矍铄沧桑的乐观爷爷，通透豁达又从容）——气质贴合"温暖沉稳"，**首选**，
先用它的 TrialURL 试听验收语气是否够"沉"。备选（中年男、描述偏沉稳）：

| VoiceType | 名称 | 描述要点 |
|-----------|------|---------|
| `ICL_uranus_zh_male_huzishushu_tob` | 胡子叔叔 2.0 | 历经风雨后变得沉稳的大叔，果敢可信赖，多情感 |
| `ICL_uranus_zh_male_shenmifashi_tob` | 神秘法师 2.0 | 低沉浑厚，满是慈爱，让人信赖 |
| `ICL_uranus_zh_male_ruyacaijun_tob` | 儒雅才俊 2.0 | 稳重儒雅大叔，温润平和 |
| `zh_male_tangseng_uranus_bigtts` | 唐僧 2.0 | 语调平缓慈悲（角色感太强，慎用） |

## 翻车记录

- 2026-09-06 ListSpeakers 实测：偶发 `CodeN 100016` 瞬时错误（疑似限流/
  服务抖动），重试即恢复；SDK 的 `.json()` 在非 2xx 时抛的是
  `Exception(bytes)`，错误解析要先 decode，否则 JSON 解析落空、错误提示
  被误分类（已在 list_speakers.py 中修复，check_balance.py 用的 `.get()`
  抛 str 不受影响）。
- 2026-09-14 首次接入实测：子用户只挂 CVFullAccess + TOSFullAccess 时
  `QueryBalanceAcct` 返回 `AccessDenied`（退出码 3，提示路径验证通过）。
  任务原始描述里写的策略名 `FinanceReadOnlyAccess` 在火山 IAM 并不存在，
  官方正确名称是 **BillingCenterReadOnlyAccess**（费用中心 → 权限管理文档确认）。
  加完策略后重跑即可。
- 2026-09-14 授权流程实测（用户操作）：IAM「添加权限」弹窗勾选策略后，
  **弹窗底部还有「提交」按钮，要下拉到弹窗底部才能看到**——只勾选不提交
  授权不生效（AccessDenied 依旧）。授权成功后输出示例：可用余额/现金余额/
  冻结金额/欠费金额/信控额度 五个字段 + 原始 JSON，欠费 >0 时打警告。
