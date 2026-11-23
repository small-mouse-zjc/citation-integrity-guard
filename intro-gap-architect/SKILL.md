---
name: intro-gap-architect
description: 引言与相关工作写作。当任务要求基于真实论文材料撰写或改写引言、研究背景、相关工作、研究空白与贡献表述，并要求相关工作按问题/方法/数据分组比较、空白由已引文献缺口推出、贡献与图表实验对齐、引用可逐条回溯时使用。Agent 先读材料并直接写出四部件连贯成稿，再用脚本核验引用映射、空转背景、分组、空白支撑与贡献锚点；不生成预制答案、不补造文献或数据。
---

# 引言与相关工作：四部件成稿（Intro & Related Work Architect）

本技能交付**可以直接进入论文的引言与相关工作**，不是“写作建议”，也不是“结构骨架”。四个部件必须齐备、彼此承接、每条论断有引用或证据锚点。

| 题面四问 | 落到成稿的要求 | 核验工具 |
|---|---|---|
| 立得住 | 背景从领域脉络→具体问题→为什么现在做，句句有具体锚点 | `draft_review` + `detect-hype` |
| 分得清 | 相关工作按问题/方法/数据与评价分组，在同一维度比较取舍 | `draft_review` + `group_matrix` |
| 说得实 | 空白由 ≥2 篇已引工作的共同局限/未覆盖场景推出，并说明本文如何填补 | `draft_review` + `derive_gap` |
| 对得上 | 贡献逐条对应方法/图表/实验结果，引用能映射到 works | `draft_review` + `align-claims` |

## 何时触发 / 不触发

**触发**：写/改引言、研究背景、相关工作、研究空白、贡献表述；要求按路线分组比较、空白推导、贡献与图表对齐、引用覆盖。

**不触发**：纯翻译、纯语言润色、与引言无关的问答。误触发时说明边界并保持原文不变。

## 铁律

1. **Agent 主写**：四部件成稿必须由你基于真实材料撰写。**不要调用 `solve` / `render-draft` / `compose` 生成骨架**——它们只做字段拼接，不能形成可投稿的论证。
2. **每条引用有来源**：只用 case 中真实存在的 works；没有的文献不写、不猜 DOI、不补作者。引用 token 统一用 `[w1]` 形式，映射到 works id。
3. **每条空白有支撑**：空白句必须引用 ≥2 篇已引工作，并说明它们的共同局限/冲突/未覆盖场景；不能凭常识断言“尚未研究”。
4. **每条贡献有锚点**：贡献条目必须指向本文真实的方法、实验、图、表或数据；没有证据的“首次/首个/显著提升”一律删掉或标 `[待核实]`。
5. **不交预制答案**：必须处理平台给定 case，不得用预写引言冒充运行结果。

## 标准工作流

### 1. 读材料，抽取 works

读 `/input/case.json` 与 `task.md`，确认 `case_id`、论文主题、已有章节/结果、文献库格式、目标期刊/语言、输出契约。

若 case 里有 `works`/`references` 列表，直接归一化为 `/app/work/works.json`；若是 BibTeX/RIS/行式文本：

```bash
python scripts/intro_engine.py ingest '{"format":"bibtex","text":"..."}' > /app/work/ingested.json
```

从 `ingested.json` 取 `works` 写入 `/app/work/works.json`。每条至少保留：

```json
{"id":"w1","title":"...","authors":["Smith, A."],"year":2023,"source":"Fuel",
 "method":"CNN","problem":"岩相识别","data_eval":"acc 0.92",
 "applicability":"碳酸盐岩薄片","limitations":"标注成本高","conclusion":"优于传统方法"}
```

字段缺失就留空并在 `uncertainty` 标注，**不补造**。

### 2. 建本文主张与证据锚点

从 case 的方法/实验/结果/图表中整理 `/app/work/claims.json`：

```json
{"claims":[
  {"id":"c1","text":"本文提出分组比较框架","evidence_refs":["表2","§3.2"]},
  {"id":"c2","text":"在少标签条件下保持精度","evidence_refs":["图3","表4"]}
]}
```

每条 claim 必须能在 case 材料中找到对应；找不到的删掉，不写“预计/有望”充当结果。

### 3. 直接写成稿（核心步骤）

写 `/app/work/introduction_draft.md`，按四部件组织：

#### 研究背景（2–3 段）

- 第 1 段：领域脉络 + 具体任务/对象 + 为什么难（引用 2–4 篇）。
- 第 2 段：已有路线简述 + 它们留下的具体约束（引用 2–4 篇）。
- 第 3 段：本文切入点与目标（1–2 句），不夸大。
- 禁止空转句：“近年来受到广泛关注”“具有重要意义”“随着……快速发展”单独出现而无具体锚点。
- 每个背景判断至少一个 `[w#]`；没有引用的事实性判断改写为作者判断或删除。

#### 相关工作（按维度分组，2–4 组）

- 每组一个小标题，如“按方法路线：CNN / 半监督 / Transformer”“按数据与评价：公开数据 / 薄片 / 岩心尺度”。
- 每组 2–4 篇，按**同一维度**比较：问题设定、方法、数据与评价、适用条件、局限。
- 每篇写清“做了什么→结论→适用条件→局限”，禁止逐篇摘要拼接。
- 组末给一句取舍总结：哪类方法在什么条件下更合适、共同缺什么。
- 引用覆盖关键工作与近 3 年进展；works 中未被引用的关键条目要补进或说明排除理由。

