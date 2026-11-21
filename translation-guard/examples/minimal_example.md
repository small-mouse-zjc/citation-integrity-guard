# 最小调用示例

> 下列输入与输出均为**示例**，用于说明接口和流程，**不是**平台正式测试案例结果，不得作为预制答案提交。

## 1. 准备输入

`examples/smoke_input.json`（示例片段）：
```json
{
  "case_id": "demo",
  "source_lang": "en", "target_lang": "zh",
  "paragraphs": [
    {"id":"P1","section":"Abstract","text":"Carbonate reservoirs are not always homogeneous. The porosity is approximately 18.5% [1]."}
  ],
  "glossary": [
    {"source":"Carbonate reservoirs","target":"碳酸盐岩储层"},
    {"source":"porosity","target":"孔隙度"}
  ],
  "translations": {"P1":"碳酸盐岩储层并非总是均质的。孔隙度约为 18.5% [1]。"}
}
```

## 2. 翻译前（准备）

```bash
# 术语候选 + 锁定提示串
python scripts/translation_guard.py build_glossary examples/smoke_input.json
python scripts/translation_guard.py lock_terms    examples/smoke_input.json
# 段落编号 + 事实保护（把 protected_text 交模型翻译，占位符原样保留）
python scripts/translation_guard.py segment examples/smoke_input.json
python scripts/translation_guard.py protect examples/smoke_input.json
```

`protect` 输出示意：
```json
{"protected":[{"id":"P1","protected_text":"... 18.5% ⟦P1_002⟧ ...",
  "tokens":[{"placeholder":"⟦P1_002⟧","kind":"citation","raw":"[1]"}]}]}
```

## 3. 翻译后（核验）

```bash
python scripts/translation_guard.py pipeline examples/smoke_input.json > result.json
python scripts/translation_guard.py pipeline examples/smoke_input.json --compact > summary.json
```

## 4. 示意输出（节选，标注为示例）

`result.result.summary`（示意）：
```
段 1；术语锁定 2/2；保护元素 2（引用1/数字1）；译文覆盖 100%；核验问题 0
```

`result.result.verification`（示意）：
```json
{"consistent":true,"issues":[],"needs_review":[]}
```

`result.result.evidence_index[0]`（示意，可回原文）：
```json
{"id":"P1","source_location":{"section":"Abstract","paragraph_id":"P1"},
 "source_head":"Carbonate reservoirs...","translation_head":"碳酸盐岩储层...",
 "basis":[{"type":"glossary","source":"porosity","target":"孔隙度"}],"translated":true}
```

## 5. 装配正式输出

真实任务把平台给定文献解析为 `paragraphs` + `glossary`，翻译后填 `translations`，跑 `pipeline`，按 `references/output_contract.md` 写 `/app/output/result.json`。完整样例见 `examples/smoke_input.json` 与 `examples/smoke_output.json`（均已标注为示例）。
