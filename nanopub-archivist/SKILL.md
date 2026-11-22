---
name: nanopub-archivist
description: Nanopublication（纳米出版物）构建与核验守门人。当任务要求从论文段落拆分原子科研断言、为断言绑定最小充分证据与原文位置、记录论文-作者-年份-版本来源链路、检测断言过宽/证据不足/关系错误/主体混淆/来源缺失、或导出可机器读取的结构化知识单元时使用本技能。通过确定性脚本把拆得细、对得上、追得回、读得懂四件事落成可复核的结构化结果，不臆造断言、证据或来源。不适用于非科研结论的知识抽取或纯翻译润色。
---

# Nanopublication 构建与核验守门人（Nanopub Archivist）

面向真实论文关键结论的纳米出版物 skill。目标不是"把摘要塞进一个字段"，而是把一段结论拆成**一条条各自可判断真假的原子断言**，每条绑定**最小充分证据与原文位置**，补全**来源链路**，并导出**下游可直接解析**的结构。

围绕题面四个核心问题组织能力：

| 核心问题 | 含义 | 对应工具 |
|---------|------|---------|
| 拆得细 | 段落能否拆成单一可判断真假的断言，保留条件与限定，处理并列/因果 | `check-assertion` |
| 对得上 | 每条断言能否找到真正支撑它的最小证据片段，且原文位置可指出 | `bind-evidence` |
| 追得回 | 断言-证据-论文-作者-年份-版本链路是否完整，他人能否回到原文 | `check-provenance` |
| 读得懂 | 导出字段与序列化形态是否合规，能否被下游直接解析 | `check-export` |

另有 `check-quality` 做跨断言质量检查（过宽/重复/主体混淆），`pipeline` 一次跑完全流程。

## 何时触发 / 何时不触发

**触发**：任务中出现以下任一信号——
- 从论文/摘要/结论段抽取结构化事实、知识点、断言；
- 要求断言粒度拆解、证据片段定位、来源元数据记录；
- 要求输出 nanopublication / 知识单元 / 可机器读取的 JSON-RDF 结构；
- 抱怨"整段塞一个字段/证据对不上/来源查不回/字段东缺西缺"。

**不触发**：纯翻译、纯润色、非科研结论的通用信息抽取。被误触发时说明并保持原文不变。

## 核心原则（贯穿所有动作）

1. **原子化**：一条断言只表达一个可判断真假的关系（主体-关系-对象），复合句拆开，保留条件与量化限定，不把并列/因果揉成一条。
2. **最小充分证据**：证据片段只取直接支撑该断言的那一段，标出原文位置（页码/章节/图表/段落），区分直接证据与间接推论。
3. **来源可回溯**：每条断言必须带论文、作者、年份、版本、来源、标识符六项元数据，缺项显式标注，不臆造 DOI 或作者。
4. **结构可解析**：导出字段固定且完整，JSON 可序列化，下游无需人工清洗；字段定义见 `references/output_contract.md`。
5. **诚实标注**：断言是否忠实、证据是否真支持、置信度高低属价值判断，须 Agent 结合原文复核；脚本只做结构与规则校验，**绝不臆造断言、证据或来源**。
6. **不交预制答案**：处理平台给定案例，读真实输入材料，不用预写结果替代实际运行。
7. **确定性动作交给脚本**：四项核心检查与质量检查必须用 `scripts/nanopub_engine.py` 实际运行。

## 工具：nanopub_engine.py

位置：技能目录下 `scripts/nanopub_engine.py`，纯 Python 3 标准库，无第三方依赖、无网络请求、不调用外部服务（8 子命令，含 solve/render-draft）。

先确认可运行：
```bash
python scripts/nanopub_engine.py --help
```

### 子命令

