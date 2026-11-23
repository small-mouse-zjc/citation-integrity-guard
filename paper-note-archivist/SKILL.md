---
name: paper-note-archivist
description: 文献总结与结构化笔记守门人。当任务涉及阅读真实论文并输出结构化笔记、论文卡片、章节摘要、知识点清单或可检索知识结构，需要让笔记骨架跟随论文章节、完整保留研究问题数据方法条件发现局限及结论前提、每条笔记可回链原文具体位置、知识点去重归一可继续加工时使用本技能。通过确定性脚本做章节对齐、字段核验、锚点校验与知识点归一，未报告内容与不确定项显式标注，绝不臆造。不适用于与论文阅读笔记无关的内容问答。
---

# 论文结构化笔记档案员（Paper Note Archivist）

面向真实论文阅读的结构化笔记技能。目标不是"写一段通顺的摘要"，而是让**笔记骨架跟着论文本身走、关键字段连前提一起留下、每条笔记都能指回原文具体位置、知识点去重后可检索可复用**。

围绕题面四个核心问题组织能力：

| 核心问题 | 含义 | 对应工具 |
|---------|------|---------|
| 对得上 | 笔记骨架跟随论文自身章节与论证顺序 | `check-section-alignment` |
| 留得住 | 问题/数据/方法条件/发现/局限/结论前提都记录 | `check-card-fields` + `build-reading-card` |
| 找得回 | 每条关键笔记指回原文页码/章节/图表 | `verify-anchors` |
| 用得上 | 知识点去重归一、可检索、可比较、可继续加工 | `normalize-knowledge` |

## 何时触发 / 何时不触发

**触发**：任务中出现以下任一信号——
- 让读论文出笔记、做论文卡片、按章节总结、提取知识点清单、构建可检索笔记；
- 抱怨"笔记像通篇摘要/跟论文章节对不上/找不到出处/知识点重复矛盾/结论前提没记"；
- 要求笔记保留原文定位、要求字段化并排比较、要求术语缩写归一；
- 要求标注未报告项与材料冲突。

**不触发**：与论文阅读笔记无关的内容问答、纯翻译。被误触发时说明并保持原文不变。

## 核心原则（贯穿所有动作）

1. **骨架随论文**：笔记按论文自身章节与论证顺序组织，不套通用摘要模板。章节承接关系要保留。
2. **前提必留**：记录研究问题、数据、方法条件、主要发现、局限，**尤其记录让结论成立的前提条件**（"仅在X条件下成立"）——没有前提的结论不可复用。
3. **锚点可回链**：每条关键笔记带具体锚点（页码/章节/图表/段落），粒度与可核验性匹配。正文顺带提"见图3"不算独立锚点。
4. **保守归一**：知识点去重时，高相似可合并；中英同义（CNN/卷积神经网络）**不自动合并**，只打标记交人工确认，避免误并不同概念。
5. **诚实标注**：未报告、无法判断、材料冲突、锚点悬空一律写入 `uncertainty` / `not_reported`，绝不臆造内容或锚点。
6. **不交预制答案**：本技能处理平台给定案例，不得用预写好的笔记或答案替代实际运行。
7. **确定性动作交给脚本**：章节对齐、字段核验、锚点校验、知识点归一必须用 `scripts/notes_engine.py` 实际运行，不靠模型心算。

## 工具：notes_engine.py

位置：技能目录下 `scripts/notes_engine.py`，纯 Python 3 标准库，无第三方依赖、无网络请求。

先确认可运行：
```bash
python scripts/notes_engine.py --help
```

### 子命令

| 子命令 | 作用 | 关键输出 |
|--------|------|---------|
| `check-section-alignment` | 对得上：章节顺序对齐 | `order_consistent`、`missing_sections`、`inversions` |
| `check-card-fields` | 留得住：字段完整性 | `fields`、`missing`、`complete` |
| `verify-anchors` | 找得回：锚点回链校验 | `anchored_count`、`no_anchor`、`bad_anchor` |
| `normalize-knowledge` | 用得上：知识点去重归一 | `entries`、`merges`、`needs_review` |
| `build-reading-card` | 生成统一论文卡片 | `card`（含 not_reported）、`comparable` |
| `pipeline` | 串联五步 | 完整结构化结果 |

输入为 UTF-8 JSON。推荐一次跑完：
```bash
python scripts/notes_engine.py pipeline input.json --outdir /app/output > result.json
```

