---
name: intro-gap-architect
description: 引言与相关工作结构化写作守门人。当任务涉及撰写或改进论文"引言/研究背景/相关工作/研究空白/贡献表述"，需要避免空转铺垫、把相关工作按统一维度分组比较、从已引文献缺口推出研究空白、让贡献表述与正文方法图表证据逐条对齐，或需要交付"可编辑稿件 + 来源映射 + 证据链"时使用本技能。通过确定性脚本把分组、推导、对齐等易含糊动作做扎实，价值判断给出可回溯依据而非臆测。不适用于与引言/相关工作无关的内容问答或纯翻译润色。
---

# 引言与相关工作架构师（Intro & Gap Architect）

面向学术论文"引言 + 相关工作"环节的结构化写作技能。目标不是"生成一段看起来通顺的文字"，而是让引言的**四个部件彼此承接、每条论断有出处、每个空白由已引文献推出、每条贡献都能在正文找到证据**。

围绕题面四个核心问题组织能力：

| 核心问题 | 含义 | 对应工具 |
|---------|------|---------|
| 立得住 | 背景指向真实脉络与具体问题，非"近年来受到广泛关注"式空转 | `detect-hype` |
| 分得清 | 相关工作按问题/方法/维度分组比较，非逐篇摘要拼接 | `group-matrix` |
| 说得实 | 研究空白由已引文献的缺口推出，附支撑文献 | `derive-gap` |
| 对得上 | 贡献与方法/图表/实验证据一一对应，不夸大 | `align-claims` + `coverage` |

## 何时触发 / 何时不触发

**触发**：任务中出现以下任一信号——
- 让撰写、改写、补全论文的引言、研究背景、相关工作、研究空白、贡献表述；
- 抱怨"引言太水/铺垫空泛/相关工作像流水账/研究空白站不住/贡献夸大"；
- 要求相关工作按维度分组比较、要求空白从文献缺口推导、要求贡献与图表对齐；
- 要求引言部分引用覆盖完整、元数据准确、论断与引用对应。

**不触发**：纯翻译、纯语言润色、与引言/相关工作无关的内容问答。被误触发时应说明"这属于其他写作任务，不是引言/相关工作结构化写作"并保持原文不变。

## 核心原则（贯穿所有动作）

1. **四件成套**：引言＝研究背景 + 相关工作 + 研究空白 + 贡献表述，四部分须齐备且彼此承接——背景引出问题，相关工作厘清已有解，空白指出未解，贡献说明本文如何填补。缺一即为不完整。
2. **证据绑定**：每条关于他人工作的转述、每个空白判断、每条贡献，都要能回到具体文献 id（背景/相关工作）或正文锚点（贡献）。只给结论不给定位视为未完成。
3. **写作与核对分离**：先用脚本做确定性的分组、推导、对齐计算，再由 Agent 做价值判断（转述是否忠实、空白是否真成立），两者分开执行，最后合并。不要一边写一边心算核对。
4. **诚实标注**：材料不足、文献库为空、字段缺失、空白缺乏依据、引用查不到原文、目标期刊格式未知——一律显式写入 `uncertainty` / `needs_review`，**绝不臆造文献、元数据、贡献或对照结果**。
5. **不交预制答案**：本技能处理平台给定的输入案例，不得用预写好的引言或答案替代实际运行。
6. **确定性动作交给脚本**：套话检测、分组、空白推导、对齐、覆盖检查必须用 `scripts/intro_engine.py` 实际运行得出，不靠模型心算。

## 工具：intro_engine.py

位置：技能目录下 `scripts/intro_engine.py`，纯 Python 3 标准库，无第三方依赖、无网络请求。

先确认可运行：
```bash
python scripts/intro_engine.py --help
```

### 子命令

| 子命令 | 作用 | 关键输出 |
|--------|------|---------|
| `detect-hype` | 立得住：空转铺垫检测 | `hype_sentences`、`holds_up`、`concrete_anchor_count` |
| `group-matrix` | 分得清：按统一维度建分组比较矩阵 | `groups`（含各维度 comparison）、`needs_review` |
| `derive-gap` | 说得实：从文献缺口推导空白（可解释链） | `gaps`（每条附 supporting_works/type/reasoning） |
| `align-claims` | 对得上：贡献与证据锚点对齐 | `aligned`、`unbacked`、`inflated` |
| `coverage` | 引用覆盖与元数据完整 | `recent_count`、`missing_metadata`、`has_recent` |
| `ingest` | 把 BibTeX/RIS/行式文本解析为 works | `works`、`work_count`、`missing_metadata` |
| `render-draft` | 可核验成稿草稿：仅用真实字段渲染四部件连贯成稿 | `draft_text`、`paragraphs`、`source_refs` |
| `compose` | 成稿草稿 + 结构骨架 + 来源映射 + 待确认项 | `draft`、`draft_text`、`sections`、`source_map` |
| `solve` | 端到端完成器：case.json →(ingest)→ 成稿 → result.json | `result.draft_text`、`delivery` |
| `compare` | 公平对照：基线四类失败 vs Skill 检出/拦截 | `gain`、`dimensions`、`verifiable` |
| `pipeline` | 串联五步 + 空白-贡献桥接 | 完整结构化结果；`--compact` 只回摘要+待确认项省 token |