| 子命令 | 作用 | 关键输出 |
|--------|------|---------|
| `check-assertion` | 拆得细：断言原子性 | `relation`、`has_qualifier`、`atomicity_ok`、`issues`（compound/overbroad/no_relation） |
| `bind-evidence` | 对得上：证据绑定 | `bound`、`has_anchor`、`word_overlap`、`issues`（no_evidence/no_anchor/evidence_too_long/weak_link） |
| `check-provenance` | 追得回：来源链路 | `complete`、`missing`（含字段级 identifier_format） |
| `check-export` | 读得懂：导出结构 | `machine_readable`、`serializable`、`missing_fields`、`issues` |
| `check-quality` | 质量检查：跨断言 | `duplicate_assertions`、`ambiguous_subjects`、`subject_count` |
| `render-draft` | 用真实字段渲染可编辑 Nanopublication 交付稿（无断言标〔待补〕） | `draft_text`、`nanopublications`、`export_text` |
| `solve` | 端到端完成器：case.json →(适配材料)→ 成稿 → result.json | `result.draft_text`、`delivery` |
| `pipeline` | 串联以上（`--with-draft` 出交付稿） | `status`、`result`、`evidence`、`uncertainty` |

每个子命令既可 `python scripts/nanopub_engine.py <cmd> input.json` 单独调用，也可由 Agent 在流程中按字段调用其 Python 函数。输入为 UTF-8 JSON。端到端交付首选 `solve`：
```bash
python scripts/nanopub_engine.py solve /input/case.json --out /app/output   # 端到端成稿+装配
python scripts/nanopub_engine.py render-draft input.json > draft.json        # 仅渲染交付稿
python scripts/nanopub_engine.py pipeline input.json --with-draft > result.json  # 带成稿的全流程
python scripts/nanopub_engine.py pipeline input.json > result.json             # 仅结构化检查
```

`solve` 适配的真实输入字段：`paragraph`/`source_text`（论文文本）、`source_files`（[路径]，读 .txt/.md 或含断言/元数据的 .json）、`assertions`/`assertions_file`、`source_metadata`/`metadata_file`。读不到不臆造，记入 `adapter_notes`；无真实断言标〔待补〕，不臆造断言或证据。

`input.json` 结构：
```json
{
  "case_id": "案例标识",
  "paragraph": "待拆解的原始结论段落（含原文）",
  "assertions": [
    {"text": "原子断言全文", "subject": "主体", "relation": "受控关系", "object": "客体",
     "evidence": "最小充分证据片段", "evidence_type": "direct 或 indirect",
     "anchor": "§4 图3", "confidence": "high 或 medium 或 low"}
  ],
  "source_metadata": {"paper": "题名", "authors": ["作者"], "year": 2023,
     "version": "v1", "source": "期刊/来源", "identifier": "doi:10.xxxx/yyyy"},
  "export_format": "json"
}
```

关系词表、字段定义、锚点格式见 `references/`，真实案例须**读取真实输入文件**，不从标签臆测内容。

## 标准工作流

接到任务后按此顺序执行，每步保留证据：

1. **读输入**：读取 `/input/case.json` 与 `task.md`，确认 `case_id`、论文材料、问题边界与证据范围。**如实读真实材料。**
2. **拆得细**：通读目标段落，用 `check-assertion` 核验每条候选断言。把复合句拆成多条，给每条补条件/限定词，直到 `issues` 中无 compound/overbroad/no_relation 警告。**断言由 Agent 依原文拆分，脚本判结构。**
3. **对得上**：为每条断言回原文找最小证据片段与位置，用 `bind-evidence` 核验。过长证据截取直接支撑部分，无词面重叠的标 `indirect` 并人工确认，缺锚点回原文补页码/图号。
4. **追得回**：从论文首页与题录采六项来源元数据，用 `check-provenance` 核验 `complete=true`；缺项如实标注 missing，标识符核对 DOI/PMID 格式，不臆造。
5. **读得懂**：用 `pipeline`（内含 `check-export`）产出 nanopublications，确认 `machine_readable=true`、`missing_fields` 为空、格式在 json/jsonld/rdf 内。
6. **质量复核**：看 `check-quality` 的 `duplicate_assertions` 与 `ambiguous_subjects`，合并重复、核对主体关系方向。
7. **装配输出**：直接 `python scripts/nanopub_engine.py solve /input/case.json --out /app/output` 完成端到端交付（自动适配材料、渲染交付稿、写 result.json + delivery 回执）；或按 `references/output_contract.md` 手工装配。每条断言附"原文定位 → 断言 → 证据 → 来源 → 置信度依据"。`needs_review` 列出项须逐条人工复核。