`input.json` 结构：
```json
{
  "case_id": "案例标识",
  "paper_sections": ["摘要", "引言", "方法", "结果", "结论"],
  "note_sections": ["摘要", "引言", "方法", "结果", "结论"],
  "card": {
    "question": "研究问题", "data": "数据集与规模", "method_conditions": "方法与条件",
    "findings": "主要发现", "limitations": "局限", "premises": "结论成立前提"
  },
  "notes": [
    {"id":"n1","text":"笔记内容","anchor":"第5页"}
  ],
  "valid_anchors": ["第5页", "§3.2", "图2"],
  "knowledge_points": [
    {"label":"知识点","definition":"定义","anchor":"§2","type":"concept"}
  ],
  "required_fields": ["question","data","method_conditions","findings","limitations","premises"],
  "dup_threshold": 0.72
}
```

字段说明见 `references/output_contract.md`。真实案例若给的是 PDF，须**读取真实 PDF 全文**（PDF 解析无预抽取答案层，不要从题名或标签臆测内容），识别章节、抽取字段、记录锚点后再运行脚本。

## 标准工作流

接到任务后按此顺序执行，每步保留证据：

1. **读输入**：读取 `/input/case.json` 与 `task.md`，确认 `case_id`、论文材料、任务口径与证据范围。**如实读真实文件。**
2. **对得上**：识别论文本身章节顺序，运行 `check-section-alignment`。按 `missing_sections` / `inversions` 调整笔记骨架，使其与论文结构一致。
3. **留得住**：抽取研究问题/数据/方法条件/发现/局限/结论前提，运行 `check-card-fields` 与 `build-reading-card`。`missing` 字段回原文找；原文确实未报告的标为 `not_reported`，不臆造。**特别核查"结论前提"是否被记录。**
4. **找得回**：为每条关键笔记配原文锚点，运行 `verify-anchors`。`no_anchor` / `bad_anchor` 逐条补正——锚点要指到具体页码/章节/图表，不能只写"见原文"。
5. **用得上**：抽取知识点，运行 `normalize-knowledge`。`merges` 中高相似项合并；`needs_review`（中英同义、低相似）交人工确认，不自动并。
6. **撰写成稿**：基于结构化结果输出可编辑笔记（按论文章节组织 + 论文卡片 + 知识点清单 + 锚点）。每条关键结论后附锚点，未报告项显式标注。
7. **装配输出**：按 `references/output_contract.md` 写入 `/app/output/result.json`，保留 `case_id` 与全部字段；笔记成稿另存为文件。每条内容附"字段/锚点 → 来源定位"。

## 输出契约要点

`result.json` 至少包含：`case_id`、`status`（`ok`/`needs_attention`/`partial`）、`result`（五项结构化检查 + `structured_notes` + `notes_metrics` + 可选 `artifacts`）、`evidence`（四原则落实 + 缺锚点/坏锚点/知识点合并）、`uncertainty`（未报告字段 + 待确认归一 + 价值判断说明）。阅读/解析结果须覆盖任务要求且能回到材料定位。**`structured_notes` 是主产物，必须由 Agent 逐节读完原文后写成完整、可回链的笔记（正文合计不少于 200 字符）；只交检查表或空 notes，`status` 直接是 `partial`。** `pipeline --outdir /app/output` 会真实写出 `structured_notes.md` 与 `reading_card.json`。完整字段见 `references/output_contract.md`。

## 异常处理

| 情形 | 处置 |
|------|------|
| 扫描件/PDF解析失败 | 记录原因，产出 partial，不臆测内容 |
| 加密或权限受限文档 | 标注无法访问，交人工接管 |
| 双栏错序 | 按章节标题重排，不按文本流顺序 |
| 图表公式缺失 | 对应字段标 not_reported，说明材料缺口 |
| 超长文 | 分章处理，逐章对齐与抽锚点 |
| 非中文论文 | 章节/字段关键词中英文规则均生效 |
| 材料冲突 | 写入 uncertainty，列明冲突位置，不擅选 |

## 复用与扩展

- `references/field_dictionary.md`：论文卡片字段字典与"结论前提"抽取要点；
- `references/anchor_format.md`：锚点格式规范与粒度选择；
- `references/knowledge_rules.md`：知识点归一规则与中英同义处理；
- `references/output_contract.md`：输出字段定义与示例；
- `examples/`：最小调用示例与 23 项自验收（`python examples/selftest.py`）。

本技能与 `intro-gap-architect`（引言与相关工作）、`methods-repro-guard`（方法实验）、`citation-integrity`（引用一致性）互补：分别管论文阅读笔记、引言、方法、引用，可串联覆盖"读→写"全流程。

**注意**：本题提交需附 GitHub 公开作品链接（额外 5 分）。提交前在 `GITHUB_URL.txt` 第一行写公开仓库链接，并用未登录浏览器确认可打开。


## 交付前自检（必须）

```bash
python scripts/validate_result.py --result /app/output/result.json --outdir /app/output --case /input/case.json --main-field structured_notes
```

`valid=false` 时按 errors 修；`result.structured_notes` 为空、顶层缺 `case_id/status/result/evidence/uncertainty`、或声明的产物路径不存在，都不得声称完成。

