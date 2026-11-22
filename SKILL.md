---
name: citation-integrity
description: 参考文献与引用一致性守门人。当任务涉及引用插入定位、正文编号与文末列表同步更新、文献去重与条目归并、BibTeX/RIS/CNKI 到 GB/T 7714 等格式的转换、DOI 与元数据核验、正文论断与所引文献的一致性检查，或需要交付"可编辑稿件 + 同步文献表 + 逐条可回溯证据"时使用本技能。通过确定性脚本把易错的重排、去重、格式化动作做准确，并对无法判断的项目显式标注而非臆测。不适用于纯内容创作或与引用管理无关的问答。
---

# 引用一致性守门人（Citation Integrity Guard）

面向真实学术稿件的参考文献与引用管理技能。目标不是"改写文字"，而是让**每一条引用都落到真实、可定位、编号一致、格式合规的文献记录上**，并让每一步改动都能回溯到证据。

## 何时触发 / 何时不触发

**触发**：任务中出现以下任一信号——
- 让插入/调整引用，或指定引用格式（顺序编码制、著者—出版年制、脚注）；
- 让更新编号、修复"编号对不上""引用悬空""文末条目没被引用"；
- 给出多份文献库要求合并、去重、辨认预印本与正式版；
- 要求格式转换或字段补齐（BibTeX / RIS / EndNote / CNKI → GB/T 7714—2015、APA 等）；
- 要求核验引用真实性、元数据准确性、正文论断与文献是否匹配。

**不触发**：纯写作润色、与引用无关的内容问答。被误触发时应说明"这属于内容写作，不是引用管理任务"并保持原文不变。

## 核心原则（贯穿所有动作）

1. **证据优先**：每条引用、每个合并决定都要能回到原始稿件行号或文献库记录。关键结论必须给出定位，不能只给结论。
2. **最小改动**：只在引用管理范围内改动。不要顺手改写正文措辞、不要改数据单位、不要调整作者原意。
3. **诚实标注**：材料不足、DOI 解析失败、条目歧义、疑似重复但证据不够——一律显式写进 `uncertainty` / `needs_review`，**绝不臆造文献、元数据或编号**。
4. **不交预制答案**：本技能处理平台给定的输入案例，不得用预写好的答案替代实际运行。
5. **确定性动作交给脚本**：去重、编号重排、格式化这些 LLM 易错动作，必须用 `scripts/citation_engine.py` 实际运行得出，不靠模型心算。

## 工具：citation_engine.py

位置：技能目录下的 `scripts/citation_engine.py`，纯 Python 3 标准库，无第三方依赖、无网络请求（11 子命令，含 solve/render-draft）。

先确认可运行：
```bash
python scripts/citation_engine.py --help
```

### 子命令

| 子命令 | 作用 | 关键输出 | 对应题面 |
|--------|------|----------|----------|
| `ingest` | 解析 BibTeX/RIS/CNKI 原文为结构化条目 | `entries`、`detected_format`、`issues` | 格式转换（省手工誊抄） |
| `normalize` | 归一化 + 可解释去重 | `entries`、`decisions`（判据/置信度/证据）、`issues`、`needs_review_count` | 收得净 |
| `renumber` | 按首次出现顺序重排，并改写可编辑正文 | `mapping`、`rewritten_manuscript`、`rewrite_changes`、`occurrences`、`unresolved` | 编得顺 |
| `format` | 渲染文后表（GB/T 7714；`--standard apa` 展示扩展） | `references`、`warnings`、`standard` | 格式转换 |
| `verify` | 正文—文末双向一致性 + 首次出现顺序 | `dangling_citations`、`uncited_entries`、`numbering_gaps`、`order_violations`、`consistent` | 编得顺 |
| `place` | 引用落点定位：识别需来源支撑的论断句与建议位置 | `sentences`、`stats.citation_gaps`、`advice`、真实文献 `candidates` | 挂得对 |
| `claims` | 论断核验预筛：元数据异常/编造线索/主题错配 | `metadata_anomalies`、`suspicious_claims`、`claim_results` | 对得上 |
| `compare` | 修复前后对照，逐项验证增益 | `diffs`、`summary.improved_metrics` | 增益可验证 |
| `render-draft` | 用真实字段渲染可编辑引用定稿稿件（未引条目显式标注） | `draft_text`、`edited_manuscript`、`bibliography`、`uncited_entries` |
| `solve` | 端到端完成器：case.json →(适配稿件/文献库)→ 定稿 → result.json | `result.draft_text`、`delivery` |
| `pipeline` | 全流程串联（`--with-draft` 出定稿草稿；`--compact` 省 token） | `result.*`、`summary`、`pipeline.<step>` 兼容旧结构 | 全部 |

