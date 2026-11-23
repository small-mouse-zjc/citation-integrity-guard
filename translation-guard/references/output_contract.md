# 输入输出字段契约（Output Contract）

## 输入：translation JSON

```json
{
  "case_id": "案例标识",
  "source_lang": "en",
  "target_lang": "zh",
  "paragraphs": [
    {"id":"P1","section":"Abstract","page":1,"kind":"body","text":"原文段落"}
  ],
  "glossary": [
    {"source":"porosity","target":"孔隙度","scope":"global"}
  ],
  "translations": {"P1":"译文段落"}
}
```

- `paragraphs[].id` 是稳定段号，贯穿全流程；缺省按 `P1,P2...`。
- `kind`：`body` / `caption` / `heading` / `reference` 等。
- `glossary[].target` 非空表示"已锁定译名"；空则为候选待确认。
- `translations`：段号→译文；翻译类子命令不需要，核验类需要。
- **交付必须带 `result.translations`**：每段含源文与真实译文；只交核验表或保护文本视为 partial。

## 输出：pipeline result.json

```json
{
  "case_id": "案例标识",
  "status": "success | partial | needs_review",
  "has_translations": true,
  "pipeline": { "...各步骤完整结果...（--compact 省略）": {} },
  "result": {
    "segment_count": 4,
    "glossary_locked": 6,
    "protected_tokens": 5,
    "restore_issues": 0,
    "aligned_coverage": 1.0,
    "term_inconsistencies": 0,
    "verification": {"consistent":true,"issues":[],"needs_review":[]},
    "evidence_index": [{"id":"P1","source_location":{...},"source_head":"...",
                        "translation_head":"...","basis":[...],"translated":true}],
    "lock_prompt": "【术语锁定表（强制）】...",
    "protected_for_translation": [{"id":"P1","protected_text":"...","tokens":[...]}],
    "translations": [
      {"id":"P1","index":1,"section":"Abstract","page":1,
       "source":"原文段落","target":"译文段落","translated":true,"basis":"目标语译文"}
    ],
    "bilingual": [{"id":"P1","source":"原文段落","target":"译文段落"}],
    "translation_metrics": {"total":4,"translated":4,"untranslated":0,
                            "coverage":1.0,"untranslated_ids":[]},
    "summary": "段 4；术语锁定 6/7；保护元素 5（公式1/引用1/数字2）；译文 4/4 段；核验问题 0"
  }
}
```

字段说明：

- `protected_for_translation`：翻译前产物，`protected_text` 交模型翻译，占位符 `⟦P1_003⟧` 必须原样保留。
- `restore_issues`：占位符丢失/篡改数；0 表示事实元素完整回填。
- `aligned_coverage`：译文段数/原文段数；<1 表示漏段。
- `verification.issues`：`number_lost`/`citation_lost`/`chemical_lost`（硬错误）与 `*_maybe_lost`（疑似，需人工）。
- `evidence_index[].basis`：该段译文的术语依据（`glossary`）与保护元素依据（`protected:*`）。
- `status` 聚合：任一 `needs_review` → needs_review；否则任一 `partial` → partial；否则 success。

## 装配正式 result.json

真实任务把平台给定文献解析为 `paragraphs` + `glossary`，翻译后填 `translations`，跑 `pipeline`，保留 `case_id` 与所有字段。平台的"证据与边界"字段 ← `evidence_index` + `verification.needs_review`；"运行状态" ← `status` + issues；"阅读/解析结果" ← 双语对照（段落级）。可编辑双语对照另存 `/app/output/`。预算紧张用 `--compact`。
