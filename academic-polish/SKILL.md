---
name: academic-polish-source-preserving
description: 学术语言润色（保源最小编辑）。当任务要求对科研稿件/摘要/基金/审稿回复做语法句法修正、术语全篇统一、学术语域调整、语义保持润色，并交付润色后完整文本与逐句修改说明时使用。先建事实台账与术语表，再由 Agent 逐句做最小编辑，最后用确定性脚本核对数字、引用、否定、限定强度、术语与段落是否守恒；不代替模型写作、不补造事实、不把整段重写当润色。
---

# 学术语言润色：保源最小编辑（Academic Polish, Source-Preserving）

核心目标不是"文字更漂亮"，而是**改得对、说得像、没改坏、讲得清**：语法与表达真的变好，术语全篇统一，数字/引用/否定/限定强度一个不丢，每处改动能回原文并说明理由。

## 何时触发 / 不触发

**触发**：论文摘要/正文/引言/方法/讨论、基金申请书、学位论文、审稿回复、中英学术文本的语法修正、术语统一、语域改写、逐句修改说明、改写前后核验。

**不触发**：纯内容创作、新增论证/文献/数据、纯翻译、与润色无关的问答。误触发时说明边界，保持原文不变。

## 五条不变量（任何修改都不能破）

1. **N 数字与单位守恒**：数值、百分比、范围、样本量、年份、单位、公式编号不得改值、增删或换单位；原文没有的数字不得补。
2. **C 引用与交叉引用守恒**：`[1,2]`、`(Smith, 2020)`、`\cite{}`、图/表/式编号必须原样保留；不得新增原文没有的引用。
3. **H 断言强度守恒**：原文的 may/might/could/suggest/indicate/可能/或许/初步 等限定不得改成 prove/demonstrate/证明/证实；原文的否定（not/no/never/不/未/无）不得丢失。
4. **T 术语与缩写守恒**：同一概念全篇同一写法；术语表锁定的译名/缩写/大小写必须执行；不得自造新译名。
5. **M 最小编辑**：只改语法、搭配、冗余、连接、语域与句内清晰度；不整段重写、不改变论证顺序、不删限定条件、不把作者判断改成事实。

## 编辑分类（每条改动必须归入 G/T/R）

| 类型 | 允许改 | 不允许 |
|---|---|---|
| **G** Grammar & mechanics | 主谓一致、时态、单复数、冠词、介词、拼写、标点、重复词、断句 | 改数字/引用/否定/限定 |
| **T** Terminology & consistency | 术语统一、缩写首次展开、单位写法、大小写、图表编号格式 | 换概念、换译名、改引用 |
| **R** Register & cohesion | 口语→书面、冗余删减、连接词、句内逻辑、客观化 | 加强/削弱断言、添加原文没有的解释 |

遇到不属于 G/T/R 的"想改写内容"的冲动，一律不做；需要作者确认的写入 `uncertainty`。

## 六阶段工作流（必须按顺序）

### 1. 读输入，建事实台账

```bash
python scripts/case_io.py /input/case.json --out /app/work/case_texts.json --dump-text /app/work/source.txt
```

先读 `case_texts.json` 的 `texts.items` 与 `contract.fields`，确认：
- `case_id`、任务口径（润色哪些章节/是否双语/目标语域/字数限制）；
- 源文本（可能是 `.md/.txt/.docx/.pdf`；docx/pdf 已由 `case_io` 抽取）；
- 是否有术语表、风格指南、必须保留的句子、禁用表达；
- 平台 `output_contract` 要求哪些字段（结果里要原样覆盖）。

然后建台账：

```bash
python scripts/polish_audit.py ledger --input /app/work/source.txt \
  --termbase /app/work/termbase.csv --out /app/work/fact_ledger.json
```

台账含段落、句子、数字、引用、限定词、否定词、标题、图表指向、术语。**逐项读一遍**，把它们当作后续不可丢的锚点。

### 2. 锁定术语与语域

- 若 case 提供术语表，复制为 `/app/work/termbase.csv`（列：`source,target,forbidden`），缺失字段留空。
- 若未提供，从台账中挑出高频专业术语、缩写、变量名，建最小术语表；只锁"原文已经确定"的写法，不新造译名。
- 读 `references/terminology.md` 与 `references/hedge_ladder.md`，确定目标语域与限定强度梯度。

### 3. 逐句最小编辑（Agent 主写）

**先写完整改文，再谈核验。** 按段落顺序逐句改：
- 只做 G/T/R 三类改动；每句改完对照原文，确认 N/C/H 未变；
- 长句可拆分、短句可合并，但不得丢限定条件、不得改因果/让步/否定方向；
- 术语按表锁定；缩写首次出现展开，后文统一；
- 不添加原文没有的事实、评价、文献、数据、机制解释；
- 原文清楚且无误的句子**保持不动**，不要为了"看起来改过"而重写。

把改文写入 `/app/work/polished.md`（段落间空行）。同时维护 `changes` 列表：每条含 `source_sentence`、`revised_sentence`、`type`（G/T/R）、`reason`、`source_ref`（段号/句号）。

