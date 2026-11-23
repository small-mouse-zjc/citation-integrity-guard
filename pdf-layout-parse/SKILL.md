---
name: pdf-layout-parse
description: 科研 PDF 版面解析守门人。当任务涉及从科研论文 PDF 提取正文/图表题注/脚注/参考文献、修正双栏与多栏阅读顺序、重建复杂表格行列与合并单元格、识别章节层级、保真公式上下标与希腊字母、判定扫描件与乱码、或需要把每段文字指回原文页码与区块时使用本技能。通过确定性几何规则把易错的串栏、错行、吞字、表格错列做准确，并对读不出的部分显式标注而非猜测补齐。不适用于理解公式科学含义或纯内容翻译问答。
---

# PDF 版面解析守门人（PDF Layout Parse Guard）

面向真实科研 PDF 的版面解析技能。目标不是"给一段看起来像全文的文本"，而是交付**逐字保真、顺序正确、结构清晰、每段可回原文页码与区块**的解析结果，并对无法读取的部分诚实标注。

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

**如何得到 layout**：优先跑可选适配器 `extract`（需 PyMuPDF）：
```bash
python scripts/pdf_layout_engine.py extract paper.pdf > layout.json
```
若环境无 PyMuPDF，会自动回退到 `pdftotext -layout`，返回 `backend="pdftotext"`、`stats.text_only=true` 的近似 layout（文字与页序保留，bbox/字号为近似值）。这时在 `uncertainty` 写明“表格/多栏顺序为文本回退、需人工复核”，不要声称精确版面。两者都不可用时，`extract` 返回降级指引而不崩溃——用平台可用的 PDF 工具导出中间表示即可，主体引擎不依赖具体库。扫描件/图片型 PDF 需先 OCR。

### 子命令（对应题面四问）

| 子命令 | 作用 | 对应题面 |
|--------|------|----------|
| `extract` | （可选）PDF → layout JSON，检测无文字层 | 提得全 |
| `clean` | 逐字保真、剔页眉页脚/边注、断行合并、标乱码 | 提得全 |
| `order` | 分栏检测 + 跨栏块识别 + 双栏按 y 交错重排 | 排得对 |
| `sections` | 章节层级与编号、结构树 | 拆得清 |
| `tables` | 表格行列/单元格重建、跨页续表候选 | 拆得清 |
| `formulas` | 希腊字母/上下标/公式编号保真（不解释含义） | 拆得清 |
| `captions` | 图表题注识别与配对 | 提得全 |
| `evidence` | 每块生成页码+区块 bbox 定位索引 | 核得回 |
| `verify` | 字符覆盖率/漏行/顺序/悬空自检 | 核得回 |
| `pipeline` | 全流程串联，`--compact` 出紧凑摘要省 token | 全部 |

推荐一次完成：
```bash
python scripts/pdf_layout_engine.py pipeline layout.json --outdir /app/output > result.json
python scripts/pdf_layout_engine.py pipeline layout.json --compact --outdir /app/output > summary.json
```

## 标准工作流

1. **识别输入**：读取 `/input/case.json` 与 `task.md`，确认案例要解析什么、证据范围。先判断是否有文字层——无文字层/图片型走 OCR 分支并如实标注，不假装能逐字提取。
2. **导出中间表示**：用 `extract` 或平台工具把 PDF 导成 layout JSON。字段缺失如实记录。
3. **提得全**：跑 `clean`，保留逐字 spans，剔除跨页重复的页眉页脚与页码，合并断行（只补换行不改字），把乱码/缺字行列入 `unreadable`。
4. **排得对**：跑 `order`，识别双/多栏、跨栏标题与图表，按 y 交错还原阅读顺序，检查 `order_violations`。
5. **拆得清**：跑 `sections`（层级）、`tables`（行列/单元格）、`formulas`（符号保真）、`captions`（题注）。公式只按结构元素保真，不解释科学含义。
6. **核得回**：跑 `evidence` 为每个块生成页码+区块，跑 `verify` 检查覆盖率（正文字符覆盖率应≥90%）、漏行、顺序异常；不确定的进 `needs_review`。
7. **装配输出**：按 `references/output_contract.md` 写 `/app/output/result.json`，保留 `case_id`。`pipeline --outdir /app/output` 会真实写出 `reading_text.md`、`sections.json`、`tables.md`，并在 `result.artifacts` 记录路径。`result.summary` 是一行紧凑结论；预算紧张用 `pipeline --compact`。每个关键结论附页码与区块定位。

