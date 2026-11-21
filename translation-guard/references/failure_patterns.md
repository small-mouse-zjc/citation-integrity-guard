# 失败模式案例（Failure Patterns）

面向复用者：记录科研文献翻译的高频失败场景、根因与本合同技能的确定性处置。非正式评测案例。

## F1 · 术语前后不一致

- **输入特征**：同一术语"porosity"在摘要译"孔隙度"、正文译"孔隙率"。
- **常见错误**：术语表写在提示里但模型没遵守，或逐段翻译各自为政。
- **正确处置**：`lock_terms` 编译强制提示串随每段翻译；`check_terms` 用 `variants` 检测同术语多译名。
- **证据**：`check_terms.issues[].type=inconsistent_term`。

## F2 · 长文漏段/重复翻译

- **输入特征**：跨页长文，段落多，逐段翻译时漏掉某段或重复译某段。
- **常见错误**：没有稳定段号，靠文本匹配对齐，段落改字后对不上。
- **正确处置**：`segment` 给稳定段号，`align` 按段号查漏段/重复/错位，`coverage` 量化。
- **证据**：`align.missing` / `extra` / `coverage`。

## F3 · 数字被改写（事实错误）

- **输入特征**：原文"18.5%"，译文写成"约20%"或"18%"。
- **常见错误**：模型"顺手"四舍五入或记忆错误。
- **正确处置**：`protect` 把数字变占位符强制保留；`restore` 核对；`verify` 检测 `number_lost`。
- **证据**：`verify.issues[].type=number_lost` + `restore.problems[].expected_raw`。

## F4 · 引用标记丢失

- **输入特征**：原文"[1]"译文里被删或改成"（Smith, 2020）"丢编号。
- **正确处置**：`protect` 保护 citation；`verify.citation_lost` 告警。
- **证据**：`verify.issues[].type=citation_lost`。

## F5 · 公式跨句误抽 / 符号失真

- **历史缺陷（本技能已修）**：早期 FORMULA_RE 不截断，把"L = ... (1). Only three basins"整句当公式；且正则把英文句号纳入。
- **正确处置**：公式在句号/分号/逗号处截断；希腊字母/上下标保真，不把 ASCII 改希腊字母。
- **证据**：`protect` 的 formula token 不含下一句内容。

## F6 · 数字单位模式边界错误

- **历史缺陷（本技能已修）**：早期 UNIT_RE 用 `\b` 边界，`18.5%` 的 `%` 后边界失效，且缺 mD（毫达西）单位，导致数字没被保护。
- **正确处置**：改用 `(?![A-Za-z])` 后向断言，补 mD/md 等单位。
- **证据**：`protect.stats.by_kind.number_unit` ≥ 实际数字个数。

## F7 · 否定/限定被译反或丢失

- **输入特征**：原文"No significant difference"，译文"观察到显著差异"（否定丢失，含义反转）。
- **正确处置**：`verify` 检测原文有否定而译文无对应 → `negation_maybe_lost`（疑似，交人工确认，因中英否定形态多变不断言）。
- **证据**：`verify.issues[].type=negation_maybe_lost`。
- **注意**：这是"疑似"不是硬错误，需人工复核——符合"译不准明确标注"。

## F8 · 术语表 None 导致崩溃

- **历史缺陷（本技能已修）**：`build_glossary` 中人工术语 Dict 可能为 None，未判空就 `.get()`，抛 AttributeError。
- **正确处置**：`_get` 对非 dict 输入返回默认值；所有术语条目访问判空。
- **证据**：selftest T1–T3 覆盖。

## F9 · 占位符被模型改写

- **输入特征**：模型把 `⟦P1_003⟧` 翻成"占位符P1_003"或删掉。
- **正确处置**：`restore` 检测占位符丢失且原文值不在 → `placeholder_lost`；若模型直接写了正确值 → 记 `preserved_direct` 不算错。
- **证据**：`restore.problems` / `preserved_direct_count`。

## F10 · 译不准被含混处理

- **输入特征**：术语拿不准、原文残缺、公式是图片。
- **正确处置**：一律进 `needs_review` 并说明位置与原因，不臆造译名/译文。
- **证据**：`evidence[].needs_review` / `verify.needs_review`。

## 复用建议

1. `build_glossary` 抽候选 → 人工确认译名 → `lock_terms` 生成提示串。
2. `segment` 编号 → `protect` 保护事实 → 交模型翻译（占位符原样保留）。
3. `restore` 回填 → `align` 对齐 → `check_terms` + `verify` + `evidence` 核验。
4. 硬错误必修；疑似项交人工；结论写进 `result.summary` 与 `verification`。
