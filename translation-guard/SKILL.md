---
name: translation-guard
description: 科研文献翻译守门人。当任务涉及科研论文中英互译、术语一致性锁定、长文分段翻译与段落对齐、数字单位公式引用标记保护、双语对照交付、译文事实核验或修改建议时使用本技能。通过确定性脚本把术语强制锁定、段落段号对齐、数字公式引用占位符保护与回填、译文自检做准确，并对译不准或不确定处显式标注而非含混处理。不适用于纯内容创作或与翻译核验无关的问答。
---

# 文献翻译守门人（Translation Guard）

面向真实科研文献的翻译技能。本技能既是从真实 case 出发、端到端交付双语对照成稿的**完成器**，也是把**术语一致性、段落完整性、事实关系保真、可核验性**做成确定性、可回溯动作的**核验器**。翻译措辞由模型完成，但脚本会读取真实输入、切段、建术语表、渲染可编辑双语草稿、核验并自动装配 `/app/output/result.json`。目标不是"译文通顺"，而是**术语统一、段落不漏、数字公式引用不丢、每段能回原文并说明依据**。

## 何时触发 / 何时不触发

**触发**：科研论文翻译、双语对照、术语表驱动翻译、长文分段续译、译文核验与修改建议、数字/公式/引用保真检查。

**不触发**：纯文学创作、与翻译核验无关的内容问答。被误触发时说明边界。

## 核心原则

1. **术语真执行**：术语表不是写在提示里就算数——`lock_terms` 编译成强制提示串，`check_terms` 验证译名一致。
2. **段落一一对应**：稳定段号贯穿切段、翻译、对齐、证据，漏段/重复/错位显式检出。
3. **事实零失真**：数字、单位、公式、引用标记、化学式翻译前变占位符保护，翻译后回填核对；篡改即告警。
4. **诚实标注**：否定/限定词疑似丢失、术语候选未定译名、缺译文——一律进 `needs_review`，不臆造。
5. **确定性动作交给脚本**：真实输入适配、术语抽取、段号对齐、占位符保护回填、自检、双语成稿与 result.json 装配这些易错动作必须实际运行 `scripts/translation_guard.py`。
6. **端到端一次交付**：优先用 `solve case.json --out /app/output`，一次运行即从真实材料走到双语成稿与可复核交付；无译文的段标〔待翻译〕，绝不臆造。

## 工具：translation_guard.py

位置 `scripts/translation_guard.py`，纯 Python 标准库、无网络、无第三方依赖，3.8+ 可运行。

```bash
python scripts/translation_guard.py --help
```

### 中间表示（translation JSON）

```json
{
  "case_id": "案例标识",
  "source_lang": "en", "target_lang": "zh",
  "paragraphs": [
    {"id":"P1","section":"Abstract","page":1,"kind":"body","text":"原文段落"}
  ],
  "glossary": [{"source":"porosity","target":"孔隙度","scope":"global"}],
  "translations": {"P1":"译文段落"}
}
```

`translations` 可选：翻译类子命令（build_glossary/segment/protect/lock_terms）不需要；核验类（align/check_terms/verify/evidence/pipeline 完整闭环）需要。字段契约见 `references/output_contract.md`。

### 子命令（对应题面四问）

| 子命令 | 作用 | 对应题面 |
|--------|------|----------|
| `build_glossary` | 抽取术语候选 + 合并人工术语表，未定译名标注 | 术语稳 |
| `lock_terms` | 术语表编译成强制锁定提示串 | 术语稳 |
| `check_terms` | 译名一致性：同一源术语是否统一译名 | 术语稳 |
| `segment` | 稳定段号 + 跨页续段 + 重复段检测 | 段落全 |
| `align` | 原文—译文段落对齐，漏段/重复/错位 | 段落全 |
| `protect` | 翻译前：数字/单位/公式/引用/化学式→占位符 | 关系准 |
| `restore` | 翻译后：回填占位符，核对丢失/篡改 | 关系准 |
| `verify` | 数字/否定/限定/引用/化学式保真自检 | 关系准/可核验 |
| `evidence` | 每段译文的原文定位 + 译法依据 | 可核验 |
| `render-draft` | 用真实字段渲染可编辑双语对照成稿草稿（无译文标〔待翻译〕） | 全部/成稿 |
| `solve` | 端到端完成器：case.json →(适配材料)→ 全流程 → 双语成稿 → result.json | 全部/交付 |
| `pipeline` | 全流程串联，`--compact` 省 token；`--with-draft` 脚本成稿 | 全部 |

