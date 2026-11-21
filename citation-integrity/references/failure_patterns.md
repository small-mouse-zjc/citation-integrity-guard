# 失败模式案例（Failure Patterns）

面向复用者：记录基础 Agent 与引用管理工具在真实稿件上高频出错的场景、根因与本合同技能的确定性处置。每条给出"输入特征 → 错误表现 → 正确处置 → 可核验证据"。这些是可分享的实践经验，非正式评测案例。

---

## F1 · DOI 前缀/大小写不一致导致重复条目

- **输入特征**：同一文献一条写 `10.1016/j.fuel.2020.1`，另一条写 `https://doi.org/10.1016/J.FUEL.2020.1`。
- **常见错误**：按字符串比对判为两条，文后表出现重复编号。
- **正确处置**：`_norm_doi` 去协议前缀、去 `doi:`、统一小写、去尾点后精确比对（`doi_exact`，置信 0.99）。
- **可核验证据**：`decisions[].rule=doi_exact`、`evidence` 写明归一化后的 DOI。

## F2 · 中英文题名/单复数差异

- **输入特征**：`Phase Behavior` vs `Phase Behaviours`。
- **常见错误**：漏并，或反过来把不同研究误并。
- **正确处置**：NFKC + 去变音 + 去标点后计算相似度；须同时满足第一作者相同且年份相同才合并（`fuzzy_title_author_year`，0.82）。
- **证据**：`evidence` 含相似度数值、作者、年份三要素。

## F3 · 预印本与正式版被误并 / 漏标

- **输入特征**：题名相近、作者相同、年份不同、DOI 前缀为 `10.48550/arxiv.*` 与期刊 DOI。
- **历史缺陷（本技能已修）**：旧逻辑仅在 `merged=True` 时记录低置信判据，`version_variant` 返回"不合并"，导致疑似版本关系被静默丢弃、不进 `needs_review`。
- **正确处置**：只要有判据命中（`conf>0`）却未达合并阈值，一律记入 `not_merged_below_threshold` 并置 `status=needs_review`，交人工确认。
- **证据**：`stats.needs_review_count≥1`、`decisions[].evidence` 说明"疑似预印本与正式版"。

## F4 · 同名作者不同文献被误并

- **输入特征**：同一第一作者、同一年，但题名主题完全不同。
- **正确处置**：相似度阈值 0.86 硬门槛，低于则不合并；`no_match` 不产生 decision。
- **证据**：`merged_count=0`。

## F5 · 编号未按首次出现顺序

- **输入特征**：正文首次出现 `[2]`，之后才 `[1]`。
- **常见错误**：沿用原编号，顺序编码制不成立。
- **正确处置**：`renumber` 按首次出现重排，输出 `mapping` 与改写后的 `rewritten_manuscript`（只换标记不改措辞）。
- **证据**：`mapping` + `rewrite_changes` 逐条列出"原标记→新标记"。

## F6 · 悬空引用与未引用条目

- **输入特征**：正文 `[7]` 但文末只到 `[4]`；或文末 `[3]` 正文从未出现。
- **正确处置**：`verify` 双向检查，分别输出 `dangling_citations` 与 `uncited_entries`。
- **证据**：`problems` 列表逐条说明；`compare` 可证明修复前后问题项下降。

## F7 · "表1/图2"被误判为数据论断需要引用

- **输入特征**：句子"结果见表1。"含数字但并非实证数据。
- **历史缺陷（本技能已修）**：旧 `NUMERIC_SIGNAL` 把任意数字当数据信号，"结果"被当论断词，产生伪 citation gap。
- **正确处置**：先用 `REF_NUM` 剥离图表/章节编号，仅认"带单位的数据或小数/百分数"；论断词去掉"结果/结论"等泛词。
- **证据**：`place_citations` 对"结果见表1"返回 `needs_citation=false`。

## F8 · 逐句核验烧掉模型请求额度

- **输入特征**：64 请求 / 900 秒预算下，对每句论断都让模型判断"是否与所引文献匹配"。
- **正确处置**：`claims` 做确定性预筛——元数据异常（缺题名/作者/年份、DOI 畸形、无出处）+ 主题词重叠三档（suspicious/review/plausible），只把 `suspicious_claims` 交模型/人工复核，把 O(n) 判断降到 O(可疑)；`pipeline --compact` 再省输出 token。
- **证据**：`claim_check.stats.suspicious_claim_count` 明确列出需复核数量。

## F9 · 字段缺失被静默忽略或臆造补齐

- **输入特征**：CNKI 导出缺年份、BibTeX 缺作者。
- **正确处置**：解析与归一化阶段把缺失字段写入 `issues`/`metadata_anomalies`，保留已知字段，绝不编造。
- **证据**：`issues[].type=missing_fields`、`anomalies[].type=year_missing/authors_missing`。

## F10 · 正文年份与所引条目年份不符

- **输入特征**：正文写"（Smith, 2018）"但所引条目年份为 2021。
- **正确处置**：`claims` 比对正文提及年份与条目 `year`，输出 `year_mismatch`。
- **证据**：`claim_results[].findings[].type=year_mismatch`。

## 复用建议

1. 先用 `ingest` 把原始文献库转成结构化 entries，避免手工逐条誊抄（省请求）。
2. `normalize` 后优先处理 `needs_review`，不要直接接受自动合并。
3. `renumber` 交付 `rewritten_manuscript` 作为可编辑稿件底稿。
4. `place` 定位缺引论断句，`claims` 只复核可疑项。
5. `verify` + `compare` 形成修复前后可验证闭环，写进 result 的 `summary`。