输入为 UTF-8 JSON。端到端交付首选 `solve`，一次运行即从真实稿件/文献库走到可编辑定稿与可复核交付：
```bash
python scripts/citation_engine.py solve /input/case.json --out /app/output   # 端到端定稿+装配
python scripts/citation_engine.py render-draft input.json > draft.json        # 仅渲染定稿草稿
python scripts/citation_engine.py pipeline input.json --with-draft > result.json  # 带成稿的全流程
python scripts/citation_engine.py pipeline input.json --compact > summary.json   # 额度紧张时用
```

`solve` 适配的真实输入字段：`manuscript`/`manuscript_file`（.md/.txt/.tex 稿件）、`entries`/`entries_file`（JSON 条目）、`bib_file`/`bibliography_file`（BibTeX/RIS/CNKI，复用 `ingest` 解析）、`checks`。读不到不臆造，记入 `adapter_notes`。

`input.json` 结构：
```json
{
  "case_id": "案例标识",
  "entries": [
    {"id":"wang2020","authors":["Wang, J.","Li, H."],"title":"...","year":2020,
     "journal":"Fuel","volume":281,"pages":"118-126","doi":"10.1016/...","type":"article"}
  ],
  "manuscript": "正文文本，引用写作 [1] 或 [1,2,3-5] 或 [@wang2020]",
  "checks": {"place": true, "claims": true, "compare_before": {"manuscript":"旧稿件","entries":[]}}
}
```

字段说明见 `references/output_contract.md`。真实案例若提供的是 BibTeX/RIS/CNKI 原文，**先跑 `ingest`** 自动解析（字段缺失如实留空并记录），无需手工逐条转换。全部子命令也可在 Python 中直接 `import citation_engine as ce` 调用其同名函数（如 `ce.normalize(entries)`、`ce.place_citations(ms, entries)`），便于嵌入自定义流程。

## 标准工作流

接到任务后按此顺序执行，每步都保留证据：

1. **读输入**：读取 `/input/case.json` 与 `task.md`（或平台给定的输入文件），确认 `case_id`、任务口径、目标引用规范、稿件与文献库位置。**如实读取真实文件，不要从标签或文件名猜测内容。**
2. **解析**：文献库若为 BibTeX/RIS/CNKI 原文，先跑 `ingest` 自动解析（省去逐条转换的请求与 token）；再识别正文每个引用点及其所在行/段落。字段缺失、编码异常、文件损坏记入 `issues`，不臆造。
3. **去重归并**：运行 `normalize`。判据与置信度见 `references/dedup_rules.md`。置信度低于阈值（默认 0.82）的疑似重复、**以及预印本 vs 正式版等 version_variant 线索**，一律不自动合并，列入 `needs_review` 并说明依据。边界案例见 `references/failure_patterns.md`。
4. **编号同步**：运行 `renumber`。按正文首次出现顺序编号；插入/删除/调序后用 `mapping` 连锁更新，交付 `rewritten_manuscript` 作为可编辑稿件底稿（`rewrite_changes` 逐条记录改动）。
5. **格式转换**：运行 `format`，按目标规范渲染（内置 GB/T 7714—2015；`--standard apa` 展示规范可扩展，扩展方法见 `references/apa_mapping.md`）。保留 DOI、卷期页、文献类型标识，处理中英文混排与标点。
6. **落点与论断核验（关键，勿用逐句心算）**：
   - 先跑 `place`：机械标出需要来源支撑却无引用的论断句（"挂得对"），候选文献只取真实条目，供定位不供最终判断。
   - 再跑 `claims`：确定性预筛元数据异常/编造线索/主题错配（"对得上"），**只对返回的 `suspicious_claims` 交模型或人工复核**，把逐句 O(n) 判断降到 O(可疑)。证据不足的句子显式标记，不擅自改论断。
7. **一致性核验**：运行 `verify`，确认无悬空引用、无未引用条目、编号连续无重复、首次出现顺序正确（`order_violations`）。需要证明增益时用 `compare` 对修复前后逐项对照。
8. **装配输出**：直接 `python scripts/citation_engine.py solve /input/case.json --out /app/output` 完成端到端交付（自动适配稿件/文献库、定稿成稿、写 result.json + delivery 回执）；或按 `references/output_contract.md` 手工装配。预算紧张时用 `pipeline --compact`。每条改动附"原文 → 改文 → 类型 → 理由 → 证据定位"。**未在正文引用的条目显式标〔未引〕，不伪装成正文引用。**

## 输出契约要点

每个案例返回一份结构化结果，至少包含：
- **输入标识**：`case_id` 及输入文件版本/来源。
- **目标产物**：可继续编辑的稿件与同步的文献表，满足题目指定体裁与格式。
- **事实与来源映射**：数字、引用、图表、关键论断的来源/修改记录，可逐条回溯，不新增材料外事实。
- **版本与边界**：修改差异、人工确认项、材料缺口、异常，`status` 取 `success` / `partial` / `needs_review` 之一并说明原因。
- **运行状态**：成功、部分完成、无法判断或拒答及原因。

详细字段与示例见 `references/output_contract.md` 和 `examples/minimal_example.md`。

## 异常处理