## 输出契约要点

每案例返回结构化结果：`case_id`、`status`（success/partial/needs_review）、`result.reading_text`（按版面顺序的可编辑正文）、`result.structure`（章节树）、`result.tables`（Markdown+行列）、`result.formulas`、`result.captions`、`result.evidence_index`（每块页码+bbox）、`result.verification`（覆盖率/问题）、`result.summary`。详见 `references/output_contract.md`。

## 异常处理

| 情况 | 处置 |
|------|------|
| 加密/损坏 PDF | `extract` 返回 `cannot_open_pdf`，说明原因，不伪造内容 |
| 无文字层扫描件 | 标注 likely_scanned，走 OCR 分支，不把空结果当成功 |
| 页眉页脚/边注 | 跨页重复文本+页边位置识别，列入 `dropped` 附 reason |
| 乱码字体/缺字 | 列入 `unreadable`，如实标注，不猜字 |
| 双栏串栏错行 | `order` 按坐标重排，输出 `order_violations` 自检 |
| 跨页续表 | `continuations` 标注候选，交人工确认合并 |
| 无 PyMuPDF | `extract` 给降级指引，主体引擎照常用中间表示运行 |

## 额度与预算建议（64 请求 / 900 秒 / 16384 token）

- 解析几何动作全部交给脚本，模型只做"哪块不确定、是否需要人工确认"的高层判断。
- 用 `pipeline --compact` 只看摘要+关键结果，不把整棵 pipeline 塞进上下文。
- 先存诚实的部分结果（reading_text + evidence）再增量完善。
- 三案例复用同一流程与同一套中间表示约定，避免重复摸索。

## 资源清单

- `scripts/pdf_layout_engine.py`：确定性版面解析引擎（10 子命令，主体纯标准库）
- `references/output_contract.md`：输入输出字段契约
- `references/reading_order_rules.md`：分栏与阅读顺序判定规则
- `references/table_structure.md`：表格结构重建规则
- `references/evidence_contract.md`：证据定位与自检契约
- `references/failure_patterns.md`：失败模式案例（可分享经验）
- `references/vocab.md`：可复用词表（章节/题注/符号模式）
- `examples/layout_sample.json`：带坐标样例（标注为示例）
- `examples/testset.json`：10 道边界测试题集
- `examples/selftest.py`：28 项自验收测试
- `examples/minimal_example.md`：最小调用示例

## 限制与边界

- 按结构元素识别图表公式，不解释科学含义；希腊字母保真保留 Unicode 原文，不把 ASCII 字母误改为希腊字母（避免 "is"→"ιζ" 失真）。
- 分栏判定基于 x0 聚类，极窄栏/不规则版式可能需人工确认；跨页表格合并给候选不替作者决定。
- 无文字层需 OCR；引擎不内置 OCR，但能如实判定并标注，不把空结果伪装成成功。
- 不联网、不臆造 PDF 中不存在的文字或数据；所有结论可回到页码与区块。


## 交付前自检（必须）

```bash
python scripts/validate_result.py --result /app/output/result.json --outdir /app/output --case /input/case.json --main-field reading_text
```

`valid=false` 时按 errors 修；`result.reading_text` 为空、顶层缺 `case_id/status/result/evidence/uncertainty`、或声明的产物路径不存在，都不得声称完成。