输入为 UTF-8 JSON。推荐 solve 一步到位；或先 full 检查，再按需取成稿/骨架/对照：
```bash
python scripts/intro_engine.py pipeline input.json > result.json          # 全量四问检查
python scripts/intro_engine.py pipeline input.json --compact > brief.json # 省 token 摘要
python scripts/intro_engine.py solve case.json --out /app/output          # 端到端成稿+装配
python scripts/intro_engine.py render-draft input.json > draft.json       # 可核验成稿草稿
python scripts/intro_engine.py compose  input.json > draft.json           # 成稿+骨架+来源映射
python scripts/intro_engine.py compare  input.json > comparison.json     # 公平对照证据
# 外部文献：python scripts/intro_engine.py ingest '{"format":"bibtex","text":"..."}'
```

`detect-hype` 按**句子**切分逐句判锚点：套话句不会被同段的具体句"洗白"，这是对照案例暴露并修复的真实缺陷（见 `references/failure_patterns.md` F01）。
`compare.gain` 只度量可复现的"缺陷检出/拦截计数"，不编造平台质量分；对照协议见 `references/comparison_protocol.md`。

`input.json` 结构：
```json
{
  "case_id": "案例标识",
  "background": "研究背景段落文本",
  "works": [
    {"id":"w1","title":"...","authors":["Smith, A."],"year":2023,"source":"Fuel",
     "route":"深度学习路线","problem":"岩相识别","method":"CNN",
     "data_eval":"acc 0.92","applicability":"碳酸盐岩薄片",
     "limitations":"标注成本高","conclusion":"优于传统方法"}
  ],
  "claims": [
    {"id":"c1","text":"本文提出分组比较驱动的空白推导方法","evidence_refs":["表2","图3"]}
  ],
  "evidence_index": {"表2":"表2 分组矩阵结果","图3":"图3 空白推导流程"},
  "dimensions": ["问题设定","方法路线","数据与评价","适用条件","局限"],
  "target_scenario": "本文关注的目标场景关键词",
  "contribution_links": [{"gap_type":"共同限制","claim_id":"c1"}],
  "recent_years": 3,
  "current_year": 2026
}
```

字段说明见 `references/output_contract.md`。真实案例若给的是 PDF 或 BibTeX 原文，先按题面把事实底稿解析为上述结构（字段缺失如实留空并记录），再运行脚本。**PDF 解析须读取真实文件，不要从题名或标签臆测内容。**

## 标准工作流

接到任务后按此顺序执行，每步保留证据：

1. **读输入**：读取 `/input/case.json` 与 `task.md`，确认 `case_id`、任务口径、事实底稿、目标受众/文体/格式、稿件与文献库位置。**如实读真实文件。** 若文献以 BibTeX/RIS 给出，先跑 `ingest` 解析为 works 并看 `missing_metadata`，缺字段留空不臆造。
2. **立得住**：运行 `detect-hype`。对 `hype_count>0` 的句子，补入具体研究脉络、未解决问题或引用锚点；无锚点的空转铺垫必须改写。`holds_up=false` 不得进入下一步。
3. **分得清**：运行 `group-matrix`。以返回的 `groups[].comparison` 为横向视图，确保每个分组在**同一维度**上比较各工作取舍，而非逐篇摘要。`needs_review` 中的工作须人工指定分组后再跑。
4. **说得实**：运行 `derive-gap`。每条空白必须带 `supporting_works`（真实文献 id）与 `reasoning`。核对空白是否真由这些文献的共同限制/未覆盖/冲突推出；证据不足的空白删除或移入 `needs_review`，不得凭空断言。若提供 `contribution_links`，用 `gap_to_contribution` 检查每条空白是否被本文贡献填补。
5. **对得上**：运行 `align-claims` + `coverage`。`unbacked`（悬空/锚点不存在）与 `inflated`（夸大断言）必须逐条修正——补正文对应处证据，或删除/下调断言。`missing_metadata` 补齐字段；元数据真实性须逐条核验。
6. **成稿（完成器）**：`solve` 一步到位——读 case.json，若输入为 BibTeX/RIS 先 `ingest`，跑四问结构化检查，再由 `render-draft` 用真实字段把四部件写成连贯草稿，装配 result.json（`delivery` 记录落盘回执）。相关工作段落点名真实工作并附同维比较；空白段由 `supporting_works`+`reasoning` 推出；贡献段只用有证据的 claim，悬空/夸大者不写成事实。
7. **核对定稿**：成稿中每条论断附 `source_refs`，材料不足处用〔待核实〕标注，不新增材料外事实。价值判断（转述忠实、空白成立、元数据真实）须回原文确认；`compose` 的 `sections`/`source_map`/`pending_confirmation` 供逐条核对。
8. **验证增益**：运行 `compare` 得到该案例的公平对照证据（`gain` 确定性计数），确认四类门禁都拦截了基线会犯的错。
9. **装配输出**：按 `references/output_contract.md` 写入 `/app/output/result.json`，保留 `case_id` 与全部要求字段；可编辑稿件另存为文件。每条改动附"类型 → 理由 → 证据定位"。

