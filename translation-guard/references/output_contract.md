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
    "summary": "段 4；术语锁定 6/7；保护元素 5（公式1/引用1/数字2）；译文覆盖 100%；核验问题 0"
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

## 端到端交付（完成器 solve / render-draft）

### 真实输入字段（solve 适配）

`solve case.json --out /app/output` 读取 case.json，并支持以下真实输入字段（读不到不臆造，记入 `adapter_notes`）：

- `paragraphs`：内联段落数组（已结构化，优先使用）。
- `source_text`：单篇纯文本，按空行/换行切段并给出稳定段号。
- `source_files`：`[路径]` 或 `{名:路径}`，读取 `.txt`/`.md`（按行切段）或 `.json`（含 `paragraphs`）。
- `translations` / `translation_files`：真实译文（段号→文本 或 段号→文件路径）；内联文本不臆造。
- `glossary` / `source_lang` / `target_lang`：术语表与语言口径。

### 输出：solve result.json

```json
{
  "case_id": "...",
  "status": "success | partial | needs_review",
  "input_mode": "case",
  "source_count": 4,
  "adapter_notes": ["文本文件:paper.txt=2段"],
  "result": {
    "bilingual_draft": "[P1 · Abstract] p1\n原文: ...\n译文: ...\n\n...",
    "draft_text": "（同 bilingual_draft）",
    "blocks": [
      {"id":"P1","section":"Abstract","page":1,"kind":"body",
       "source":"...","target":"译文或〔待翻译：...〕",
       "source_protected":"...","glossary_basis":[{"source":"porosity","target":"孔隙度"}],
       "protected_kinds":["number_unit","citation"],"status":"ok | needs_translation"}
    ],
    "segment_count": 4, "glossary_locked": 6, "aligned_coverage": 1.0,
    "verification": {"consistent":true,"issues":[],"needs_review":[]},
    "evidence_index": [...], "lock_prompt": "...", "summary": "..."
  },
  "needs_review": ["术语『...』未定译名", "段 X 否定/限定词疑似丢失..."],
  "uncertainty": ["只用真实段落/译文/术语成稿；缺译文标〔待翻译〕，不臆造..."],
  "delivery": {"written":true,"path":"/app/output/result.json","bytes":10292}
}
```

- `result.bilingual_draft` / `draft_text`：可编辑双语对照成稿草稿，段号 + section/page + 原文 + 译文/〔待翻译〕；**无真实译文的段一律标〔待翻译〕，不臆造译文**。
- `result.blocks`：逐段结构，含 `glossary_basis`（该段命中的真实术语译名）、`protected_kinds`（该段保护元素类型）、`status`（`ok` 或 `needs_translation`）。
- `status`：`success`=全段落有真实译文且核验干净；`partial`/`needs_review`=缺译文、术语未定译名或否定/限定疑似丢失（进 `needs_review`，交人工确认）。
- `delivery`：落盘回执；`written=true` 且 `bytes>0` 才算交付成功。任何异常不静默吞错，写入 `input_error` 或显式降级。

### render-draft / pipeline --with-draft

`render-draft input.json` 与 `pipeline input.json --with-draft` 在 `result` 中额外产出 `bilingual_draft` 与 `draft_detail`（同上的逐段成稿结构）；默认 `pipeline` 不含成稿字段。两者都不臆造译文，缺译文标〔待翻译〕。

## 装配正式 result.json（手工路径）

真实任务若不用 `solve`，可把平台给定文献解析为 `paragraphs` + `glossary`，翻译后填 `translations`，跑 `pipeline --with-draft`，保留 `case_id` 与所有字段，再自行写 `/app/output/result.json`。平台的"证据与边界"字段 ← `evidence_index` + `verification.needs_review`；"运行状态" ← `status` + issues；"阅读/解析结果" ← 双语对照（段落级 `bilingual_draft`）。预算紧张用 `--compact`。