| 情况 | 处置 |
|------|------|
| 文献库字段缺失 | 保留已知字段，缺失留空，记入 `issues`，不编造 |
| DOI 解析/核验失败 | 标注 `doi_unverified`，不据此判定条目不存在 |
| 条目歧义、疑似同名不同文献 | 不自动合并，列入 `needs_review`，给出双方证据 |
| 编号冲突/不连续 | 用 `renumber` 重排，输出新旧映射，保留原文引用点定位 |
| 稿件格式不支持/文件损坏 | 说明无法处理的具体位置与原因，保存已完成的诚实部分结果 |
| 正文论断与文献不匹配 | 逐句标记 `claim_source_mismatch`，给出主题差异说明，不擅自改论断 |

## 交付文件（solve 自动生成，评审可直接打开）

`solve /input/case.json --out /app/output` 在 `result.json` 之外还会写出：`manuscript.md`（改后稿件）、`draft.md`、`references.csv`（文献条目）、`references.bib`（若有 BibTeX），以及 `deliverable.md`（人读版：概要 / 主结果 / 需人工确认 / 文件清单）。这些文件全部由 `result` 渲染而来，字段缺失就不生成对应文件、不补造；`delivery.artifacts` 里逐个记录文件名、字节数与用途。

## 资源清单

- `scripts/citation_engine.py`：确定性处理引擎（11 子命令，含 solve/render-draft，纯标准库，必需）
- `scripts/artifacts.py`：交付物渲染器（result → deliverable.md + 领域文件，纯标准库）
- `references/dedup_rules.md`：去重判据与置信度表
- `references/format_gb7714.md`：GB/T 7714—2015 格式映射与字段规则
- `references/apa_mapping.md`：APA 7th 扩展映射（证明规范可扩展）
- `references/output_contract.md`：输出字段契约与装配说明
- `references/verification_checklist.md`：来源与论断核验清单
- `references/failure_patterns.md`：10 类失败模式案例（可分享经验）
- `references/vocab.md`：可复用词表（预印本 DOI 前缀、字段别名、类型标识、信号词）
- `examples/testset.json`：14 道边界回归测试题集（可复用）
- `examples/selftest.py`：33 项自验收测试（覆盖率证据）
- `examples/`：最小调用示例与样例输入输出（示例输出已标注，非正式案例结果）

## 额度与预算建议（64 请求 / 900 秒 / 16384 token）

- 文献库原文一律用 `ingest` 解析，不手工逐条转换；输出用 `pipeline --compact` 省 token。
- 论断核验只跑 `claims`，**只把 `suspicious_claims` 交模型复核**，不要逐句心算。
- 去重低置信项据 `needs_review` 批量交人工确认，不逐条来回追问。
- 早存诚实的部分结果再增量完善；三个案例在同一流程内复用，避免重复解析。

## 限制与适用边界

- 内置格式化以 GB/T 7714—2015 顺序编码制为主；APA 7th 为展示性扩展，具体版本细则（英文大小写、编者/译者、出版地省路等）须人工核对，见 `references/apa_mapping.md`。
- 去重保守：证据不足（含 version_variant）时保留两条并标注待核，宁可漏并不误并。
- 脚本不联网，DOI 真实性、编造条目判定与数据库比对需结合平台工具或模型核验，`claims` 只给确定性线索与 `needs_review`，结论须给可回溯依据。
- `place`/`claims` 基于关键词重叠与元数据规则的确定性预筛，候选与分档供定位与分流，不构成学术判断；论断是否成立、文献是否恰当由作者最终确认。
- 本技能只保证引用管理动作的准确、可解释与可核验，不改写正文观点、不新增材料外事实。


## 可复现证据与冲分材料

本 Skill 针对四问（挂得对 / 编得顺 / 收得净 / 对得上）配置了确定性检查机制，并提供可复现的公平对照证据：

- `scripts/compare_engine.py`：对同一输入给出"基线常见失败 vs Skill 四问检查机制"的对照，客观呈现观测值，**不编造平台质量分**（正式对照由平台固定案例与白板给出）。
  ```bash
  python scripts/compare_engine.py examples/smoke_input.json    # 单案例机制对照
  python scripts/compare_engine.py examples/benchmark.json      # 干净+缺陷两案例
  ```
- `examples/benchmark.json`：干净案例（验证不误报）+ 按四问注入缺陷的案例（验证能检出）。
- `references/innovation_boundary.md`：相对通用对话模型/现有工具的创新边界与可复现路径。
- `references/comparison_protocol.md`：公平对照协议与度量边界。
- `references/failure_patterns.md`：失败模式库、降级优先级；`references/vocab.md`：判定词表。

创新边界摘要：`citation_engine.py` 把 "挂得对 / 编得顺 / 收得净 / 对得上" 中每问的易错动作固化为脚本判定，价值判断须建立在其可回溯证据之上；材料不足时诚实降级为 `partial`/`needs_attention`，不臆造事实、数值或来源。
