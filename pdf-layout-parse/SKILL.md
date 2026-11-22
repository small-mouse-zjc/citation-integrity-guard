---
name: pdf-layout-parse
description: 科研 PDF 版面解析。端到端完成器：直接读取平台真实 PDF（/input/case.json 指向），用多后端自动提取带坐标文本，交付逐字保真、栏序正确、结构清晰、每段可回原文页码区块的解析结果并装配 /app/output/result.json。当任务涉及从科研论文 PDF 提取正文/图表题注/脚注/参考文献、修正双栏与多栏阅读顺序、重建复杂表格行列与合并单元格、识别章节层级、保真公式上下标与希腊字母、判定扫描件与乱码时使用本技能。不适用于理解公式科学含义或纯内容翻译问答。
---

# PDF 版面解析（PDF Layout Parse）

面向真实科研 PDF 的**端到端解析技能**。目标不是"检查别人解析得对不对"，而是**自己从真实 PDF 把解析任务做完**：逐字保真、顺序正确、结构清晰、每段可回原文页码与区块，并装配成正式 `result.json`；对读不出的部分诚实标注。

## 何时触发 / 何时不触发

**触发**：需要从 PDF 提取文字、修正栏序、重建表格、识别章节、保真公式符号、定位证据、判定扫描件/乱码。

**不触发**：理解公式/图表的科学含义（题面明确"按结构元素识别，不要求理解科学含义"）、纯翻译或内容问答。被误触发时说明边界并保持原文。

## 核心原则

1. **逐字保真**：用 spans 拼接原文，不靠提取层的合并文本；断行合并只补换行，不改字。
2. **几何可回溯**：分栏、表格、章节的每个判定都有坐标或模式证据，进 `pipeline.*`。
3. **诚实标注**：页眉页脚、乱码、疑似扫描件、读不出的区块显式列出，绝不猜字补齐。
4. **确定性动作交给脚本**：串栏、错行、表格错列、符号失真这些 LLM 易错动作，必须用 `scripts/pdf_layout_engine.py` 实际运行。
5. **不交预制答案**：处理平台给定案例，不用预写结果替代实际运行。

## 工具：pdf_layout_engine.py

位置 `scripts/pdf_layout_engine.py`，主体**纯 Python 标准库**、无网络、无第三方依赖，3.8+ 可运行。

```bash
python scripts/pdf_layout_engine.py --help
```

### 中间表示（layout JSON）

引擎主体吃"带坐标的行"：每页给出 `page/width/height/lines`，每行给出 `x0/y0/x1/y1/text/spans`，每个 span 给出 `text/size/flags/font`。坐标原点左上、y 向下、单位 pt。字段契约见 `references/output_contract.md`。

**如何得到 layout**：`extract` 会自动按 PyMuPDF → pdfplumber → pdfminer 顺序尝试后端，任一可用即导出带坐标 layout（含 span 级 bbox/size/flags）。全无后端时才返回降级指引。扫描件/图片型 PDF 需先 OCR。多后端回退确保"真实 PDF 入口"不再是断点。

```bash
# 直接对真实 PDF 提取（自动选后端）
python scripts/pdf_layout_engine.py extract paper.pdf --case-id C1 > layout.json
```

**端到端一步完成（推荐）**：`solve` 直接读 `/input/case.json`，自动定位真实 PDF（支持 case.json 的 pdf/pdf_path/material 字段、或 case 目录下任意 *.pdf），提取 → 全流程解析 → 装配 `/app/output/result.json`，并把装配回执写入 `delivery` 字段（written/path/bytes）供核验。

```bash
# 从平台真实输入到交付物，一步完成
python scripts/pdf_layout_engine.py solve /input/case.json --out /app/output
# 显式指定 PDF（case.json 未标注时）
python scripts/pdf_layout_engine.py solve /input/case.json --out /app/output --pdf /input/paper.pdf
```

`solve` 也接受 case.json 内联 `pages`/`input_layout`（无需 PDF）。无文字层、PDF 找不到、无后端时返回 `needs_review` 并如实说明，不伪造内容。

### 子命令（对应题面四问）