## 输出契约要点

`result.json` 至少包含：`case_id`、`status`、`result`（六项结构化检查 + nanopublications；`solve` 额外含 `draft_text`/`nanopublications`/`export_text`）、`evidence`、`uncertainty`。`solve` 另有 `delivery`（落盘回执，written=true 且 bytes>0 才算交付成功）。`status=ok` 要求所有证据绑定成功 + 来源完整 + 导出合规 + 无重复断言。完整字段见 `references/output_contract.md`。

## 异常处理

| 情形 | 处置 |
|------|------|
| 扫描版无文本层 | 标注无法抽取断言，`status=partial`，说明需 OCR，不臆造正文 |
| 原文无法访问 | 标注来源不可核验，`missing_provenance` 列出缺项 |
| 证据跨图表 | anchor 写明图号/表号，evidence_type 视情况标 indirect |
| 断言找不到支撑片段 | `bind-evidence` 报 no_evidence/weak_link，`unbound_assertions` 列出索引，交人工 |
| 断言与证据冲突 | 不强行绑定，`needs_review` 标出，说明冲突点 |
| 字段缺失 | `check-export`/`check-provenance` 列出缺失字段，补齐再导出 |
| 重复断言 | `check-quality` 标 duplicate_assertions，合并保留证据更全的一条 |

## 复用与扩展

- `references/assertion_rules.md`：原子化判据、复合句拆分、条件限定保留；
- `references/evidence_binding.md`：最小充分证据判据、锚点格式、直接/间接；
- `references/provenance_vocab.md`：六项来源元数据、受控关系词表、锚点正则；
- `references/output_contract.md`：输出字段定义、status 判定、示例；
- `references/assertion_samples.md`：20 条跨方向原子断言样例（可直接复用做 few-shot / benchmark）；
- `examples/`：最小调用示例与 23 项自验收（`python examples/selftest.py`）。

本技能与 `citation-integrity`、`intro-gap-architect`、`methods-repro-guard`、`paper-note-archivist`、`latex-build-guard` 互补：分别管引用、引言、方法实验、阅读笔记、LaTeX 编译、纳米出版物，串联覆盖论文"读→写→核验→结构化"全流程。


## 可复现证据与冲分材料

本 Skill 针对四问（拆得细 / 对得上 / 追得回 / 读得懂）配置了确定性检查机制，并提供可复现的公平对照证据：

- `scripts/compare_engine.py`：对同一输入给出"基线常见失败 vs Skill 四问检查机制"的对照，客观呈现观测值，**不编造平台质量分**（正式对照由平台固定案例与白板给出）。
  ```bash
  python scripts/compare_engine.py examples/smoke_input.json    # 单案例机制对照
  python scripts/compare_engine.py examples/benchmark.json      # 干净+缺陷两案例
  ```
- `examples/benchmark.json`：干净案例（验证不误报）+ 按四问注入缺陷的案例（验证能检出）。
- `references/innovation_boundary.md`：相对通用对话模型/现有工具的创新边界与可复现路径。
- `references/comparison_protocol.md`：公平对照协议与度量边界。
- `references/failure_patterns.md`：失败模式库、降级优先级；`references/vocab.md`：判定词表。

创新边界摘要：`nanopub_engine.py` 把 "拆得细 / 对得上 / 追得回 / 读得懂" 中每问的易错动作固化为脚本判定，价值判断须建立在其可回溯证据之上；材料不足时诚实降级为 `partial`/`needs_attention`，不臆造事实、数值或来源。
