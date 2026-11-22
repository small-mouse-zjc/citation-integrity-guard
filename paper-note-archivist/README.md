# paper-note-archivist · 论文结构化笔记档案员

一个面向真实论文阅读的可调用 Skill。既是从真实 case/材料端到端产出逐章结构化笔记并装配 result.json 的**完成器**，也是把章节对齐、字段化整理、锚点回链、知识点归一四件事做成可运行、可复核、可回溯确定性流程的**核验器**。缺内容标〔待补〕，绝不臆造。

## 解决什么问题

论文笔记的四个高频失败：
- **对不上**：套通用摘要模板，笔记骨架跟论文本身章节错位；
- **留不住**：漏记关键字段，尤其漏掉"让结论成立的前提条件"；
- **找不回**：笔记只给笼统出处，指不回原文具体位置；
- **用不上**：知识点重复、术语缩写混乱、无法检索复用。

本 Skill 用 `scripts/notes_engine.py` 把四个动作做成确定性计算。

## 目录结构

```
paper-note-archivist/
├── SKILL.md                       # 技能主文件（平台加载）
├── README.md                      # 本文件
├── GITHUB_URL.txt                 # 公开仓库链接（本题 +5 分）
├── scripts/
│   └── notes_engine.py            # 纯标准库确定性引擎（8 子命令，含 solve/render-draft）
├── references/
│   ├── field_dictionary.md        # 字段字典与结论前提
│   ├── anchor_format.md           # 锚点格式规范
│   ├── knowledge_rules.md         # 知识点归一规则
│   └── output_contract.md         # 输出字段定义
└── examples/
    ├── minimal_example.md         # 最小调用示例
    ├── selftest.py                # 51 项自验收（含成稿/适配/solve）
    ├── smoke_input.json           # 冒烟输入
    └── smoke_output.json          # 冒烟输出
```

## 运行环境

- Python 3.8+，仅标准库，无第三方依赖、无网络请求。
- 验证：`python scripts/notes_engine.py --help`

## 快速开始

```bash
python scripts/notes_engine.py --help
python scripts/notes_engine.py check-section-alignment '{"paper_sections":["摘要","方法"],"note_sections":["摘要","方法"]}'
python scripts/notes_engine.py solve /input/case.json --out /app/output   # 端到端成稿+装配
python scripts/notes_engine.py render-draft examples/smoke_input.json > draft.json
python scripts/notes_engine.py pipeline examples/smoke_input.json --with-draft > result.json
python examples/selftest.py
```

## 四个能力对应子命令

| 核心问题 | 子命令 | 产出 |
|---------|--------|------|
| 对得上 | `check-section-alignment` | 章节顺序对齐检查 |
| 留得住 | `check-card-fields` + `build-reading-card` | 字段完整性 + 统一卡片 |
| 找得回 | `verify-anchors` | 锚点回链校验 |
| 用得上 | `normalize-knowledge` | 知识点去重归一 |

## 设计原则

- 确定性动作用脚本；价值判断（笔记忠实、锚点对应）留给 Agent 但必须给证据定位。
- 未报告内容、中英同义、低相似归一一律显式标注，不臆造、不误并。
- 与 `intro-gap-architect`、`methods-repro-guard`、`citation-integrity` 互补，串联覆盖"读→写"全流程。

## 适用与限制

- 适用：中英文论文的结构化阅读笔记，可跨学科。
- 限制：脚本只做结构与格式校验，不做语义忠实判定；PDF 解析须读真实文件；不生成预制答案。

## 提交注意

本题有 **GitHub 公开作品链接 +5 分**。`GITHUB_URL.txt` 第一行须写公开仓库链接，评审免登录可打开方得分。

## 许可与复用

规则文档、字段模板、测试题集均可复用；引用请标注来源仓库（见 GITHUB_URL.txt）。


## 冲分证据（可复现）

- 四问：对得上 / 留得住 / 找得回 / 用得上
- 公平对照：`python scripts/compare_engine.py examples/benchmark.json`（clean 验证不误报，defect 验证能检出，可复现）。
- 只度量 Skill 检查机制的可运行证据，不编造平台质量分；真实对照由平台给出。
- 自验收：`python examples/selftest.py`（含对照可复现验证）。