## 输出契约要点

`result.json` 至少包含：
- `case_id`：输入案例标识；
- `status`：`ok` / `needs_attention` / `partial`；
- `result`：四部件成稿草稿（`draft_text`/`paragraphs`）+ 结构化检查结果（`background_check` / `related_work_matrix` / `research_gap` / `contribution_alignment` / `citation_coverage` / `gap_to_contribution`）；
- `evidence`：每条论断/空白/贡献的来源定位，以及四原则的落实说明；
- `uncertainty`：`needs_review` 清单 + 价值判断说明（哪些结论须 Agent 结合原文复核）；
- 可编辑稿件作为独立文件交付，路径记录在结果中。

完整字段定义见 `references/output_contract.md`。

## 异常处理

| 情形 | 处置 |
|------|------|
| 文献库为空 | `coverage` 返回 0，`derive-gap` 产出 needs_review；在结果标注"无文献可支撑相关工作与空白"，不臆造 |
| 背景无具体锚点 | `holds_up=false`，返回待补锚点清单，提示补入脉络/问题/引用 |
| 引用查不到原文 | 不据此下转述结论，标入 `needs_review`，说明"无法核验原文" |
| 空白缺依据 | `gap_count=0`，不生成空白段，标注"材料不足以推出空白" |
| 目标期刊格式未知 | 用通用学术文体，格式项写入 `uncertainty`，不假装知道特定规范 |
| 语言/学科切换 | 关键词与规则对中英文均生效；跨学科时 `dimensions` 可按领域调整 |
| PDF/文件读取失败 | 如实记录失败原因，产出 partial 结果并标明限制，不编造内容 |

## 复用与扩展

- `references/grouping_templates.md`：常见学科的分组维度模板与示例；
- `references/gap_patterns.md`：四类空白模式的判据、证据要求与常见误判；
- `references/claim_alignment.md`：贡献-证据对齐的判定规则与夸大词表；
- `references/output_contract.md`：输出字段定义与示例；
- `references/innovation_boundary.md`：相对通用模型/文献工具的创新边界与可复现证据；
- `references/comparison_protocol.md`：公平对照协议（增益如何度量、哪些结论须由平台给出）；
- `references/failure_patterns.md`：12 类失败模式、降级优先级与复用者自查；
- `examples/benchmark.json`：3 个跨学科公平对照案例（增益可复现）；
- `examples/`：最小调用示例与 45 项自验收（含成稿/solve 端到端）（`python examples/selftest.py`）。

本技能与 `citation-integrity`（引用一致性守门人）互补：本技能管引言结构与证据绑定，`citation-integrity` 管引用编号/去重/格式，可串联使用。

## 交付文件（solve 自动生成，评审可直接打开）

`solve /input/case.json --out /app/output` 在 `result.json` 之外还会写出：`draft.md`（成稿）、`deliverable.md`，以及 `deliverable.md`（人读版：概要 / 主结果 / 需人工确认 / 文件清单）。这些文件全部由 `result` 渲染而来，字段缺失就不生成对应文件、不补造；`delivery.artifacts` 里逐个记录文件名、字节数与用途。

## 引言叙事审计（narrative_audit，CARS 三语步）

除空转铺垫检测外，新增对引言修辞结构的确定性审计，写入 `result.narrative_audit`：

- `territory`：是否确立领域（recent years / 近年来 / 广泛关注等线索）；
- `niche`：是否指出缺口（however / remains unclear / 尚未 / 缺乏等）；
- `occupy`：是否说明本文如何填补（this paper / 本文提出等）；
- `citation_density`：带引用标记的句子占比（<34% 提示“背景缺文献支撑”）；
- `missing_moves` + `issues`：缺哪一语步，直接给出补写方向。

中英文线索均可识别；只报结构缺失，不代替作者判断缺口是否真成立。
