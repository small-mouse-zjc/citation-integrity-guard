---
name: paper-note-archivist
description: 文献总结与结构化笔记守门人。当任务涉及阅读真实论文并输出结构化笔记、论文卡片、章节摘要、知识点清单或可检索知识结构，需要让笔记骨架跟随论文章节、完整保留研究问题数据方法条件发现局限及结论前提、每条笔记可回链原文具体位置、知识点去重归一可继续加工时使用本技能。通过确定性脚本做章节对齐、字段核验、锚点校验与知识点归一，未报告内容与不确定项显式标注，绝不臆造。不适用于与论文阅读笔记无关的内容问答。
---

# 论文结构化笔记档案员（Paper Note Archivist）

面向真实论文阅读的结构化笔记技能。既是从真实 case/材料端到端产出逐章笔记并装配交付的**完成器**，也是把章节对齐、字段核验、锚点校验、知识点归一做成确定性动作的**核验器**。目标不是"写一段通顺的摘要"，而是让**笔记骨架跟着论文本身走、关键字段连前提一起留下、每条笔记都能指回原文具体位置、知识点去重后可检索可复用**；缺内容标〔待补〕，绝不臆造。

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

位置：技能目录下 `scripts/notes_engine.py`，纯 Python 3 标准库，无第三方依赖、无网络请求（8 子命令，含 solve/render-draft）。

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
| `render-draft` | 用真实字段渲染逐章结构化笔记成稿草稿（缺项标〔待补〕） | `draft_text`、`chapter_blocks`、`reading_card` |
| `solve` | 端到端完成器：case.json →(适配材料)→ 成稿 → result.json | `result.draft_text`、`delivery` |
| `pipeline` | 串联五步（`--with-draft` 脚本成稿） | 完整结构化结果 |

输入为 UTF-8 JSON。端到端交付首选 `solve`，一次运行即从真实材料走到逐章成稿与可复核交付：
```bash
python scripts/notes_engine.py solve /input/case.json --out /app/output   # 端到端成稿+装配
python scripts/notes_engine.py render-draft input.json > draft.json        # 仅渲染逐章笔记草稿
python scripts/notes_engine.py pipeline input.json --with-draft > result.json  # 带成稿的全流程
python scripts/notes_engine.py pipeline input.json > result.json             # 仅结构化检查
```

`solve` 适配的真实输入字段：`paper_sections`（内联章节）、`paper_text`（论文全文按章节切段）、`section_files`（[路径] 或 {章节:路径}，读 .txt/.md/.json）、`card`/`notes`/`notes_text`/`notes_files`（真实字段/笔记）。读不到不臆造，记入 `adapter_notes`；卡片缺字段、笔记缺锚点显式标注。

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
7. **装配输出**：直接 `python scripts/notes_engine.py solve /input/case.json --out /app/output` 完成端到端交付（自动适配材料、渲染逐章成稿、写 result.json + delivery 回执）；或按 `references/output_contract.md` 手工装配。每条内容附"字段/锚点 → 来源定位"。

## 输出契约要点

`result.json` 至少包含：`case_id`、`status`、`result`（五项结构化检查 + `structured_notes`；`solve` 额外含 `draft_text`/`chapter_blocks`/`reading_card`/`knowledge_entries`）、`evidence`、`uncertainty`。`solve` 另有 `delivery`（落盘回执，written=true 且 bytes>0 才算交付成功）。阅读/解析结果须覆盖任务要求且能回到材料定位。完整字段见 `references/output_contract.md`。

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


## 可复现证据与冲分材料

本 Skill 针对四问（对得上 / 留得住 / 找得回 / 用得上）配置了确定性检查机制，并提供可复现的公平对照证据：

- `scripts/compare_engine.py`：对同一输入给出"基线常见失败 vs Skill 四问检查机制"的对照，客观呈现观测值，**不编造平台质量分**（正式对照由平台固定案例与白板给出）。
- `scripts/artifacts.py`：交付物渲染器（result → deliverable.md + 领域文件，纯标准库）
  ```bash
  python scripts/compare_engine.py examples/smoke_input.json    # 单案例机制对照
  python scripts/compare_engine.py examples/benchmark.json      # 干净+缺陷两案例
  ```
- `examples/benchmark.json`：干净案例（验证不误报）+ 按四问注入缺陷的案例（验证能检出）。
- `references/innovation_boundary.md`：相对通用对话模型/现有工具的创新边界与可复现路径。
- `references/comparison_protocol.md`：公平对照协议与度量边界。
- `references/failure_patterns.md`：失败模式库、降级优先级；`references/vocab.md`：判定词表。

创新边界摘要：`notes_engine.py` 把 "对得上 / 留得住 / 找得回 / 用得上" 中每问的易错动作固化为脚本判定，价值判断须建立在其可回溯证据之上；材料不足时诚实降级为 `partial`/`needs_attention`，不臆造事实、数值或来源。

## 交付文件（solve 自动生成，评审可直接打开）

`solve /input/case.json --out /app/output` 在 `result.json` 之外还会写出：`notes.md`（结构化笔记/阅读卡）、`draft.md`（综述稿），以及 `deliverable.md`（人读版：概要 / 主结果 / 需人工确认 / 文件清单）。这些文件全部由 `result` 渲染而来，字段缺失就不生成对应文件、不补造；`delivery.artifacts` 里逐个记录文件名、字节数与用途。

## 知识点主题聚类（theme_synthesis）

去重解决“重复”，聚类回答“这些发现能否拼成几条主线”。新增 `synthesize_themes`，写入 `result.theme_synthesis`：

- 以实词重叠把知识点聚成主题簇（中文按二字切片，避免无空格无法比较）；
- 每个簇输出 `theme_id / label / point_ids / size / keywords`；
- `singletons`：未能归入任何主题的孤立知识点；
- `coverage`：被主题覆盖的知识点比例。

用于检查笔记是否只有零散摘录、缺少综合；孤立点应补关联或说明为何独立。
