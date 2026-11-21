# intro-gap-architect · 引言与相关工作架构师

一个面向学术论文"引言 + 相关工作"环节的可调用 Skill。把空转铺垫检测、相关工作分组比较、研究空白推导、贡献—证据对齐四件事，从模型的自由发挥变成可运行、可复核、可回溯的确定性流程。

## 解决什么问题

引言写作的四个高频失败：
- **背景空转**："近年来受到广泛关注"式的万能开头，不指向具体问题；
- **相关工作流水账**：逐篇摘要拼接，没有统一比较维度；
- **空白凭空断言**：没说清空白从哪些文献的什么缺口推出；
- **贡献夸大/悬空**：贡献条目在正文找不到对应方法、图表或实验证据。

本 Skill 用 `scripts/intro_engine.py` 把这四个动作做成确定性计算，价值判断给出可回溯依据。

## 目录结构

```
intro-gap-architect/
├── SKILL.md                       # 技能主文件（平台加载）
├── README.md                      # 本文件
├── GITHUB_URL.txt                 # 公开仓库链接（第一行）
├── scripts/
│   └── intro_engine.py            # 纯标准库确定性引擎（9 子命令）
├── references/
│   ├── grouping_templates.md      # 相关工作分组维度模板
│   ├── gap_patterns.md            # 四类空白模式判据与误判
│   ├── claim_alignment.md         # 贡献对齐规则与夸大词表
│   ├── output_contract.md         # 输出字段定义
│   ├── innovation_boundary.md     # 相对通用模型/文献工具的创新边界
│   ├── comparison_protocol.md     # 公平对照协议与增益度量边界
│   └── failure_patterns.md        # 12 类失败模式与降级优先级
└── examples/
    ├── minimal_example.md         # 最小调用示例
    ├── selftest.py                # 33 项自验收
    ├── benchmark.json             # 3 个跨学科公平对照案例
    ├── smoke_input.json           # 冒烟输入
    └── smoke_output.json          # 冒烟输出
```

## 九个引擎子命令

`detect-hype`（立得住，按句切分）、`group-matrix`（分得清）、`derive-gap`（说得实）、`align-claims`（对得上）、`coverage`（引用覆盖）、`ingest`（BibTeX/RIS 解析）、`compose`（成稿骨架+来源映射）、`compare`（公平对照证据）、`pipeline`（端到端，`--compact` 省 token）。

## 运行环境

- Python 3.8+，仅标准库，无第三方依赖、无网络请求。
- 验证：`python scripts/intro_engine.py --help`

## 快速开始

```bash
# 1. 看命令
python scripts/intro_engine.py --help

# 2. 单步：检测背景是否立得住
python scripts/intro_engine.py detect-hype "近年来受到广泛关注[1]，但标注成本高。"

# 3. 端到端（推荐）：pipeline
python scripts/intro_engine.py pipeline examples/smoke_input.json > result.json
python scripts/intro_engine.py pipeline examples/smoke_input.json --compact > brief.json  # 省 token

# 4. 成稿骨架 + 公平对照证据
python scripts/intro_engine.py compose  examples/smoke_input.json > draft.json
python scripts/intro_engine.py compare  examples/smoke_input.json > comparison.json

# 5. 自验收（33 项）+ 三案例 benchmark
python examples/selftest.py
```

`pipeline` 输入结构见 `SKILL.md` 与 `references/output_contract.md`。真实案例须读取平台提供的 `/input/case.json` 与事实底稿，解析为结构后运行，不得用预制答案。

## 四个能力对应四个子命令

| 核心问题 | 子命令 | 产出 |
|---------|--------|------|
| 立得住 | `detect-hype` | 空转句清单 + 是否立得住 |
| 分得清 | `group-matrix` | 分组比较矩阵（同维度横向视图） |
| 说得实 | `derive-gap` | 可解释空白推导链（附支撑文献） |
| 对得上 | `align-claims` + `coverage` | 贡献对齐结果 + 引用覆盖检查 |

## 冲分设计（对照评分表）

| 评分维度 | 本 Skill 的对应机制 |
|---|---|
| 实际效果 40 | 四问全覆盖 + 门禁；`compose` 产出可直接填写的成稿骨架与来源映射 |
| 使用增益 25 | `compare` 提供公平对照的确定性缺陷检出/拦截证据；`--compact` 省额度 |
| 创新增益 15 | `references/innovation_boundary.md` 论证相对通用模型/文献工具的边界；按句切分修复是真实方法改进 |
| 可靠体验 10 | 中英双语规则、跨学科可配维度、12 类失败模式降级处置 |
| 生态贡献 10 | 完整文档 + 3 案例 benchmark + 33 项自测 + 失败库，均可复用 |

对照只度量可复现的"缺陷检出/拦截计数"，不编造平台质量分；真实对照由平台固定案例与白板给出（见 `references/comparison_protocol.md`）。

## 设计原则

- 确定性动作用脚本；价值判断（转述忠实、空白成立、元数据真实）留给 Agent 但必须给证据定位。
- 材料不足、字段缺失、空白无据一律显式标注，不臆造文献/贡献/对照结果。
- 与 `citation-integrity` 互补：本 Skill 管引言结构与证据绑定，后者管引用编号/去重/格式。

## 适用与限制

- 适用：中英文引言/相关工作写作，可跨学科（维度可配）。
- 限制：不做文献真实性外部核验（需 DOI/原文比对）；空白推导基于关键词与结构，语义须人工确认；不生成预制答案。

## 许可与复用

规则文档、模板、测试题集均可复用；引用请标注来源仓库（见 GITHUB_URL.txt）。