若 case 要求双语/对照，另存 `/app/work/bilingual.md`，逐段原文—译文对应；没有要求则不额外生成。

### 4. 全篇一致性回扫

改完通读一遍，专查：
- 同一术语/缩写是否全篇同一写法（标题、摘要、正文、图注、结论）；
- 时态、语态、人称是否统一；
- 数字格式（小数位、千分位、百分号、单位空格）是否统一；
- 图表/公式/章节编号是否连续，首次提及是否在前；
- 段落之间连接是否自然，是否有重复句、漏句、错位。

### 5. 保源核验（脚本）

```bash
python scripts/polish_audit.py check \
  --source /app/work/source.txt --revised /app/work/polished.md \
  --termbase /app/work/termbase.csv --out /app/work/audit.json \
  --outdir /app/output
```

看 `gate`：
- `pass`：进入装配；
- `review`：逐条读 `violations`，能改则改，改不了写进 `uncertainty`；
- `fail`：**必须修到没有 critical 才能交付**。典型 critical：`number_missing`、`citation_missing`、`negation_dropped`、`hedge_dropped`、`paragraph_dropped`。修完重跑，直到 `gate != fail`。

`violations` 每条都带原文句、改文句、定位；逐条处理，不要只看计数。

### 6. 装配输出

写 `/app/output/result.json`，至少包含：

```json
{
  "case_id": "与输入一致",
  "status": "success | partial | needs_attention",
  "result": {
    "polished_text": "润色后的完整文本",
    "paragraphs": [
      {"id": "P1", "source_ref": "原文段1", "text": "改文段1", "changes": ["S1"]}
    ],
    "changes": [
      {"id": "S1", "type": "G", "source_sentence": "...", "revised_sentence": "...",
       "reason": "...", "source_ref": "P1-S1"}
    ],
    "termbase": [{"source": "...", "target": "...", "forbidden": "..."}],
    "audit": {"gate": "pass", "counts": {...}, "violations": [...]},
    "summary": "一段话：改了哪几类、保住了哪些硬事实、还剩哪些需作者确认",
    "artifacts": {"polished_md": "/app/output/polished.md", "audit_json": "/app/output/polish_audit.json"}
  },
  "evidence": {
    "principles": {"改得对": "...", "说得像": "...", "没改坏": "...", "讲得清": "..."},
    "preserved": {"numbers": [...], "citations": [...], "hedges": [...], "negations": [...]},
    "audit_ref": "/app/work/audit.json"
  },
  "uncertainty": {
    "needs_author_confirmation": ["术语X是否应译为Y"],
    "not_polished": ["因原文不清/缺上下文未改的句子"],
    "note": "脚本只做守恒检查；措辞质量与原意忠实度由 Agent 逐句复核"
  }
}
```

同时落盘：
- `/app/output/polished.md`（完整改文）；
- `/app/output/changes.json`（逐条改动）；
- `/app/output/audit.json`（核验结果）；
- 若 case 明确要求 Word：`python scripts/office_io.py write --input /app/output/polished.md --out /app/output/polished.docx`，并在 `result.delivery` 记录路径。

最后自检：

```bash
python scripts/validate_result.py --result /app/output/result.json \
  --outdir /app/output --case /input/case.json
```

`valid=false` 时按 errors 修，不要带病交付。

## 异常处理

| 情形 | 处置 |
|---|---|
| case 是 PDF 且无文字层 | `case_io` 会报 `pdf_text_unavailable`；如实标 partial，不猜内容 |
| docx 有批注/修订痕迹 | 纯文本读取会丢失痕迹；在 uncertainty 说明，必要时请作者提供干净版 |
| 源文本语言混杂 | 分语言段落处理；术语按各自语言锁定；不强行统一 |
| 术语表冲突 | 不擅自选一个；列入 `needs_author_confirmation`，正文保持原写法 |
| 原文句子本身有事实/逻辑问题 | 不代作者改事实；标 `needs_author_confirmation`，只做语言层修正 |
| 字数限制与保源冲突 | 优先保 N/C/H；删减只删冗余表达，并在 changes 说明 |
| 无法确定该不该改 | 不改，列入 `not_polished`；宁少改，不乱改 |

## 资源

- `scripts/case_io.py`：读 case.json / txt / md / docx / pdf，抽取文本与 output_contract 字段
- `scripts/polish_audit.py`：事实台账 `ledger` + 保源核验 `check`（数字/引用/否定/限定/术语/段落/标题/图表指向）
- `scripts/validate_result.py`：result.json 契约与交付物自检
- `scripts/office_io.py`：无依赖 docx 读写
- `references/protocol.md`：五不变量与六阶段细则
- `references/hedge_ladder.md`：限定强度梯度与改法
- `references/terminology.md`：术语表格式与锁定规则
- `references/edit_taxonomy.md`：G/T/R 分类与正反例
- `references/output_contract.md`：字段契约
- `examples/`：最小示例、正例/反例、自测

## 限制与边界

- 本技能不生成新论证、不补文献、不补数据；只做语言层最小编辑。
- 脚本不判断"这句话学术不学术"，只判断守恒与结构；语域质量由 Agent 负责。
- 不联网；不虚构术语译名；拿不准的写法一律交作者确认。