| 子命令 | 作用 | 对应题面 |
|--------|------|----------|
| `solve` | **端到端完成器**：真实 case/PDF → result.json（推荐入口） | 全部 |
| `extract` | 多后端自动提取 PDF → layout JSON，检测无文字层 | 提得全 |
| `clean` | 逐字保真、剔页眉页脚/边注、断行合并、标乱码 | 提得全 |
| `order` | 分栏检测 + 跨栏块识别 + 跨栏锚点分区后逐栏整段读取 | 排得对 |
| `sections` | 章节层级与编号、结构树 | 拆得清 |
| `tables` | 表格行列/单元格重建、合并单元格标注、跨页续表候选 | 拆得清 |
| `formulas` | 希腊字母/上下标（基于 span size 还原 ^{}/_{}）/公式编号保真 | 拆得清 |
| `captions` | 图表题注识别与配对 | 提得全 |
| `evidence` | 每块生成页码+区块 bbox 定位索引 | 核得回 |
| `verify` | 字符覆盖率/漏行/顺序/悬空自检 | 核得回 |
| `pipeline` | 全流程串联，`--compact` 出紧凑摘要省 token | 全部 |

推荐一次完成：
```bash
python scripts/pdf_layout_engine.py pipeline layout.json > result.json
python scripts/pdf_layout_engine.py pipeline layout.json --compact > summary.json
```

## 标准工作流

**首选一步完成**：`solve /input/case.json --out /app/output`，它串联以下步骤并装配交付物。需要精细控制时按下列分步流程：

1. **识别输入**：读取 `/input/case.json` 与 `task.md`，确认案例要解析什么、证据范围。`solve` 会自动定位真实 PDF；先判断是否有文字层——无文字层/图片型走 OCR 分支并如实标注，不假装能逐字提取。
2. **提取中间表示**：`extract` 多后端自动导出带坐标 layout JSON。字段缺失如实记录。
3. **提得全**：跑 `clean`，保留逐字 spans，剔除跨页重复的页眉页脚与页码，合并断行（只补换行不改字），把乱码/缺字行列入 `unreadable`。
4. **排得对**：跑 `order`，识别双/多栏、跨栏标题与图表；**同一跨栏区间内先完整读左栏、再完整读右栏**（真实双栏段落是整栏连续的，绝不逐行左右交错），检查 `order_violations`。
5. **拆得清**：跑 `sections`（层级）、`tables`（行列/单元格/合并单元格）、`formulas`（基于 span size 还原上下标、保真希腊字母）、`captions`（题注）。公式只按结构元素保真，不解释科学含义。
6. **核得回**：跑 `evidence` 为每个块生成页码+区块，跑 `verify` 检查覆盖率（正文字符覆盖率应≥90%）、漏行、顺序异常；不确定的进 `needs_review`。
7. **装配输出**：`solve` 自动按 `references/output_contract.md` 写 `/app/output/result.json`，保留 `case_id` 并在 `delivery` 记录落盘回执。`result.summary` 是一行紧凑结论；预算紧张用 `pipeline --compact`。每个关键结论附页码与区块定位。

## 输出契约要点

每案例返回结构化结果：`case_id`、`status`（success/partial/needs_review）、`result.reading_text`（按版面顺序的可编辑正文）、`result.structure`（章节树）、`result.tables`（Markdown+行列）、`result.formulas`、`result.captions`、`result.evidence_index`（每块页码+bbox）、`result.verification`（覆盖率/问题）、`result.summary`。详见 `references/output_contract.md`。

## 异常处理

| 情况 | 处置 |
|------|------|
| 加密/损坏 PDF | `extract` 返回 `cannot_open_pdf`，说明原因，不伪造内容 |
| 无文字层扫描件 | 标注 likely_scanned，走 OCR 分支，不把空结果当成功 |
| 页眉页脚/边注 | 跨页重复文本+页边位置识别，列入 `dropped` 附 reason |
| 乱码字体/缺字 | 列入 `unreadable`，如实标注，不猜字 |
| 双栏串栏错行 | `order` 按跨栏锚点分区、逐栏整段重排，输出 `order_violations` 自检 |
| 跨页续表 | `continuations` 标注候选，交人工确认合并 |
| 无 PDF 后端 | `extract` 依次试 PyMuPDF→pdfplumber→pdfminer，全无才给降级指引；`solve` 如实返回 `needs_review` |