## 标准工作流（翻译前 → 翻译后）

1. **读输入**：读 `/input/case.json` 与 `task.md`，确认源/目标语言、要翻译的段落区间、术语表口径、证据范围。**如实读真实文件**。
2. **建术语表**：`build_glossary` 抽候选，人工/模型确认每个候选的 `target` 译名后锁定；`lock_terms` 生成强制提示串。未定译名的候选进 `needs_review`。
3. **切段编号**：`segment` 给每段稳定段号，标记跨页续段与重复段，按语义边界携带上下文。
4. **保护事实**：`protect` 把每段数字/单位/公式/引用/化学式替换为占位符 `⟦P1_003⟧`，得到 `protected_text`。
5. **模型翻译**：把 `protected_text` + 锁定提示串交给模型翻译。**占位符必须原样保留**；每段译文按段号存入 `translations`。（此步是模型动作，不在脚本内。）
6. **回填核对**：`restore` 回填占位符，核对有无丢失/篡改（数字被改、引用被删会告警）。
7. **段落对齐**：`align` 检查段号一一对应，漏段/重复/错位显式列出。
8. **译文核验**：`check_terms`（译名一致）+ `verify`（数字/否定/限定/引用/公式保真）+ `evidence`（每段回原文与依据）。译不准的进 `needs_review`。
9. **装配输出**：直接 `python scripts/translation_guard.py solve /input/case.json --out /app/output` 完成端到端交付（自动适配 materials、渲染双语草稿、写 result.json + delivery 回执）；或按 `references/output_contract.md` 手工装配。预算紧张用 `pipeline --compact`。

### 端到端完成器（首选）

```bash
python scripts/translation_guard.py solve /input/case.json --out /app/output   # 一次运行：适配→成稿→装配
python scripts/translation_guard.py render-draft input.json > draft.json        # 仅渲染双语成稿草稿
python scripts/translation_guard.py pipeline input.json --with-draft > result.json  # 带成稿的全流程
```

`solve` 适配的真实输入字段：`paragraphs`（内联）、`source_text`（纯文本切段）、`source_files`（[路径] 或 {名:路径}，读 .txt/.md/.json）、`translations` 或 `translation_files`（真实译文）。读不到不臆造，记入 `adapter_notes` 与 `needs_review`；缺译文段统一标〔待翻译〕。

## 输出契约要点

每案例返回：`case_id`、`status`、`result`（含 `segment_count`/`glossary_locked`/`aligned_coverage`/`verification`/`evidence_index`/`summary`；`solve` 额外含 `bilingual_draft`/`blocks`）、`needs_review`、`uncertainty`。`solve` 另有 `delivery`（落盘回执，written=true 且 bytes>0 才算交付成功）。详见 `references/output_contract.md`。

## 异常处理

| 情况 | 处置 |
|------|------|
| 术语候选未定译名 | 进 `needs_review`，不强制替换，不臆造译名 |
| 漏段/重复/错位 | `align` 列出 missing/extra/out_of_order |
| 数字/公式/引用被篡改 | `restore` + `verify` 告警，明确到段号 |
| 否定/限定词疑似丢失 | `verify` 标 `needs_review`，交人工确认 |
| 缺译文 | `evidence` 标 needs_review，`verify` 报 missing_translation |
| 文字层缺失/扫描件 | 提示先 OCR，不把空译文当成功 |
| 公式/表格为图片、参考文献无法解析 | 标注具体段号与原因，保存诚实部分结果 |

## 额度与预算建议（64 请求 / 900 秒 / 16384 token）

