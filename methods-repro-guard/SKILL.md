---
name: methods-repro-guard
description: 方法与实验章节写作与复现守门。当任务要求把散落的实验记录、配置、日志、代码与数据说明整理成可执行、可复现的方法与实验章节，并核对步骤、设置、参数、数据集、对照、限制时使用。Agent 先读真实材料并写出完整章节，再用脚本核对六要素、数值来源、复现清单、参数表与缺口追问；不补造数值、不代作者回答缺口。
---

# 方法与实验：可执行、可复现（Methods & Experiments Guard）

交付**能直接进入论文的方法与实验章节**，不是检查报告。章节要写得全、写得准、做得着、说得住：读者能按步骤复做，参数与配置/日志一致，缺口显式交作者。

| 题面四问 | 成稿要求 | 工具 |
|---|---|---|
| 写得全 | 步骤/设置/参数/数据/对照/复现限制六类要素齐全 | `check-completeness` |
| 写得准 | 参数值、版本、划分、条件与配置/日志/代码一致 | `verify-values` + `build-param-table` |
| 做得着 | 复现清单含代码版本、环境、种子、命令、数据获取 | `check-reproducibility` |
| 说得住 | 缺口显式追问，限制落到具体失效场景 | `probe-gaps` |

## 何时触发 / 不触发

**触发**：写/改方法、实验设置、实验步骤、参数表、数据集与划分、对照实验、复现清单、限制条件。

**不触发**：纯文献综述、引言写作、纯语言润色。误触发时说明边界，保持原文不变。

## 铁律

1. **Agent 主写**：`method_experiment_draft` 必须由你写成完整章节；不要只交 `pipeline` 的检查结果，也不要让脚本代写。
2. **不补造数值**：每个数值必须能在 case 的配置/日志/代码/表格中找到来源；找不到就标 `[待核实]`，不为了通顺补。
3. **条件不串台**：训练/验证/测试、不同数据集、不同基线的条件分开写；同一数值只在同一条件下比较。
4. **缺口交作者**：材料缺失、配置冲突、版本不明、参数无来源，写入 `uncertainty.open_questions` / `needs_author_confirmation`，不代答。
5. **限制要具体**：不写“方法还有一些不足”；写清“在何种数据/尺度/条件/预算下失效或未验证”。

## 标准工作流

### 1. 读真实材料

```bash
python scripts/case_io.py /input/case.json --out /app/work/case_texts.json
```

读 `case_texts.json`：确认 `case_id`、任务口径、材料形态（PDF/docx/配置/日志/代码/数据说明）、目标章节范围与输出契约。

逐一打开真实文件，**不要根据文件名猜内容**。把材料分成：
- 实验步骤/流程记录；
- 配置（超参、硬件、软件版本、随机种子）；
- 日志（训练/评测指标、轮次、异常）；
- 代码（数据划分、预处理、模型/训练入口、命令）；
- 数据说明（名称、版本、规模、划分、用途）；
- 对照/基线（对象、版本、预算、指标、统计方式）。

### 2. 建事实表（先于写作）

在 `/app/work/facts.json` 记录：
- `steps`：每步输入/操作/输出/判断条件；
- `params`：名称、取值、单位、作用对象、来源（文件:行/字段）；
- `datasets`：名称、版本、规模、预处理、划分比例与随机方式、各子集用途；
- `baselines`：对象、版本、对照条件、指标、重复次数；
- `repro`：代码版本、环境、依赖、种子、命令、数据获取；
- `gaps`：材料没有或冲突的项，标 `source=author_confirmation`。

**数值原样保留**，不四舍五入、不换算单位（除非材料明确给换算）。

### 3. 写完整章节（核心）

写 `/app/work/method_experiment_draft.md`，按以下结构（可按学科调整标题，但要素不能少）：

```markdown
# 方法

## 3.1 总体流程
（一段总览：输入→处理→模型/实验→输出；点明与本文贡献的对应）

## 3.2 步骤
1. **数据读取与预处理**：输入…；操作…；输出…；判断条件…
2. **划分**：训练/验证/测试比例…；随机方式…；各子集用途…
3. **模型/实验设置**：结构/参数…；硬件/软件…；种子/重复…
4. **训练/评测**：轮次…；指标…；早停/选择准则…
（每步都要有输入、操作、输出、条件，不把多步压成一句）

## 3.3 参数
（表格：名称 | 取值 | 单位 | 作用对象 | 来源；正文数值与表一致）

## 3.4 数据集与划分
（名称、版本、规模、预处理、划分、用途；版本/随机方式必须写）

## 3.5 对照与评价
（基线对象+版本；是否同预算/同划分；指标与统计方式；重复次数）

## 3.6 复现与限制
（代码版本、环境、依赖、种子、命令、数据获取；限制落到具体失效场景）
```

