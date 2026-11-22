---
name: academic-polish
description: 学术语言润色守门与完成器。当任务涉及科研稿件语法句法修正、术语全篇一致性、学术语气与语域贴合、语义保持与最小编辑、中英文表达质量改进，或需要"润色后完整文本＋逐句修改说明"的交付与核验时使用本技能。通过确定性脚本把高置信度硬错误检测、术语锁定回扫、语域诊断、数字单位引用图表与限定强度守护、逐句原文—改文—理由对照做准确，并对无真实改文处标〔待润色〕、对不确定处显式标注而非臆造。不适用于纯内容创作或与润色核验无关的问答。
---

# 学术语言润色守门/完成器（Academic Polish）

面向真实科研稿件的润色技能。本技能既是从真实 case 出发、端到端交付可编辑润色成稿的**完成器**，也是把题面四问（**改得对 / 说得像 / 没改坏 / 讲得清**）做成确定性、可回溯动作的**核验器**。润色措辞由模型完成，但脚本会读取真实输入、切句、建守护清单、渲染逐句成稿草稿、核验限定强度守恒并自动装配 `/app/output/result.json`。目标不是"文字更漂亮"，而是**硬错误真改掉、术语全篇统一、原意数值引用不丢、每处修改能回原文并说明理由**。

## 何时触发 / 何时不触发

**触发**：科研论文/摘要/基金/学位/审稿回复的语法修正、术语统一、语域改写、语义保持润色、中英表达质量改进、逐句修改说明、改写前后核验。

**不触发**：纯内容创作、与润色核验无关的内容问答、纯事实查询。被误触发时说明边界，不擅自改写。

## 核心原则（题面四问）

1. **改得对**：`detect_grammar` 只标高置信度硬错误（重复词、双冠词、句首小写、标点重复、中英粘连），给出原文与理由，不替模型重写整段——避免"换种说法掩盖错误"。
2. **说得像**：`check_terms` 让术语表真正执行全篇一致性回扫；`check_register` 诊断口语化/绝对化/宣传化/人称误用，按目标语域给建议。
3. **没改坏**：`protect` 把数字单位、引用编号、图表指向、公式、化学式、限定词、否定词抽成守护清单；`check_preserve` 逐项核对原文与真实改文，限定强度被加强或削弱、否定丢失、引用被改即告警。
4. **讲得清**：`segment` + `evidence` + `render_draft` 逐句给"原文—改文—修改类型—理由—守护依据—核验结论"，第三方可据此判断这处该不该改。

## 诚实边界（不臆造）

- 脚本**不替代模型做润色措辞**。无真实 `polished` 文本的句一律标〔待润色〕，绝不臆造改文或术语写法。
- 无真实改文时 `check_preserve` 不做守恒核验，显式写"无真实 polished 文本，无法核限定强度守恒"。
- 硬错误检测为保守高置信度模式，未标句子不等于无误，须通读复核；限定强度、因果边界、语域贴合属价值判断，进 `needs_review`。

## 工具：polish_engine.py

位置 `scripts/polish_engine.py`，纯 Python 标准库、无网络、无第三方依赖，3.8+ 可运行。

```bash
python scripts/polish_engine.py --help
```

子命令：`segment` / `protect` / `detect_grammar` / `check_terms` / `check_register` /
`check_preserve` / `verify` / `evidence` / `pipeline`（`--compact` / `--with-draft`）/
`render-draft` / `solve`。

### 中间表示（polish JSON）

```json
{
  "case_id": "案例标识",
  "target_register": "journal",
  "source_lang": "en",
  "paragraphs": [
    {"id":"P1","section":"Abstract","kind":"body","text":"原文段落"}
  ],
  "glossary": [{"source":"porosity","target":"孔隙度","scope":"global"}],
  "polished": {"P1":"真实润色段落文本（可选）"}
}
```

## 真实输入字段（solve 适配）

`solve` 从 case.json 出发，支持以下真实字段（详见 `references/output_contract.md`）：
- `paragraphs`：内联结构化段落；
- `source_text`：单篇纯文本，按空行/换行切段；
- `source_files`：`[路径]` 或 `{名:路径}`，读 `.txt/.md/.json` 真实稿件；
- `glossary_file`：术语表文件（.json 或两列 TSV/CSV）；
- `polished` / `polished_files`：真实润色文本（`{段号:文本}` 或 `{段号:路径}`）。

## 端到端一次交付（推荐）

```bash
python scripts/polish_engine.py solve /input/case.json --out /app/output
```

一次运行完成：真实材料适配 → 四问检查 → 逐句润色成稿 → 装配 `/app/output/result.json`，
返回 `delivery`（`written/path/bytes`）回执。`result.json` 含
`polished_draft`/`draft_text`/`blocks`/`verification`/`evidence_index` 与 `case_id`。

## 公平对照

```bash
python scripts/compare_engine.py examples/smoke_input.json
```

对照只呈现四问检查机制的可运行证据与逐句成稿结构，**不编造平台质量分/效率分**；
正式质量对照由平台固定案例与白板给出。

## 资源清单

- `scripts/polish_engine.py`：主引擎（守门 + 完成器）。
- `scripts/compare_engine.py`：公平对照证据引擎。
- `examples/`：selftest、benchmark、最小示例、冒烟输入输出。
- `references/`：输出契约、守护规则、语域指南、术语格式、失败模式、创新边界、核验清单、词表。

## 限制

- 不调用外部润色/翻译服务，不臆造润色措辞；真实改文由模型在锁定约束下补全。
- 硬错误检测面向高置信度模式，不保证覆盖全部语法错误。
- 资源规模遵守 ≤50 个 UTF-8 文本文件、单文件 ≤500KB、总计 ≤2MB、无软链。