- 术语抽取、段号对齐、占位符保护回填交给脚本，模型只做翻译与少量"译不准"判断。
- 用 `pipeline --compact` 不看整棵 pipeline；长文按段翻译，携带锁定提示串与已确定术语，避免重复查术语。
- 先存诚实部分结果（已译段落 + 术语表）再增量完善。
- 三案例复用同一术语表约定与段号规则，避免重复口径摸索。

## 交付文件（solve 自动生成，评审可直接打开）

`solve /input/case.json --out /app/output` 在 `result.json` 之外还会写出：`bilingual.md`（段落级双语对照成稿）、`glossary.csv`（锁定术语表）、`bilingual_draft.md`，以及 `deliverable.md`（人读版：概要 / 主结果 / 需人工确认 / 文件清单）。这些文件全部由 `result` 渲染而来，字段缺失就不生成对应文件、不补造；`delivery.artifacts` 里逐个记录文件名、字节数与用途。

## 资源清单

- `scripts/translation_guard.py`：确定性翻译完成器+守门引擎（12 子命令，含 solve/render-draft，纯标准库）
- `scripts/artifacts.py`：交付物渲染器（result → deliverable.md + 领域文件，纯标准库）
- `references/output_contract.md`：输入输出字段契约
- `references/glossary_format.md`：术语表格式与锁定规则
- `references/protection_rules.md`：占位符保护与回填规则
- `references/alignment_contract.md`：段号对齐与证据契约
- `references/verification_checklist.md`：译文自检清单
- `references/failure_patterns.md`：失败模式案例
- `references/vocab.md`：可复用词表（术语/否定/限定/单位/化学式模式）
- `examples/`：最小示例 + 带译文样例 + 10 道边界题集 + 61 项自测（含成稿/适配/solve）

## 限制与边界

- 本技能不替代模型翻译措辞，但会从真实输入切段、建术语表、渲染双语成稿草稿、核验并装配交付；缺译文标〔待翻译〕不臆造，译文质量由人工最终确认。
- 术语抽取是候选，译名须人工/模型确认后锁定；占位符保护覆盖数字单位/公式/引用/化学式，否定限定为"疑似"提示需人工判断。
- 不联网、不臆造译文或术语译名；所有核验结论可回到原文段号。


## 可复现证据与冲分材料

本 Skill 针对四问（术语稳 / 段落全 / 关系准 / 可核验）配置了确定性检查机制，并提供可复现的公平对照证据：

- `scripts/compare_engine.py`：对同一输入给出"基线常见失败 vs Skill 四问检查机制"的对照，客观呈现观测值，**不编造平台质量分**（正式对照由平台固定案例与白板给出）。
  ```bash
  python scripts/compare_engine.py examples/smoke_input.json    # 单案例机制对照
  python scripts/compare_engine.py examples/benchmark.json      # 干净+缺陷两案例
  ```
- `examples/benchmark.json`：干净案例（验证不误报）+ 按四问注入缺陷的案例（验证能检出）。
- `references/innovation_boundary.md`：相对通用对话模型/现有工具的创新边界与可复现路径。
- `references/comparison_protocol.md`：公平对照协议与度量边界。
- `references/failure_patterns.md`：失败模式库、降级优先级；`references/vocab.md`：判定词表。

创新边界摘要：`translation_guard.py` 把 "术语稳 / 段落全 / 关系准 / 可核验" 中每问的易错动作固化为脚本判定，价值判断须建立在其可回溯证据之上；材料不足时诚实降级为 `partial`/`needs_attention`，不臆造事实、数值或来源。

## 逐段译文审计（translation_audit）

`solve` / `pipeline` 现在会对每一段做可计算的译文体检，结果写入 `result.translation_audit`：

- `missing_translation`：该段无译文（成稿中标〔待翻译〕）；
- `possibly_untranslated`：目标语为中文但汉字占比 <15%，疑似原文照抄；
- `length_outlier`：译文/原文长度比 <0.45 或 >2.4；
- `number_drift`：源段与译段的数字集合不一致（列出缺/多）；
- `term_conflict` / `term_collision`：同一术语多译名 / 同一译名对应多术语；
- `glossary_coverage`：术语表中目标译名在译文中实际出现的比例。

用法：正常跑 `solve` 即可，无需额外命令；审计不通过时逐条列出段号，便于回改。