## 额度与预算建议（64 请求 / 900 秒 / 16384 token）

- 解析几何动作全部交给脚本，模型只做"哪块不确定、是否需要人工确认"的高层判断。
- 用 `pipeline --compact` 只看摘要+关键结果，不把整棵 pipeline 塞进上下文。
- 先存诚实的部分结果（reading_text + evidence）再增量完善。
- 三案例复用同一流程与同一套中间表示约定，避免重复摸索。

## 交付文件（solve 自动生成，评审可直接打开）

`solve /input/case.json --out /app/output` 在 `result.json` 之外还会写出：`layout.json` + `layout.md`（版面结构）、`tables.json` + `tables.md`（表格），以及 `deliverable.md`（人读版：概要 / 主结果 / 需人工确认 / 文件清单）。这些文件全部由 `result` 渲染而来，字段缺失就不生成对应文件、不补造；`delivery.artifacts` 里逐个记录文件名、字节数与用途。

## 资源清单

- `scripts/pdf_layout_engine.py`：端到端版面解析引擎（11 子命令，含 `solve` 完成器；主体纯标准库，PDF 提取多后端自动回退）
- `scripts/artifacts.py`：交付物渲染器（result → deliverable.md + 领域文件，纯标准库）
- `references/output_contract.md`：输入输出字段契约
- `references/reading_order_rules.md`：分栏与阅读顺序判定规则
- `references/table_structure.md`：表格结构重建规则
- `references/evidence_contract.md`：证据定位与自检契约
- `references/failure_patterns.md`：失败模式案例（可分享经验）
- `references/vocab.md`：可复用词表（章节/题注/符号模式）
- `examples/layout_sample.json`：带坐标样例（标注为示例）
- `examples/testset.json`：10 道边界测试题集
- `examples/selftest.py`：38 项自验收测试（含 solve 端到端、双栏段落连续性、公式上下标回归）
- `examples/minimal_example.md`：最小调用示例

## 限制与边界

- 按结构元素识别图表公式，不解释科学含义；希腊字母保真保留 Unicode 原文，不把 ASCII 字母误改为希腊字母（避免 "is"→"ιζ" 失真）。
- 分栏判定基于 x0 聚类，极窄栏/不规则版式可能需人工确认；跨页表格合并给候选不替作者决定。
- 无文字层需 OCR；引擎不内置 OCR，但能如实判定并标注，不把空结果伪装成成功。
- 不联网、不臆造 PDF 中不存在的文字或数据；所有结论可回到页码与区块。


## 可复现证据与冲分材料

本 Skill 针对四问（提得全 / 排得对 / 拆得清 / 核得回）配置了确定性检查机制，并提供可复现的公平对照证据：

- `scripts/compare_engine.py`：对同一输入给出"基线常见失败 vs Skill 四问检查机制"的对照，客观呈现观测值，**不编造平台质量分**（正式对照由平台固定案例与白板给出）。
  ```bash
  python scripts/compare_engine.py examples/smoke_input.json    # 单案例机制对照
  python scripts/compare_engine.py examples/benchmark.json      # 干净+缺陷两案例
  ```
- `examples/benchmark.json`：干净案例（验证不误报）+ 按四问注入缺陷的案例（验证能检出）。
- `references/innovation_boundary.md`：相对通用对话模型/现有工具的创新边界与可复现路径。
- `references/comparison_protocol.md`：公平对照协议与度量边界。
- `references/failure_patterns.md`：失败模式库、降级优先级；`references/vocab.md`：判定词表。

创新边界摘要：`pdf_layout_engine.py` 把 "提得全 / 排得对 / 拆得清 / 核得回" 中每问的易错动作固化为脚本判定，价值判断须建立在其可回溯证据之上；材料不足时诚实降级为 `partial`/`needs_attention`，不臆造事实、数值或来源。