写作要求：
- 步骤有序、可执行；每步写清输入/操作/输出/判断条件；
- 训练、验证、测试分开；不同实验条件不混写；
- 参数表与正文数值一致；单位、有效数字统一；
- 对照写“同划分/同预算/同指标”，否则明确“不可直接比较”；
- 限制写“在 X 数据/尺度/预算下未验证”，不写套话；
- 材料没有的数值不编，写 `[待核实]` 并列入 gaps。

### 4. 脚本核验（不代替写作）

```bash
python scripts/methods_engine.py pipeline /app/work/pipeline_input.json \
  --draft-file /app/work/method_experiment_draft.md > /app/work/checks.json
```

`pipeline_input.json` 至少：

```json
{
  "case_id": "案例标识",
  "section_text": "从成稿中复制的正文（或事实表中的章节摘要）",
  "sources": {"config.yaml": "lr: 0.001\nseed: 42", "train.log": "epoch 100 acc 0.95"},
  "params": [{"name":"学习率","value":0.001,"unit":"","scope":"优化器","source":"config.yaml"}],
  "gaps": [{"field":"数据集版本","reason":"材料未给出","source":"author_confirmation"}],
  "limitations": ["在少样本条件下未验证"],
  "open_questions": ["基线版本是否与本文对齐？"],
  "required_elements": ["steps","setup","params","data","baseline","repro_limit"],
  "required_repro": ["code_version","env","seed","command","data_access","split_detail"]
}
```

看 `checks.json`：
- `completeness.missing`：缺哪类要素 → 回成稿补写，不是只记录；
- `value_verification.unsupported`：数值在来源找不到 → 回原文核对，确属补造则删/改真值；
- `parameter_table.missing_source`：参数无来源 → 标 `[待核实]` 或补来源；
- `reproducibility.missing`：复现项缺 → 能补则补，不能补写原因；
- `gap_probe.generic_limitations`：套话限制 → 改成具体失效场景。

**`method_experiment_draft` 少于 200 字符时 pipeline 会判 partial**：这表示你没有写章节，必须先完成第 3 步。

### 5. 装配输出

写 `/app/output/result.json`：

```json
{
  "case_id": "与输入一致",
  "status": "success | needs_attention | partial",
  "result": {
    "method_experiment_draft": "完整章节全文",
    "draft_metrics": {"chars": 2500, "present": true},
    "completeness": {...},
    "value_verification": {...},
    "reproducibility": {...},
    "gap_probe": {...},
    "parameter_table": {...},
    "delivery": {"draft_md": "/app/output/method_experiment_draft.md", "checks_json": "/app/output/checks.json"},
    "summary": "六要素齐全；参数 X 个均有来源；复现清单 Y 项；缺口 Z 条"
  },
  "evidence": {
    "principles": {"写得全": "...", "写得准": "...", "做得着": "...", "说得住": "..."},
    "source_location": {"学习率 0.001": ["config.yaml:3"]},
    "unsupported_values": [],
    "unsourced_params": []
  },
  "uncertainty": {
    "open_questions": [...],
    "needs_author_confirmation": [...],
    "gap_count": 0,
    "note": "数值是否同一条件、限制是否成立仍需作者确认"
  }
}
```

同时落盘：
- `/app/output/method_experiment_draft.md`；
- `/app/output/checks.json`；
- `/app/output/parameter_table.csv`（参数表，便于复用）。

### 6. 最终自检

```bash
python scripts/validate_result.py --result /app/output/result.json \
  --outdir /app/output --case /input/case.json --main-field method_experiment_draft
```

`valid=false` 按 errors 修；不得只交检查结果而不交章节。

## 异常处理

| 情形 | 处置 |
|---|---|
| 配置两处数值冲突 | 不擅自选；列出冲突来源，正文标 `[待核实]`，交作者裁定 |
| 参数无来源 | 标 `missing_source`，不臆造来源 |
| 数据集版本不明 | 写“版本待确认”，列入 open_questions |
| 代码/数据无法访问 | 记录权限限制，交付 partial，不编内容 |
| 材料只有摘要没有细节 | 按已有细节写，缺口逐条列出；不补实验 |
| PDF/docx 读取失败 | `case_io` 报错原因写入 uncertainty；尝试 pdftotext/PyMuPDF 后仍失败则 partial |
| 语言/学科切换 | 中英文规则均适用；要素名可本地化，但六类不能少 |

## 资源

- `scripts/methods_engine.py`：六要素/数值核验/复现清单/缺口追问/参数表/`pipeline`（支持 `--draft-file`）
- `scripts/case_io.py`：读 case.json/txt/md/docx/pdf
- `scripts/validate_result.py`：result 契约与交付物自检
- `references/element_checklist.md`：六类要素判据
- `references/value_provenance.md`：数值来源核验
- `references/repro_template.md`：复现清单模板
- `references/output_contract.md`：字段契约
- `examples/`：示例与自测

## 限制与边界

- 脚本只做确定性的集合/字段比对，不判断“实验设计是否合理”“限制是否真成立”；这些由 Agent 回材料核对并交作者确认。
- 不联网、不补实验、不补数值；材料不足时诚实 partial。