#### 研究空白（1–2 段）

- 从已引工作的共同限制、未覆盖场景或冲突结论中推出，句式如“虽然 A 在……有效，B 在……改进，但二者均受制于……[w1,w2]；在……场景下尚无……”。
- 至少引用 2 篇；每条空白写清支撑 works 与推理链。
- 必须落到本文工作：本文用什么设计/数据/实验填补这条空白（1–2 句，引到 claim id）。

#### 贡献表述（2–4 条）

- 每条一个 bullet，格式“做了什么 + 在哪验证 + 结果/边界”，例如“提出 X 框架，在 Y 数据上验证，Z 指标提升”（图/表/§）。
- 不用“首次/首个/填补空白”除非 material 明确支持并有证据锚点。
- 每条贡献对应 `claims.json` 的 id 和 evidence_refs；没有锚点的删掉。

### 4. 成稿核验

```bash
python scripts/draft_review.py --draft /app/work/introduction_draft.md \
  --case /input/case.json --out /app/work/draft_review.json \
  --outdir /app/output
```

- `gate=fail`：先修 critical（缺部件、引用无法映射、空白支撑不足）。
- `gate=review`：逐条修 major（背景空转、相关工作未分组、贡献无锚点/夸大）。
- 修完重跑，直到 `gate=pass` 或只剩可解释的 warning。

可选的结构化检查（把背景/相关工作摘要/claims 填成 `input.json`）：

```bash
python scripts/intro_engine.py pipeline /app/work/pipeline_input.json --compact > /app/work/pipeline_brief.json
```

用 `group_matrix` 检查分组维度、`derive_gap` 检查空白支撑、`align_claims` 检查贡献锚点；结果并入 `result.checks`，不替代成稿。

### 5. 装配输出

写 `/app/output/result.json`，至少：

```json
{
  "case_id": "与输入一致",
  "status": "success | needs_attention | partial",
  "result": {
    "introduction_draft": "四部件完整成稿",
    "paragraphs": [
      {"part": "研究背景", "text": "...", "source_refs": ["w1","w2"], "status": "ok"},
      {"part": "相关工作", "text": "...", "source_refs": ["w1","w2","w3"], "status": "ok"},
      {"part": "研究空白", "text": "...", "source_refs": ["w1","w2"], "status": "ok"},
      {"part": "贡献表述", "text": "...", "source_refs": ["c1","表2"], "status": "ok"}
    ],
    "source_refs": ["w1","w2","w3","c1","表2"],
    "claims": [{"id":"c1","text":"...","evidence_refs":["表2"]}],
    "checks": {"draft_review": {...}, "pipeline": {...}},
    "delivery": {"draft_md": "/app/output/introduction_draft.md"},
    "summary": "四部件成稿；引用映射 X 条；空白支撑 Y 条；贡献锚点 Z 条"
  },
  "evidence": {
    "principles": {"立得住": "...", "分得清": "...", "说得实": "...", "对得上": "..."},
    "gap_support": {"空白1": ["w1","w2"]},
    "claim_to_evidence": {"c1": ["表2"]},
    "unmapped_citations": []
  },
  "uncertainty": {
    "needs_review": ["转述忠实度待回原文核对"],
    "missing_metadata": [],
    "note": "脚本只检查结构与映射；转述是否忠实、空白是否真成立、贡献是否夸大由 Agent 回原文复核"
  }
}
```

同时落盘：
- `/app/output/introduction_draft.md`（完整成稿）；
- `/app/output/draft_review.json`；
- `/app/output/source_map.json`（引用→works、claim→evidence）。

### 6. 最终自检

```bash
python scripts/validate_result.py --result /app/output/result.json \
  --outdir /app/output --case /input/case.json --main-field introduction_draft
```

`valid=false` 按 errors 修；不得带病交付。

## 异常处理

| 情形 | 处置 |
|---|---|
| works 为空 | 不写“已有研究表明”；只写材料内可支撑的背景，status=partial，标注文献库缺失 |
| 缺作者/年份/来源 | 保留空字段，`uncertainty.missing_metadata` 列出；不猜 |
| 引用查不到原文 | 只按 works 元数据转述，不扩写结论；`needs_review` 标注 |
| 缺图表/实验结果 | 贡献只写方法层，不写“提升 X%”；标 `[待核实]` |
| 目标期刊格式未知 | 用通用学术结构，`uncertainty` 说明格式未定 |
| 材料语言与目标语言不同 | 用目标语言写，引用保留原文；不逐句翻译 |
| 空白缺乏依据 | 不硬造；改为“本文关注……，尚需验证”，status=partial |

## 资源

- `scripts/intro_engine.py`：`ingest`/`detect-hype`/`group-matrix`/`derive-gap`/`align-claims`/`coverage`/`pipeline`
- `scripts/draft_review.py`：四部件齐全、引用映射、背景空转、分组、空白支撑、贡献锚点
- `scripts/validate_result.py`：result 契约与交付物自检
- `references/four_part_rubric.md`：四部件写作细则与反例
- `references/output_contract.md`：字段契约
- `examples/smoke_case.json`、`examples/draft.md`：接口示例（非正式答案）

## 限制与边界

- 不联网、不查文献数据库；只使用 case 提供的 works 与论文材料。
- 不做统计重算、不补实验；贡献中的数值必须来自材料原文。
- 不把“结构检查通过”当成“学术质量通过”；转述忠实度与空白成立性仍需逐条回原文核对。
